"""Lead capture & CRM engine: dedup, customer linking, consent records, summaries, follow-up drafts."""
import asyncio
import json
import logging
import re
import uuid

from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone

STATUSES = ["new", "contacted", "qualified", "booked", "closed"]
LEGACY_STATUS = {"won": "closed", "lost": "closed"}
CHANNELS = ("email", "sms")
INQUIRY = "inquiry_reply"
EMAIL_OK = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
EMAIL_FIND = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}")
PHONE_FIND = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_NM = r"([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+)?)"
NAME_FINDS = [re.compile(r"(?i:my name is|my name's|i am|i'm|this is|it's|name\s*[:\-])\s*" + _NM),
              re.compile(r"(?:^|[.!?,]\s*)" + _NM + r"\s+(?i:here)\b")]
OPT_OUT = re.compile(r"\b(unsubscribe|opt[ -]?out|stop (?:texting|messaging|emailing|sending)|no more (?:emails|texts|messages))\b", re.I)
CHECKBOX_TEXT = {"email": "Yes, send me occasional offers and updates by email (optional).",
                 "sms": "Yes, send me occasional offers and updates by text message (optional)."}
SUMMARY_MODEL = ("gemini", "gemini-3-flash-preview")
_locks: dict = {}


class LeadError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


def now():
    return datetime.now(timezone.utc).isoformat()


def consent_question(biz_name):
    return (f"Would you like to receive occasional offers and updates from {biz_name} by email, by text message, both, or neither? "
            "This is optional. Reply \"email\", \"text\", \"both\" or \"no\".")


def inquiry_question(channel):
    how = "email you" if channel == "email" else "text you"
    return (f"May we {how} a personal reply about this inquiry? This is only about your question, not marketing. "
            "Reply \"yes\" or \"no\".")


def parse_yes_no(text):
    t = re.sub(r"[^a-z\s']", " ", (text or "").lower())
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+(please|thanks|thank you)$", "", t)
    if t in {"yes", "yes please", "yeah", "yep", "sure", "ok", "okay", "please do", "that's fine", "that is fine", "yes you may", "yes that's fine", "of course"}:
        return True
    if t in {"no", "no thanks", "no thank you", "nope", "not needed", "no need", "please don't", "don't"}:
        return False
    return None


def norm_email(e):
    e = (e or "").strip().lower()
    return e if EMAIL_OK.match(e) else ""


def norm_phone(p):
    d = re.sub(r"\D", "", p or "")
    return d[-10:] if 7 <= len(d) <= 15 else ""


def extract_contact(text):
    e, p = EMAIL_FIND.search(text or ""), PHONE_FIND.search(text or "")
    n = next((m for m in (rx.search(text or "") for rx in NAME_FINDS) if m), None)
    return {"email": e.group(0) if e else None, "phone": p.group(0).strip() if p else None, "name": n.group(1) if n else None}


def parse_consent_reply(text):
    """Strict: only a short, direct answer to the consent question counts. Anything else -> None (no consent)."""
    t = re.sub(r"[^a-z\s-]", " ", (text or "").lower())
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^(yes|yeah|yep|sure|ok|okay)\s+", "", t)
    t = re.sub(r"\s+(please|thanks|thank you|is fine|works|is good)$", "", t)
    t = re.sub(r"^(by|via|just|only)\s+", "", t)
    t = re.sub(r"\s+only$", "", t)
    if t in {"both", "both of them", "email and text", "text and email", "email and sms", "sms and email", "to both", "yes to both"}:
        return {"email": True, "sms": True}
    if t in {"email", "e-mail", "emails"}:
        return {"email": True, "sms": False}
    if t in {"text", "texts", "sms", "text message", "text messages"}:
        return {"email": False, "sms": True}
    if t in {"no", "neither", "none", "no thanks", "no thank you", "nope", "not interested", "no neither"}:
        return {"email": False, "sms": False}
    return None


def _lock(bid):
    return _locks.setdefault(bid, asyncio.Lock())


async def _find(db, bid, en, pn, session_id):
    qs = ([{"email_norm": en}] if en else []) + ([{"phone_norm": pn}] if pn else []) + ([{"chat_session_ids": session_id}] if session_id else [])
    qs += ([{"alternate_email_norms": en}] if en else []) + ([{"alternate_phone_norms": pn}] if pn else [])
    for q in qs:
        lead = await db.leads.find_one({"business_id": bid, "archived": {"$ne": True}, **q}, {"_id": 0})
        if lead:
            return lead
    return None


def contact_keys(bid, en, pn):
    """DB-level uniqueness keys for active leads (partial unique indexes on string values)."""
    return {"email_key": f"{bid}|{en}" if en else None, "phone_key": f"{bid}|{pn}" if pn else None}


async def _link_customer(db, new_id, bid, lead):
    en, pn = lead.get("email_norm"), lead.get("phone_norm")
    ors = ([{"email_norm": en}, {"email": en}] if en else []) + ([{"phone_norm": pn}] if pn else [])
    if lead.get("customer_id"):
        ors.append({"customer_id": lead["customer_id"]})
    cust = await db.customers.find_one({"business_id": bid, "$or": ors}, {"_id": 0}) if ors else None
    fields = {"name": lead["name"], "lead_id": lead["lead_id"], "email_norm": en, "phone_norm": pn,
              **({"email": lead["email"]} if lead.get("email") else {}), **({"phone": lead["phone"]} if lead.get("phone") else {})}
    if cust:
        await db.customers.update_one({"customer_id": cust["customer_id"], "business_id": bid}, {"$set": fields})
        cid = cust["customer_id"]
    else:
        cid = new_id("cust")
        await db.customers.insert_one({"customer_id": cid, "business_id": bid, "notes": "Created from AI-captured lead",
                                       "created_by": "ai_lead", "created_at": now(), "email": "", "phone": "", **fields})
    if lead.get("customer_id") != cid:
        await db.leads.update_one({"lead_id": lead["lead_id"], "business_id": bid}, {"$set": {"customer_id": cid}})
    return cid


async def upsert_lead(db, new_id, biz, *, name=None, email=None, phone=None, session_id=None, interests=None,
                      booking_id=None, source="website chat"):
    """Create or update the business's lead for this contact. Requires a name plus a valid email or phone for new leads."""
    bid = biz["business_id"]
    en, pn = norm_email(email), norm_phone(phone)
    name = (name or "").strip()
    async with _lock(bid):
        for attempt in range(3):
            lead = await _find(db, bid, en, pn, session_id)
            if not lead and not (name and (en or pn)):
                return None
            ts = now()
            if lead:
                sets = {"last_contact_at": ts}
                if name and (not lead.get("name") or lead["name"] == "Website visitor"):
                    sets["name"] = name.title()
                if en and not lead.get("email_norm"):
                    sets.update(email=email.strip(), email_norm=en, email_key=contact_keys(bid, en, None)["email_key"])
                if pn and not lead.get("phone_norm"):
                    sets.update(phone=phone.strip(), phone_norm=pn, phone_key=contact_keys(bid, None, pn)["phone_key"])
                if booking_id and lead.get("status") != "closed":
                    sets["status"] = "booked"
                add = {}
                if session_id:
                    add["chat_session_ids"] = session_id
                if interests:
                    add["service_interests"] = {"$each": list(interests)}
                if booking_id:
                    add["booking_ids"] = booking_id
                try:
                    await db.leads.update_one({"lead_id": lead["lead_id"], "business_id": bid}, {"$set": sets, **({"$addToSet": add} if add else {})})
                except DuplicateKeyError:
                    # contact already belongs to another active lead: attach the activity without claiming the contact
                    sets = {k: v for k, v in sets.items() if k not in ("email", "email_norm", "email_key", "phone", "phone_norm", "phone_key")}
                    await db.leads.update_one({"lead_id": lead["lead_id"], "business_id": bid}, {"$set": sets, **({"$addToSet": add} if add else {})})
                break
            lead = {"lead_id": new_id("lead"), "business_id": bid, "name": name.title(), "email": (email or "").strip() if en else "",
                    "phone": (phone or "").strip() if pn else "", "email_norm": en, "phone_norm": pn, **contact_keys(bid, en, pn),
                    "source": source, "status": "booked" if booking_id else "new", "notes": "", "summary": "",
                    "service_interests": list(interests or []), "chat_session_ids": [session_id] if session_id else [],
                    "booking_ids": [booking_id] if booking_id else [], "consent": {"email": None, "sms": None}, "consent_log": [],
                    "drafts": [], "follow_ups": [], "status_history": [{"status": "booked" if booking_id else "new", "at": ts, "by": source}],
                    "inquiry_date": ts, "last_contact_at": ts, "created_at": ts}
            try:
                await db.leads.insert_one(lead)
                break
            except DuplicateKeyError:
                continue  # another request created it first; loop re-finds and updates it
        lead = await db.leads.find_one({"lead_id": lead["lead_id"], "business_id": bid}, {"_id": 0})
        await _link_customer(db, new_id, bid, lead)
        if booking_id:
            await db.bookings.update_one({"booking_id": booking_id, "business_id": bid},
                                         {"$set": {"lead_id": lead["lead_id"], "customer_id": (await db.leads.find_one({"lead_id": lead["lead_id"]}, {"customer_id": 1}))["customer_id"]}})
        if session_id:
            await _apply_pending_consent(db, bid, lead["lead_id"], session_id)
        return await db.leads.find_one({"lead_id": lead["lead_id"], "business_id": bid}, {"_id": 0})


def backfill_fields(lead):
    """Missing CRM fields for legacy/seeded leads."""
    out = {}
    if "email_norm" not in lead:
        out["email_norm"] = norm_email(lead.get("email"))
    if "phone_norm" not in lead:
        out["phone_norm"] = norm_phone(lead.get("phone"))
    if lead.get("status") in LEGACY_STATUS or lead.get("status") not in STATUSES:
        out["status"] = LEGACY_STATUS.get(lead.get("status"), "new")
    defaults = {"consent": {"email": None, "sms": None}, "consent_log": [], "drafts": [], "service_interests": [],
                "booking_ids": [lead["booking_id"]] if lead.get("booking_id") else [], "summary": "",
                "chat_session_ids": [lead["chat_session_id"]] if lead.get("chat_session_id") else [],
                "inquiry_date": lead.get("created_at"), "last_contact_at": lead.get("created_at")}
    out.update({k: v for k, v in defaults.items() if k not in lead})
    return out


async def record_consent(db, bid, lead_id, channel, granted, text, source, **extra):
    entry = {"channel": channel, "granted": bool(granted), "text": text, "source": source, "at": now(), **extra}
    res = await db.leads.update_one({"lead_id": lead_id, "business_id": bid},
                                    {"$set": {f"consent.{channel}": entry}, "$push": {"consent_log": entry}})
    if not res.matched_count:
        raise LeadError("Lead not found", 404)
    return entry


async def session_state(db, bid, session_id):
    return await db.chat_sessions.find_one({"business_id": bid, "session_id": session_id}, {"_id": 0}) or {}


async def stage_consent(db, bid, session_id, channel, granted, text, source, **extra):
    """Store a consent decision on the session; applied to the lead when it exists."""
    entry = {"granted": bool(granted), "text": text, "source": source, "at": now(), **extra}
    await db.chat_sessions.update_one({"business_id": bid, "session_id": session_id},
                                      {"$set": {f"pending_consent.{channel}": entry}}, upsert=True)
    lead = await db.leads.find_one({"business_id": bid, "chat_session_ids": session_id, "archived": {"$ne": True}}, {"_id": 0, "lead_id": 1})
    if lead:
        await _apply_pending_consent(db, bid, lead["lead_id"], session_id)


async def _apply_pending_consent(db, bid, lead_id, session_id):
    st = await session_state(db, bid, session_id)
    for ch, e in (st.get("pending_consent") or {}).items():
        await record_consent(db, bid, lead_id, ch, e["granted"], e["text"], e["source"],
                             **({"channel_to_use": e["channel_to_use"]} if e.get("channel_to_use") else {}))
    if st.get("pending_consent"):
        await db.chat_sessions.update_one({"business_id": bid, "session_id": session_id}, {"$unset": {"pending_consent": ""}})


async def handle_chat_consent(db, biz, session_id, message, checkbox):
    """Process widget checkboxes (only checked = consent), replies to our consent question, and opt-outs."""
    bid = biz["business_id"]
    st = await session_state(db, bid, session_id)
    lead = await db.leads.find_one({"business_id": bid, "chat_session_ids": session_id, "archived": {"$ne": True}}, {"_id": 0, "consent": 1})
    for ch in CHANNELS:
        current = ((lead or {}).get("consent") or {}).get(ch) or (st.get("pending_consent") or {}).get(ch)
        if (checkbox or {}).get(ch) is True and not current:
            await stage_consent(db, bid, session_id, ch, True, CHECKBOX_TEXT[ch], "chat widget checkbox")
    if OPT_OUT.search(message or ""):
        for ch in CHANNELS:
            await stage_consent(db, bid, session_id, ch, False, f"Customer message: \"{message[:200]}\"", "chat opt-out")
        return "opted_out"
    if st.get("inquiry_prompted_at") and not st.get("inquiry_answered_at"):
        await db.chat_sessions.update_one({"business_id": bid, "session_id": session_id}, {"$set": {"inquiry_answered_at": now()}})
        yn = parse_yes_no(message)
        if yn is not None:
            await stage_consent(db, bid, session_id, INQUIRY, yn, f"{st.get('inquiry_question', '')} Answer: \"{message[:200]}\"",
                                "ai chat question", channel_to_use=st.get("inquiry_channel", "email"))
            return "inquiry_granted" if yn else "inquiry_declined"
        return None
    if st.get("consent_prompted_at") and not st.get("consent_answered_at"):
        # One-shot window: only the message immediately after the question can answer it.
        await db.chat_sessions.update_one({"business_id": bid, "session_id": session_id}, {"$set": {"consent_answered_at": now()}})
        parsed = parse_consent_reply(message)
        if parsed is not None:
            q = st.get("consent_question", consent_question(biz["name"]))
            for ch, v in parsed.items():
                await stage_consent(db, bid, session_id, ch, v, f"{q} Answer: \"{message[:200]}\"", "ai chat question")
            return "answered"
    return None


async def next_prompt(db, biz, session_id, lead):
    """One consent question per turn: inquiry-reply permission first, then optional marketing."""
    if not lead:
        return None
    st = await session_state(db, biz["business_id"], session_id)
    c = lead.get("consent") or {}
    if not st.get("inquiry_prompted_at"):
        return "inquiry"  # each conversation is a new inquiry; permission is asked per conversation
    if st.get("inquiry_prompted_at") and not st.get("inquiry_answered_at"):
        return None
    if not st.get("consent_prompted_at") and not all(c.get(ch) is not None for ch in CHANNELS):
        return "marketing"
    return None


async def mark_prompted(db, biz, session_id, kind, lead=None):
    if kind == "inquiry":
        ch = "email" if (lead or {}).get("email_norm") else "sms"
        q = inquiry_question(ch)
        sets = {"inquiry_prompted_at": now(), "inquiry_question": q, "inquiry_channel": ch}
    else:
        q = consent_question(biz["name"])
        sets = {"consent_prompted_at": now(), "consent_question": q}
    await db.chat_sessions.update_one({"business_id": biz["business_id"], "session_id": session_id}, {"$set": sets}, upsert=True)
    return q


async def should_ask_consent(db, biz, session_id, lead):
    if not lead:
        return False
    st = await session_state(db, biz["business_id"], session_id)
    c = lead.get("consent") or {}
    decided = all(c.get(ch) is not None for ch in CHANNELS)
    return not st.get("consent_prompted_at") and not decided


async def mark_consent_asked(db, biz, session_id):
    await db.chat_sessions.update_one({"business_id": biz["business_id"], "session_id": session_id},
                                      {"$set": {"consent_prompted_at": now(), "consent_question": consent_question(biz["name"])}}, upsert=True)


async def summarize(db, api_key, biz, lead_id):
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    bid = biz["business_id"]
    lead = await db.leads.find_one({"lead_id": lead_id, "business_id": bid}, {"_id": 0})
    if not lead:
        return None
    msgs = await db.chat_messages.find({"business_id": bid, "session_id": {"$in": lead.get("chat_session_ids") or []}},
                                       {"_id": 0, "role": 1, "content": 1}).sort("created_at", 1).to_list(60)
    if not msgs:
        return lead
    catalog = [s["name"] for s in biz.get("service_catalog") or []]
    bookings = await db.bookings.find({"business_id": bid, "booking_id": {"$in": lead.get("booking_ids") or []}}, {"_id": 0, "service": 1, "start_utc": 1, "status": 1}).to_list(20)
    sys = ("Summarize a customer's conversation with a business's AI assistant for the owner's CRM. Return ONLY JSON "
           '{"summary": string, "service_interests": [string]}. The summary: 2-3 factual sentences, only what the customer said or what '
           "the booking system confirmed. No speculation, no marketing language. service_interests must use names from: "
           f"{catalog or 'any service mentioned'}.")
    convo = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in msgs[-40:]) + f"\nConfirmed bookings: {bookings or 'none'}"
    try:
        raw = await LlmChat(api_key=api_key, session_id=f"sum_{uuid.uuid4().hex[:8]}", system_message=sys).with_model(*SUMMARY_MODEL).send_message(UserMessage(text=convo))
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    except Exception as e:
        logging.exception("lead summary failed: %s", e)
        return lead
    interests = [s for s in data.get("service_interests") or [] if not catalog or s in catalog]
    await db.leads.update_one({"lead_id": lead_id, "business_id": bid},
                              {"$set": {"summary": str(data.get("summary", ""))[:1200], "summary_updated_at": now()},
                               "$addToSet": {"service_interests": {"$each": interests}}})
    return await db.leads.find_one({"lead_id": lead_id, "business_id": bid}, {"_id": 0})


async def create_draft(db, new_id, api_key, biz, lead_id, channel, kind="marketing"):
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    bid = biz["business_id"]
    lead = await db.leads.find_one({"lead_id": lead_id, "business_id": bid}, {"_id": 0})
    if not lead:
        raise LeadError("Lead not found", 404)
    if kind == INQUIRY:
        msgs = await db.chat_messages.find({"business_id": bid, "session_id": {"$in": lead.get("chat_session_ids") or []}, "role": "user"},
                                           {"_id": 0, "content": 1}).sort("created_at", 1).to_list(30)
        sys = (f"You write a personal {channel} reply from {biz['name']} answering a customer's inquiry. "
               f"Business facts: services {biz.get('services', '')}; hours {biz.get('hours', '')}; FAQs {biz.get('faqs', '')}. "
               f"Tone: {biz.get('ai_tone', 'warm, professional')}. {'Under 120 words.' if channel == 'email' else 'Under 300 characters.'} "
               "Answer only what they asked using the business facts. No promotions or discounts. No placeholders. Plain text. Sign off as the team.")
        facts = (f"Customer first name: {lead['name'].split()[0]}. Their messages: " + " | ".join(m["content"][:300] for m in msgs[-8:])
                 + f". Summary: {lead.get('summary') or 'none'}.")
    else:
        sys = (f"You write a short personalized {channel} follow-up for {biz['name']} ({biz.get('industry', 'local business')}). "
               f"Tone: {biz.get('ai_tone', 'warm, professional')}. {'Under 70 words.' if channel == 'email' else 'Under 300 characters.'} "
               "Use only the facts given. No placeholders in brackets. Plain text. Sign off as the team.")
        facts = (f"Customer first name: {lead['name'].split()[0]}. Interests: {', '.join(lead.get('service_interests') or []) or 'not stated'}. "
                 f"Conversation summary: {lead.get('summary') or lead.get('notes') or 'none'}. Status: {lead.get('status')}.")
    try:
        text = await LlmChat(api_key=api_key, session_id=f"draft_{uuid.uuid4().hex[:8]}", system_message=sys).with_model(*SUMMARY_MODEL).send_message(UserMessage(text=facts))
    except Exception as e:
        logging.exception("draft failed: %s", e)
        raise LeadError("Could not generate a draft right now", 502)
    draft = {"draft_id": new_id("drf"), "channel": channel, "kind": kind, "message": text.strip(), "status": "pending", "created_at": now()}
    await db.leads.update_one({"lead_id": lead_id, "business_id": bid}, {"$push": {"drafts": draft}})
    return draft


async def approve_draft(db, new_id, bid, lead_id, draft_id, approver, message=None):
    lead = await db.leads.find_one({"lead_id": lead_id, "business_id": bid}, {"_id": 0})
    if not lead:
        raise LeadError("Lead not found", 404)
    draft = next((d for d in lead.get("drafts") or [] if d["draft_id"] == draft_id), None)
    if not draft or draft["status"] != "pending":
        raise LeadError("Draft not found or already handled", 404)
    ch, kind = draft["channel"], draft.get("kind", "marketing")
    consent = lead.get("consent") or {}
    if kind == INQUIRY:
        c = consent.get(INQUIRY) or {}
        if not c.get("granted") or c.get("channel_to_use") != ch:
            raise LeadError(f"{lead['name']} has not given permission for a {'n email' if ch == 'email' else ' text'} reply to this inquiry. Nothing was sent.", 403)
    elif not (consent.get(ch) or {}).get("granted"):
        raise LeadError(f"{lead['name']} has not opted in to {'email' if ch == 'email' else 'text message'} marketing. Nothing was sent.", 403)
    if not lead.get("email_norm" if ch == "email" else "phone_norm"):
        raise LeadError(f"No {'email address' if ch == 'email' else 'phone number'} on file.", 400)
    body = (message or draft["message"]).strip()
    ts = now()
    entry = {"id": new_id("fu"), "channel": ch, "message": body, "status": "simulated-sent", "simulated": True, "delivered": False,
             "kind": kind, "draft_id": draft_id, "approved_by": approver, "sent_at": ts,
             "to": lead.get("email") if ch == "email" else lead.get("phone")}
    await db.leads.update_one(
        {"lead_id": lead_id, "business_id": bid, "drafts.draft_id": draft_id},
        {"$set": {"drafts.$.status": "approved", "drafts.$.message": body, "drafts.$.approved_at": ts, "drafts.$.approved_by": approver,
                  "status": "contacted" if lead.get("status") == "new" else lead.get("status")},
         "$push": {"follow_ups": entry}})
    return entry
