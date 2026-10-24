"""Lead capture tests: creation without booking, dedup, booking association, consent rules, drafts, isolation."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import leads_engine as le  # noqa: E402
import booking_agent  # noqa: E402
import scheduling as sch  # noqa: E402

TZ = "America/New_York"


def new_id(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def biz(bid=None):
    return {"business_id": bid or new_id("biz"), "name": "Aura Test Spa",
            "scheduling": {"timezone": TZ, "capacity": 3, "slot_minutes": 30, "default_duration": 60,
                           "weekly": {d: ["09:00", "18:00"] for d in sch.DAYS}},
            "service_catalog": [{"name": "Signature Aura Facial", "duration_min": 60}]}


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    d = client[f"lead_test_{uuid.uuid4().hex[:6]}"]
    yield d
    run(client.drop_database(d.name))


def test_lead_created_without_booking_and_linked_to_customer(db):
    b = biz()
    lead = run(le.upsert_lead(db, new_id, b, name="nora quinn", email="Nora.Quinn@Example.com", session_id="s1", interests=["Signature Aura Facial"]))
    assert lead["name"] == "Nora Quinn" and lead["status"] == "new" and lead["booking_ids"] == []
    assert lead["email_norm"] == "nora.quinn@example.com" and lead["chat_session_ids"] == ["s1"]
    assert lead["consent"] == {"email": None, "sms": None} and lead["inquiry_date"]
    cust = run(db.customers.find_one({"customer_id": lead["customer_id"]}))
    assert cust["business_id"] == b["business_id"] and cust["lead_id"] == lead["lead_id"]


def test_requires_name_and_valid_contact(db):
    b = biz()
    assert run(le.upsert_lead(db, new_id, b, name=None, email="a@example.com", session_id="s")) is None
    assert run(le.upsert_lead(db, new_id, b, name="Ann", email="not-an-email", session_id="s")) is None
    assert run(db.leads.count_documents({})) == 0


def test_dedup_by_email_phone_and_session(db):
    b = biz()
    a = run(le.upsert_lead(db, new_id, b, name="Leo Park", email="leo@example.com", session_id="s1"))
    b1 = run(le.upsert_lead(db, new_id, b, name="Leo Park", email="LEO@example.com ", session_id="s2"))
    c = run(le.upsert_lead(db, new_id, b, name="Leo", phone="+1 (555) 010-7777", session_id="s2"))
    d = run(le.upsert_lead(db, new_id, b, name="Leo Park", phone="555.010.7777", session_id="s3"))
    assert a["lead_id"] == b1["lead_id"] == c["lead_id"] == d["lead_id"]
    assert run(db.leads.count_documents({"business_id": b["business_id"]})) == 1
    assert set(d["chat_session_ids"]) == {"s1", "s2", "s3"} and d["phone_norm"] == "5550107777"
    assert run(db.customers.count_documents({"business_id": b["business_id"]})) == 1


def test_concurrent_capture_does_not_duplicate(db):
    b = biz()
    run(asyncio.gather(*[le.upsert_lead(db, new_id, b, name="Ivy Stone", email="ivy@example.com", session_id=f"s{i}") for i in range(5)]))
    assert run(db.leads.count_documents({"business_id": b["business_id"]})) == 1


def test_booking_links_lead_customer_and_appointment(db):
    b = biz()
    run(le.upsert_lead(db, new_id, b, name="Mila Grant", email="mila@example.com", session_id="chat1"))
    date = (datetime.now(ZoneInfo(TZ)) + timedelta(days=3)).strftime("%Y-%m-%d")
    r = run(booking_agent.execute(db, new_id, b, {"intent": "book", "service": "Signature Aura Facial", "date": date, "time": "11:00",
                                                  "name": "Mila Grant", "email": "mila@example.com"}, "chat1"))
    assert r["kind"] == "confirmed"
    lead = run(db.leads.find_one({"business_id": b["business_id"]}))
    bk = run(db.bookings.find_one({"booking_id": r["booking"]["booking_id"]}))
    assert run(db.leads.count_documents({"business_id": b["business_id"]})) == 1
    assert lead["status"] == "booked" and bk["booking_id"] in lead["booking_ids"]
    assert bk["lead_id"] == lead["lead_id"] and bk["customer_id"] == lead["customer_id"]
    assert any(f["kind"] == "booking_confirmation" and f["simulated"] and not f["delivered"] for f in lead["follow_ups"])


def test_business_isolation(db):
    a, other = biz(), biz()
    la = run(le.upsert_lead(db, new_id, a, name="Zoe Hart", email="zoe@example.com", session_id="s"))
    lb = run(le.upsert_lead(db, new_id, other, name="Zoe Hart", email="zoe@example.com", session_id="s"))
    assert la["lead_id"] != lb["lead_id"] and la["customer_id"] != lb["customer_id"]
    assert run(db.leads.count_documents({"business_id": a["business_id"]})) == 1


def test_consent_reply_parsing():
    assert le.parse_consent_reply("both please") == {"email": True, "sms": True}
    assert le.parse_consent_reply("Email only please") == {"email": True, "sms": False}
    assert le.parse_consent_reply("text") == {"email": False, "sms": True}
    assert le.parse_consent_reply("no thanks") == {"email": False, "sms": False}
    for not_consent in ["What time do you open?", "yes", "Do you offer both facials and massages on the same day?",
                        "Don't email me, text is fine", "Can I text you to reschedule?", "What's your email address?",
                        "I got your message, thanks", "I'd like the Couples Massage for both of us"]:
        assert le.parse_consent_reply(not_consent) is None, not_consent


def test_consent_window_is_one_shot(db):
    b = biz()
    run(le.upsert_lead(db, new_id, b, name="Tess Ford", email="tess@example.com", session_id="s"))
    run(le.mark_consent_asked(db, b, "s"))
    assert run(le.handle_chat_consent(db, b, "s", "Is parking free?", None)) is None
    assert run(le.handle_chat_consent(db, b, "s", "both", None)) is None  # too late: window closed
    lead = run(db.leads.find_one({"business_id": b["business_id"]}))
    assert lead["consent"] == {"email": None, "sms": None}


def test_checkbox_never_overrides_opt_out(db):
    b = biz()
    run(le.handle_chat_consent(db, b, "s", "hi", {"email": True}))
    run(le.upsert_lead(db, new_id, b, name="Ola Berg", email="ola@example.com", session_id="s"))
    run(le.handle_chat_consent(db, b, "s", "please unsubscribe me", {"email": True}))
    run(le.handle_chat_consent(db, b, "s", "thanks", {"email": True}))
    lead = run(db.leads.find_one({"business_id": b["business_id"]}))
    assert lead["consent"]["email"]["granted"] is False


def test_inquiry_reply_consent_separate_from_marketing(db):
    b = biz()
    lead = run(le.upsert_lead(db, new_id, b, name="Jessica Miller", email="jessica.t@example.com", session_id="s"))
    assert run(le.next_prompt(db, b, "s", lead)) == "inquiry"
    q = run(le.mark_prompted(db, b, "s", "inquiry", lead))
    assert "email you a personal reply" in q
    assert run(le.next_prompt(db, b, "s", lead)) is None  # wait for the answer
    assert run(le.handle_chat_consent(db, b, "s", "Yes please", None)) == "inquiry_granted"
    lead = run(db.leads.find_one({"lead_id": lead["lead_id"]}))
    inq = lead["consent"]["inquiry_reply"]
    assert inq["granted"] and inq["channel_to_use"] == "email" and inq["source"] == "ai chat question" and inq["at"]
    assert lead["consent"]["email"] is None and lead["consent"]["sms"] is None
    assert run(le.next_prompt(db, b, "s", lead)) == "marketing"
    run(le.mark_prompted(db, b, "s", "marketing", lead))
    assert run(le.handle_chat_consent(db, b, "s", "no thanks", None)) == "answered"
    lead = run(db.leads.find_one({"lead_id": lead["lead_id"]}))
    assert lead["consent"]["email"]["granted"] is False and lead["consent"]["sms"]["granted"] is False
    assert lead["consent"]["inquiry_reply"]["granted"] is True


def test_inquiry_draft_approval_uses_inquiry_consent_not_marketing(db):
    b = biz()
    lead = run(le.upsert_lead(db, new_id, b, name="Jo Park", email="jo@example.com", session_id="s"))
    d = {"draft_id": "drf_i", "channel": "email", "kind": "inquiry_reply", "message": "Hi Jo", "status": "pending", "created_at": le.now()}
    run(db.leads.update_one({"lead_id": lead["lead_id"]}, {"$push": {"drafts": d}}))
    with pytest.raises(le.LeadError):
        run(le.approve_draft(db, new_id, b["business_id"], lead["lead_id"], "drf_i", "o"))
    run(le.record_consent(db, b["business_id"], lead["lead_id"], "inquiry_reply", True, "q", "test", channel_to_use="email"))
    fu = run(le.approve_draft(db, new_id, b["business_id"], lead["lead_id"], "drf_i", "o"))
    assert fu["kind"] == "inquiry_reply" and fu["delivered"] is False and fu["simulated"]
    m = {"draft_id": "drf_m", "channel": "email", "kind": "marketing", "message": "Offer", "status": "pending", "created_at": le.now()}
    run(db.leads.update_one({"lead_id": lead["lead_id"]}, {"$push": {"drafts": m}}))
    with pytest.raises(le.LeadError):  # inquiry permission never counts as marketing consent
        run(le.approve_draft(db, new_id, b["business_id"], lead["lead_id"], "drf_m", "o"))


def test_yes_no_parsing_strict():
    assert le.parse_yes_no("Yes please") is True and le.parse_yes_no("no thanks") is False
    for x in ["Do you have parking?", "yes but only on weekends", "maybe"]:
        assert le.parse_yes_no(x) is None


def test_name_variants():
    assert le.extract_contact("Jessica Miller here, jessica@example.com")["name"] == "Jessica Miller"
    assert le.extract_contact("Name: Jessica Miller")["name"] == "Jessica Miller"


def test_checkbox_not_restaged_every_message(db):
    b = biz()
    run(le.upsert_lead(db, new_id, b, name="Uma Sol", email="uma@example.com", session_id="s"))
    for _ in range(3):
        run(le.handle_chat_consent(db, b, "s", "hello", {"email": True}))
    lead = run(db.leads.find_one({"business_id": b["business_id"]}))
    assert len(lead["consent_log"]) == 1


def test_name_regex_case_insensitive_prefix():
    assert le.extract_contact("Hi, I'm Mia Park")["name"] == "Mia Park"


def test_unanswered_and_unchecked_never_consent(db):
    b = biz()
    run(le.upsert_lead(db, new_id, b, name="Ana Ruiz", email="ana@example.com", session_id="s"))
    run(le.handle_chat_consent(db, b, "s", "What are your hours?", {"email": False, "sms": None}))
    run(le.mark_consent_asked(db, b, "s"))
    run(le.handle_chat_consent(db, b, "s", "Do you have parking?", {}))
    lead = run(db.leads.find_one({"business_id": b["business_id"]}))
    assert lead["consent"] == {"email": None, "sms": None}


def test_checkbox_and_chat_answer_recorded_with_text_source_timestamp(db):
    b = biz()
    run(le.handle_chat_consent(db, b, "s", "hi", {"sms": True}))  # before lead exists: staged
    lead = run(le.upsert_lead(db, new_id, b, name="Eve Lin", phone="+1 555 010 8888", session_id="s"))
    assert lead["consent"]["sms"]["granted"] is True and lead["consent"]["sms"]["source"] == "chat widget checkbox"
    run(le.mark_consent_asked(db, b, "s"))
    assert run(le.handle_chat_consent(db, b, "s", "email only", None)) == "answered"
    lead = run(db.leads.find_one({"lead_id": lead["lead_id"]}))
    e = lead["consent"]["email"]
    assert e["granted"] is True and "Would you like to receive" in e["text"] and e["source"] == "ai chat question" and e["at"]
    assert lead["consent"]["sms"]["granted"] is False  # chose email only
    assert len(lead["consent_log"]) == 3


def test_opt_out_revokes(db):
    b = biz()
    run(le.handle_chat_consent(db, b, "s", "hi", {"email": True}))
    run(le.upsert_lead(db, new_id, b, name="Kai Moss", email="kai@example.com", session_id="s"))
    assert run(le.handle_chat_consent(db, b, "s", "Please unsubscribe me", None)) == "opted_out"
    lead = run(db.leads.find_one({"business_id": b["business_id"]}))
    assert lead["consent"]["email"]["granted"] is False and lead["consent"]["sms"]["granted"] is False


def test_draft_approval_requires_consent_and_records_simulated_send(db):
    b = biz()
    lead = run(le.upsert_lead(db, new_id, b, name="Rae Cole", email="rae@example.com", session_id="s"))
    d = {"draft_id": "drf_1", "channel": "email", "message": "Hi Rae", "status": "pending", "created_at": le.now()}
    run(db.leads.update_one({"lead_id": lead["lead_id"]}, {"$push": {"drafts": d}}))
    with pytest.raises(le.LeadError) as ex:
        run(le.approve_draft(db, new_id, b["business_id"], lead["lead_id"], "drf_1", "owner@example.com"))
    assert ex.value.code == 403
    run(le.record_consent(db, b["business_id"], lead["lead_id"], "email", True, "test consent", "test"))
    fu = run(le.approve_draft(db, new_id, b["business_id"], lead["lead_id"], "drf_1", "owner@example.com"))
    assert fu["status"] == "simulated-sent" and fu["simulated"] and fu["delivered"] is False
    saved = run(db.leads.find_one({"lead_id": lead["lead_id"]}))
    assert saved["drafts"][0]["status"] == "approved" and saved["status"] == "contacted"
    with pytest.raises(le.LeadError):
        run(le.approve_draft(db, new_id, "other_biz", lead["lead_id"], "drf_1", "x"))
