# Demo Business Workspace tests: admin demo mode, reset, isolation, revenue exclusion, security
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def admin_h():
    h = login("admin@vantora.ai", os.environ["ADMIN_PASSWORD"])
    yield h
    requests.post(f"{API}/admin/demo-workspace/exit", headers=h)


@pytest.fixture(scope="module")
def owner_h():
    return login("demo@aurasalon.com", os.environ["DEMO_OWNER_PASSWORD"])


@pytest.fixture(scope="module")
def new_owner():
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"name": "TEST Owner", "email": email, "password": "Test123!", "business_name": "TEST Biz"})
    assert r.status_code == 200, r.text
    d = r.json()
    h = {"Authorization": f"Bearer {d['token']}"}
    # seed one lead + booking in this real business
    lr = requests.post(f"{API}/leads", headers=h, json={"name": "TEST RealLead", "email": "real@example.com", "phone": "", "source": "manual", "status": "new", "notes": ""})
    assert lr.status_code == 200, lr.text
    br = requests.post(f"{API}/bookings", headers=h, json={"customer_name": "TEST RealBk", "service": "Cut", "datetime": "2026-02-01T10:00", "status": "confirmed", "notes": ""})
    assert br.status_code == 200, br.text
    return {"h": h, "business_id": d["user"]["business_id"]}


def get_me(h):
    return requests.get(f"{API}/auth/me", headers=h).json()


class TestAdminDemo:
    def test_admin_stats_excludes_demo(self, admin_h):
        requests.post(f"{API}/admin/demo-workspace/exit", headers=admin_h)
        s = requests.get(f"{API}/admin/stats", headers=admin_h).json()
        assert s["demo_workspaces"] == 1
        biz = requests.get(f"{API}/admin/businesses", headers=admin_h).json()
        aura = [b for b in biz if b.get("is_demo")]
        assert len(aura) == 1 and aura[0]["name"] == "Aura Luxury Spa"
        real = [b for b in biz if not b.get("is_demo")]
        assert s["total_businesses"] == len(real)
        assert s["active_subscriptions"] == len([b for b in real if b.get("subscription_status") == "active"])

    def test_aura_active_not_counted(self, admin_h):
        biz = requests.get(f"{API}/admin/businesses", headers=admin_h).json()
        aura = [b for b in biz if b.get("is_demo")][0]
        before = requests.get(f"{API}/admin/stats", headers=admin_h).json()
        orig = aura.get("subscription_status")
        requests.put(f"{API}/admin/businesses/{aura['business_id']}/status", headers=admin_h, json={"subscription_status": "active"})
        after = requests.get(f"{API}/admin/stats", headers=admin_h).json()
        requests.put(f"{API}/admin/businesses/{aura['business_id']}/status", headers=admin_h, json={"subscription_status": orig})
        if orig != "active":
            assert after["active_subscriptions"] == before["active_subscriptions"]
            assert after["estimated_mrr"] == before["estimated_mrr"]

    def test_enter_demo(self, admin_h):
        r = requests.post(f"{API}/admin/demo-workspace/enter", headers=admin_h)
        assert r.status_code == 200
        me = get_me(admin_h)
        assert me["user"]["demo_mode"] is True
        assert me["business"]["name"] == "Aura Luxury Spa"
        assert me["business"]["is_demo"] is True

    def test_demo_chat_and_lead_capture(self, admin_h):
        sid = "test_" + uuid.uuid4().hex[:8]
        msg = "Hi, I'm Laura Bennett, I'd like a Hot Stone Ritual on Saturday. My email is laura.b@example.com"
        r = requests.post(f"{API}/chat/stream", headers=admin_h, json={"session_id": sid, "message": msg}, timeout=120)
        assert r.status_code == 200, r.text
        assert len(r.text) > 20
        assert "Business not found" not in r.text and "trouble responding" not in r.text
        time.sleep(1)
        leads = requests.get(f"{API}/leads", headers=admin_h).json()
        laura = [l for l in leads if l["name"] == "Laura Bennett"]
        assert laura and laura[0]["email"] == "laura.b@example.com" and laura[0]["source"] == "website chat"

    def test_demo_isolation(self, admin_h, new_owner):
        leads = requests.get(f"{API}/leads", headers=admin_h).json()
        bks = requests.get(f"{API}/bookings", headers=admin_h).json()
        custs = requests.get(f"{API}/customers", headers=admin_h).json()
        bid = get_me(admin_h)["business"]["business_id"]
        assert all(x["business_id"] == bid for x in leads + bks + custs)
        # admin in demo cannot touch other business's lead
        nl = requests.get(f"{API}/leads", headers=new_owner["h"]).json()[0]
        r = requests.delete(f"{API}/leads/{nl['lead_id']}", headers=admin_h)
        assert r.status_code == 404

    def test_followup_booking_call(self, admin_h):
        lead = [l for l in requests.get(f"{API}/leads", headers=admin_h).json() if l["name"] == "Laura Bennett"][0]
        r = requests.post(f"{API}/leads/{lead['lead_id']}/follow-up", headers=admin_h, json={"channel": "email", "message": "Hi Laura!"})
        assert r.status_code == 200 and r.json()["status"] == "simulated-sent"
        r = requests.post(f"{API}/bookings", headers=admin_h, json={"customer_name": "Laura Bennett", "service": "Hot Stone Ritual", "datetime": "2026-02-07T11:00", "status": "confirmed", "notes": ""})
        assert r.status_code == 200
        r = requests.post(f"{API}/call-logs/simulate", headers=admin_h, timeout=120)
        assert r.status_code == 200 and r.json()["simulated"] is True

    def test_reset(self, admin_h, new_owner):
        r = requests.post(f"{API}/demo/reset", headers=admin_h)
        assert r.status_code == 200
        names = sorted(l["name"] for l in requests.get(f"{API}/leads", headers=admin_h).json())
        assert names == ["Isabella Moreau", "James Carter", "Sofia Alvarez"]
        assert len(requests.get(f"{API}/bookings", headers=admin_h).json()) == 3
        assert len(requests.get(f"{API}/customers", headers=admin_h).json()) == 4
        # new owner untouched
        assert len(requests.get(f"{API}/leads", headers=new_owner["h"]).json()) == 1
        assert len(requests.get(f"{API}/bookings", headers=new_owner["h"]).json()) == 1

    def test_exit_demo(self, admin_h):
        r = requests.post(f"{API}/admin/demo-workspace/exit", headers=admin_h)
        assert r.status_code == 200
        me = get_me(admin_h)
        assert me["user"]["business_id"] is None and me["user"]["demo_mode"] is False
        r = requests.post(f"{API}/chat/stream", headers=admin_h, json={"session_id": "x", "message": "hi"})
        assert r.status_code == 403
        r = requests.post(f"{API}/demo/reset", headers=admin_h)
        assert r.status_code == 403


class TestSecurity:
    def test_owner_cannot_enter_demo(self, new_owner):
        r = requests.post(f"{API}/admin/demo-workspace/enter", headers=new_owner["h"])
        assert r.status_code == 403

    def test_non_demo_owner_cannot_reset(self, new_owner):
        r = requests.post(f"{API}/demo/reset", headers=new_owner["h"])
        assert r.status_code == 403
        assert len(requests.get(f"{API}/leads", headers=new_owner["h"]).json()) == 1

    def test_demo_owner_login_and_reset(self, owner_h):
        me = get_me(owner_h)
        assert me["user"]["role"] == "owner" and me["user"]["demo_mode"] is False
        assert me["business"]["is_demo"] is True
        r = requests.post(f"{API}/demo/reset", headers=owner_h)
        assert r.status_code == 200

    def test_public_widget_chat(self, owner_h):
        bid = get_me(owner_h)["business"]["business_id"]
        r = requests.post(f"{API}/chat/stream", json={"business_id": bid, "session_id": "test_w_" + uuid.uuid4().hex[:6], "message": "What are your Saturday hours?"}, timeout=120)
        assert r.status_code == 200 and len(r.text) > 10
        assert "trouble responding" not in r.text

    def test_regression_plans_demo_requests(self, admin_h):
        assert requests.get(f"{API}/plans").status_code == 200
        p = requests.get(f"{API}/plans").json()[0]
        body = {k: p[k] for k in ("name", "setup_fee", "monthly_fee", "features")}
        r = requests.put(f"{API}/admin/plans/{p['plan_id']}", headers=admin_h, json=body)
        assert r.status_code == 200 and r.json()["name"] == p["name"]
        assert requests.get(f"{API}/admin/demo-requests", headers=admin_h).status_code == 200
