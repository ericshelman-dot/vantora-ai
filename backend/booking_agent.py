"""AI booking workflow: extract intent with an LLM, then verify and execute against the scheduling engine."""
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import scheduling as sch

PLANNER_MODEL = ("gemini", "gemini-3-flash-preview")
CLAIM_RE = re.compile(r"\b(is|are|has been|have been|you're|you are|i've|i have|all)\s+(now\s+)?(booked|confirmed|scheduled|reserved)\b", re.I)


async def plan(api_key, biz, history, message):
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    cfg = sch.config(biz)
    now = datetime.now(ZoneInfo(cfg["timezone"]))
    days = ", ".join((now + timedelta(days=i)).strftime("%a %Y-%m-%d") for i in range(14))
    catalog = "; ".join(f"{s['name']} ({s['duration_min']} min)" for s in biz.get("service_catalog") or []) or biz.get("services", "")
    sys = (
        "You extract appointment requests for a booking system. Return ONLY a JSON object, no prose.\n"
        f"Now: {now.strftime('%A %Y-%m-%d %H:%M')} ({cfg['timezone']}). Next 14 days: {days}.\n"
        f"Services: {catalog}.\n"
        'Schema: {"intent": "book"|"availability"|"none", "service": string|null, "date": "YYYY-MM-DD"|null, '
        '"time": "HH:MM" (24h)|null, "name": string|null, "email": string|null, "phone": string|null}.\n'
        "intent=book when the customer wants to book/reserve/schedule or accepts an offered time. "
        "intent=availability when they ask what times are open. Otherwise none.\n"
        "Use the exact service name from the list when possible. Collect name/email/phone from anywhere in the conversation. "
        "If the customer accepts a time the assistant offered, use it. Never invent values; use null when unknown.")
    convo = "\n".join(f"{h['role']}: {h['content']}" for h in history[-12:]) + f"\nuser: {message}"
    try:
        chat = LlmChat(api_key=api_key, session_id=f"plan_{uuid.uuid4().hex[:10]}", system_message=sys).with_model(*PLANNER_MODEL)
        raw = await chat.send_message(UserMessage(text=convo))
        m = re.search(r"\{.*\}", raw, re.S)
        return json.loads(m.group(0)) if m else {"intent": "none"}
    except Exception as e:
        logging.exception("booking planner failed: %s", e)
        return {"intent": "error"}


def _fmt_alts(biz, alts):
    tz = ZoneInfo(sch.config(biz)["timezone"])
    return ", ".join(datetime.strptime(f"{a['date']} {a['time']}", "%Y-%m-%d %H:%M").replace(tzinfo=tz).strftime("%a %b %-d %-I:%M %p") for a in alts) or "none in the next week"


async def _upsert_contact(db, new_id, biz, session_id, name, email, phone, booking, now_iso):
    import leads_engine
    bid = biz["business_id"]
    lead = await leads_engine.upsert_lead(db, new_id, biz, name=name, email=email, phone=phone, session_id=session_id,
                                          interests=[booking["service"]], booking_id=booking["booking_id"])
    if not lead:
        return
    channel = "email" if email else "sms"
    fu = {"id": new_id("fu"), "channel": channel, "status": "simulated-sent", "simulated": True, "delivered": False,
          "kind": "booking_confirmation", "sent_at": now_iso,
          "message": f"[SIMULATED {channel.upper()} — not delivered] Hi {name}, your {booking['service']} at {biz['name']} is confirmed for "
                     f"{sch.describe(biz, sch.parse_iso(booking['start_utc']))}. Reference {booking['booking_id']}."}
    await db.leads.update_one({"lead_id": lead["lead_id"], "business_id": bid}, {"$push": {"follow_ups": fu}})


async def execute(db, new_id, biz, p, session_id):
    """Returns dict(kind, facts, footer, booking). facts is authoritative context for the reply model."""
    intent = (p or {}).get("intent")
    if intent == "error":
        return {"kind": "error", "facts": "The booking system could not process this request. Do NOT confirm any appointment; say no appointment was created.",
                "footer": "\n\nNo appointment was created. Please try again in a moment."}
    if intent not in ("book", "availability"):
        return None
    cfg = sch.config(biz)
    svc_in = p.get("service")
    svc = sch.match_service(biz, svc_in)
    catalog = biz.get("service_catalog") or []
    if svc_in and catalog and not svc:
        names = ", ".join(s["name"] for s in catalog)
        return {"kind": "unknown_service", "facts": f"Requested service '{svc_in}' is not offered. Offered services: {names}. No appointment was created.", "footer": ""}
    service = svc["name"] if svc else svc_in
    duration = sch.duration_for(biz, service) if service else cfg["default_duration"]
    date, time_ = p.get("date"), p.get("time")
    start = None
    if date and time_:
        try:
            start = sch.local_to_utc(date, time_, cfg["timezone"])
        except ValueError:
            return {"kind": "invalid", "facts": "The requested date/time could not be understood. Ask the customer to restate it. No appointment was created.", "footer": ""}

    if intent == "availability" or not start:
        if not date:
            return {"kind": "need_date", "facts": f"Ask which date they prefer. Hours: {biz.get('hours', '')}. Nothing is booked yet.", "footer": ""}
        slots = await sch.free_slots(db, biz, date, duration, limit=8)
        alts = [] if slots else await sch.alternatives(db, biz, date, duration)
        facts = (f"VERIFIED AVAILABILITY for {service or 'a ' + str(duration) + '-minute service'} on {date}: {', '.join(slots)} (local time, {cfg['timezone']})."
                 if slots else f"No openings on {date}. Nearest available: {_fmt_alts(biz, alts)}.")
        return {"kind": "availability", "facts": facts + " Nothing is booked yet; to book, the customer must choose a time and give name plus email or phone.", "footer": ""}

    now = datetime.now(timezone.utc)
    if start < now:
        return {"kind": "past", "facts": "The requested time is in the past. Ask for a future time. No appointment was created.", "footer": ""}
    end = start + timedelta(minutes=duration)
    if not sch.within_hours(cfg, start, end):
        alts = await sch.alternatives(db, biz, date, duration, around_utc=start)
        return {"kind": "outside_hours", "facts": f"{date} {time_} is outside business hours for a {duration}-minute {service or 'service'}. Available alternatives: {_fmt_alts(biz, alts)}. No appointment was created.",
                "footer": "\n\nNo appointment was created for that time."}
    # A retry must find its saved reservation before its own slot is counted as full.
    existing = await db.bookings.find_one({"business_id": biz["business_id"], "chat_session_id": session_id, "start_utc": sch.iso(start),
                                           "service": service, **sch.ACTIVE}, {"_id": 0})
    if not existing and not await sch.is_free(db, biz, start, end):
        alts = await sch.alternatives(db, biz, date, duration, around_utc=start)
        return {"kind": "unavailable", "facts": f"{sch.describe(biz, start)} is fully booked. Available alternatives: {_fmt_alts(biz, alts)}. No appointment was created.",
                "footer": "\n\nNo appointment was created for that time."}
    missing = [k for k, v in (("service", service), ("name", p.get("name"))) if not v]
    import leads_engine
    if not (leads_engine.norm_email(p.get("email")) or leads_engine.norm_phone(p.get("phone"))):
        missing.append("email or phone number")
    if missing:
        return {"kind": "missing", "facts": f"{sch.describe(biz, start)} is currently AVAILABLE but NOT booked. To book, still need: {', '.join(missing)}. Ask for them.", "footer": ""}

    if existing:
        booking = existing
    else:
        name = p["name"].strip().title()
        doc = sch.booking_doc(new_id, biz, name, service, start, duration, status="confirmed", source="ai_chat",
                              notes="Booked by AI chat assistant", chat_session_id=session_id,
                              customer_email=p.get("email") or "", customer_phone=p.get("phone") or "")
        try:
            booking = await sch.reserve(db, biz, doc)
        except sch.SchedulingError:
            alts = await sch.alternatives(db, biz, date, duration, around_utc=start)
            return {"kind": "unavailable", "facts": f"That time was just taken. Alternatives: {_fmt_alts(biz, alts)}. No appointment was created.",
                    "footer": "\n\nNo appointment was created for that time."}
        except Exception as e:
            logging.exception("booking save failed: %s", e)
            return {"kind": "error", "facts": "Saving the booking FAILED. Do NOT confirm. Apologize and say no appointment was created.",
                    "footer": "\n\nNo appointment was created. Please try again or contact us directly."}
        try:
            await _upsert_contact(db, new_id, biz, session_id, name, p.get("email"), p.get("phone"), booking, sch.iso(now))
        except Exception as e:
            logging.exception("contact upsert failed: %s", e)
    when = sch.describe(biz, sch.parse_iso(booking["start_utc"]))
    return {"kind": "confirmed", "booking": booking,
            "facts": f"BOOKING SAVED AND CONFIRMED: {booking['service']} for {booking['customer_name']} on {when} ({cfg['timezone']}), reference {booking['booking_id']}. "
                     "You may confirm it. Say a confirmation has been logged but do not claim an email or SMS was actually sent.",
            "footer": f"\n\nBooking confirmed. Reference: {booking['booking_id']}\n{booking['service']} · {when}\n"
                      "Confirmation logged as SIMULATED. No email or SMS was sent."}


def guard_footer(result, reply):
    """Ensure no unverified confirmation claim goes out without a correction."""
    if (not result or result["kind"] != "confirmed") and CLAIM_RE.search(reply or ""):
        return "\n\nNote: no appointment has been booked yet. A booking is only confirmed once you receive a booking reference."
    return ""
