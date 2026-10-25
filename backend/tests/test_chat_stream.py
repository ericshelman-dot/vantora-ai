# Chat stream regression tests (owner / admin / public widget / unauth)
import os, uuid, pytest, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def owner():
    return login("demo@aurasalon.com", os.environ['DEMO_OWNER_PASSWORD'])


@pytest.fixture(scope="module")
def admin():
    return login("admin@localbiz.ai", os.environ['ADMIN_PASSWORD'])


def stream(payload, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return requests.post(f"{API}/chat/stream", json=payload, headers=h, timeout=120)


# Owner chat - real AI reply, plain text, not JSON
def test_owner_chat_and_multiturn(owner):
    sid = "TEST_" + uuid.uuid4().hex[:8]
    r = stream({"session_id": sid, "message": "What are your hours?"}, owner["token"])
    assert r.status_code == 200, r.text
    assert "text/plain" in r.headers.get("content-type", "")
    txt = r.text
    print("REPLY1:", txt[:300])
    assert len(txt) > 20 and not txt.strip().startswith("{")
    r2 = stream({"session_id": sid, "message": "Great, and what did I just ask you about?"}, owner["token"])
    assert r2.status_code == 200
    print("REPLY2:", r2.text[:300])
    assert len(r2.text) > 10
    assert "hour" in r2.text.lower(), "multi-turn context not retained"


# Admin with no business -> 403 friendly
def test_admin_chat_403(admin):
    r = stream({"session_id": "TEST_a", "message": "hi"}, admin["token"])
    assert r.status_code == 403
    assert "business" in r.json()["detail"].lower()


# No token, no business_id -> 401
def test_unauth_no_business():
    r = stream({"session_id": "TEST_u", "message": "hi"})
    assert r.status_code == 401
    assert "detail" in r.json()


# Invalid business_id -> 404
def test_invalid_business():
    r = stream({"session_id": "TEST_u", "message": "hi", "business_id": "biz_nope"})
    assert r.status_code == 404


# Public widget with demo business id
def test_public_widget(owner):
    bid = owner["user"]["business_id"]
    r = stream({"session_id": "TEST_w" + uuid.uuid4().hex[:6], "message": "Do you offer massages?", "business_id": bid})
    assert r.status_code == 200, r.text
    print("WIDGET:", r.text[:200])
    assert len(r.text) > 10


# Disabled chat blocks public widget; restore
def test_disabled_chat_blocks_widget(owner):
    h = {"Authorization": f"Bearer {owner['token']}"}
    bid = owner["user"]["business_id"]
    try:
        r = requests.put(f"{API}/business", json={"chat_enabled": False}, headers=h)
        assert r.status_code == 200 and r.json()["chat_enabled"] is False
        r = stream({"session_id": "TEST_d", "message": "hi", "business_id": bid})
        assert r.status_code == 403
    finally:
        r = requests.put(f"{API}/business", json={"chat_enabled": True}, headers=h)
        assert r.json()["chat_enabled"] is True


# Multi-turn memory: name recall (owner) and public widget
def test_owner_name_memory(owner):
    sid = "TEST_" + uuid.uuid4().hex[:8]
    r = stream({"session_id": sid, "message": "My name is Priya"}, owner["token"])
    assert r.status_code == 200
    r2 = stream({"session_id": sid, "message": "What is my name?"}, owner["token"])
    print("NAME REPLY:", r2.text[:300])
    assert "priya" in r2.text.lower()


def test_widget_name_memory(owner):
    bid = owner["user"]["business_id"]
    sid = "TEST_w" + uuid.uuid4().hex[:6]
    stream({"session_id": sid, "message": "Hi, I'm Rahul", "business_id": bid})
    r2 = stream({"session_id": sid, "message": "What is my name?", "business_id": bid})
    print("WIDGET NAME:", r2.text[:300])
    assert "rahul" in r2.text.lower()


# Sessions are isolated: a new session must not know the name
def test_session_isolation(owner):
    sid = "TEST_" + uuid.uuid4().hex[:8]
    stream({"session_id": sid, "message": "My name is Zorblax"}, owner["token"])
    r = stream({"session_id": "TEST_" + uuid.uuid4().hex[:8], "message": "What is my name?"}, owner["token"])
    print("ISOLATION:", r.text[:300])
    assert "zorblax" not in r.text.lower()
