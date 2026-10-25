"""LocalBiz AI backend regression tests (auth, business, leads, bookings, customers, AI, admin, tenancy)"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER = {"email": "demo@aurasalon.com", "password": os.environ['DEMO_OWNER_PASSWORD']}
ADMIN = {"email": "admin@localbiz.ai", "password": os.environ['ADMIN_PASSWORD']}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def owner_h():
    return {"Authorization": f"Bearer {_login(OWNER)['token']}"}


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login(ADMIN)['token']}"}


@pytest.fixture(scope="module")
def new_owner():
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "name": "TEST Owner", "email": email, "password": "Test123!", "business_name": "TEST_Biz"}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"h": {"Authorization": f"Bearer {d['token']}"}, "user": d["user"], "email": email}


# --- Auth ---
class TestAuth:
    def test_owner_login(self):
        d = _login(OWNER)
        assert d["user"]["role"] == "owner" and d["user"]["business_id"]

    def test_admin_login(self):
        assert _login(ADMIN)["user"]["role"] == "admin"

    def test_bad_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": OWNER["email"], "password": "x"})
        assert r.status_code == 401

    def test_register_and_me(self, new_owner):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=new_owner["h"])
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == new_owner["email"]
        assert d["business"]["name"] == "TEST_Biz"

    def test_register_duplicate(self, new_owner):
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "x", "email": new_owner["email"], "password": "x", "business_name": "x"})
        assert r.status_code == 400

    def test_unauth(self):
        assert requests.get(f"{BASE_URL}/api/leads").status_code == 401


# --- Business & stats ---
class TestBusiness:
    def test_stats(self, owner_h):
        d = requests.get(f"{BASE_URL}/api/stats", headers=owner_h).json()
        for k in ("leads", "bookings", "customers", "calls", "chats"):
            assert isinstance(d[k], int)

    def test_update_business_persists(self, new_owner):
        h = new_owner["h"]
        r = requests.put(f"{BASE_URL}/api/business", headers=h, json={
            "services": "TEST svc", "hours": "24/7", "faqs": "Q?A", "ai_tone": "playful", "chat_enabled": False})
        assert r.status_code == 200
        g = requests.get(f"{BASE_URL}/api/business", headers=h).json()
        assert g["services"] == "TEST svc" and g["ai_tone"] == "playful" and g["chat_enabled"] is False


# --- Leads / bookings / customers CRUD ---
class TestCrud:
    def test_lead_crud_and_followup(self, new_owner):
        h = new_owner["h"]
        lead = requests.post(f"{BASE_URL}/api/leads", headers=h, json={"name": "TEST_Lead", "email": "l@x.com"}).json()
        lid = lead["lead_id"]
        fu = requests.post(f"{BASE_URL}/api/leads/{lid}/follow-up", headers=h, json={"channel": "email", "message": "hi"})
        assert fu.status_code == 200 and fu.json()["status"] == "simulated-sent"
        got = [l for l in requests.get(f"{BASE_URL}/api/leads", headers=h).json() if l["lead_id"] == lid][0]
        assert got["status"] == "contacted" and len(got["follow_ups"]) == 1
        assert requests.delete(f"{BASE_URL}/api/leads/{lid}", headers=h).status_code == 200
        assert not [l for l in requests.get(f"{BASE_URL}/api/leads", headers=h).json() if l["lead_id"] == lid]

    def test_followup_blocked_without_consent(self, new_owner):
        h = new_owner["h"]
        lid = requests.post(f"{BASE_URL}/api/leads", headers=h, json={"name": "TEST_L2"}).json()["lead_id"]
        requests.put(f"{BASE_URL}/api/business", headers=h, json={"follow_up_consent": False})
        r = requests.post(f"{BASE_URL}/api/leads/{lid}/follow-up", headers=h, json={"channel": "sms", "message": "hi"})
        requests.put(f"{BASE_URL}/api/business", headers=h, json={"follow_up_consent": True})
        assert r.status_code == 403

    def test_booking_crud(self, new_owner):
        h = new_owner["h"]
        b = requests.post(f"{BASE_URL}/api/bookings", headers=h, json={
            "customer_name": "TEST_C", "service": "Cut", "datetime": "2030-01-01T10:00"}).json()
        assert any(x["booking_id"] == b["booking_id"] for x in requests.get(f"{BASE_URL}/api/bookings", headers=h).json())
        requests.delete(f"{BASE_URL}/api/bookings/{b['booking_id']}", headers=h)
        assert not any(x["booking_id"] == b["booking_id"] for x in requests.get(f"{BASE_URL}/api/bookings", headers=h).json())

    def test_customer_crud(self, new_owner):
        h = new_owner["h"]
        c = requests.post(f"{BASE_URL}/api/customers", headers=h, json={"name": "TEST_Cust"}).json()
        assert any(x["customer_id"] == c["customer_id"] for x in requests.get(f"{BASE_URL}/api/customers", headers=h).json())
        requests.delete(f"{BASE_URL}/api/customers/{c['customer_id']}", headers=h)
        assert not any(x["customer_id"] == c["customer_id"] for x in requests.get(f"{BASE_URL}/api/customers", headers=h).json())


# --- Multi-tenant isolation ---
class TestTenancy:
    def test_new_owner_sees_no_demo_data(self, new_owner, owner_h):
        demo_leads = requests.get(f"{BASE_URL}/api/leads", headers=owner_h).json()
        mine = requests.get(f"{BASE_URL}/api/leads", headers=new_owner["h"]).json()
        demo_ids = {l["lead_id"] for l in demo_leads}
        assert not demo_ids & {l["lead_id"] for l in mine}

    def test_cannot_delete_other_tenant_lead(self, new_owner, owner_h):
        lid = requests.get(f"{BASE_URL}/api/leads", headers=owner_h).json()[0]["lead_id"]
        requests.delete(f"{BASE_URL}/api/leads/{lid}", headers=new_owner["h"])
        assert any(l["lead_id"] == lid for l in requests.get(f"{BASE_URL}/api/leads", headers=owner_h).json())

    def test_put_other_tenant_lead_does_not_leak(self, new_owner, owner_h):
        lid = requests.get(f"{BASE_URL}/api/leads", headers=owner_h).json()[0]["lead_id"]
        r = requests.put(f"{BASE_URL}/api/leads/{lid}", headers=new_owner["h"], json={"name": "HACK"})
        body = r.json() if r.status_code == 200 else None
        assert r.status_code == 404 or body is None, f"leaked other tenant lead: {body}"

    def test_owner_forbidden_admin(self, owner_h):
        assert requests.get(f"{BASE_URL}/api/admin/stats", headers=owner_h).status_code == 403


# --- AI (Gemini) ---
class TestAI:
    def test_chat_stream(self, owner_h):
        r = requests.post(f"{BASE_URL}/api/chat/stream", headers=owner_h,
                          json={"session_id": f"t_{uuid.uuid4().hex[:6]}", "message": "What are your hours?"}, timeout=90)
        assert r.status_code == 200 and len(r.text) > 5

    def test_simulate_call(self, new_owner):
        r = requests.post(f"{BASE_URL}/api/call-logs/simulate", headers=new_owner["h"], timeout=120)
        assert r.status_code == 200
        d = r.json()
        assert d["simulated"] is True and len(d["transcript"]) > 20
        assert any(c["call_id"] == d["call_id"] for c in requests.get(f"{BASE_URL}/api/call-logs", headers=new_owner["h"]).json())

    def test_ai_draft(self, new_owner):
        h = new_owner["h"]
        lid = requests.post(f"{BASE_URL}/api/leads", headers=h, json={"name": "TEST_Draft"}).json()["lead_id"]
        r = requests.post(f"{BASE_URL}/api/leads/{lid}/ai-draft", headers=h, json={"channel": "email", "message": ""}, timeout=120)
        assert r.status_code == 200 and len(r.json()["draft"]) > 10


# --- Admin ---
class TestAdmin:
    def test_admin_stats(self, admin_h):
        d = requests.get(f"{BASE_URL}/api/admin/stats", headers=admin_h).json()
        assert {"total_businesses", "active_subscriptions", "estimated_mrr"} <= set(d)

    def test_plan_edit_persists(self, admin_h):
        p = requests.get(f"{BASE_URL}/api/plans").json()[0]
        orig = p["setup_fee"]
        r = requests.put(f"{BASE_URL}/api/admin/plans/{p['plan_id']}", headers=admin_h, json={
            "name": p["name"], "setup_fee": orig + 1, "monthly_fee": p["monthly_fee"], "features": p["features"]})
        assert r.status_code == 200 and r.json()["setup_fee"] == orig + 1
        requests.put(f"{BASE_URL}/api/admin/plans/{p['plan_id']}", headers=admin_h, json={
            "name": p["name"], "setup_fee": orig, "monthly_fee": p["monthly_fee"], "features": p["features"]})

    def test_set_business_status(self, admin_h, new_owner):
        bid = new_owner["user"]["business_id"]
        r = requests.put(f"{BASE_URL}/api/admin/businesses/{bid}/status", headers=admin_h, json={"subscription_status": "active"})
        assert r.status_code == 200 and r.json()["subscription_status"] == "active"
        bl = requests.get(f"{BASE_URL}/api/admin/businesses", headers=admin_h).json()
        assert [b for b in bl if b["business_id"] == bid][0]["subscription_status"] == "active"
