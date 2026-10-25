# Live API regression (iteration 8): strict one-shot consent, checkbox de-dup, name capture, admin 403, demo reset customers
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
TAG = uuid.uuid4().hex[:6]
Q = "Would you like to receive occasional offers"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {login('demo@aurasalon.com', os.environ['DEMO_OWNER_PASSWORD'])}"
    return s


def chat(owner, sid, msg, consent=None):
    body = {"session_id": sid, "message": msg}
    if consent is not None:
        body["consent"] = consent
    r = owner.post(f"{API}/chat/stream", json=body, timeout=120)
    assert r.status_code == 200, r.text
    return r.text


def lead_by_email(owner, email):
    return [l for l in owner.get(f"{API}/leads").json() if (l.get("email") or "").lower() == email.lower()]


def lead_detail(owner, lid):
    return owner.get(f"{API}/leads/{lid}").json()["lead"]


def new_lead(owner, key, first, last):
    sid, email = f"t8{key}_{TAG}", f"{first.lower()}.{key}{TAG}@example.com"
    reply = chat(owner, sid, f"Hi, I'm {first} {last}, {email}.")
    assert Q in reply, f"consent question missing: {reply[-300:]}"
    found = lead_by_email(owner, email)
    assert len(found) == 1
    return sid, found[0]


# --- CRITICAL: unrelated keyword message is not consent, and later 'both' in same session is ignored
def test_unrelated_then_both_no_consent(owner):
    sid, l = new_lead(owner, "a", "Lena", "Fischer")
    chat(owner, sid, "Do you offer both facials and massages on the same day?")
    assert lead_detail(owner, l["lead_id"])["consent"] == {"email": None, "sms": None}
    chat(owner, sid, "both")
    d = lead_detail(owner, l["lead_id"])
    assert d["consent"] == {"email": None, "sms": None}, d["consent"]
    assert d.get("consent_log", []) == []


@pytest.mark.parametrize("key,answer,exp", [
    ("b", "email", {"email": True, "sms": False}),
    ("c", "text", {"email": False, "sms": True}),
    ("d", "both", {"email": True, "sms": True}),
    ("e", "no thanks", {"email": False, "sms": False}),
])
def test_direct_answer_records(owner, key, answer, exp):
    sid, l = new_lead(owner, key, "Ava", "Stone")
    chat(owner, sid, answer)
    c = lead_detail(owner, l["lead_id"])["consent"]
    assert {ch: (c[ch] or {}).get("granted") for ch in ("email", "sms")} == exp, c
    for ch in ("email", "sms"):
        assert c[ch]["source"] == "ai chat question" and Q in c[ch]["text"]


@pytest.mark.parametrize("key,msg", [
    ("f", "Don't email me, text is fine"),
    ("g", "Can I text you to reschedule?"),
    ("h", "What's your email address?"),
])
def test_ambiguous_immediate_reply_records_nothing(owner, key, msg):
    sid, l = new_lead(owner, key, "Ben", "Hart")
    chat(owner, sid, msg)
    assert lead_detail(owner, l["lead_id"])["consent"] == {"email": None, "sms": None}


# --- checkbox ticked across 3 messages -> one consent_log entry
def test_checkbox_no_duplicate_log(owner):
    sid, email = f"t8i_{TAG}", f"cara.i{TAG}@example.com"
    cb = {"email": True, "sms": False}
    chat(owner, sid, f"Hi, I'm Cara Lund, {email}.", consent=cb)
    chat(owner, sid, f"My email again is {email}, what are your hours?", consent=cb)
    chat(owner, sid, f"Cara Lund here ({email}), do you sell gift cards?", consent=cb)
    l = lead_by_email(owner, email)[0]
    d = lead_detail(owner, l["lead_id"])
    emails = [e for e in d["consent_log"] if e["channel"] == "email"]
    assert len(emails) == 1, d["consent_log"]
    assert d["consent"]["email"]["granted"] is True and d["consent"]["email"]["source"] == "chat widget checkbox"
    assert d["consent"]["sms"] is None


def test_name_capture_mia(owner):
    sid, email = f"t8j_{TAG}", f"mia.p{TAG}@example.com"
    chat(owner, sid, f"Hi, I'm Mia Park, {email}")
    found = lead_by_email(owner, email)
    assert len(found) == 1 and found[0]["name"] == "Mia Park", found


def test_admin_without_workspace_403():
    h = {"Authorization": f"Bearer {login('admin@vantora.ai', os.environ['ADMIN_PASSWORD'])}"}
    requests.post(f"{API}/admin/demo-workspace/exit", headers=h)
    r = requests.get(f"{API}/leads", headers=h)
    assert r.status_code == 403, r.text


# --- demo reset (runs last: wipes leads)
def test_demo_reset_customers(owner):
    custs = owner.get(f"{API}/customers").json()
    print("customers before reset:", len(custs), [c["name"] for c in custs])
    assert any(c.get("lead_id") for c in custs)
    r = owner.post(f"{API}/demo/reset")
    assert r.status_code == 200
    custs = owner.get(f"{API}/customers").json()
    names = sorted(c["name"] for c in custs)
    assert names == ["Elena Rossi", "Marcus Webb", "Olivia Chen", "Priya Raman"], names
    assert not any(c.get("lead_id") for c in custs)
    assert sorted(l["name"] for l in owner.get(f"{API}/leads").json()) == ["Isabella Moreau", "James Carter", "Sofia Alvarez"]


# --- edge: AI lead that reuses a seeded customer's email must not delete the seeded customer on reset
def test_reset_keeps_seeded_customer_linked_to_ai_lead(owner):
    chat(owner, f"t8k_{TAG}", "Hi, I'm Olivia Chen, olivia.chen@example.com. Do you sell gift cards?")
    custs = owner.get(f"{API}/customers").json()
    oli = [c for c in custs if c["name"] == "Olivia Chen"]
    print("olivia after chat:", oli)
    assert owner.post(f"{API}/demo/reset").status_code == 200
    names = sorted(c["name"] for c in owner.get(f"{API}/customers").json())
    assert "Olivia Chen" in names, f"seeded customer deleted by reset: {names}"


# --- edge: opt-out via chat must not be silently re-granted by a still-ticked checkbox on the next message
def test_optout_not_regranted_by_ticked_checkbox(owner):
    sid, email = f"t8l_{TAG}", f"rita.l{TAG}@example.com"
    cb = {"email": True, "sms": False}
    chat(owner, sid, f"Hi, I'm Rita Holm, {email}.", consent=cb)
    chat(owner, sid, "please unsubscribe me", consent=cb)
    l = lead_by_email(owner, email)[0]
    assert lead_detail(owner, l["lead_id"])["consent"]["email"]["granted"] is False
    chat(owner, sid, "What are your Sunday hours?", consent=cb)
    c = lead_detail(owner, l["lead_id"])["consent"]["email"]
    assert c["granted"] is False, f"opt-out reverted by checkbox: {c}"
