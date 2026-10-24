# Iteration 10: inquiry-reply consent, Jessica dedup, isolation, public widget, AI booking, capture errors.
# NOTE: never calls /api/demo/reset and never deletes existing records.
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import re
import time
import uuid
from datetime import datetime, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
TAG = uuid.uuid4().hex[:6]
JESS = "jessica.demo@example.com"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {login('demo@aurasalon.com', os.environ["DEMO_OWNER_PASSWORD"])}"
    return s


@pytest.fixture(scope="module")
def biz(owner):
    return owner.get(f"{API}/business").json()


def chat(sess, sid, msg, business_id=None):
    body = {"session_id": sid, "message": msg}
    if business_id:
        body["business_id"] = business_id
    r = sess.post(f"{API}/chat/stream", json=body, timeout=150)
    assert r.status_code == 200, r.text
    return r.text


def by_email(owner, email):
    return [l for l in owner.get(f"{API}/leads").json() if l.get("email_norm") == email.lower()]


# --- Jessica: exactly one lead, consent kept, sessions grow, no marketing re-ask
def test_jessica_single_lead_and_new_session_updates(owner):
    before = by_email(owner, JESS)
    assert len(before) == 1
    lid, n_sess = before[0]["lead_id"], len(before[0]["chat_session_ids"])
    old_consent = owner.get(f"{API}/leads/{lid}").json()["lead"]["consent"]
    sid = f"t10j_{TAG}"
    reply = chat(owner, sid, "Hi, this is Jessica Miller again (JESSICA.DEMO@example.com). Do you have parking?")
    assert "May we email you" not in reply and "offers and updates" not in reply, reply
    after = by_email(owner, JESS)
    assert len(after) == 1 and after[0]["lead_id"] == lid
    assert sid in after[0]["chat_session_ids"] and len(after[0]["chat_session_ids"]) == n_sess + 1
    lead = owner.get(f"{API}/leads/{lid}").json()["lead"]
    for ch in ("email", "sms", "inquiry_reply"):
        assert lead["consent"][ch]["granted"] == old_consent[ch]["granted"]
    assert lead["booking_ids"] == []


# --- Fresh lead: inquiry question -> yes -> marketing question -> no; inquiry draft generated
def test_fresh_lead_inquiry_flow(owner):
    email = f"test_hannah.{TAG}@example.com"
    sid = f"t10h_{TAG}"
    r1 = chat(owner, sid, f"Hi, I'm Hannah Brooks. I'm interested in facials. My email is {email}. Not booking yet.")
    assert "May we email you a personal reply about this inquiry?" in r1, r1[-400:]
    assert r1.rstrip().endswith('Reply "yes" or "no".')
    r2 = chat(owner, sid, "Yes please")
    assert "offers and updates" in r2 and r2.rstrip().endswith('Reply "email", "text", "both" or "no".'), r2[-400:]
    chat(owner, sid, "No thanks")
    leads = by_email(owner, email)
    assert len(leads) == 1
    lid = leads[0]["lead_id"]
    lead = None
    for _ in range(12):
        time.sleep(5)
        lead = owner.get(f"{API}/leads/{lid}").json()["lead"]
        if any(d.get("kind") == "inquiry_reply" for d in lead["drafts"]) and lead.get("summary"):
            break
    c = lead["consent"]
    assert c["inquiry_reply"]["granted"] is True and c["inquiry_reply"]["channel_to_use"] == "email"
    assert c["email"]["granted"] is False and c["sms"]["granted"] is False
    assert lead["status"] == "new" and lead["source"] == "website chat" and lead["booking_ids"] == []
    assert lead["summary"]
    inq = [d for d in lead["drafts"] if d.get("kind") == "inquiry_reply" and d["status"] == "pending"]
    assert len(inq) == 1
    ok = owner.post(f"{API}/leads/{lid}/drafts/{inq[0]['draft_id']}/approve")
    assert ok.status_code == 200 and ok.json()["simulated"] is True and ok.json()["kind"] == "inquiry_reply"
    md = owner.post(f"{API}/leads/{lid}/drafts", json={"channel": "email"}, timeout=90)
    assert md.status_code == 200 and md.json()["kind"] == "marketing"
    deny = owner.post(f"{API}/leads/{lid}/drafts/{md.json()['draft_id']}/approve")
    assert deny.status_code == 403


# --- Declining the inquiry reply: inquiry approval blocked
def test_inquiry_declined(owner):
    email = f"test_omar.{TAG}@example.com"
    sid = f"t10o_{TAG}"
    r1 = chat(owner, sid, f"My name is Omar Haddad, email {email}. What are your hours?")
    assert "May we email you" in r1
    chat(owner, sid, "No thanks")
    lead = by_email(owner, email)[0]
    d = owner.get(f"{API}/leads/{lead['lead_id']}").json()["lead"]
    assert d["consent"]["inquiry_reply"]["granted"] is False


# --- Isolation
def test_isolation(owner):
    jid = by_email(owner, JESS)[0]["lead_id"]
    r = requests.post(f"{API}/auth/register", json={"name": "TEST Iso10", "email": f"test_iso10_{TAG}@example.com",
                                                   "password": "Test1234!", "business_name": f"TEST Iso10 {TAG}"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    ls = requests.get(f"{API}/leads", headers=h).json()
    assert not any(l.get("email_norm") == JESS for l in ls)
    assert requests.get(f"{API}/leads/{jid}", headers=h).status_code == 404
    ah = {"Authorization": f"Bearer {login('admin@vantora.ai', os.environ["ADMIN_PASSWORD"])}"}
    assert requests.get(f"{API}/leads", headers=ah).status_code == 403
    assert requests.get(f"{API}/leads/{jid}", headers=ah).status_code == 403


# --- Public widget path (no auth)
def test_public_widget_creates_lead(owner, biz):
    email = f"test_widget10.{TAG}@example.com"
    reply = chat(requests.Session(), f"w10_{TAG}", f"Hi, I'm Priya Natarajan, {email}. Do you do couples massage?", biz["business_id"])
    assert "May we email you" in reply
    ls = by_email(owner, email)
    assert len(ls) == 1 and ls[0]["name"] == "Priya Natarajan" and ls[0]["business_id"] == biz["business_id"]


# --- Capture errors endpoint
def test_capture_errors_empty(owner):
    r = owner.get(f"{API}/lead-capture-errors")
    assert r.status_code == 200 and r.json() == []


# --- AI booking still works
def test_ai_booking(owner):
    slot = None
    for d in range(3, 7):
        day = (datetime.utcnow() + timedelta(days=d)).strftime("%Y-%m-%d")
        s = owner.get(f"{API}/bookings/availability", params={"date": day, "service": "Signature Aura Facial"}).json()["slots"]
        if s:
            slot = (day, s[len(s) // 2])
            break
    assert slot, "no free slot"
    print("SLOT", slot)
    email = f"test_book10.{TAG}@example.com"
    sid = f"t10b_{TAG}"
    t = slot[1] if isinstance(slot[1], str) else slot[1].get("time") or slot[1].get("start") or str(slot[1])
    reply = chat(owner, sid, f"I'd like to book a Signature Aura Facial on {slot[0]} at {t}. My name is Liam Becker, email {email}.")
    m = re.search(r"Booking confirmed\. Reference: (bk_\w+)", reply)
    if not m:
        reply = chat(owner, sid, "Yes, please confirm that booking.")
        m = re.search(r"Booking confirmed\. Reference: (bk_\w+)", reply)
    assert m, reply[-600:]
    bid = m.group(1)
    print("BOOKING_ID", bid)
    assert any(b["booking_id"] == bid for b in owner.get(f"{API}/bookings").json())
    lead = by_email(owner, email)[0]
    assert bid in lead["booking_ids"] and lead["status"] == "booked"
