"""Execute existing Vantora engines against fresh in-memory synthetic records only.

No server import, .env loading, provider SDK, real MongoDB or connection option.
Intent objects and owner-written draft are scripted, NOT AI-generated.
"""
import asyncio
import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from mongomock_motor import AsyncMongoMockClient
import booking_agent
import leads_engine as le
import scheduling as sch


def new_id(prefix):
    return f"pilot_{prefix}_{uuid.uuid4().hex[:12]}"


def business():
    return json.loads(Path(__file__).with_name("business.json").read_text())


def next_weekday():
    day = datetime.now(ZoneInfo("America/New_York")).date() + timedelta(days=7)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day.isoformat()


def make_db():
    return AsyncMongoMockClient()["vantora_salon_offline_only"]


def booking_plan(**changes):
    return {"intent": "book", "service": "Haircut and Finish", "date": next_weekday(),
            "time": "10:00", "name": "Alex Sample", "email": "alex.salon@example.com", **changes}


async def journey(db, biz):
    session = "synthetic_salon_journey"
    inquiry = "Do you offer a haircut and finish? What does it cost?"
    # Preserve a transcript for owner review without calling a language model.
    await db.chat_messages.insert_one({"business_id": biz["business_id"], "session_id": session,
                                       "role": "user", "content": inquiry, "created_at": le.now()})
    contact = le.extract_contact("My name is Alex Sample, alex.salon@example.com")
    lead = await le.upsert_lead(db, new_id, biz, **contact, session_id=session, interests=["Haircut and Finish"])
    inquiry_prompt = await le.mark_prompted(db, biz, session, "inquiry", lead)
    await le.handle_chat_consent(db, biz, session, "Yes please", None)
    marketing_prompt = await le.mark_prompted(db, biz, session, "marketing", lead)
    await le.handle_chat_consent(db, biz, session, "No thanks", None)
    available = await booking_agent.execute(db, new_id, biz, booking_plan(intent="availability"), session)
    booked = await booking_agent.execute(db, new_id, biz, booking_plan(), session)
    if booked["kind"] != "confirmed":
        raise AssertionError(booked)
    # Owner-written reply tests approval and scope without a paid draft-generation call.
    draft = {"draft_id": "pilot_owner_reply", "channel": "email", "kind": "inquiry_reply", "status": "pending",
             "message": "Hi Alex, our fictional demo includes a 45-minute Haircut and Finish. Pricing needs owner review. No real appointment or message has been made.", "created_at": le.now()}
    await db.leads.update_one({"business_id": biz["business_id"], "lead_id": lead["lead_id"]}, {"$push": {"drafts": draft}})
    await le.approve_draft(db, new_id, biz["business_id"], lead["lead_id"], draft["draft_id"], "synthetic-owner@example.com")
    saved = await db.leads.find_one({"business_id": biz["business_id"], "lead_id": lead["lead_id"]}, {"_id": 0})
    appointment = await db.bookings.find_one({"business_id": biz["business_id"], "booking_id": booked["booking"]["booking_id"]}, {"_id": 0})
    assert saved["consent"]["inquiry_reply"]["granted"] is True
    assert saved["consent"]["email"]["granted"] is False
    assert saved["consent"]["sms"]["granted"] is False
    assert appointment["lead_id"] == saved["lead_id"]
    assert all(f["simulated"] and not f["delivered"] for f in saved["follow_ups"])
    return {"mode": "OFFLINE SYNTHETIC — not a live salon", "verification": "Real engine functions; mocked database; scripted intents; no LLM or HTTP/UI test",
            "inquiry": inquiry, "inquiry_permission_question": inquiry_prompt, "marketing_permission_question": marketing_prompt,
            "availability": available, "booking": appointment, "owner_review": saved,
            "live_delivery": False, "external_calendar_connected": False}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(journey(make_db(), business())), indent=2))
