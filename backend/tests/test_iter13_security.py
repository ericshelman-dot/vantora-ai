# Iteration 13: security hardening - credential rotation, brute force, admin protection, Jessica merge preview (no execute)
import os, re, uuid, requests, pytest
from pathlib import Path

def _env(path, key):
    for line in Path(path).read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')
    return None

BASE_URL = _env("/app/frontend/.env", "REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_PW = _env("/app/backend/.env", "ADMIN_PASSWORD")
DEMO_PW = _env("/app/backend/.env", "DEMO_OWNER_PASSWORD")
API = f"{BASE_URL}/api"


def login(email, pw):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)


@pytest.fixture(scope="module")
def owner_h():
    r = login("demo@aurasalon.com", DEMO_PW)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def admin_h():
    r = login("admin@vantora.ai", ADMIN_PW)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --- Password rotation ---
class TestRotation:
    @pytest.mark.parametrize("email,old", [("demo@aurasalon.com", "Demo123!"), ("admin@vantora.ai", "Admin123!"), ("admin@localbiz.ai", "Admin123!")])
    def test_old_password_rejected_then_new_works(self, email, old):
        r = login(email, old)
        assert r.status_code == 401, r.text
        new = DEMO_PW if email.startswith("demo") else ADMIN_PW
        r2 = login(email, new)  # success clears failed attempt counter
        assert r2.status_code == 200, r2.text
        assert r2.json()["user"]["email"] == email

    def test_no_plaintext_passwords_in_server(self):
        src = Path("/app/backend/server.py").read_text()
        for s in ("Demo123", "Admin123", ADMIN_PW, DEMO_PW):
            assert s not in src
        assert not re.search(r"JWT_SECRET\s*=\s*['\"]", src)

    def test_stored_hash_is_bcrypt(self):
        from pymongo import MongoClient
        c = MongoClient(_env("/app/backend/.env", "MONGO_URL"))
        db = c[_env("/app/backend/.env", "DB_NAME")]
        for e in ("demo@aurasalon.com", "admin@vantora.ai", "admin@localbiz.ai"):
            u = db.users.find_one({"email": e})
            assert u["password_hash"].startswith("$2"), e


# --- Brute force ---
class TestBruteForce:
    def test_sixth_attempt_429(self):
        email = f"test_bf_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register", json={"name": "TEST BF", "email": email, "password": "Correct-Pass-9x", "business_name": "TEST BF Biz"}, timeout=30)
        assert r.status_code in (200, 201), r.text
        codes = [login(email, "wrong-pw").status_code for _ in range(5)]
        assert codes == [401] * 5, codes
        r6 = login(email, "Correct-Pass-9x")
        assert r6.status_code == 429, r6.text

    def test_spoofed_xff_does_not_bypass(self):
        email = f"test_bf2_{uuid.uuid4().hex[:8]}@example.com"
        for i in range(5):
            requests.post(f"{API}/auth/login", json={"email": email, "password": "x"}, headers={"X-Forwarded-For": f"10.0.0.{i}"}, timeout=30)
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "x"}, headers={"X-Forwarded-For": "10.9.9.9"}, timeout=30)
        assert r.status_code == 429


# --- Admin protection ---
class TestAdminProtection:
    EPS = ["/admin/stats", "/admin/businesses", "/admin/demo-requests"]

    @pytest.mark.parametrize("ep", EPS)
    def test_anon_401(self, ep):
        assert requests.get(f"{API}{ep}", timeout=30).status_code == 401

    @pytest.mark.parametrize("ep", EPS)
    def test_owner_403(self, ep, owner_h):
        assert requests.get(f"{API}{ep}", headers=owner_h, timeout=30).status_code == 403

    @pytest.mark.parametrize("ep", EPS)
    def test_admin_200(self, ep, admin_h):
        assert requests.get(f"{API}{ep}", headers=admin_h, timeout=30).status_code == 200

    def test_forged_jwt_rejected(self):
        import jwt
        tok = jwt.encode({"user_id": "x"}, "secret", algorithm="HS256")
        assert requests.get(f"{API}/admin/stats", headers={"Authorization": f"Bearer {tok}"}, timeout=30).status_code == 401


# --- Jessica: state intact (no merge executed) ---
class TestJessicaIntact:
    def test_three_active_and_consent(self, owner_h):
        r = requests.get(f"{API}/leads", headers=owner_h, timeout=30)
        assert r.status_code == 200
        leads = r.json() if isinstance(r.json(), list) else r.json().get("leads", [])
        by_id = {l["lead_id"]: l for l in leads}
        for lid in ("lead_3f803b6e8f47", "lead_b404523b315e", "lead_a4c6e4cdc976"):
            assert lid in by_id, lid
            assert not by_id[lid].get("archived") and not by_id[lid].get("merged_into"), by_id[lid]
        p = by_id["lead_3f803b6e8f47"]
        print("PRIMARY consent:", p.get("consent"))
