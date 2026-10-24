"""Scheduling engine tests: success, full slot, manual overlap, outside hours, DB failure, isolation."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import scheduling as sch  # noqa: E402
import booking_agent  # noqa: E402

TZ = "America/New_York"


def new_id(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def biz(capacity=3, bid=None):
    return {"business_id": bid or new_id("biz"), "name": "Test Spa",
            "scheduling": {"timezone": TZ, "capacity": capacity, "slot_minutes": 30, "default_duration": 60,
                           "weekly": {d: ["09:00", "18:00"] for d in sch.DAYS}},
            "service_catalog": [{"name": "Signature Aura Facial", "duration_min": 60}, {"name": "Hot Stone Ritual", "duration_min": 90}]}


def future_date(days=3):
    return (datetime.now(ZoneInfo(TZ)) + timedelta(days=days)).strftime("%Y-%m-%d")


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    d = client[f"sched_test_{uuid.uuid4().hex[:6]}"]
    yield d
    asyncio.get_event_loop().run_until_complete(client.drop_database(d.name))


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def plan(date, time_, **kw):
    return {"intent": "book", "service": "Signature Aura Facial", "date": date, "time": time_,
            "name": "Sarah Johnson", "email": "sarah.johnson@example.com", "phone": None, **kw}


def test_successful_ai_booking_creates_booking_lead_customer_and_simulated_followup(db):
    b = biz()
    r = run(booking_agent.execute(db, new_id, b, plan(future_date(), "14:00"), "sess1"))
    assert r["kind"] == "confirmed"
    bk = run(db.bookings.find_one({"booking_id": r["booking"]["booking_id"]}))
    assert bk and bk["business_id"] == b["business_id"] and bk["status"] == "confirmed" and bk["duration_min"] == 60
    assert sch.parse_iso(bk["start_utc"]) == sch.local_to_utc(future_date(), "14:00", TZ)
    lead = run(db.leads.find_one({"business_id": b["business_id"], "email": "sarah.johnson@example.com"}))
    assert bk["booking_id"] in lead["booking_ids"] and lead["follow_ups"][0]["status"] == "simulated-sent"
    assert "SIMULATED" in lead["follow_ups"][0]["message"]
    assert run(db.customers.count_documents({"business_id": b["business_id"], "email": "sarah.johnson@example.com"})) == 1
    assert r["booking"]["booking_id"] in r["footer"] and "No email or SMS was sent" in r["footer"]


def test_repeat_message_is_idempotent(db):
    b = biz()
    p = plan(future_date(), "15:00")
    r1 = run(booking_agent.execute(db, new_id, b, p, "sess2"))
    r2 = run(booking_agent.execute(db, new_id, b, p, "sess2"))
    assert r1["booking"]["booking_id"] == r2["booking"]["booking_id"]
    assert run(db.bookings.count_documents({"business_id": b["business_id"]})) == 1


def test_fully_booked_slot_offers_alternatives_and_creates_nothing(db):
    b = biz(capacity=3)
    for i in range(3):
        assert run(booking_agent.execute(db, new_id, b, plan(future_date(), "10:00", email=f"c{i}@example.com"), f"s{i}"))["kind"] == "confirmed"
    r = run(booking_agent.execute(db, new_id, b, plan(future_date(), "10:30", email="x@example.com"), "s4"))
    assert r["kind"] == "unavailable" and "No appointment was created" in r["facts"] and "No appointment was created" in r["footer"]
    assert run(db.bookings.count_documents({"business_id": b["business_id"]})) == 3


def test_manual_overlap_blocked_at_capacity(db):
    b = biz(capacity=1)
    start = sch.local_to_utc(future_date(), "11:00", TZ)
    run(sch.reserve(db, b, sch.booking_doc(new_id, b, "A", "Hot Stone Ritual", start, 90)))
    with pytest.raises(sch.SchedulingError):
        run(sch.reserve(db, b, sch.booking_doc(new_id, b, "B", "Facial", start + timedelta(minutes=60), 60)))
    run(sch.reserve(db, b, sch.booking_doc(new_id, b, "C", "Facial", start + timedelta(minutes=90), 60)))


def test_concurrent_reservations_never_exceed_capacity(db):
    b = biz(capacity=2)
    start = sch.local_to_utc(future_date(), "12:00", TZ)

    async def attempt(i):
        try:
            await sch.reserve(db, b, sch.booking_doc(new_id, b, f"P{i}", "Facial", start, 60))
            return True
        except sch.SchedulingError:
            return False
    results = run(asyncio.gather(*[attempt(i) for i in range(6)]))
    assert sum(results) == 2


def test_outside_hours_rejected(db):
    r = run(booking_agent.execute(db, new_id, biz(), plan(future_date(), "20:00"), "s"))
    assert r["kind"] == "outside_hours" and "No appointment was created" in r["facts"]


def test_missing_contact_does_not_book(db):
    b = biz()
    r = run(booking_agent.execute(db, new_id, b, plan(future_date(), "13:00", email=None), "s"))
    assert r["kind"] == "missing" and "NOT booked" in r["facts"]
    assert run(db.bookings.count_documents({})) == 0


def test_db_failure_never_confirms(db):
    class Broken:
        def __init__(self, real):
            self.real = real

        def __getattr__(self, n):
            return getattr(self.real, n)

        async def insert_one(self, *a, **k):
            raise RuntimeError("disk full")

    class FailingDB:
        def __init__(self, real):
            self.real, self.bookings = real, Broken(real.bookings)

        def __getattr__(self, n):
            return getattr(self.real, n)

    r = run(booking_agent.execute(FailingDB(db), new_id, biz(), plan(future_date(), "14:00"), "s"))
    assert r["kind"] == "error" and "booking" not in r and "No appointment was created" in r["footer"]


def test_unconfirmed_claim_is_corrected():
    assert booking_agent.guard_footer(None, "Your facial is booked for 2pm!")
    assert booking_agent.guard_footer({"kind": "unavailable"}, "You're confirmed.")
    assert not booking_agent.guard_footer({"kind": "confirmed"}, "Your facial is booked.")


def test_business_isolation(db):
    a, other = biz(capacity=1), biz(capacity=1)
    start = sch.local_to_utc(future_date(), "09:00", TZ)
    run(sch.reserve(db, a, sch.booking_doc(new_id, a, "A", "Facial", start, 60)))
    run(sch.reserve(db, other, sch.booking_doc(new_id, other, "B", "Facial", start, 60)))
    assert run(db.bookings.count_documents({"business_id": a["business_id"]})) == 1


def test_timezone_conversion_dst_aware():
    assert sch.local_to_utc("2026-07-01", "14:00", TZ).hour == 18
    assert sch.local_to_utc("2026-12-01", "14:00", TZ).hour == 19
