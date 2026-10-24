"""Duplicate prevention (DB-level), duplicate review, approved merge, cautious consent, archive + undo, tenant isolation."""
import asyncio
import os
import sys
import uuid

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import leads_engine as le  # noqa: E402
import lead_merge as lm  # noqa: E402


def new_id(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def biz():
    return {"business_id": new_id("biz"), "name": "Aura Test", "service_catalog": []}


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    d = client[f"merge_test_{uuid.uuid4().hex[:6]}"]
    for k in ("email_key", "phone_key"):
        run(d.leads.create_index(k, unique=True, partialFilterExpression={k: {"$type": "string"}}))
    yield d
    run(client.drop_database(d.name))


def test_new_chat_same_email_updates_existing(db):
    b = biz()
    a = run(le.upsert_lead(db, new_id, b, name="Jessica Miller", email="jessica.demo@example.com", session_id="c1"))
    c = run(le.upsert_lead(db, new_id, b, name="Jessica Miller", email=" Jessica.Demo@Example.com", session_id="c2"))
    assert a["lead_id"] == c["lead_id"] and c["chat_session_ids"] == ["c1", "c2"]
    assert run(db.leads.count_documents({"business_id": b["business_id"], "archived": {"$ne": True}})) == 1


def test_db_unique_index_blocks_race_even_without_process_lock(db, monkeypatch):
    b = biz()
    monkeypatch.setattr(le, "_lock", lambda bid: asyncio.Lock())  # fresh lock per call = no in-process protection
    run(asyncio.gather(*[le.upsert_lead(db, new_id, b, name="Jessica Miller", email="jessica.demo@example.com", session_id=f"s{i}") for i in range(8)]))
    leads = run(db.leads.find({"business_id": b["business_id"]}).to_list(20))
    assert len(leads) == 1 and len(leads[0]["chat_session_ids"]) == 8


def test_same_name_flagged_not_merged(db):
    b = biz()
    run(le.upsert_lead(db, new_id, b, name="Jessica Miller", email="jessica.demo@example.com", session_id="a"))
    run(le.upsert_lead(db, new_id, b, name="jessica  miller", email="repro1.jm@example.com", session_id="b"))
    groups = run(lm.find_duplicate_groups(db, b["business_id"]))
    assert len(groups) == 1 and groups[0]["match"] == "name_only" and len(groups[0]["lead_ids"]) == 2
    assert run(db.leads.count_documents({"archived": True})) == 0


def _pair(db, b):
    p = run(le.upsert_lead(db, new_id, b, name="Jessica Miller", email="jessica.demo@example.com", session_id="p1", interests=["Hot Stone Ritual"]))
    d = run(le.upsert_lead(db, new_id, b, name="Jessica Miller", email="repro1.jm@example.com", session_id="d1", interests=["Couples Massage"]))
    run(db.bookings.insert_one({"booking_id": "bk_t1", "business_id": b["business_id"], "lead_id": d["lead_id"], "customer_id": d["customer_id"], "service": "x"}))
    run(db.leads.update_one({"lead_id": d["lead_id"]}, {"$push": {"booking_ids": "bk_t1", "follow_ups": {"id": "fu1", "sent_at": "2026-01-01"}}}))
    run(le.record_consent(db, b["business_id"], p["lead_id"], "email", True, "yes", "test"))
    run(le.record_consent(db, b["business_id"], d["lead_id"], "email", False, "opt-out", "test"))
    run(le.record_consent(db, b["business_id"], p["lead_id"], "inquiry_reply", True, "yes", "test", channel_to_use="email"))
    run(le.record_consent(db, b["business_id"], d["lead_id"], "inquiry_reply", True, "yes", "test", channel_to_use="email"))
    return p, d


def test_merge_preserves_data_cautious_consent_and_archives(db):
    b = biz()
    p, d = _pair(db, b)
    pv = run(lm.preview(db, b["business_id"], p["lead_id"], [d["lead_id"]]))
    assert pv["result_consent"]["email"]["granted"] is False  # opt-out wins
    assert run(db.leads.count_documents({"archived": True})) == 0  # preview changes nothing
    run(lm.merge(db, new_id, b["business_id"], p["lead_id"], [d["lead_id"]], "owner@example.com"))
    m = run(db.leads.find_one({"lead_id": p["lead_id"]}))
    assert set(m["chat_session_ids"]) == {"p1", "d1"} and "bk_t1" in m["booking_ids"]
    assert set(m["service_interests"]) == {"Hot Stone Ritual", "Couples Massage"}
    assert m["consent"]["email"]["granted"] is False and m["consent"]["sms"] is None and m["consent"]["inquiry_reply"]["granted"] is True
    assert len(m["consent_log"]) == 5 and any(f["id"] == "fu1" for f in m["follow_ups"]) and m["alternate_emails"] == ["repro1.jm@example.com"]
    arch = run(db.leads.find_one({"lead_id": d["lead_id"]}))
    assert arch["archived"] and arch["merged_into"] == p["lead_id"] and arch["email"] == "repro1.jm@example.com"
    assert run(db.bookings.find_one({"booking_id": "bk_t1"}))["lead_id"] == p["lead_id"]
    assert run(db.customers.find_one({"customer_id": d["customer_id"]}))["archived"] is True
    assert run(lm.find_duplicate_groups(db, b["business_id"])) == []


def test_undo_restores_everything(db):
    b = biz()
    p, d = _pair(db, b)
    before = run(db.leads.find_one({"lead_id": p["lead_id"]}, {"_id": 0}))
    r = run(lm.merge(db, new_id, b["business_id"], p["lead_id"], [d["lead_id"]], "o"))
    run(lm.undo(db, b["business_id"], r["merge_id"], "o"))
    after = run(db.leads.find_one({"lead_id": p["lead_id"]}, {"_id": 0}))
    assert after["consent"] == before["consent"] and after["chat_session_ids"] == before["chat_session_ids"]
    dd = run(db.leads.find_one({"lead_id": d["lead_id"]}))
    assert not dd.get("archived") and dd["email_key"]
    assert run(db.bookings.find_one({"booking_id": "bk_t1"}))["lead_id"] == d["lead_id"]
    assert not run(db.customers.find_one({"customer_id": d["customer_id"]})).get("archived")
    with pytest.raises(le.LeadError):
        run(lm.undo(db, b["business_id"], r["merge_id"], "o"))


def test_recontact_with_merged_email_updates_primary_and_undo_is_safe(db):
    b = biz()
    p, d = _pair(db, b)
    r = run(lm.merge(db, new_id, b["business_id"], p["lead_id"], [d["lead_id"]], "o"))
    again = run(le.upsert_lead(db, new_id, b, name="Jessica Miller", email="REPRO1.jm@example.com", session_id="later"))
    assert again["lead_id"] == p["lead_id"]
    assert run(db.leads.count_documents({"business_id": b["business_id"], "archived": {"$ne": True}})) == 1
    out = run(lm.undo(db, b["business_id"], r["merge_id"], "o"))
    assert out["ok"] and run(db.lead_merges.find_one({"merge_id": r["merge_id"]}))["undone"]
    prim = run(db.leads.find_one({"lead_id": p["lead_id"]}))
    assert "later" in prim["chat_session_ids"] and "d1" not in prim["chat_session_ids"]


def test_optout_after_merge_survives_undo(db):
    b = biz()
    p, d = _pair(db, b)
    r = run(lm.merge(db, new_id, b["business_id"], p["lead_id"], [d["lead_id"]], "o"))
    run(le.record_consent(db, b["business_id"], p["lead_id"], "inquiry_reply", False, "opt-out after merge", "owner"))
    run(lm.undo(db, b["business_id"], r["merge_id"], "o"))
    prim = run(db.leads.find_one({"lead_id": p["lead_id"]}))
    assert prim["consent"]["inquiry_reply"]["granted"] is False
    assert any(c.get("text") == "opt-out after merge" for c in prim["consent_log"])
    assert prim["consent"]["email"]["granted"] is True  # pre-merge primary decision restored


def test_merged_status_reflects_bookings(db):
    b = biz()
    p, d = _pair(db, b)
    run(lm.merge(db, new_id, b["business_id"], p["lead_id"], [d["lead_id"]], "o"))
    assert run(db.leads.find_one({"lead_id": p["lead_id"]}))["status"] == "booked"


def test_cross_tenant_merge_refused(db):
    a, other = biz(), biz()
    la = run(le.upsert_lead(db, new_id, a, name="Jessica Miller", email="jessica.demo@example.com", session_id="x"))
    lb = run(le.upsert_lead(db, new_id, other, name="Jessica Miller", email="jessica.demo@example.com", session_id="y"))
    assert la["lead_id"] != lb["lead_id"]
    with pytest.raises(le.LeadError):
        run(lm.merge(db, new_id, a["business_id"], la["lead_id"], [lb["lead_id"]], "o"))
    assert run(lm.find_duplicate_groups(db, a["business_id"])) == []
