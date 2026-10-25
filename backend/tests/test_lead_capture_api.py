# E2E API tests for automatic AI lead capture, consent, dedup, CRM, drafts, isolation (iteration 7)
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
TAG = uuid.uuid4().hex[:6]
STATE = {}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {login('demo@aurasalon.com', os.environ['DEMO_OWNER_PASSWORD'])}"
    return s


@pytest.fixture(scope="module")
def biz(owner):
    return owner.get(f"{API}/business").json()


def chat(owner, sid, msg, consent=None):
    body = {"session_id": sid, "message": msg}
    if consent is not None:
        body["consent"] = consent
    r = owner.post(f"{API}/chat/stream", json=body, timeout=120)
    assert r.status_code == 200, r.text
    return r.text


def leads(owner):
    return owner.get(f"{API}/leads").json()


def lead_by_email(owner, email):
    return [l for l in leads(owner) if (l.get("email") or "").lower() == email.lower()]


def detail(owner, lid):
    r = owner.get(f"{API}/leads/{lid}")
    assert r.status_code == 200
    return r.json()


# --- capture without booking + consent question
def test_capture_without_booking(owner):
    email = f"nora.{TAG}@example.com"
    sid = f"t7a_{TAG}"
    before = len(owner.get(f"{API}/bookings").json())
    reply = chat(owner, sid, f"Hi, I'm Nora Lindqvist, {email}. Tell me about the Hot Stone Ritual.")
    assert "Would you like to receive occasional offers" in reply
    assert "Booking confirmed" not in reply
    assert len(owner.get(f"{API}/bookings").json()) == before
    found = lead_by_email(owner, email)
    assert len(found) == 1
    l = found[0]
    assert l["status"] == "new" and l["name"] == "Nora Lindqvist"
    assert sid in l["chat_session_ids"]
    STATE.update(lead=l["lead_id"], email=email, sid=sid)
    time.sleep(12)
    l = detail(owner, l["lead_id"])["lead"]
    print("summary:", l.get("summary"), "interests:", l.get("service_interests"))
    assert l.get("summary"), "summary not generated"
    assert "Hot Stone Ritual" in l["service_interests"]


# --- consent answer via AI question
def test_consent_email_only(owner):
    chat(owner, STATE["sid"], "email only")
    l = detail(owner, STATE["lead"])["lead"]
    assert l["consent"]["email"]["granted"] is True
    assert l["consent"]["email"]["source"] == "ai chat question"
    assert "Would you like to receive" in l["consent"]["email"]["text"]
    assert l["consent"]["email"]["at"]
    assert l["consent"]["sms"]["granted"] is False


# --- unanswered consent question never counts
def test_unanswered_consent(owner):
    sid = f"t7b_{TAG}"
    email = f"otto.{TAG}@example.com"
    chat(owner, sid, f"Hello, my name is Otto Brandt, {email}.")
    chat(owner, sid, "What time do you open on Saturday?")
    l = lead_by_email(owner, email)[0]
    assert l["consent"] == {"email": None, "sms": None}


# --- adversarial: unrelated question mentioning 'both' / 'email' right after consent question
def test_unrelated_reply_with_keyword_is_not_consent(owner):
    sid = f"t7c_{TAG}"
    email = f"lena.{TAG}@example.com"
    chat(owner, sid, f"Hi, I'm Lena Fischer, {email}.")
    chat(owner, sid, "Do you offer both facials and massages on the same day?")
    l = lead_by_email(owner, email)[0]
    STATE["adv"] = l["consent"]
    assert l["consent"] == {"email": None, "sms": None}, f"false consent recorded: {l['consent']}"


# --- checkbox consent
def test_checkbox_sms(owner):
    sid = f"t7d_{TAG}"
    phone = f"+1 555 77{TAG[:1].isdigit() and TAG[:1] or '1'}{int(time.time()) % 10000:04d}"
    chat(owner, sid, f"Hi, I'm Pia Novak, my number is {phone}.", consent={"sms": True, "email": False})
    l = [x for x in leads(owner) if x["name"] == "Pia Novak" and sid in x.get("chat_session_ids", [])][0]
    assert l["consent"]["sms"]["granted"] is True and l["consent"]["sms"]["source"] == "chat widget checkbox"
    assert l["consent"]["email"] is None
    STATE["pia"] = l["lead_id"]


# --- unsubscribe
def test_unsubscribe(owner):
    chat(owner, STATE["sid"], "please unsubscribe me")
    l = detail(owner, STATE["lead"])["lead"]
    assert l["consent"]["email"]["granted"] is False and l["consent"]["sms"]["granted"] is False


# --- dedup different case
def test_dedup_case_insensitive(owner):
    sid = f"t7e_{TAG}"
    chat(owner, sid, f"Hi, I'm Nora Lindqvist, {STATE['email'].upper()}. Do you sell gift cards?")
    assert len(lead_by_email(owner, STATE["email"])) == 1
    d = detail(owner, STATE["lead"])
    assert len(d["conversations"]) == 2


def test_manual_add_duplicate_409(owner):
    r = owner.post(f"{API}/leads", json={"name": "Dup", "email": STATE["email"].title()})
    assert r.status_code == 409


def test_invalid_email_400(owner):
    r = owner.put(f"{API}/leads/{STATE['lead']}", json={"email": "not-an-email"})
    assert r.status_code == 400


# --- drafts
def test_draft_requires_consent(owner):
    iso = [l for l in leads(owner) if l["name"] == "Isabella Moreau"][0]
    d = owner.post(f"{API}/leads/{iso['lead_id']}/drafts", json={"channel": "email"}, timeout=90)
    assert d.status_code == 200, d.text
    did = d.json()["draft_id"]
    r = owner.post(f"{API}/leads/{iso['lead_id']}/drafts/{did}/approve")
    assert r.status_code == 403 and "Nothing was sent" in r.json()["detail"]
    l = detail(owner, iso["lead_id"])["lead"]
    assert [x for x in l["drafts"] if x["draft_id"] == did][0]["status"] == "pending"
    assert owner.post(f"{API}/leads/{iso['lead_id']}/drafts/{did}/discard").status_code == 200
    l = detail(owner, iso["lead_id"])["lead"]
    assert all(x["draft_id"] != did or x["status"] != "pending" for x in l["drafts"])


def test_draft_approve_with_consent(owner):
    d = owner.post(f"{API}/leads/{STATE['pia']}/drafts", json={"channel": "sms"}, timeout=90)
    assert d.status_code == 200
    did = d.json()["draft_id"]
    assert owner.put(f"{API}/leads/{STATE['pia']}/drafts/{did}", json={"message": "Edited TEST message"}).status_code == 200
    r = owner.post(f"{API}/leads/{STATE['pia']}/drafts/{did}/approve")
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["simulated"] is True and e["delivered"] is False and e["message"] == "Edited TEST message"
    l = detail(owner, STATE["pia"])["lead"]
    assert l["status"] == "contacted"


# --- booking association
def test_booking_links_same_lead(owner):
    sid = f"t7f_{TAG}"
    reply = chat(owner, sid, f"Hi, I'm Nora Lindqvist, {STATE['email']}. Please book a Signature Aura Facial on Tuesday October 27 2026 at 11:00 AM.")
    print(reply[-400:])
    if "Booking confirmed" not in reply:
        reply = chat(owner, sid, "Yes, please confirm that booking.")
        print(reply[-400:])
    assert "Booking confirmed. Reference: bk_" in reply
    found = lead_by_email(owner, STATE["email"])
    assert len(found) == 1 and found[0]["status"] == "booked"
    d = detail(owner, found[0]["lead_id"])
    assert len(d["bookings"]) >= 1
    assert any(f.get("kind") == "booking_confirmation" for f in d["lead"]["follow_ups"])
    STATE["bk"] = d["bookings"][0]["booking_id"]


# --- isolation & public widget
def test_isolation(owner):
    r = requests.post(f"{API}/auth/register", json={"name": "TEST Iso7", "email": f"test_iso7_{TAG}@example.com",
                                                     "password": "Test1234!", "business_name": f"TEST Iso7 {TAG}"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert requests.get(f"{API}/leads", headers=h).json() == []
    assert requests.get(f"{API}/leads/{STATE['lead']}", headers=h).status_code == 404
    assert requests.put(f"{API}/leads/{STATE['lead']}", headers=h, json={"status": "closed"}).status_code == 404


def test_public_widget(biz):
    r = requests.post(f"{API}/chat/stream", json={"session_id": f"t7w_{TAG}", "message": "What are your hours?",
                                                    "business_id": biz["business_id"], "consent": {}}, timeout=120)
    assert r.status_code == 200 and len(r.text) > 10
