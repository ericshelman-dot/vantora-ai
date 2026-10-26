"""Offline integration/regression tests using real engines and an in-memory Mongo fake."""
import asyncio
import copy
import socket
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).parent))
from run_demo import business, make_db, new_id, journey, booking_plan, booking_agent, le, sch


@pytest.fixture(autouse=True)
def no_external_connections(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline pilot must not open external connections")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


def run(coro):
    return asyncio.run(coro)


def test_complete_synthetic_journey():
    result = run(journey(make_db(), business()))
    assert result["booking"]["duration_min"] == 45
    assert result["owner_review"]["status"] == "booked"
    assert len(result["owner_review"]["follow_ups"]) == 2


def test_repeat_booking_at_capacity_one_keeps_reference_and_one_confirmation():
    async def check():
        db, biz = make_db(), business()
        a = await booking_agent.execute(db, new_id, biz, booking_plan(), "same-session")
        b = await booking_agent.execute(db, new_id, biz, booking_plan(), "same-session")
        assert a["kind"] == b["kind"] == "confirmed"
        assert a["booking"]["booking_id"] == b["booking"]["booking_id"]
        assert await db.bookings.count_documents({}) == 1
        lead = await db.leads.find_one({})
        assert len(lead["follow_ups"]) == 1
    run(check())


@pytest.mark.parametrize("changes,expected", [
    ({"email": None, "phone": None}, "missing"),
    ({"email": "not-an-email", "phone": "abc"}, "missing"),
    ({"service": "Tattoo"}, "unknown_service"),
    ({"time": "16:30"}, "outside_hours"),
    ({"date": "2020-01-01"}, "past"),
    ({"date": "not-a-date"}, "invalid"),
    ({"intent": "error"}, "error"),
])
def test_rejected_requests_never_book(changes, expected):
    async def check():
        db = make_db()
        result = await booking_agent.execute(db, new_id, business(), booking_plan(**changes), "request")
        assert result["kind"] == expected
        assert await db.bookings.count_documents({}) == 0
    run(check())


def test_conflict_and_closed_day():
    async def check():
        db, biz = make_db(), business()
        await booking_agent.execute(db, new_id, biz, booking_plan(), "a")
        result = await booking_agent.execute(db, new_id, biz, booking_plan(email="other@example.com"), "b")
        assert result["kind"] == "unavailable"
        assert await db.bookings.count_documents({}) == 1
        assert await sch.free_slots(db, biz, "2099-01-04", 45) == []  # Sunday
    run(check())


def test_same_contact_deduplicated_but_other_tenant_untouched():
    async def check():
        db, biz = make_db(), business()
        other = {**copy.deepcopy(biz), "business_id": "other_synthetic_salon"}
        old = await le.upsert_lead(db, new_id, other, name="Alex Sample", email="alex.salon@example.com", session_id="other")
        await journey(db, biz)
        again = await le.upsert_lead(db, new_id, biz, name="Alex Sample", email="ALEX.SALON@EXAMPLE.COM", session_id="return")
        assert await db.leads.count_documents({"business_id": biz["business_id"]}) == 1
        assert await db.customers.count_documents({"business_id": biz["business_id"]}) == 1
        assert again["lead_id"] != old["lead_id"]
        assert await db.leads.find_one({"lead_id": old["lead_id"]}, {"_id": 0}) == old
    run(check())


def test_marketing_declined_blocks_owner_approval():
    async def check():
        db, biz = make_db(), business()
        result = await journey(db, biz)
        lead = result["owner_review"]
        await db.leads.update_one({"lead_id": lead["lead_id"]}, {"$push": {"drafts": {
            "draft_id": "marketing", "channel": "email", "kind": "marketing", "status": "pending", "message": "Offer"}}})
        with pytest.raises(le.LeadError) as exc:
            await le.approve_draft(db, new_id, biz["business_id"], lead["lead_id"], "marketing", "synthetic-owner")
        assert exc.value.code == 403
    run(check())


def test_unanswered_question_does_not_grant_permission():
    async def check():
        db, biz = make_db(), business()
        lead = await le.upsert_lead(db, new_id, biz, name="Alex Sample", email="alex@example.com", session_id="s")
        await le.mark_prompted(db, biz, "s", "inquiry", lead)
        await le.handle_chat_consent(db, biz, "s", "How much is it?", None)
        saved = await db.leads.find_one({})
        assert not saved["consent"].get("inquiry_reply")
    run(check())


def test_opt_out_revokes_marketing():
    async def check():
        db, biz = make_db(), business()
        await le.upsert_lead(db, new_id, biz, name="Alex Sample", email="alex@example.com", session_id="s")
        await le.handle_chat_consent(db, biz, "s", "hello", {"email": True})
        assert await le.handle_chat_consent(db, biz, "s", "Please unsubscribe", None) == "opted_out"
        saved = await db.leads.find_one({})
        assert saved["consent"]["email"]["granted"] is False
    run(check())


def test_save_failure_never_confirms(monkeypatch):
    async def check():
        async def fail(*args, **kwargs):
            raise RuntimeError("synthetic storage failure")
        monkeypatch.setattr(sch, "reserve", fail)
        db = make_db()
        result = await booking_agent.execute(db, new_id, business(), booking_plan(), "fail")
        assert result["kind"] == "error" and "booking" not in result
        assert await db.bookings.count_documents({}) == 0
    run(check())


def test_concurrent_competing_requests_same_process_capacity():
    async def check():
        db, biz = make_db(), business()
        results = await asyncio.gather(*[
            booking_agent.execute(db, new_id, biz, booking_plan(email=f"sample{i}@example.com"), f"s{i}")
            for i in range(5)])
        assert sum(r["kind"] == "confirmed" for r in results) == 1
        assert await db.bookings.count_documents({}) == 1
    run(check())


def test_timezone_winter_and_summer():
    assert sch.local_to_utc("2099-07-01", "10:00", "America/New_York").hour == 14
    assert sch.local_to_utc("2099-12-01", "10:00", "America/New_York").hour == 15


@pytest.mark.xfail(strict=True, reason="Known gap: bare STOP is not recognized by existing chat opt-out parser; no live SMS allowed")
def test_bare_stop_requires_future_delivery_hardening():
    assert le.OPT_OUT.search("STOP")
