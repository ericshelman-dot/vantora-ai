"""Zero-provider-cost sales pilot. No send, calendar-write, billing or LLM clients."""
from datetime import datetime, timezone
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict


def stamp():
    return datetime.now(timezone.utc).isoformat()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Prospect(Input):
    name: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=160)
    service: str = Field(min_length=1, max_length=160)
    source: str = Field(min_length=1, max_length=200)
    need: str = Field(default="", max_length=1000)
    email: str = Field(default="", max_length=254)
    decision_maker: bool = False
    timing: Literal["unknown", "later", "this_month"] = "unknown"
    permission: Literal["unknown", "granted", "opted_out"] = "unknown"
    permission_evidence: str = Field(default="", max_length=500)


class Setup(Input):
    business_name: str = Field(min_length=1, max_length=160)
    owner_name: str = Field(min_length=1, max_length=120)
    services: str = Field(min_length=1, max_length=1000)
    timezone: str
    consent_evidence: str = Field(min_length=10, max_length=1000)
    owner_consented: Literal[True]


class Action(Input):
    kind: Literal["draft", "edit_draft", "approve_draft", "response", "stage", "booking_proposal"]
    text: str = Field(default="", max_length=4000)
    stage: Literal["new", "qualified", "contacted", "responded", "booked", "won", "lost"] = "new"
    outcome: Literal["interested", "not_now", "opt_out"] = "interested"
    starts_at: str = ""
    duration_min: int = Field(default=30, ge=5, le=240)
    revenue_cents: int = Field(default=0, ge=0, le=100000000)
    expected_revision: int = Field(ge=0)


def qualify(p):
    reasons = []
    for yes, label in [(bool(p.get("need")), "Business need recorded"),
                       (p.get("decision_maker"), "Decision maker confirmed"),
                       (p.get("timing") == "this_month", "Timing within this month"),
                       (p.get("permission") == "granted", "Outreach permission recorded")]:
        if yes:
            reasons.append(label)
    return {"score": len(reasons) * 25, "reasons": reasons,
            "method": "Transparent rules; no paid AI calls", "eligible": p.get("permission") == "granted"}


def apply_action(p, body, actor):
    """Pure transition function; callers persist using optimistic concurrency."""
    if p["revision"] != body.expected_revision:
        raise HTTPException(409, "Record changed. Refresh before trying again.")
    p = dict(p)
    ts = stamp()
    if body.kind in {"draft", "approve_draft"} and p["permission"] != "granted":
        raise HTTPException(409, "Record contact permission before preparing outreach.")
    if body.kind == "draft":
        p["draft"] = {"message": f"Hi {p['name']}, you mentioned {p['need'] or p['service']}. "
                      f"Would a short conversation about {p['service']} for {p['company']} be useful? "
                      "If you would prefer no follow-up, please let us know.",
                      "status": "pending", "revision": p["revision"] + 1, "created_at": ts,
                      "generator": "local template", "delivery": "not_sent"}
    elif body.kind == "edit_draft":
        if not body.text or not p.get("draft") or p["draft"]["status"] != "pending":
            raise HTTPException(409, "A pending draft and non-empty message are required.")
        p["draft"] = {**p["draft"], "message": body.text, "revision": p["revision"] + 1}
    elif body.kind == "approve_draft":
        if not p.get("draft") or p["draft"]["status"] != "pending":
            raise HTTPException(409, "No pending draft to approve.")
        p["draft"] = {**p["draft"], "status": "approved_for_manual_review", "approved_by": actor,
                      "approved_at": ts, "delivery": "not_sent"}
    elif body.kind == "response":
        if not body.text:
            raise HTTPException(422, "Record the response before saving.")
        p["responses"] = [*p.get("responses", []), {"text": body.text, "outcome": body.outcome, "at": ts, "by": actor}]
        p["stage"] = "responded"
        if body.outcome == "opt_out":
            p["permission"] = "opted_out"
            if p.get("draft"):
                p["draft"] = {**p["draft"], "status": "blocked_opt_out"}
    elif body.kind == "booking_proposal":
        try:
            start = datetime.fromisoformat(body.starts_at)
            if not start.tzinfo or start <= datetime.now(timezone.utc):
                raise ValueError()
        except ValueError:
            raise HTTPException(422, "Choose a future appointment with an explicit timezone offset.")
        p["booking_proposal"] = {"starts_at": start.isoformat(), "duration_min": body.duration_min,
                                 "status": "awaiting_calendar_authorization", "created_at": ts,
                                 "calendar_event_created": False}
    elif body.kind == "stage":
        if body.stage == "booked":
            raise HTTPException(409, "Calendar authorization and confirmed event are required. This pilot only saves proposals.")
        if body.stage in {"contacted", "won", "lost"} and not body.text:
            raise HTTPException(422, "Add evidence for this manually recorded outcome.")
        if body.stage == "qualified" and qualify(p)["score"] < 50:
            raise HTTPException(409, "At least two qualification criteria are required.")
        if body.stage == "contacted" and p["permission"] != "granted":
            raise HTTPException(409, "Contact is blocked without permission.")
        p["stage"] = body.stage
        p["revenue_cents"] = body.revenue_cents if body.stage == "won" else 0
        p["outcome_evidence"] = body.text
    p["revision"] += 1
    p["updated_at"] = ts
    return p


def router(db, current_user):
    api = APIRouter(prefix="/api/sales-pilot", tags=["sales-pilot"])

    def scope(user, mode):
        # Request bodies cannot choose another tenant; demo is also physically separated.
        tenant = user.get("business_id") or user["user_id"]
        if mode == "live" and (not user.get("business_id") or user.get("demo_mode")):
            raise HTTPException(403, "Choose an authorized business workspace first.")
        return {"tenant_id": tenant, "mode": mode}

    def collection(mode):
        return db.sales_pilot_demo if mode == "demo" else db.sales_pilot_live

    async def enabled(user, mode):
        s = scope(user, mode)
        if mode == "live" and not await db.sales_pilot_consents.find_one({**s, "active": True}):
            raise HTTPException(403, "Business owner consent and setup are required before live data can be used.")
        return s

    def event(user, kind, prospect_id=None):
        return {"event_id": uuid.uuid4().hex, "at": stamp(), "actor": user["user_id"],
                "action": kind, "prospect_id": prospect_id}

    @api.get("")
    async def workspace(mode: Literal["demo", "live"] = "demo", user=Depends(current_user)):
        s = scope(user, mode)
        setup = await db.sales_pilot_consents.find_one({**s, "active": True}, {"_id": 0}) if mode == "live" else None
        rows = await collection(mode).find(s, {"_id": 0}).to_list(1000) if mode == "demo" or setup else []
        for p in rows:
            p["qualification"] = qualify(p)
        won = [p for p in rows if p["stage"] == "won"]
        return {"mode": mode, "ready": mode == "demo" or bool(setup), "prospects": rows,
                "report": {"total": len(rows), "qualified": sum(qualify(p)["score"] >= 50 for p in rows),
                           "responses": sum(bool(p.get("responses")) for p in rows), "won": len(won),
                           "conversion_percent": round(len(won) / len(rows) * 100, 1) if rows else 0,
                           "recorded_revenue_cents": sum(p.get("revenue_cents", 0) for p in won),
                           "basis": "Manually recorded outcomes; no attributed or collected revenue"},
                "safeguards": {"sending_enabled": False, "calendar": "not_connected", "paid_ai_calls": False,
                               "report_limit": 1000}, "setup": setup}

    @api.post("/setup")
    async def setup(body: Setup, user=Depends(current_user)):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(body.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(422, "Unknown timezone")
        s = scope(user, "live")
        record = {**s, **body.model_dump(), "active": True, "recorded_by": user["user_id"], "recorded_at": stamp()}
        await db.sales_pilot_consents.update_one(s, {"$set": record,
                  "$push": {"audit": event(user, "owner_consent_recorded")}}, upsert=True)
        return {"ready": True, "calendar": "not_connected", "sending_enabled": False}

    @api.post("/pause")
    async def pause(user=Depends(current_user)):
        s = scope(user, "live")
        await db.sales_pilot_consents.update_one(s, {"$set": {"active": False},
                  "$push": {"audit": event(user, "owner_authorization_paused")}})
        return {"ready": False, "data_preserved": True}

    @api.post("/prospects")
    async def create(body: Prospect, mode: Literal["demo", "live"] = "demo", user=Depends(current_user)):
        s = await enabled(user, mode)
        if body.permission == "granted" and not body.permission_evidence:
            raise HTTPException(422, "Permission requires evidence.")
        if mode == "demo" and body.email and not body.email.endswith("@example.com"):
            raise HTTPException(422, "Use fictional @example.com contacts in demo mode.")
        if body.email and ("@" not in body.email or " " in body.email):
            raise HTTPException(422, "Enter a valid contact email.")
        p = {**s, **body.model_dump(), "prospect_id": uuid.uuid4().hex, "stage": "new", "revision": 0,
             "created_at": stamp(), "audit": [event(user, "prospect_created")], "responses": []}
        await collection(mode).insert_one(dict(p))
        return p

    @api.post("/prospects/{pid}/actions")
    async def act(pid: str, body: Action, mode: Literal["demo", "live"] = "demo", user=Depends(current_user)):
        s = await enabled(user, mode)
        c = collection(mode)
        query = {**s, "prospect_id": pid}
        p = await c.find_one(query, {"_id": 0})
        if not p:
            raise HTTPException(404, "Prospect not found")
        updated = apply_action(p, body, user["user_id"])
        updated["audit"] = [*p["audit"], event(user, body.kind, pid)]
        result = await c.update_one({**query, "revision": body.expected_revision}, {"$set": updated})
        if not result.matched_count:
            raise HTTPException(409, "Record changed. Refresh before trying again.")
        return updated

    return api
