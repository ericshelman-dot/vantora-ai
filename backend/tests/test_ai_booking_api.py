# AI booking + scheduling engine API regression (iteration 6)
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
CAP_DATE = "2026-10-27"          # Tuesday, EDT
CAP_UTC = "2026-10-27T15:00:00Z"  # 11:00 NY


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def owner():
    t = login("demo@aurasalon.com", os.environ["DEMO_OWNER_PASSWORD"])
    return {"Authorization": f"Bearer {t}"}


def chat(h, msg, sid):
    r = requests.post(f"{API}/chat/stream", json={"session_id": sid, "message": msg}, headers=h, timeout=120)
    assert r.status_code == 200, r.text
    return r.text


def bookings(h):
    return requests.get(f"{API}/bookings", headers=h, timeout=30).json()


# Availability within hours
def test_availability_weekday(owner):
    r = requests.get(f"{API}/bookings/availability", params={"date": "2026-10-26", "service": "Signature Aura Facial"}, headers=owner)
    assert r.status_code == 200
    d = r.json()
    assert d["duration_min"] == 60 and d["timezone"] == "America/New_York"
    assert d["slots"][0] == "09:00" and d["slots"][-1] == "19:00"


def test_availability_sat_sun(owner):
    sat = requests.get(f"{API}/bookings/availability", params={"date": "2026-10-24", "service": "Signature Aura Facial"}, headers=owner).json()
    sun = requests.get(f"{API}/bookings/availability", params={"date": "2026-10-25", "service": "Signature Aura Facial"}, headers=owner).json()
    assert sat["slots"] and sat["slots"][-1] <= "17:00" and sat["slots"][0] >= "09:00"
    assert sun["slots"][0] == "10:00" and sun["slots"][-1] == "15:00"


def test_availability_bad_date(owner):
    r = requests.get(f"{API}/bookings/availability", params={"date": "10/27/2026"}, headers=owner)
    assert r.status_code == 400


# Capacity 3 + 409 + AI refuses
class TestCapacity:
    created = []

    def test_fill_and_reject(self, owner):
        for i in range(3):
            r = requests.post(f"{API}/bookings", json={"customer_name": f"TEST_cap{i}", "service": "Signature Aura Facial", "datetime": CAP_UTC}, headers=owner)
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["booking_id"].startswith("bk_") and b["start_utc"] == "2026-10-27T15:00:00+00:00" and b["end_utc"] == "2026-10-27T16:00:00+00:00"
            TestCapacity.created.append(b["booking_id"])
        r = requests.post(f"{API}/bookings", json={"customer_name": "TEST_cap4", "service": "Deep Tissue Massage", "datetime": "2026-10-27T15:30:00Z"}, headers=owner)
        assert r.status_code == 409
        assert "fully booked" in r.json()["detail"]
        assert not any(b["customer_name"] == "TEST_cap4" for b in bookings(owner))

    def test_put_into_full_slot_409(self, owner):
        r = requests.post(f"{API}/bookings", json={"customer_name": "TEST_mover", "service": "Signature Aura Facial", "datetime": "2026-10-27T18:00:00Z"}, headers=owner)
        assert r.status_code == 200
        bid = r.json()["booking_id"]
        TestCapacity.created.append(bid)
        r = requests.put(f"{API}/bookings/{bid}", json={"customer_name": "TEST_mover", "service": "Signature Aura Facial", "datetime": CAP_UTC}, headers=owner)
        assert r.status_code == 409

    def test_ai_refuses_full_slot(self, owner):
        before = len(bookings(owner))
        txt = chat(owner, f"Hi I'm Tess Tester, please book a Signature Aura Facial on {CAP_DATE} at 11:00 AM, email tess.tester@example.com", f"TEST_{uuid.uuid4().hex[:8]}")
        print(txt)
        assert "No appointment was created for that time." in txt
        assert "Booking confirmed" not in txt
        assert len(bookings(owner)) == before

    def test_cleanup(self, owner):
        for bid in TestCapacity.created:
            assert requests.delete(f"{API}/bookings/{bid}", headers=owner).status_code == 200


# Outside hours via AI
def test_ai_outside_hours(owner):
    before = len(bookings(owner))
    txt = chat(owner, "I'm Nora Night, book a Deep Tissue Massage on 2026-10-28 at 11:00 PM, email nora.night@example.com", f"TEST_{uuid.uuid4().hex[:8]}")
    print(txt)
    assert "No appointment was created for that time." in txt and "Booking confirmed" not in txt
    assert len(bookings(owner)) == before


# Missing contact
def test_ai_missing_contact(owner):
    before = len(bookings(owner))
    txt = chat(owner, "Hi I'm Mia Nocontact, book a Signature Aura Facial on 2026-10-28 at 2:00 PM please", f"TEST_{uuid.uuid4().hex[:8]}")
    print(txt)
    assert "Booking confirmed" not in txt
    assert any(w in txt.lower() for w in ("email", "phone"))
    assert len(bookings(owner)) == before


# Scheduling settings validation + persistence
class TestSettings:
    def test_capacity_persist_and_restore(self, owner):
        biz = requests.get(f"{API}/business", headers=owner).json()
        sc = biz["scheduling"]
        r = requests.put(f"{API}/business", json={"scheduling": {**sc, "capacity": 4}}, headers=owner)
        assert r.status_code == 200 and r.json()["scheduling"]["capacity"] == 4
        assert requests.get(f"{API}/business", headers=owner).json()["scheduling"]["capacity"] == 4
        r = requests.put(f"{API}/business", json={"scheduling": {**sc, "capacity": 3}}, headers=owner)
        assert r.json()["scheduling"]["capacity"] == 3

    def test_invalid_tz_422(self, owner):
        sc = requests.get(f"{API}/business", headers=owner).json()["scheduling"]
        assert requests.put(f"{API}/business", json={"scheduling": {**sc, "timezone": "Mars/Olympus"}}, headers=owner).status_code == 422

    def test_close_before_open_422(self, owner):
        sc = requests.get(f"{API}/business", headers=owner).json()["scheduling"]
        bad = {**sc, "weekly": {**sc["weekly"], "mon": ["18:00", "09:00"]}}
        assert requests.put(f"{API}/business", json={"scheduling": bad}, headers=owner).status_code == 422
        assert requests.get(f"{API}/business", headers=owner).json()["scheduling"]["weekly"]["mon"] == ["09:00", "20:00"]


# Isolation for new signup
def test_isolation_new_owner(owner):
    email = f"test_iso_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"name": "TEST Iso", "email": email, "password": "Test1234!", "business_name": "TEST Iso Biz"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert bookings(h) == []
    biz = requests.get(f"{API}/business", headers=h).json()
    av = requests.get(f"{API}/bookings/availability", params={"date": CAP_DATE}, headers=h).json()
    assert av["slots"][0] == "09:00" and av["slots"][-1] == "17:00"
    sat = requests.get(f"{API}/bookings/availability", params={"date": "2026-10-24"}, headers=h).json()
    assert sat["slots"] == []
    # capacity 1 by default
    r1 = requests.post(f"{API}/bookings", json={"customer_name": "TEST_a", "service": "x", "datetime": CAP_UTC}, headers=h)
    r2 = requests.post(f"{API}/bookings", json={"customer_name": "TEST_b", "service": "x", "datetime": CAP_UTC}, headers=h)
    assert r1.status_code == 200 and r2.status_code == 409
    # cannot delete Aura booking
    aura = bookings(owner)
    if aura:
        assert requests.delete(f"{API}/bookings/{aura[0]['booking_id']}", headers=h).status_code == 404
    print("new biz scheduling:", biz.get("scheduling"))
