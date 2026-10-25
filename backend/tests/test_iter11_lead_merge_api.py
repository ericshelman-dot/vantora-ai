"""Iteration 11: duplicate review / approved merge / archive / tenant isolation / concurrency via public API.
Never touches Jessica's records (only reads them). Uses fictional TEST leads only."""
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


@pytest.fixture(scope="module")
def owner():
    r = requests.post(f"{BASE}/auth/login", json={"email": "demo@aurasalon.com", "password": os.environ['DEMO_OWNER_PASSWORD']})
    assert r.status_code == 200
    d = r.json()
    return {"h": {"Authorization": f"Bearer {d['token']}"}, "bid": d["user"]["business_id"]}


def chat(bid, sid, msg, consent=None):
    r = requests.post(f"{BASE}/chat/stream", json={"session_id": sid, "message": msg, "business_id": bid, "consent": consent}, timeout=150)
    return r.status_code, r.text


def active(bid, email):
    return list(mdb.leads.find({"business_id": bid, "email_norm": email, "archived": {"$ne": True}}, {"_id": 0}))


# --- Jessica: read-only checks
def test_jessica_group_is_flagged_not_merged(owner):
    g = requests.get(f"{BASE}/lead-duplicates", headers=owner["h"]).json()
    jg = [x for x in g if set(x["lead_ids"]) == JESSICA]
    assert len(jg) == 1 and jg[0]["match"] == "name_only"
    assert all(len(b["lead"]) and "conversations" in b and "bookings" in b for b in jg[0]["leads"])
    assert mdb.leads.count_documents({"lead_id": {"$in": list(JESSICA)}, "archived": True}) == 0


def test_jessica_preview_does_not_change_anything(owner):
    r = requests.post(f"{BASE}/lead-merges/preview", headers=owner["h"],
                      json={"primary_id": "lead_3f803b6e8f47", "duplicate_ids": ["lead_b404523b315e"]})
    assert r.status_code == 200 and "result_consent" in r.json()
    assert mdb.leads.count_documents({"lead_id": {"$in": list(JESSICA)}, "archived": {"$ne": True}}) == 3


def test_merge_without_confirm_400(owner):
    r = requests.post(f"{BASE}/lead-merges", headers=owner["h"],
                      json={"primary_id": "lead_3f803b6e8f47", "duplicate_ids": ["lead_b404523b315e"]})
    assert r.status_code == 400
    assert mdb.leads.count_documents({"lead_id": {"$in": list(JESSICA)}, "archived": {"$ne": True}}) == 3


# --- tenant isolation
@pytest.fixture(scope="module")
def other_owner():
    em = f"test_iter11_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{BASE}/auth/register", json={"name": "TEST Owner", "email": em, "password": "Test123!", "business_name": "TEST Biz"})
    assert r.status_code == 200, r.text
    d = r.json()
    return {"h": {"Authorization": f"Bearer {d['token']}"}, "bid": d["user"]["business_id"]}


def test_new_owner_sees_no_aura_duplicates(other_owner):
    g = requests.get(f"{BASE}/lead-duplicates", headers=other_owner["h"]).json()
    assert all(not (set(x["lead_ids"]) & JESSICA) for x in g) and g == []


def test_cross_tenant_merge_404(other_owner):
    mine = requests.post(f"{BASE}/leads", headers=other_owner["h"], json={"name": "TEST Xeno", "email": f"xeno{uuid.uuid4().hex[:5]}@example.com"}).json()
    r = requests.post(f"{BASE}/lead-merges", headers=other_owner["h"],
                      json={"primary_id": mine["lead_id"], "duplicate_ids": ["lead_b404523b315e"], "confirm": True})
    assert r.status_code == 404
    r2 = requests.post(f"{BASE}/lead-merges/preview", headers=other_owner["h"],
                       json={"primary_id": mine["lead_id"], "duplicate_ids": ["lead_b404523b315e"]})
    assert r2.status_code == 404
    assert mdb.leads.find_one({"lead_id": "lead_b404523b315e"}).get("archived") is not True


# --- DB indexes
def test_unique_partial_indexes_exist():
    idx = mdb.leads.index_information()
    assert "uniq_active_email_key" in idx and idx["uniq_active_email_key"].get("unique")
    assert "uniq_active_phone_key" in idx


# --- concurrency via public widget
def test_parallel_chat_same_email_single_lead(owner):
    em = f"test.concur.{uuid.uuid4().hex[:6]}@example.com"
    msg = f"Hi, I'm Ignatius Thorne, {em}. What are your hours on Sunday?"
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda i: chat(owner["bid"], f"test_conc_{uuid.uuid4().hex[:8]}", msg), range(6)))
    assert all(s == 200 for s, _ in res)
    leads = active(owner["bid"], em)
    assert len(leads) == 1, [l["lead_id"] for l in leads]
    assert len(leads[0]["chat_session_ids"]) == 6


def test_parallel_manual_create_same_email_single_lead(owner):
    """POST /api/leads race — manual create path."""
    em = f"test.manual.{uuid.uuid4().hex[:6]}@example.com"
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda i: requests.post(f"{BASE}/leads", headers=owner["h"], json={"name": "TEST Manual Race", "email": em}).status_code, range(6)))
    leads = active(owner["bid"], em)
    for l in leads:
        requests.delete(f"{BASE}/leads/{l['lead_id']}", headers=owner["h"])
    assert len(leads) == 1, f"statuses={res} leads={len(leads)}"


def test_manual_lead_gets_email_key(owner):
    em = f"test.key.{uuid.uuid4().hex[:6]}@example.com"
    l = requests.post(f"{BASE}/leads", headers=owner["h"], json={"name": "TEST Key", "email": em}).json()
    doc = mdb.leads.find_one({"lead_id": l["lead_id"]})
    requests.delete(f"{BASE}/leads/{l['lead_id']}", headers=owner["h"])
    assert doc.get("email_key") == f"{owner['bid']}|{em}"


# --- archive instead of delete
def test_delete_archives(owner):
    l = requests.post(f"{BASE}/leads", headers=owner["h"], json={"name": "TEST Archive Me", "email": f"arch{uuid.uuid4().hex[:5]}@example.com"}).json()
    r = requests.delete(f"{BASE}/leads/{l['lead_id']}", headers=owner["h"])
    assert r.status_code == 200
    ids = [x["lead_id"] for x in requests.get(f"{BASE}/leads", headers=owner["h"]).json()]
    assert l["lead_id"] not in ids
    doc = mdb.leads.find_one({"lead_id": l["lead_id"]})
    assert doc and doc["archived"] is True and doc["email_key"] is None


# --- API merge + undo on fictional pair, including re-contact by archived email after merge
def test_merge_then_recontact_dup_email_then_undo(owner):
    h, bid = owner["h"], owner["bid"]
    tag = uuid.uuid4().hex[:5]
    e1, e2 = f"rowan.pike.a{tag}@example.com", f"rowan.pike.b{tag}@example.com"
    a = requests.post(f"{BASE}/leads", headers=h, json={"name": f"Rowan Pike{tag}", "email": e1}).json()
    b = requests.post(f"{BASE}/leads", headers=h, json={"name": f"Rowan Pike{tag}", "email": e2}).json()
    g = [x for x in requests.get(f"{BASE}/lead-duplicates", headers=h).json() if set(x["lead_ids"]) == {a["lead_id"], b["lead_id"]}]
    assert len(g) == 1 and g[0]["match"] == "name_only"
    m = requests.post(f"{BASE}/lead-merges", headers=h, json={"primary_id": a["lead_id"], "duplicate_ids": [b["lead_id"]], "confirm": True})
    assert m.status_code == 200
    mid = m.json()["merge_id"]
    # customer later chats with the archived (alternate) email -> should attach to primary, not create a new lead
    s, _ = chat(bid, f"test_recontact_{tag}", f"Hi I'm Rowan Pike{tag}, {e2}. Are you open Monday?")
    assert s == 200
    act = active(bid, e2)
    recontact_new = [x["lead_id"] for x in act]
    u = requests.post(f"{BASE}/lead-merges/{mid}/undo", headers=h)
    undo_status = u.status_code
    # cleanup
    for x in recontact_new + [a["lead_id"], b["lead_id"]]:
        requests.delete(f"{BASE}/leads/{x}", headers=h)
    assert recontact_new == [], f"new lead created for archived alternate email after merge: {recontact_new}"
    assert undo_status == 200, f"undo failed {undo_status} {u.text[:200]}"


def test_optout_recorded_after_merge_survives_undo(owner):
    """Consent safety: an opt-out recorded on the primary after a merge must not be reverted by undo."""
    h, bid = owner["h"], owner["bid"]
    tag = uuid.uuid4().hex[:5]
    a = requests.post(f"{BASE}/leads", headers=h, json={"name": f"Tamsin Reed{tag}", "email": f"tamsin.a{tag}@example.com"}).json()
    b = requests.post(f"{BASE}/leads", headers=h, json={"name": f"Tamsin Reed{tag}", "email": f"tamsin.b{tag}@example.com"}).json()
    mdb.leads.update_one({"lead_id": a["lead_id"]}, {"$set": {"consent.email": {"channel": "email", "granted": True, "text": "TEST", "source": "test", "at": "2026-01-01"}}})
    mdb.leads.update_one({"lead_id": b["lead_id"]}, {"$set": {"consent.email": {"channel": "email", "granted": True, "text": "TEST", "source": "test", "at": "2026-01-01"}}})
    mid = requests.post(f"{BASE}/lead-merges", headers=h, json={"primary_id": a["lead_id"], "duplicate_ids": [b["lead_id"]], "confirm": True}).json()["merge_id"]
    assert requests.post(f"{BASE}/leads/{a['lead_id']}/opt-out", headers=h, json={"channel": "email"}).status_code == 200
    assert requests.post(f"{BASE}/lead-merges/{mid}/undo", headers=h).status_code == 200
    doc = mdb.leads.find_one({"lead_id": a["lead_id"]})
    for x in (a, b):
        requests.delete(f"{BASE}/leads/{x['lead_id']}", headers=h)
    assert doc["consent"]["email"]["granted"] is False, "undo reverted a post-merge opt-out back to opted-in"
