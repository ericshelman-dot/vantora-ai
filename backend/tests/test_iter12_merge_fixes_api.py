"""Iteration 12: retest of merge fixes (alternate-norm lookup, safe undo, post-merge consent/activity kept, status recompute,
manual-create keys). Fictional leads only; Jessica's records are only read. Cleanup archives (never deletes)."""
import os
import uuid
import concurrent.futures as cf

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
JESSICA = {"lead_3f803b6e8f47", "lead_b404523b315e", "lead_a4c6e4cdc976"}
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
CREATED = []


@pytest.fixture(scope="module")
def owner():
    r = requests.post(f"{BASE}/auth/login", json={"email": "demo@aurasalon.com", "password": os.environ["DEMO_OWNER_PASSWORD"]})
    assert r.status_code == 200
    d = r.json()
    o = {"h": {"Authorization": f"Bearer {d['token']}"}, "bid": d["user"]["business_id"]}
    yield o
    for lid in CREATED:  # archive (soft delete) everything we created
        requests.delete(f"{BASE}/leads/{lid}", headers=o["h"])


def mk(o, name, email, **kw):
    r = requests.post(f"{BASE}/leads", headers=o["h"], json={"name": name, "email": email, **kw})
    assert r.status_code == 200, r.text
    CREATED.append(r.json()["lead_id"])
    return r.json()


def chat(bid, sid, msg):
    r = requests.post(f"{BASE}/chat/stream", json={"session_id": sid, "message": msg, "business_id": bid}, timeout=150)
    return r.status_code


def active(bid, en):
    return list(mdb.leads.find({"business_id": bid, "archived": {"$ne": True}, "email_norm": en}, {"_id": 0}))


def merge(o, a, b):
    r = requests.post(f"{BASE}/lead-merges", headers=o["h"], json={"primary_id": a, "duplicate_ids": [b], "confirm": True})
    assert r.status_code == 200, r.text
    return r.json()["merge_id"]


# Recontact via chat with archived duplicate email -> attaches to primary; undo 200 + undone + conflicts list
def test_recontact_attaches_to_primary_and_undo_clean(owner):
    h, bid, t = owner["h"], owner["bid"], uuid.uuid4().hex[:5]
    e1, e2 = f"orla.finch.a{t}@example.com", f"orla.finch.b{t}@example.com"
    a, b = mk(owner, f"Orla Finch{t}", e1), mk(owner, f"Orla Finch{t}", e2)
    mid = merge(owner, a["lead_id"], b["lead_id"])
    p = mdb.leads.find_one({"lead_id": a["lead_id"]})
    assert e2 in p.get("alternate_email_norms", [])
    sid = f"test_i12_recontact_{t}"
    assert chat(bid, sid, f"Hi I'm Orla Finch{t}, {e2}. Are you open Monday?") == 200
    assert active(bid, e2) == [], "new lead created for alternate email"
    p = mdb.leads.find_one({"lead_id": a["lead_id"]})
    assert sid in p["chat_session_ids"]
    u = requests.post(f"{BASE}/lead-merges/{mid}/undo", headers=h)
    assert u.status_code == 200, u.text
    assert isinstance(u.json().get("conflicts"), list)
    m = mdb.lead_merges.find_one({"merge_id": mid})
    assert m["undone"] is True
    p = mdb.leads.find_one({"lead_id": a["lead_id"]})
    d = mdb.leads.find_one({"lead_id": b["lead_id"]})
    assert sid in p["chat_session_ids"], "post-merge session lost from primary on undo"
    assert d.get("archived") is not True and d.get("email_key") == f"{bid}|{e2}"
    assert p.get("alternate_email_norms") in ([], None)
    # undo twice -> 409
    assert requests.post(f"{BASE}/lead-merges/{mid}/undo", headers=h).status_code == 409


# Manual POST /api/leads with the archived duplicate's email after a merge
def test_manual_create_with_alternate_email_after_merge(owner):
    t = uuid.uuid4().hex[:5]
    e1, e2 = f"piers.lark.a{t}@example.com", f"piers.lark.b{t}@example.com"
    a, b = mk(owner, f"Piers Lark{t}", e1), mk(owner, f"Piers Lark{t}", e2)
    mid = merge(owner, a["lead_id"], b["lead_id"])
    r = requests.post(f"{BASE}/leads", headers=owner["h"], json={"name": f"Piers Lark{t}", "email": e2})
    if r.status_code == 200:
        CREATED.append(r.json()["lead_id"])
    u = requests.post(f"{BASE}/lead-merges/{mid}/undo", headers=owner["h"])
    print("manual create status", r.status_code, "undo", u.status_code, u.text[:200])
    assert u.status_code == 200
    if r.status_code == 200:
        assert u.json()["conflicts"], "conflict expected when another lead took the email"
    assert r.status_code == 409, "manual create with a merged-away (alternate) email created a separate lead"


# Post-merge opt-out, follow-up and activity survive undo; duplicate-origin items removed
def test_post_merge_consent_and_activity_kept(owner):
    h, bid, t = owner["h"], owner["bid"], uuid.uuid4().hex[:5]
    a, b = mk(owner, f"Sabine Holt{t}", f"sabine.a{t}@example.com"), mk(owner, f"Sabine Holt{t}", f"sabine.b{t}@example.com")
    g = {"channel": "email", "granted": True, "text": "TEST", "source": "test", "at": "2026-01-01T00:00:00+00:00"}
    for x, s in ((a, "sess_a"), (b, "sess_b")):
        mdb.leads.update_one({"lead_id": x["lead_id"]}, {"$set": {"consent.email": g, "consent_log": [{**g, "text": f"TEST {x['lead_id']}"}],
                                                              "chat_session_ids": [f"test_i12_{s}_{t}"],
                                                              "follow_ups": [{"id": f"fu_{s}_{t}", "sent_at": "2026-01-01"}]}})
    mid = merge(owner, a["lead_id"], b["lead_id"])
    fu = requests.post(f"{BASE}/leads/{a['lead_id']}/follow-up", headers=h, json={"channel": "email", "message": "TEST hello"})
    assert fu.status_code == 200, fu.text
    mdb.leads.update_one({"lead_id": a["lead_id"]}, {"$addToSet": {"chat_session_ids": f"test_i12_new_{t}", "booking_ids": f"bk_test_new_{t}"}})
    assert requests.post(f"{BASE}/leads/{a['lead_id']}/opt-out", headers=h, json={"channel": "email"}).status_code == 200
    u = requests.post(f"{BASE}/lead-merges/{mid}/undo", headers=h)
    assert u.status_code == 200, u.text
    p = mdb.leads.find_one({"lead_id": a["lead_id"]})
    d = mdb.leads.find_one({"lead_id": b["lead_id"]})
    assert p["consent"]["email"]["granted"] is False
    assert any(c.get("granted") is False and c.get("channel") == "email" for c in p["consent_log"])
    assert not any(c.get("text") == f"TEST {b['lead_id']}" for c in p["consent_log"]), "dup consent log kept on primary"
    assert f"test_i12_new_{t}" in p["chat_session_ids"] and f"test_i12_sess_b_{t}" not in p["chat_session_ids"]
    assert f"bk_test_new_{t}" in p["booking_ids"]
    fids = [f.get("id") for f in p["follow_ups"]]
    assert f"fu_sess_b_{t}" not in fids and len(fids) == 2, fids
    assert d["consent"]["email"]["granted"] is True and f"test_i12_sess_b_{t}" in d["chat_session_ids"]


# Status recomputed to booked when duplicate has a booking; undo restores booking link
def test_status_booked_after_merge(owner):
    h, t = owner["h"], uuid.uuid4().hex[:5]
    a, b = mk(owner, f"Cassius Wren{t}", f"cassius.a{t}@example.com"), mk(owner, f"Cassius Wren{t}", f"cassius.b{t}@example.com")
    bk = requests.post(f"{BASE}/bookings", headers=h, json={"customer_name": f"Cassius Wren{t}", "service": "Signature Aura Facial",
                                                           "datetime": "2026-11-17T15:00:00", "status": "confirmed"})
    assert bk.status_code == 200, bk.text
    bid_ = bk.json()["booking_id"]
    mdb.bookings.update_one({"booking_id": bid_}, {"$set": {"lead_id": b["lead_id"]}})
    mdb.leads.update_one({"lead_id": b["lead_id"]}, {"$set": {"booking_ids": [bid_], "status": "booked"}})
    mid = merge(owner, a["lead_id"], b["lead_id"])
    assert mdb.leads.find_one({"lead_id": a["lead_id"]})["status"] == "booked"
    assert mdb.bookings.find_one({"booking_id": bid_})["lead_id"] == a["lead_id"]
    assert requests.post(f"{BASE}/lead-merges/{mid}/undo", headers=h).status_code == 200
    assert mdb.bookings.find_one({"booking_id": bid_})["lead_id"] == b["lead_id"]
    st = mdb.leads.find_one({"lead_id": a["lead_id"]})["status"]
    print("primary status after undo:", st)
    requests.put(f"{BASE}/bookings/{bid_}", headers=h, json={"customer_name": f"Cassius Wren{t}", "service": "Signature Aura Facial",
                                                            "datetime": "2026-11-17T15:00:00", "status": "cancelled"})
    assert st == "new", f"primary still '{st}' after undo although the booking went back to the duplicate"


# 6 parallel manual creates with same email -> exactly 1 active lead, others 409 (run 3x)
@pytest.mark.parametrize("run", range(3))
def test_parallel_manual_create(owner, run):
    em = f"test.i12.race{run}.{uuid.uuid4().hex[:6]}@example.com"
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda i: requests.post(f"{BASE}/leads", headers=owner["h"], json={"name": "TEST Race", "email": em}), range(6)))
    CREATED.extend(r.json()["lead_id"] for r in res if r.status_code == 200)
    codes = sorted(r.status_code for r in res)
    assert codes == [200, 409, 409, 409, 409, 409], codes
    assert len(active(owner["bid"], em)) == 1


# Jessica read-only regression
def test_jessica_untouched(owner):
    g = requests.get(f"{BASE}/lead-duplicates", headers=owner["h"]).json()
    assert len([x for x in g if set(x["lead_ids"]) == JESSICA and x["match"] == "name_only"]) == 1
    assert mdb.leads.count_documents({"lead_id": {"$in": list(JESSICA)}, "archived": {"$ne": True}}) == 3
    assert mdb.lead_merges.count_documents({"$or": [{"primary_id": {"$in": list(JESSICA)}}, {"duplicate_ids": {"$in": list(JESSICA)}}]}) == 0
