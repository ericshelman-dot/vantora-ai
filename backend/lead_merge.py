"""Duplicate lead review & approved merges with archive + undo. All operations are scoped to one business."""
import re
from datetime import datetime, timezone

from leads_engine import INQUIRY, CHANNELS, LeadError, contact_keys

CONSENT_KINDS = (*CHANNELS, INQUIRY)
STATUS_RANK = {"new": 0, "contacted": 1, "qualified": 2, "booked": 3, "closed": 4}
ACTIVE = {"archived": {"$ne": True}}


def now():
    return datetime.now(timezone.utc).isoformat()


def norm_name(n):
    return re.sub(r"\s+", " ", (n or "").strip().lower())


async def find_duplicate_groups(db, bid):
    leads = await db.leads.find({"business_id": bid, **ACTIVE}, {"_id": 0, "consent_log": 0, "drafts": 0}).to_list(5000)
    groups, seen = [], set()
    for field, reason, kind in (("email_norm", "Same email address", "exact"), ("phone_norm", "Same phone number", "exact"),
                                ("name", "Same name, different contact details — review manually", "name_only")):
        buckets = {}
        for ld in leads:
            key = norm_name(ld.get("name")) if field == "name" else ld.get(field)
            if key and key != "website visitor":
                buckets.setdefault(key, []).append(ld)
        for key, items in buckets.items():
            ids = frozenset(i["lead_id"] for i in items)
            if len(items) > 1 and ids not in seen:
                seen.add(ids)
                groups.append({"group_id": f"{field}:{key}", "reason": reason, "match": kind, "lead_ids": sorted(ids)})
    return groups


async def lead_bundle(db, bid, lead_id):
    lead = await db.leads.find_one({"lead_id": lead_id, "business_id": bid}, {"_id": 0})
    if not lead:
        return None
    sessions = lead.get("chat_session_ids") or []
    msgs = await db.chat_messages.find({"business_id": bid, "session_id": {"$in": sessions}}, {"_id": 0}).sort("created_at", 1).to_list(500)
    bookings = await db.bookings.find({"business_id": bid, "$or": [{"lead_id": lead_id}, {"booking_id": {"$in": lead.get("booking_ids") or []}}]},
                                      {"_id": 0}).to_list(200)
    return {"lead": lead, "conversations": [{"session_id": s, "messages": [m for m in msgs if m["session_id"] == s]} for s in sessions],
            "bookings": bookings}


def cautious_consent(entries):
    """Most cautious effective preference: any opt-out wins; any unknown means no consent; only unanimous grants survive."""
    present = [e for e in entries if e]
    if any(not e.get("granted") for e in present):
        return max((e for e in present if not e.get("granted")), key=lambda e: e.get("at", ""))
    if len(present) < len(entries):
        return None
    return max(present, key=lambda e: e.get("at", "")) if present else None


def plan_merge(primary, dups):
    allx = [primary, *dups]
    consent = {k: cautious_consent([(ld.get("consent") or {}).get(k) for ld in allx]) for k in CONSENT_KINDS}
    uniq = lambda key: list(dict.fromkeys(x for ld in allx for x in (ld.get(key) or [])))  # noqa: E731
    return {
        "consent": consent,
        "chat_session_ids": uniq("chat_session_ids"), "booking_ids": uniq("booking_ids"), "service_interests": uniq("service_interests"),
        "alternate_emails": [e for e in dict.fromkeys(d.get("email") for d in dups if d.get("email")) if e.lower() != (primary.get("email") or "").lower()],
        "alternate_phones": [p for p in dict.fromkeys(d.get("phone") for d in dups if d.get("phone")) if p != primary.get("phone")],
        "follow_ups": sorted([f for ld in allx for f in ld.get("follow_ups") or []], key=lambda f: f.get("sent_at", "")),
        "drafts": [d for ld in allx for d in ld.get("drafts") or []],
        "consent_log": sorted([c for ld in allx for c in ld.get("consent_log") or []], key=lambda c: c.get("at", "")),
        "status_history": sorted([h for ld in allx for h in ld.get("status_history") or []], key=lambda h: h.get("at", "")),
        "inquiry_date": min(ld.get("inquiry_date") or ld.get("created_at") or "" for ld in allx),
        "alternate_email_norms": list(dict.fromkeys(x for ld in dups for x in [ld.get("email_norm"), *(ld.get("alternate_email_norms") or [])]
                                                    if x and x != primary.get("email_norm"))),
        "alternate_phone_norms": list(dict.fromkeys(x for ld in dups for x in [ld.get("phone_norm"), *(ld.get("alternate_phone_norms") or [])]
                                                    if x and x != primary.get("phone_norm"))),
        "status": "booked" if uniq("booking_ids") and primary.get("status") != "closed"
                  else max((ld.get("status") or "new" for ld in allx), key=lambda s: STATUS_RANK.get(s, 0)),
    }


async def _load(db, bid, primary_id, dup_ids):
    if primary_id in dup_ids or not dup_ids:
        raise LeadError("Choose one primary lead and at least one different duplicate.")
    docs = await db.leads.find({"business_id": bid, "lead_id": {"$in": [primary_id, *dup_ids]}, **ACTIVE}, {"_id": 0}).to_list(50)
    by = {d["lead_id"]: d for d in docs}
    if len(by) != len(set(dup_ids)) + 1:
        raise LeadError("All leads must be active and belong to this business.", 404)
    return by[primary_id], [by[i] for i in dup_ids]


async def preview(db, bid, primary_id, dup_ids):
    primary, dups = await _load(db, bid, primary_id, dup_ids)
    p = plan_merge(primary, dups)
    return {"primary_id": primary_id, "duplicate_ids": dup_ids, "result_consent": p["consent"],
            "conversations": len(p["chat_session_ids"]), "bookings": len(p["booking_ids"]), "booking_ids": p["booking_ids"],
            "follow_ups": len(p["follow_ups"]), "result_status": p["status"],
            "service_interests": p["service_interests"], "alternate_emails": p["alternate_emails"], "alternate_phones": p["alternate_phones"]}


async def merge(db, new_id, bid, primary_id, dup_ids, approver):
    primary, dups = await _load(db, bid, primary_id, dup_ids)
    p = plan_merge(primary, dups)
    ts = now()
    bookings_before = await db.bookings.find({"business_id": bid, "lead_id": {"$in": dup_ids}}, {"_id": 0, "booking_id": 1, "lead_id": 1, "customer_id": 1}).to_list(500)
    dup_customers = [d["customer_id"] for d in dups if d.get("customer_id") and d.get("customer_id") != primary.get("customer_id")]
    merge_id = new_id("mrg")
    await db.lead_merges.insert_one({
        "merge_id": merge_id, "business_id": bid, "primary_id": primary_id, "duplicate_ids": dup_ids, "approved_by": approver, "at": ts,
        "primary_before": primary, "duplicates_before": dups, "bookings_before": bookings_before,
        "customers_archived": dup_customers, "merged_status": p["status"], "undone": False})
    # archive duplicates first so their contact keys are released
    for d in dups:
        await db.leads.update_one({"lead_id": d["lead_id"], "business_id": bid}, {
            "$set": {"archived": True, "archived_at": ts, "merged_into": primary_id, "merge_id": merge_id, "email_key": None, "phone_key": None}})
    merge_log = {"channel": "merge", "granted": None, "text": f"Merged {', '.join(dup_ids)} into {primary_id}; consent set to most cautious preference",
                 "source": f"approved by {approver}", "at": ts}
    await db.leads.update_one({"lead_id": primary_id, "business_id": bid}, {"$set": {
        "consent": p["consent"], "chat_session_ids": p["chat_session_ids"], "booking_ids": p["booking_ids"],
        "service_interests": p["service_interests"], "alternate_emails": p["alternate_emails"], "alternate_phones": p["alternate_phones"],
        "alternate_email_norms": p["alternate_email_norms"], "alternate_phone_norms": p["alternate_phone_norms"], "status": p["status"],
        "follow_ups": p["follow_ups"], "drafts": p["drafts"], "consent_log": [*p["consent_log"], merge_log],
        "status_history": [*p["status_history"], {"status": p["status"], "at": ts, "by": f"merge approved by {approver}"}],
        "inquiry_date": p["inquiry_date"], "last_contact_at": ts},
        "$push": {"merge_history": {"merge_id": merge_id, "merged_ids": dup_ids, "at": ts, "by": approver}}})
    await db.bookings.update_many({"business_id": bid, "lead_id": {"$in": dup_ids}},
                                  {"$set": {"lead_id": primary_id, "customer_id": primary.get("customer_id")}})
    if dup_customers:
        await db.customers.update_many({"business_id": bid, "customer_id": {"$in": dup_customers}},
                                       {"$set": {"archived": True, "archived_at": ts, "merged_into": primary.get("customer_id"), "merge_id": merge_id}})
    return {"merge_id": merge_id, "primary_id": primary_id, "archived": dup_ids}


async def undo(db, bid, merge_id, actor):
    """Reverse a merge without losing anything recorded after it (consent changes, new activity)."""
    m = await db.lead_merges.find_one({"merge_id": merge_id, "business_id": bid}, {"_id": 0})
    if not m:
        raise LeadError("Merge not found", 404)
    if m["undone"]:
        raise LeadError("This merge was already undone.", 409)
    before, dups, ts = m["primary_before"], m["duplicates_before"], now()
    cur = await db.leads.find_one({"lead_id": before["lead_id"], "business_id": bid}, {"_id": 0}) or {}
    dup_sessions = {x for d in dups for x in d.get("chat_session_ids") or []} - set(before.get("chat_session_ids") or [])
    dup_bookings = {x for d in dups for x in d.get("booking_ids") or []} - set(before.get("booking_ids") or [])
    dup_fu = {f.get("id") for d in dups for f in d.get("follow_ups") or []}
    dup_drafts = {x.get("draft_id") for d in dups for x in d.get("drafts") or []}
    dup_log = {(c.get("channel"), c.get("at"), c.get("text")) for d in dups for c in d.get("consent_log") or []}
    log = [c for c in cur.get("consent_log") or [] if (c.get("channel"), c.get("at"), c.get("text")) not in dup_log]
    consent = dict(before.get("consent") or {})
    for c in log:  # consent decisions recorded on the primary after the merge win over the pre-merge snapshot
        if c.get("at", "") > m["at"] and c.get("channel") in CONSENT_KINDS:
            consent[c["channel"]] = c
    log.append({"channel": "merge", "granted": None, "text": f"Merge {merge_id} undone", "source": f"undone by {actor}", "at": ts})
    await db.leads.update_one({"lead_id": before["lead_id"], "business_id": bid}, {"$set": {
        "consent": consent, "consent_log": log,
        "chat_session_ids": [s for s in cur.get("chat_session_ids") or [] if s not in dup_sessions],
        "booking_ids": [b for b in cur.get("booking_ids") or [] if b not in dup_bookings],
        "follow_ups": [f for f in cur.get("follow_ups") or [] if f.get("id") not in dup_fu],
        "drafts": [x for x in cur.get("drafts") or [] if x.get("draft_id") not in dup_drafts],
        "alternate_emails": before.get("alternate_emails") or [], "alternate_phones": before.get("alternate_phones") or [],
        "alternate_email_norms": before.get("alternate_email_norms") or [], "alternate_phone_norms": before.get("alternate_phone_norms") or [],
        "inquiry_date": before.get("inquiry_date"),
        "status": before.get("status") if cur.get("status") == m.get("merged_status", cur.get("status")) else cur.get("status"),
        "service_interests": list(dict.fromkeys([*(before.get("service_interests") or []),
                                                 *[i for i in cur.get("service_interests") or [] if i not in {x for d in dups for x in d.get("service_interests") or []}]])),
        "status_history": [*(cur.get("status_history") or []), {"status": cur.get("status"), "at": ts, "by": f"merge undone by {actor}"}]}})
    conflicts = []
    for d in dups:
        keys = contact_keys(bid, d.get("email_norm"), d.get("phone_norm"))
        for k, v in list(keys.items()):
            if v and await db.leads.find_one({"business_id": bid, k: v, "lead_id": {"$ne": d["lead_id"]}}, {"_id": 1}):
                keys[k] = None
                conflicts.append({"lead_id": d["lead_id"], "field": k.split("_")[0]})
        await db.leads.replace_one({"lead_id": d["lead_id"], "business_id": bid}, {**d, **keys, "restored_at": ts,
                                   **({"restore_note": "Contact now used by another active lead; left for duplicate review"} if any(c["lead_id"] == d["lead_id"] for c in conflicts) else {})})
    for b in m["bookings_before"]:
        await db.bookings.update_one({"booking_id": b["booking_id"], "business_id": bid}, {"$set": {"lead_id": b["lead_id"], "customer_id": b.get("customer_id")}})
    await db.customers.update_many({"business_id": bid, "customer_id": {"$in": m["customers_archived"]}},
                                   {"$unset": {"archived": "", "archived_at": "", "merged_into": "", "merge_id": ""}})
    await db.lead_merges.update_one({"merge_id": merge_id}, {"$set": {"undone": True, "undone_at": ts, "undone_by": actor, "undo_conflicts": conflicts}})
    return {"ok": True, "conflicts": conflicts}
