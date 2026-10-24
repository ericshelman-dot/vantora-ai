# Offline unit tests: strict consent parser + name extraction (iteration 8)
import pytest
from leads_engine import parse_consent_reply, extract_contact

BOTH, EMAIL, SMS, NONE = {"email": True, "sms": True}, {"email": True, "sms": False}, {"email": False, "sms": True}, {"email": False, "sms": False}


@pytest.mark.parametrize("msg,exp", [
    ("email", EMAIL), ("Email.", EMAIL), ("text", SMS), ("both", BOTH), ("Both!", BOTH), ("no thanks", NONE),
    ("neither", NONE), ("yes, email please", EMAIL), ("SMS only", SMS), ("no", NONE),
])
def test_direct_answers(msg, exp):
    assert parse_consent_reply(msg) == exp


@pytest.mark.parametrize("msg", [
    "Don't email me, text is fine", "Can I text you to reschedule?", "What's your email address?",
    "Do you offer both facials and massages on the same day?", "I got your message, thanks",
    "I'd like the Couples Massage for both of us", "don't text", "not email", "no email", "email me never",
    "", None,
])
def test_non_answers(msg):
    assert parse_consent_reply(msg) is None


def test_name_mia_park():
    c = extract_contact("Hi, I'm Mia Park, mia.p@example.com")
    assert c["name"] == "Mia Park" and c["email"] == "mia.p@example.com"


def test_name_lowercase_prefix():
    assert extract_contact("hi i am Leo Brandt")["name"] == "Leo Brandt"


def test_name_not_from_sentence():
    assert extract_contact("I'm looking for a facial")["name"] is None
