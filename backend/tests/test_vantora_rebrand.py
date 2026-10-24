# Vantora rebrand regression: auth (new + legacy admin), demo-requests, admin guards, tenant isolation
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_tok():
    return login("admin@vantora.ai", os.environ["ADMIN_PASSWORD"])["token"]


@pytest.fixture(scope="module")
def owner_tok():
    return login("demo@aurasalon.com", os.environ["DEMO_OWNER_PASSWORD"])["token"]


# --- Root & plans
def test_root_branding():
    r = requests.get(f"{API}/")
    assert r.status_code == 200 and "Vantora" in r.json()["message"]


def test_plans_public():
    r = requests.get(f"{API}/plans")
    assert r.status_code == 200
    assert len(r.json()) >= 3 and all("_id" not in p for p in r.json())


# --- Auth
def test_admin_vantora_login():
    d = login("admin@vantora.ai", os.environ["ADMIN_PASSWORD"])
    assert d["user"]["role"] == "admin" and d["user"]["business_id"] is None


def test_legacy_admin_login():
    d = login("admin@localbiz.ai", os.environ["ADMIN_PASSWORD"])
    assert d["user"]["role"] == "admin"


def test_owner_login():
    d = login("demo@aurasalon.com", os.environ["DEMO_OWNER_PASSWORD"])
    assert d["user"]["role"] == "owner" and d["user"]["business_id"]


# --- Demo requests
def test_demo_request_create_list_update(admin_tok):
    name = f"TEST_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/demo-requests", json={"name": name, "email": "test@example.com",
                                                    "company": "TEST Co", "message": "hi", "kind": "demo"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "received" and d["alert_status"] == "simulated-sent"
    rid = d["request_id"]
    lst = requests.get(f"{API}/admin/demo-requests", headers=h(admin_tok)).json()
    item = next(x for x in lst if x["request_id"] == rid)
    assert item["name"] == name and item["status"] == "new" and "_id" not in item
    u = requests.put(f"{API}/admin/demo-requests/{rid}", json={"status": "contacted"}, headers=h(admin_tok))
    assert u.status_code == 200
    lst = requests.get(f"{API}/admin/demo-requests", headers=h(admin_tok)).json()
    assert next(x for x in lst if x["request_id"] == rid)["status"] == "contacted"
    bad = requests.put(f"{API}/admin/demo-requests/{rid}", json={"status": "bogus"}, headers=h(admin_tok))
    assert bad.status_code == 400
    nf = requests.put(f"{API}/admin/demo-requests/req_nope", json={"status": "new"}, headers=h(admin_tok))
    assert nf.status_code == 404


def test_contact_kind():
    r = requests.post(f"{API}/demo-requests", json={"name": "TEST_contact", "email": "c@example.com", "kind": "contact"})
    assert r.status_code == 200


def test_demo_request_invalid_email():
    r = requests.post(f"{API}/demo-requests", json={"name": "TEST_x", "email": "not-an-email"})
    assert r.status_code == 422


def test_demo_request_missing_name():
    r = requests.post(f"{API}/demo-requests", json={"name": "", "email": "a@example.com"})
    assert r.status_code == 422


def test_demo_request_bad_kind():
    r = requests.post(f"{API}/demo-requests", json={"name": "TEST_x", "email": "a@example.com", "kind": "spam"})
    assert r.status_code == 422


def test_demo_requests_non_admin_403(owner_tok):
    r = requests.get(f"{API}/admin/demo-requests", headers=h(owner_tok))
    assert r.status_code == 403


def test_demo_requests_no_auth_401():
    assert requests.get(f"{API}/admin/demo-requests").status_code == 401


# --- Business guard
def test_admin_get_business_403(admin_tok):
    r = requests.get(f"{API}/business", headers=h(admin_tok))
    assert r.status_code == 403
    assert "Business not found" not in r.text and "workspace" in r.json()["detail"]


def test_owner_get_business(owner_tok):
    r = requests.get(f"{API}/business", headers=h(owner_tok))
    assert r.status_code == 200 and r.json()["name"] == "Aura Luxury Spa"


# --- Owner CRUD
def test_owner_lead_and_booking(owner_tok):
    lr = requests.post(f"{API}/leads", json={"name": "TEST_lead", "email": "l@example.com"}, headers=h(owner_tok))
    assert lr.status_code == 200
    lid = lr.json()["lead_id"]
    assert any(x["lead_id"] == lid for x in requests.get(f"{API}/leads", headers=h(owner_tok)).json())
    br = requests.post(f"{API}/bookings", json={"customer_name": "TEST_bk", "service": "Facial",
                                                "datetime": "2026-02-01T10:00:00Z"}, headers=h(owner_tok))
    assert br.status_code == 200
    bid = br.json()["booking_id"]
    assert any(x["booking_id"] == bid for x in requests.get(f"{API}/bookings", headers=h(owner_tok)).json())
    requests.delete(f"{API}/leads/{lid}", headers=h(owner_tok))
    requests.delete(f"{API}/bookings/{bid}", headers=h(owner_tok))


# --- Tenant isolation
def test_tenant_isolation(owner_tok):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"name": "TEST User", "email": email,
                                                    "password": "Test1234!", "business_name": "TEST Biz"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    demo_leads = {x["lead_id"] for x in requests.get(f"{API}/leads", headers=h(owner_tok)).json()}
    new_leads = requests.get(f"{API}/leads", headers=h(tok)).json()
    new_bk = requests.get(f"{API}/bookings", headers=h(tok)).json()
    assert not demo_leads & {x["lead_id"] for x in new_leads}
    assert new_leads == [] and new_bk == []
    assert requests.get(f"{API}/admin/demo-requests", headers=h(tok)).status_code == 403


# --- Admin plans still save
def test_admin_plan_update(admin_tok):
    plans = requests.get(f"{API}/plans").json()
    p = plans[0]
    body = {"name": p["name"], "setup_fee": p["setup_fee"], "monthly_fee": p["monthly_fee"], "features": p["features"]}
    r = requests.put(f"{API}/admin/plans/{p['plan_id']}", json=body, headers=h(admin_tok))
    assert r.status_code == 200 and r.json()["name"] == p["name"]


def test_admin_stats_businesses(admin_tok):
    assert requests.get(f"{API}/admin/stats", headers=h(admin_tok)).status_code == 200
    assert requests.get(f"{API}/admin/businesses", headers=h(admin_tok)).status_code == 200


# --- Chat stream (owner)
def test_owner_chat_stream(owner_tok):
    r = requests.post(f"{API}/chat/stream", json={"session_id": f"TEST_{uuid.uuid4().hex[:6]}", "message": "What are your hours?"},
                      headers=h(owner_tok), timeout=90)
    assert r.status_code == 200 and len(r.text) > 10
