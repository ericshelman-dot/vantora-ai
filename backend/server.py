from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, jwt, bcrypt, requests
import scheduling as sch
import booking_agent
import leads_engine
import lead_merge
from pymongo.errors import DuplicateKeyError
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, field_validator
from zoneinfo import ZoneInfo
from typing import List, Optional, Literal
from datetime import datetime, timezone, timedelta

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def now_utc():
    return datetime.now(timezone.utc)


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------- Models ----------
class RegisterInput(BaseModel):
    name: str
    email: EmailStr
    password: str
    business_name: str


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    services: Optional[str] = None
    hours: Optional[str] = None
    faqs: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    ai_tone: Optional[str] = None
    ai_greeting: Optional[str] = None
    phone_reception_enabled: Optional[bool] = None
    chat_enabled: Optional[bool] = None
    follow_up_consent: Optional[bool] = None
    scheduling: Optional["SchedulingConfig"] = None
    service_catalog: Optional[List["CatalogService"]] = None


class SchedulingConfig(BaseModel):
    timezone: str
    capacity: int = Field(ge=1, le=50)
    slot_minutes: int = Field(default=30, ge=5, le=240)
    default_duration: int = Field(default=60, ge=5, le=600)
    weekly: dict

    @field_validator("timezone")
    @classmethod
    def valid_tz(cls, v):
        try:
            ZoneInfo(v)
        except Exception:
            raise ValueError("Unknown time zone")
        return v

    @field_validator("weekly")
    @classmethod
    def valid_weekly(cls, v):
        out = {}
        for d in sch.DAYS:
            span = v.get(d)
            if span:
                o, c = datetime.strptime(span[0], "%H:%M"), datetime.strptime(span[1], "%H:%M")
                if c <= o:
                    raise ValueError(f"{d}: closing time must be after opening time")
                out[d] = [span[0], span[1]]
            else:
                out[d] = None
        return out


class CatalogService(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    duration_min: int = Field(ge=5, le=600)
    price: Optional[str] = ""


class LeadInput(BaseModel):
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    source: Optional[str] = "manual"
    status: Optional[str] = "new"
    notes: Optional[str] = ""


class BookingInput(BaseModel):
    customer_name: str
    service: str
    datetime: str
    notes: Optional[str] = ""
    status: Optional[str] = "confirmed"
    duration_min: Optional[int] = Field(default=None, ge=5, le=600)


class CustomerInput(BaseModel):
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    notes: Optional[str] = ""


class FollowUpInput(BaseModel):
    channel: str  # email | sms
    message: str


class DemoRequestInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=40)
    message: str = Field(default="", max_length=2000)
    kind: Literal["demo", "contact"] = "demo"


class ChatInput(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    business_id: Optional[str] = None  # for public widget
    consent: Optional[dict] = None  # widget checkboxes: {"email": true, "sms": true}; only true counts


class PlanInput(BaseModel):
    name: str
    setup_fee: float
    monthly_fee: float
    features: List[str] = []


# ---------- Auth helpers ----------
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def make_jwt(user_id: str) -> str:
    payload = {"user_id": user_id, "exp": now_utc() + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def get_current_user(request: Request):
    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if not token:
        token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = None
    # Try JWT first
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id")
    except Exception:
        # Try session token (Google OAuth)
        sess = await db.sessions.find_one({"session_token": token}, {"_id": 0})
        if sess:
            exp = sess["expires_at"]
            if isinstance(exp, str):
                exp = datetime.fromisoformat(exp)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now_utc():
                user_id = sess["user_id"]
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user["demo_mode"] = False
    if user.get("role") == "admin" and user.get("active_business_id"):
        demo = await db.businesses.find_one({"business_id": user["active_business_id"], "is_demo": True}, {"_id": 0, "business_id": 1})
        if demo:
            user["business_id"] = demo["business_id"]
            user["demo_mode"] = True
    return user


async def require_business(user=Depends(get_current_user)):
    if not user.get("business_id"):
        raise HTTPException(status_code=403, detail="This account isn't linked to a business workspace.")
    return user


async def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def create_business_and_owner(name, email, pw_hash, business_name, provider="password", picture=""):
    business_id = new_id("biz")
    user_id = new_id("user")
    plan = await db.plans.find_one({"is_default": True}, {"_id": 0})
    biz = {
        "business_id": business_id, "name": business_name, "owner_id": user_id,
        "industry": "", "services": "", "hours": "Mon-Fri 9am-6pm", "faqs": "",
        "phone": "", "address": "", "ai_tone": "warm and professional",
        "ai_greeting": f"Thank you for calling {business_name}. How may I help you today?",
        "phone_reception_enabled": True, "chat_enabled": True, "follow_up_consent": True,
        "plan_id": plan["plan_id"] if plan else None,
        "subscription_status": "trialing", "setup_fee_paid": False,
        "created_at": now_utc().isoformat(),
    }
    user = {
        "user_id": user_id, "name": name, "email": email, "password_hash": pw_hash,
        "role": "owner", "business_id": business_id, "provider": provider,
        "picture": picture, "created_at": now_utc().isoformat(),
    }
    await db.businesses.insert_one(biz)
    await db.users.insert_one(user)
    return user, biz


# ---------- Auth routes ----------
@api_router.post("/auth/register")
async def register(body: RegisterInput):
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user, biz = await create_business_and_owner(
        body.name, body.email.lower(), hash_pw(body.password), body.business_name)
    token = make_jwt(user["user_id"])
    return {"token": token, "user": {k: user[k] for k in ("user_id", "name", "email", "role", "business_id")}}


@api_router.post("/auth/login")
async def login(body: LoginInput, request: Request):
    email = body.email.lower()
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    ident = f"{ip}:{email}"
    since = (now_utc() - timedelta(minutes=15)).isoformat()
    per_ip = await db.login_attempts.count_documents({"identifier": ident, "at": {"$gte": since}})
    per_email = await db.login_attempts.count_documents({"email": email, "at": {"$gte": since}})
    if per_ip >= 5 or per_email >= 20:
        raise HTTPException(status_code=429, detail="Too many failed sign-in attempts. Please wait 15 minutes and try again.")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_pw(body.password, user["password_hash"]):
        await db.login_attempts.insert_one({"identifier": ident, "email": email, "at": now_utc().isoformat()})
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await db.login_attempts.delete_many({"identifier": ident})
    token = make_jwt(user["user_id"])
    return {"token": token, "user": {k: user.get(k) for k in ("user_id", "name", "email", "role", "business_id")}}


@api_router.post("/auth/session")
async def google_session(request: Request, response: Response):
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        body = await request.json()
        session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session id")
    r = requests.get(
        "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
        headers={"X-Session-ID": session_id}, timeout=15)
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    data = r.json()
    email = data["email"].lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user, _ = await create_business_and_owner(
            data.get("name", email), email, "", data.get("name", "My Business"),
            provider="google", picture=data.get("picture", ""))
    session_token = data["session_token"]
    await db.sessions.insert_one({
        "user_id": user["user_id"], "session_token": session_token,
        "expires_at": (now_utc() + timedelta(days=7)).isoformat(), "created_at": now_utc().isoformat()})
    response.set_cookie("session_token", session_token, httponly=True, secure=True,
                        samesite="none", path="/", max_age=7 * 24 * 3600)
    return {"token": session_token, "user": {k: user.get(k) for k in ("user_id", "name", "email", "role", "business_id")}}


@api_router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    biz = None
    if user.get("business_id"):
        biz = await db.businesses.find_one({"business_id": user["business_id"]}, {"_id": 0})
    return {"user": {k: user.get(k) for k in ("user_id", "name", "email", "role", "business_id", "picture", "demo_mode")}, "business": biz}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# ---------- Business ----------
@api_router.get("/business")
async def get_business(user=Depends(get_current_user)):
    if not user.get("business_id"):
        raise HTTPException(status_code=403, detail="This account isn't linked to a business workspace.")
    biz = await db.businesses.find_one({"business_id": user["business_id"]}, {"_id": 0})
    if not biz:
        raise HTTPException(status_code=404, detail="We couldn't find your business profile. Please refresh or contact support.")
    return biz


@api_router.put("/business")
async def update_business(body: BusinessUpdate, user=Depends(get_current_user)):
    if not user.get("business_id"):
        raise HTTPException(status_code=403, detail="This account isn't linked to a business workspace.")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.businesses.update_one({"business_id": user["business_id"]}, {"$set": updates})
    return await db.businesses.find_one({"business_id": user["business_id"]}, {"_id": 0})


# ---------- Leads (CRM) ----------
class LeadUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    source: Optional[str] = Field(default=None, max_length=60)
    status: Optional[Literal["new", "contacted", "qualified", "booked", "closed"]] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class OptOutInput(BaseModel):
    channel: Literal["email", "sms"]


class DraftInput(BaseModel):
    channel: Literal["email", "sms"]


class DraftEdit(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _lead_err(e: leads_engine.LeadError):
    return HTTPException(status_code=e.code, detail=str(e))


async def _contact_clash(bid, en, pn, exclude=None):
    ors = ([{"email_norm": en}, {"alternate_email_norms": en}] if en else []) + ([{"phone_norm": pn}, {"alternate_phone_norms": pn}] if pn else [])
    if not ors:
        return None
    q = {"business_id": bid, "$or": ors, "archived": {"$ne": True}}
    if exclude:
        q["lead_id"] = {"$ne": exclude}
    return await db.leads.find_one(q, {"_id": 0, "lead_id": 1, "name": 1})


@api_router.get("/leads")
async def list_leads(user=Depends(require_business)):
    return await db.leads.find({"business_id": user["business_id"], "archived": {"$ne": True}}, {"_id": 0, "consent_log": 0}).sort("last_contact_at", -1).to_list(1000)


@api_router.get("/leads/{lead_id}")
async def get_lead(lead_id: str, user=Depends(require_business)):
    bid = user["business_id"]
    lead = await db.leads.find_one({"lead_id": lead_id, "business_id": bid}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    sessions = lead.get("chat_session_ids") or []
    msgs = await db.chat_messages.find({"business_id": bid, "session_id": {"$in": sessions}}, {"_id": 0}).sort("created_at", 1).to_list(500)
    convos = [{"session_id": s, "messages": [m for m in msgs if m["session_id"] == s]} for s in sessions]
    bookings = await db.bookings.find({"business_id": bid, "$or": [{"booking_id": {"$in": lead.get("booking_ids") or []}}, {"lead_id": lead_id}]},
                                      {"_id": 0}).sort("start_utc", 1).to_list(100)
    customer = await db.customers.find_one({"business_id": bid, "customer_id": lead.get("customer_id")}, {"_id": 0}) if lead.get("customer_id") else None
    return {"lead": lead, "conversations": convos, "bookings": bookings, "customer": customer}


@api_router.post("/leads")
async def create_lead(body: LeadInput, user=Depends(require_business)):
    bid = user["business_id"]
    en, pn = leads_engine.norm_email(body.email), leads_engine.norm_phone(body.phone)
    if body.email and not en:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    clash = await _contact_clash(bid, en, pn)
    if clash:
        raise HTTPException(status_code=409, detail=f"A lead with this contact already exists ({clash['name']}).")
    data = body.model_dump()
    data["status"] = data["status"] if data["status"] in leads_engine.STATUSES else "new"
    lead = {"lead_id": new_id("lead"), "business_id": bid, **data, "follow_ups": [], "created_at": now_utc().isoformat()}
    lead.update(leads_engine.backfill_fields(lead))
    lead.update(leads_engine.contact_keys(bid, en, pn))
    try:
        await db.leads.insert_one(lead)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A lead with this contact already exists.")
    lead.pop("_id", None)
    return lead


@api_router.put("/leads/{lead_id}")
async def update_lead(lead_id: str, body: LeadUpdate, user=Depends(require_business)):
    bid = user["business_id"]
    sets = {k: v for k, v in body.model_dump().items() if v is not None}
    if "email" in sets:
        en = leads_engine.norm_email(sets["email"])
        if sets["email"] and not en:
            raise HTTPException(status_code=400, detail="Please enter a valid email address.")
        sets["email_norm"] = en
        sets["email_key"] = leads_engine.contact_keys(bid, en, None)["email_key"]
    if "phone" in sets:
        sets["phone_norm"] = leads_engine.norm_phone(sets["phone"])
        sets["phone_key"] = leads_engine.contact_keys(bid, None, sets["phone_norm"])["phone_key"]
    clash = await _contact_clash(bid, sets.get("email_norm"), sets.get("phone_norm"), exclude=lead_id)
    if clash:
        raise HTTPException(status_code=409, detail=f"Another lead already uses this contact ({clash['name']}).")
    push = {"$push": {"status_history": {"status": sets["status"], "at": now_utc().isoformat(), "by": user["email"]}}} if "status" in sets else {}
    try:
        res = await db.leads.update_one({"lead_id": lead_id, "business_id": bid, "archived": {"$ne": True}}, {"$set": sets, **push})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Another lead already uses this contact.")
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    return await db.leads.find_one({"lead_id": lead_id, "business_id": bid}, {"_id": 0})


@api_router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, user=Depends(require_business)):
    res = await db.leads.update_one({"lead_id": lead_id, "business_id": user["business_id"], "archived": {"$ne": True}},
                                    {"$set": {"archived": True, "archived_at": now_utc().isoformat(), "archived_by": user["email"],
                                              "email_key": None, "phone_key": None}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"ok": True}


@api_router.post("/leads/{lead_id}/opt-out")
async def lead_opt_out(lead_id: str, body: OptOutInput, user=Depends(require_business)):
    try:
        return await leads_engine.record_consent(db, user["business_id"], lead_id, body.channel, False,
                                                 f"Opt-out recorded by {user['email']}", "owner recorded opt-out")
    except leads_engine.LeadError as e:
        raise _lead_err(e)


@api_router.post("/leads/{lead_id}/summarize")
async def lead_summarize(lead_id: str, user=Depends(require_business)):
    biz = await db.businesses.find_one({"business_id": user["business_id"]}, {"_id": 0})
    lead = await leads_engine.summarize(db, EMERGENT_LLM_KEY, biz, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@api_router.post("/leads/{lead_id}/drafts")
async def lead_create_draft(lead_id: str, body: DraftInput, user=Depends(require_business)):
    biz = await db.businesses.find_one({"business_id": user["business_id"]}, {"_id": 0})
    try:
        return await leads_engine.create_draft(db, new_id, EMERGENT_LLM_KEY, biz, lead_id, body.channel)
    except leads_engine.LeadError as e:
        raise _lead_err(e)


@api_router.put("/leads/{lead_id}/drafts/{draft_id}")
async def lead_edit_draft(lead_id: str, draft_id: str, body: DraftEdit, user=Depends(require_business)):
    res = await db.leads.update_one({"lead_id": lead_id, "business_id": user["business_id"],
                                     "drafts": {"$elemMatch": {"draft_id": draft_id, "status": "pending"}}},
                                    {"$set": {"drafts.$.message": body.message.strip()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Draft not found or already handled")
    return {"ok": True}


@api_router.post("/leads/{lead_id}/drafts/{draft_id}/approve")
async def lead_approve_draft(lead_id: str, draft_id: str, user=Depends(require_business)):
    try:
        return await leads_engine.approve_draft(db, new_id, user["business_id"], lead_id, draft_id, user["email"])
    except leads_engine.LeadError as e:
        raise _lead_err(e)


@api_router.post("/leads/{lead_id}/drafts/{draft_id}/discard")
async def lead_discard_draft(lead_id: str, draft_id: str, user=Depends(require_business)):
    res = await db.leads.update_one({"lead_id": lead_id, "business_id": user["business_id"],
                                     "drafts": {"$elemMatch": {"draft_id": draft_id, "status": "pending"}}},
                                    {"$set": {"drafts.$.status": "discarded"}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Draft not found or already handled")
    return {"ok": True}


@api_router.post("/leads/{lead_id}/follow-up")
async def follow_up(lead_id: str, body: FollowUpInput, user=Depends(require_business)):
    """Direct owner-written follow-up: same consent rules as drafts, always simulated."""
    if body.channel not in leads_engine.CHANNELS:
        raise HTTPException(status_code=400, detail="Channel must be email or sms")
    bid = user["business_id"]
    lead = await db.leads.find_one({"lead_id": lead_id, "business_id": bid}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    draft = {"draft_id": new_id("drf"), "channel": body.channel, "message": body.message, "status": "pending",
             "created_at": now_utc().isoformat(), "written_by": "owner"}
    await db.leads.update_one({"lead_id": lead_id, "business_id": bid}, {"$push": {"drafts": draft}})
    try:
        return await leads_engine.approve_draft(db, new_id, bid, lead_id, draft["draft_id"], user["email"])
    except leads_engine.LeadError as e:
        await db.leads.update_one({"lead_id": lead_id, "business_id": bid}, {"$pull": {"drafts": {"draft_id": draft["draft_id"]}}})
        raise _lead_err(e)


# ---------- Bookings ----------
@api_router.get("/bookings")
async def list_bookings(user=Depends(get_current_user)):
    return await db.bookings.find({"business_id": user["business_id"]}, {"_id": 0}).sort("datetime", 1).to_list(500)


@api_router.post("/bookings")
async def create_booking(body: BookingInput, user=Depends(require_business)):
    biz = await db.businesses.find_one({"business_id": user["business_id"]}, {"_id": 0})
    try:
        start = sch.parse_iso(body.datetime)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date/time")
    duration = body.duration_min or sch.duration_for(biz, body.service)
    doc = sch.booking_doc(new_id, biz, body.customer_name, body.service, start, duration,
                          status=body.status or "confirmed", notes=body.notes or "", source="manual")
    try:
        return await sch.reserve(db, biz, doc)
    except sch.SchedulingError:
        cap = sch.config(biz)["capacity"]
        raise HTTPException(status_code=409, detail=f"That time is fully booked ({cap} of {cap} appointments already overlap). Choose another time.")


@api_router.put("/bookings/{booking_id}")
async def update_booking(booking_id: str, body: BookingInput, user=Depends(require_business)):
    bid = user["business_id"]
    biz = await db.businesses.find_one({"business_id": bid}, {"_id": 0})
    current = await db.bookings.find_one({"booking_id": booking_id, "business_id": bid}, {"_id": 0})
    if not current:
        raise HTTPException(status_code=404, detail="Booking not found")
    try:
        start = sch.parse_iso(body.datetime)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date/time")
    duration = body.duration_min or current.get("duration_min") or sch.duration_for(biz, body.service)
    end = start + timedelta(minutes=duration)
    updates = {**body.model_dump(exclude={"duration_min"}), "datetime": sch.iso(start), "start_utc": sch.iso(start),
               "end_utc": sch.iso(end), "duration_min": duration}
    async with sch.lock_for(bid):
        if updates["status"] not in ("cancelled", "canceled") and not await sch.is_free(db, biz, start, end, exclude_id=booking_id):
            raise HTTPException(status_code=409, detail="That time is fully booked. Choose another time.")
        await db.bookings.update_one({"booking_id": booking_id, "business_id": bid}, {"$set": updates})
    return await db.bookings.find_one({"booking_id": booking_id, "business_id": bid}, {"_id": 0})


@api_router.get("/bookings/availability")
async def booking_availability(date: str, service: str = "", user=Depends(require_business)):
    biz = await db.businesses.find_one({"business_id": user["business_id"]}, {"_id": 0})
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Use YYYY-MM-DD")
    duration = sch.duration_for(biz, service)
    return {"date": date, "duration_min": duration, "timezone": sch.config(biz)["timezone"],
            "slots": await sch.free_slots(db, biz, date, duration, limit=40)}


@api_router.delete("/bookings/{booking_id}")
async def delete_booking(booking_id: str, user=Depends(require_business)):
    res = await db.bookings.delete_one({"booking_id": booking_id, "business_id": user["business_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"ok": True}


# ---------- Customers ----------
@api_router.get("/customers")
async def list_customers(user=Depends(get_current_user)):
    return await db.customers.find({"business_id": user["business_id"], "archived": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.post("/customers")
async def create_customer(body: CustomerInput, user=Depends(require_business)):
    c = {"customer_id": new_id("cust"), "business_id": user["business_id"], **body.model_dump(),
         "created_at": now_utc().isoformat()}
    await db.customers.insert_one(c)
    c.pop("_id", None)
    return c


@api_router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: str, user=Depends(require_business)):
    res = await db.customers.delete_one({"customer_id": customer_id, "business_id": user["business_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"ok": True}


# ---------- Call logs (simulated phone reception) ----------
@api_router.get("/call-logs")
async def list_calls(user=Depends(get_current_user)):
    return await db.call_logs.find({"business_id": user["business_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api_router.post("/call-logs/simulate")
async def simulate_call(user=Depends(require_business)):
    if not user.get("business_id"):
        raise HTTPException(status_code=403, detail="No business workspace for this account")
    biz = await db.businesses.find_one({"business_id": user["business_id"]}, {"_id": 0})
    sys = (f"You are an AI phone receptionist for {biz['name']} ({biz.get('industry','local business')}). "
           f"Generate a realistic short phone call transcript between 'Caller' and 'AI Receptionist' where a "
           f"customer asks about services ({biz.get('services','general services')}) and books or inquires. "
           f"Then on a new line add 'SUMMARY:' with a one-sentence summary. Keep under 150 words.")
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"call_{uuid.uuid4().hex[:8]}", system_message=sys).with_model("gemini", "gemini-3.1-pro-preview")
    text = ""
    async for ev in chat.stream_message(UserMessage(text="Generate the simulated inbound call transcript now.")):
        if isinstance(ev, TextDelta):
            text += ev.content
        elif isinstance(ev, StreamDone):
            break
    transcript, summary = text, ""
    if "SUMMARY:" in text:
        parts = text.split("SUMMARY:")
        transcript, summary = parts[0].strip(), parts[1].strip()
    transcript = transcript.replace("**", "")
    summary = summary.replace("**", "")
    log = {"call_id": new_id("call"), "business_id": user["business_id"], "caller": "+1 (555) 0" + str(uuid.uuid4().int)[:3],
           "transcript": transcript, "summary": summary, "simulated": True, "created_at": now_utc().isoformat()}
    await db.call_logs.insert_one(log)
    log.pop("_id", None)
    return log


# ---------- AI Chat (public widget + dashboard preview) streaming ----------
def weekly_hours(biz):
    w = sch.config(biz)["weekly"]
    return ", ".join(f"{d.title()} {w[d][0]}-{w[d][1]}" if w[d] else f"{d.title()} closed" for d in sch.DAYS) + f" ({sch.config(biz)['timezone']})"

BOOKING_RULES = (
    "\n\nBOOKING RULES: You cannot book appointments yourself. Only the booking system can. "
    "Never say an appointment is booked, confirmed, reserved or scheduled unless the BOOKING SYSTEM RESULT says "
    "'BOOKING SAVED AND CONFIRMED'. Only offer times listed as available by the booking system. "
    "If the result says no appointment was created, say so clearly and offer the alternatives given. "
    "Do not invent booking references.")
async def _after_turn(biz, lead_id, inquiry_granted):
    try:
        await leads_engine.summarize(db, EMERGENT_LLM_KEY, biz, lead_id)
        if inquiry_granted:
            lead = await db.leads.find_one({"lead_id": lead_id, "business_id": biz["business_id"]}, {"_id": 0, "consent": 1, "drafts": 1})
            ch = ((lead.get("consent") or {}).get(leads_engine.INQUIRY) or {}).get("channel_to_use", "email")
            if not any(d.get("kind") == leads_engine.INQUIRY and d["status"] == "pending" for d in lead.get("drafts") or []):
                await leads_engine.create_draft(db, new_id, EMERGENT_LLM_KEY, biz, lead_id, ch, kind=leads_engine.INQUIRY)
    except Exception as e:
        logging.exception("post-turn lead work failed: %s", e)


@api_router.get("/chat/session-lead/{session_id}")
async def chat_session_lead(session_id: str, user=Depends(require_business)):
    lead = await db.leads.find_one({"business_id": user["business_id"], "chat_session_ids": session_id, "archived": {"$ne": True}},
                                   {"_id": 0, "lead_id": 1, "name": 1, "email": 1, "phone": 1, "status": 1})
    return {"lead": lead}


class MergeInput(BaseModel):
    primary_id: str
    duplicate_ids: List[str] = Field(min_length=1, max_length=20)
    confirm: bool = False


@api_router.get("/lead-duplicates")
async def lead_duplicates(user=Depends(require_business)):
    bid = user["business_id"]
    groups = await lead_merge.find_duplicate_groups(db, bid)
    for g in groups:
        g["leads"] = [await lead_merge.lead_bundle(db, bid, i) for i in g["lead_ids"]]
    return groups


@api_router.post("/lead-merges/preview")
async def lead_merge_preview(body: MergeInput, user=Depends(require_business)):
    try:
        return await lead_merge.preview(db, user["business_id"], body.primary_id, body.duplicate_ids)
    except leads_engine.LeadError as e:
        raise _lead_err(e)


@api_router.post("/lead-merges")
async def lead_merge_approve(body: MergeInput, user=Depends(require_business)):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Explicit approval required (confirm=true).")
    try:
        return await lead_merge.merge(db, new_id, user["business_id"], body.primary_id, body.duplicate_ids, user["email"])
    except leads_engine.LeadError as e:
        raise _lead_err(e)


@api_router.get("/lead-merges")
async def lead_merge_history(user=Depends(require_business)):
    return await db.lead_merges.find({"business_id": user["business_id"]},
                                     {"_id": 0, "merge_id": 1, "primary_id": 1, "duplicate_ids": 1, "approved_by": 1, "at": 1, "undone": 1,
                                      "primary_before.name": 1}).sort("at", -1).to_list(100)


@api_router.post("/lead-merges/{merge_id}/undo")
async def lead_merge_undo(merge_id: str, user=Depends(require_business)):
    try:
        return await lead_merge.undo(db, user["business_id"], merge_id, user["email"])
    except leads_engine.LeadError as e:
        raise _lead_err(e)


@api_router.get("/lead-capture-errors")
async def lead_capture_errors(user=Depends(require_business)):
    return await db.lead_capture_errors.find({"business_id": user["business_id"], "resolved": False}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.post("/lead-capture-errors/{error_id}/resolve")
async def resolve_capture_error(error_id: str, user=Depends(require_business)):
    await db.lead_capture_errors.update_one({"error_id": error_id, "business_id": user["business_id"]}, {"$set": {"resolved": True}})
    return {"ok": True}


@api_router.post("/chat/stream")
async def chat_stream(body: ChatInput, request: Request):
    business_id = body.business_id
    public = bool(business_id)
    if not business_id:
        try:
            user = await get_current_user(request)
        except HTTPException:
            raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again to chat.")
        business_id = user.get("business_id")
        if not business_id:
            raise HTTPException(status_code=403, detail="This account isn't linked to a business workspace. Sign in as a business owner to use the chat assistant.")
    biz = await db.businesses.find_one({"business_id": business_id}, {"_id": 0})
    if not biz:
        raise HTTPException(status_code=404, detail="We couldn't find your business profile. Please refresh or contact support.")
    if public and not biz.get("chat_enabled"):
        raise HTTPException(status_code=403, detail="Chat assistant is disabled for this business")
    sys = (f"You are the AI assistant for {biz['name']}, a {biz.get('industry','local business')}. "
           f"Be {biz.get('ai_tone','warm and professional')}. "
           f"Business hours (authoritative booking hours): {weekly_hours(biz)}. Services: {biz.get('services','')}. "
           f"Address: {biz.get('address','')}. Phone: {biz.get('phone','')}. "
           f"FAQs: {biz.get('faqs','')}. Help customers with questions, bookings and info. "
           f"If asked something unknown, offer to take their details for follow-up. "
           f"When a customer wants to book or be contacted, politely ask for their name and email or phone number. "
           f"Keep replies concise and in plain text without markdown symbols.")
    history = await db.chat_messages.find({"business_id": business_id, "session_id": body.session_id},
                                          {"_id": 0, "role": 1, "content": 1}).sort("created_at", -1).to_list(40)
    history.reverse()
    if history:
        sys += "\n\nConversation so far:\n" + "\n".join(f"{h['role'].capitalize()}: {h['content']}" for h in history)

    await db.chat_messages.insert_one({"business_id": business_id, "session_id": body.session_id,
                                       "role": "user", "content": body.message, "created_at": now_utc().isoformat()})

    async def gen():
        result, p = None, {}
        try:
            p = await booking_agent.plan(EMERGENT_LLM_KEY, biz, history, body.message)
            result = await booking_agent.execute(db, new_id, biz, p, body.session_id)
        except Exception as e:
            logging.exception("booking workflow failed: %s", e)
            result = {"kind": "error", "facts": "The booking system failed. Do NOT confirm anything; say no appointment was created.",
                      "footer": "\n\nNo appointment was created. Please try again in a moment."}
        lead, consent_event, ask_kind, capture_failed = None, None, None, False
        try:
            consent_event = await leads_engine.handle_chat_consent(db, biz, body.session_id, body.message, body.consent)
            rx = leads_engine.extract_contact(body.message)
            p = p if isinstance(p, dict) else {}
            lead = await leads_engine.upsert_lead(
                db, new_id, biz, name=p.get("name") or rx["name"], email=p.get("email") or rx["email"],
                phone=p.get("phone") or rx["phone"], session_id=body.session_id,
                interests=[s for s in [(sch.match_service(biz, p.get("service")) or {}).get("name")] if s])
            ask_kind = await leads_engine.next_prompt(db, biz, body.session_id, lead)
        except Exception as e:
            logging.exception("lead capture failed: %s", e)
            rx = leads_engine.extract_contact(body.message)
            if rx["email"] or rx["phone"]:
                capture_failed = True
                await db.lead_capture_errors.insert_one({
                    "error_id": new_id("lce"), "business_id": business_id, "session_id": body.session_id,
                    "message": body.message[:2000], "error": str(e)[:500], "resolved": False, "created_at": now_utc().isoformat()})
        lead_note = ""
        if lead:
            lead_note = ("\n\nCRM: the customer's contact details are saved. Do not ask for consent or permission to contact them yourself; "
                         "the system adds those questions. ")
        elif (p.get("email") or p.get("phone")) and not p.get("name"):
            lead_note = "\n\nCRM: the customer shared contact details but no name. Politely ask for their name."
        if consent_event == "opted_out":
            lead_note += "\n\nThe customer opted out of marketing messages. Acknowledge briefly that they won't receive offers."
        elif consent_event == "answered":
            lead_note += "\n\nThe customer just answered the marketing consent question; acknowledge their choice briefly."
        elif consent_event == "inquiry_granted":
            lead_note += "\n\nThe customer agreed to receive a personal reply about their inquiry. Thank them; say the team will review and reply. Do not claim anything was sent."
        elif consent_event == "inquiry_declined":
            lead_note += "\n\nThe customer declined a personal reply. Acknowledge politely."
        reply_sys = sys + BOOKING_RULES + lead_note + (f"\n\nBOOKING SYSTEM RESULT (authoritative, verified by the backend): {result['facts']}" if result else
                                                       "\n\nBOOKING SYSTEM RESULT: no booking action was taken this turn. Nothing has been booked.")
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"{business_id}_{body.session_id}", system_message=reply_sys).with_model("gemini", "gemini-3.1-pro-preview")
        full = ""
        try:
            async for ev in chat.stream_message(UserMessage(text=body.message)):
                if isinstance(ev, TextDelta):
                    full += ev.content
                    yield ev.content
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:
            logging.exception("chat stream failed: %s", e)
            msg = "Sorry, I'm having trouble responding right now. Please try again in a moment."
            prefix = "\n\n" if full else ""
            full += prefix + msg
            yield prefix + msg
        tail = (result or {}).get("footer", "") + booking_agent.guard_footer(result, full)
        if ask_kind:
            tail += "\n\n" + await leads_engine.mark_prompted(db, biz, body.session_id, ask_kind, lead)
        if capture_failed:
            tail += ("\n\nNote: we couldn't save your contact details because of a technical problem. "
                     "Your message has been kept for our team, but please also contact us directly so we don't miss you.")
        if tail:
            full += tail
            yield tail
        await db.chat_messages.insert_one({"business_id": business_id, "session_id": body.session_id,
                                          "role": "assistant", "content": full, "created_at": now_utc().isoformat()})
        if lead:
            asyncio.create_task(_after_turn(biz, lead["lead_id"], consent_event == "inquiry_granted"))

    return StreamingResponse(gen(), media_type="text/plain",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- Dashboard stats ----------
@api_router.get("/stats")
async def stats(user=Depends(get_current_user)):
    bid = user["business_id"]
    leads = await db.leads.count_documents({"business_id": bid})
    new_leads = await db.leads.count_documents({"business_id": bid, "status": "new"})
    bookings = await db.bookings.count_documents({"business_id": bid})
    customers = await db.customers.count_documents({"business_id": bid})
    calls = await db.call_logs.count_documents({"business_id": bid})
    chats = await db.chat_messages.count_documents({"business_id": bid, "role": "user"})
    return {"leads": leads, "new_leads": new_leads, "bookings": bookings,
            "customers": customers, "calls": calls, "chats": chats}


# ---------- Plans (public read + admin edit) ----------
@api_router.get("/plans")
async def list_plans():
    return await db.plans.find({}, {"_id": 0}).sort("monthly_fee", 1).to_list(50)


@api_router.post("/admin/plans")
async def create_plan(body: PlanInput, user=Depends(require_admin)):
    p = {"plan_id": new_id("plan"), **body.model_dump(), "is_default": False}
    await db.plans.insert_one(p)
    p.pop("_id", None)
    return p


@api_router.put("/admin/plans/{plan_id}")
async def update_plan(plan_id: str, body: PlanInput, user=Depends(require_admin)):
    await db.plans.update_one({"plan_id": plan_id}, {"$set": body.model_dump()})
    return await db.plans.find_one({"plan_id": plan_id}, {"_id": 0})


# ---------- Admin ----------
@api_router.get("/admin/businesses")
async def admin_businesses(user=Depends(require_admin)):
    businesses = await db.businesses.find({}, {"_id": 0}).to_list(1000)
    for b in businesses:
        owner = await db.users.find_one({"user_id": b["owner_id"]}, {"_id": 0})
        b["owner_email"] = owner["email"] if owner else ""
        b["owner_name"] = owner["name"] if owner else ""
        b["leads_count"] = await db.leads.count_documents({"business_id": b["business_id"]})
        b["bookings_count"] = await db.bookings.count_documents({"business_id": b["business_id"]})
    return businesses


@api_router.put("/admin/businesses/{business_id}/status")
async def admin_set_status(business_id: str, body: dict, user=Depends(require_admin)):
    updates = {}
    if body.get("subscription_status") in ("trialing", "active", "past_due", "canceled"):
        updates["subscription_status"] = body["subscription_status"]
    if "setup_fee_paid" in body:
        updates["setup_fee_paid"] = bool(body["setup_fee_paid"])
    if "plan_id" in body:
        updates["plan_id"] = body["plan_id"]
    res = await db.businesses.update_one({"business_id": business_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Business not found")
    return await db.businesses.find_one({"business_id": business_id}, {"_id": 0})


@api_router.get("/admin/stats")
async def admin_stats(user=Depends(require_admin)):
    real = {"is_demo": {"$ne": True}}
    total_biz = await db.businesses.count_documents(real)
    active = await db.businesses.count_documents({**real, "subscription_status": "active"})
    plans = await db.plans.find({}, {"_id": 0}).to_list(50)
    plan_map = {p["plan_id"]: p["monthly_fee"] for p in plans}
    default_fee = next((p["monthly_fee"] for p in plans if p.get("is_default")), 0)
    mrr = 0
    async for b in db.businesses.find({**real, "subscription_status": "active"}, {"_id": 0, "plan_id": 1}):
        mrr += plan_map.get(b.get("plan_id"), default_fee)
    return {"total_businesses": total_biz, "active_subscriptions": active,
            "trialing": await db.businesses.count_documents({**real, "subscription_status": "trialing"}),
            "estimated_mrr": mrr, "demo_workspaces": await db.businesses.count_documents({"is_demo": True})}


# ---------- Demo workspace ----------
@api_router.post("/admin/demo-workspace/enter")
async def enter_demo_workspace(user=Depends(require_admin)):
    demo = await db.businesses.find_one({"is_demo": True}, {"_id": 0})
    if not demo:
        raise HTTPException(status_code=404, detail="Demo workspace is not available.")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"active_business_id": demo["business_id"]}})
    return {"business": demo}


@api_router.post("/admin/demo-workspace/exit")
async def exit_demo_workspace(user=Depends(require_admin)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$unset": {"active_business_id": ""}})
    return {"ok": True}


@api_router.post("/demo/reset")
async def reset_demo(user=Depends(require_business)):
    bid = user["business_id"]
    biz = await db.businesses.find_one({"business_id": bid, "is_demo": True}, {"_id": 0, "business_id": 1})
    if not biz:
        raise HTTPException(status_code=403, detail="Only demo workspaces can be reset.")
    for coll in (db.leads, db.bookings, db.chat_messages, db.chat_sessions):
        await coll.delete_many({"business_id": bid})
    await db.customers.delete_many({"business_id": bid, "$or": [{"created_by": "ai_lead"}, {"notes": {"$regex": r"^(Booked |Created from AI-captured lead)"}}]})
    await db.customers.update_many({"business_id": bid}, {"$unset": {"lead_id": ""}})
    for c in DEMO_CUSTOMERS:
        await db.customers.update_one({"business_id": bid, "email": c["email"]}, {"$set": c, "$setOnInsert": {
            "customer_id": new_id("cust"), "business_id": bid, "created_at": now_utc().isoformat()}}, upsert=True)
    await seed_demo_records(bid)
    return {"ok": True}


# ---------- Demo & contact requests ----------
@api_router.post("/demo-requests")
async def create_demo_request(body: DemoRequestInput, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip()
    since = (now_utc() - timedelta(minutes=10)).isoformat()
    if await db.demo_requests.count_documents({"ip": ip, "created_at": {"$gte": since}}) >= 5:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again in a few minutes.")
    req = {"request_id": new_id("req"), **body.model_dump(), "status": "new",
           "alert_status": "simulated-sent", "ip": ip, "created_at": now_utc().isoformat()}
    await db.demo_requests.insert_one(req)
    req.pop("_id", None)
    label = "Demo request" if body.kind == "demo" else "Contact message"
    await db.notifications.insert_one({
        "notification_id": new_id("ntf"), "channel": "email", "to": "admin@vantora.ai",
        "subject": f"[Vantora AI] New {label.lower()} from {body.name}",
        "body": f"{body.name} <{body.email}> {('· ' + body.company) if body.company else ''}\n{body.message}",
        "status": "simulated-sent", "related_id": req["request_id"], "created_at": now_utc().isoformat()})
    return {"request_id": req["request_id"], "status": "received", "alert_status": "simulated-sent"}


@api_router.get("/admin/demo-requests")
async def admin_demo_requests(user=Depends(require_admin)):
    return await db.demo_requests.find({}, {"_id": 0, "ip": 0}).sort("created_at", -1).to_list(200)


@api_router.put("/admin/demo-requests/{request_id}")
async def admin_update_demo_request(request_id: str, body: dict, user=Depends(require_admin)):
    status = body.get("status")
    if status not in ("new", "contacted", "closed"):
        raise HTTPException(status_code=400, detail="Invalid status")
    res = await db.demo_requests.update_one({"request_id": request_id}, {"$set": {"status": status}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"request_id": request_id, "status": status}


@api_router.get("/")
async def root():
    return {"message": "Vantora AI API"}


app.include_router(api_router)

# Additive pilot module; existing authentication, lead records and booking code are unchanged.
import sales_pilot
app.include_router(sales_pilot.router(db, get_current_user))
app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
async def seed():
    if await db.plans.count_documents({}) == 0:
        await db.plans.insert_many([
            {"plan_id": new_id("plan"), "name": "Starter", "setup_fee": 499, "monthly_fee": 299,
             "features": ["AI Phone Reception", "Website Chat Assistant", "Up to 500 leads/mo",
                          "Appointment Scheduling", "Email & SMS Follow-ups", "Business Dashboard"],
             "is_default": True},
            {"plan_id": new_id("plan"), "name": "Growth", "setup_fee": 799, "monthly_fee": 549,
             "features": ["Everything in Starter", "Unlimited leads", "Multi-location support",
                          "Priority AI responses", "Calendar integrations", "Advanced analytics"],
             "is_default": False},
            {"plan_id": new_id("plan"), "name": "Enterprise", "setup_fee": 1499, "monthly_fee": 999,
             "features": ["Everything in Growth", "Dedicated success manager", "Custom AI training",
                          "White-glove onboarding", "API access", "SLA guarantees"],
             "is_default": False},
        ])
    admin_pw, demo_pw = os.environ["ADMIN_PASSWORD"], os.environ["DEMO_OWNER_PASSWORD"]
    for admin_email in ("admin@localbiz.ai", "admin@vantora.ai"):
        existing = await db.users.find_one({"email": admin_email}, {"_id": 0, "password_hash": 1})
        if not existing:
            await db.users.insert_one({
                "user_id": new_id("user"), "name": "Platform Admin", "email": admin_email,
                "password_hash": hash_pw(admin_pw), "role": "admin", "business_id": None,
                "provider": "password", "picture": "", "created_at": now_utc().isoformat()})
        elif not verify_pw(admin_pw, existing.get("password_hash") or ""):
            await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_pw(admin_pw), "password_rotated_at": now_utc().isoformat()}})

    # Seed / upgrade the demo business (Aura Luxury Spa)
    owner = await db.users.find_one({"email": "demo@aurasalon.com"}, {"_id": 0})
    if not owner:
        owner, biz = await create_business_and_owner(
            "Sophia Laurent", "demo@aurasalon.com", hash_pw(demo_pw), "Aura Luxury Spa")
        await seed_demo_records(biz["business_id"])
    elif not verify_pw(demo_pw, owner.get("password_hash") or ""):
        await db.users.update_one({"email": "demo@aurasalon.com"}, {"$set": {"password_hash": hash_pw(demo_pw), "password_rotated_at": now_utc().isoformat()}})
    await db.login_attempts.create_index("identifier")
    await db.users.create_index("email", unique=True)
    bid = owner["business_id"]
    if not await db.businesses.find_one({"business_id": bid, "is_demo": True}):
        await db.businesses.update_one({"business_id": bid}, {"$set": {**DEMO_PROFILE, "is_demo": True}})
    if not await db.businesses.find_one({"business_id": bid, "scheduling": {"$exists": True}}):
        await db.businesses.update_one({"business_id": bid}, {"$set": DEMO_SCHEDULING})
    # Backfill scheduling fields on legacy bookings so conflict checks cover them
    async for b in db.bookings.find({"start_utc": {"$exists": False}}, {"_id": 0}):
        bz = await db.businesses.find_one({"business_id": b["business_id"]}, {"_id": 0}) or {}
        try:
            raw = sch.datetime.fromisoformat(b["datetime"].replace("Z", "+00:00"))
            start = raw if raw.tzinfo else raw.replace(tzinfo=ZoneInfo(sch.config(bz)["timezone"]))
        except (ValueError, KeyError):
            continue
        dur = sch.duration_for(bz, b.get("service", "")) if bz else 60
        await db.bookings.update_one({"booking_id": b["booking_id"]}, {"$set": {
            "datetime": sch.iso(start), "start_utc": sch.iso(start), "end_utc": sch.iso(start + timedelta(minutes=dur)),
            "duration_min": dur, "source": b.get("source", "manual")}})
    await db.bookings.create_index([("business_id", 1), ("start_utc", 1)])
    await db.bookings.create_index("booking_id", unique=True)
    async for ld in db.leads.find({}, {"_id": 0}):
        fix = leads_engine.backfill_fields(ld)
        if fix:
            await db.leads.update_one({"lead_id": ld["lead_id"]}, {"$set": fix})
    await db.leads.create_index([("business_id", 1), ("email_norm", 1)])
    async for ld in db.leads.find({"email_key": {"$exists": False}}, {"_id": 0, "lead_id": 1, "business_id": 1, "email_norm": 1, "phone_norm": 1, "archived": 1}):
        keys = {"email_key": None, "phone_key": None} if ld.get("archived") else leads_engine.contact_keys(ld["business_id"], ld.get("email_norm"), ld.get("phone_norm"))
        for k, v in keys.items():
            try:
                await db.leads.update_one({"lead_id": ld["lead_id"]}, {"$set": {k: v}})
            except DuplicateKeyError:
                await db.leads.update_one({"lead_id": ld["lead_id"]}, {"$set": {k: None}})  # existing duplicate: left for manual review
    for k in ("email_key", "phone_key"):
        await db.leads.create_index(k, unique=True, name=f"uniq_active_{k}", partialFilterExpression={k: {"$type": "string"}})
    await db.leads.create_index([("business_id", 1), ("phone_norm", 1)])
    await db.leads.create_index([("business_id", 1), ("chat_session_ids", 1)])
    await db.chat_sessions.create_index([("business_id", 1), ("session_id", 1)], unique=True)
    if await db.customers.count_documents({"business_id": bid}) < 3:
        await db.customers.delete_many({"business_id": bid})
        await db.customers.insert_many([
            {"customer_id": new_id("cust"), "business_id": bid, **c, "created_at": now_utc().isoformat()}
            for c in DEMO_CUSTOMERS])


DEMO_PROFILE = {
    "industry": "Luxury Spa & Salon",
    "services": ("Signature Aura Facial (60 min, $185); Hydra-Glow Facial (75 min, $220); "
                 "Deep Tissue Massage (60 min, $160); Hot Stone Ritual (90 min, $240); "
                 "Couples Massage (60 min, $340); Precision Cut & Style ($120); Balayage Color (from $280); "
                 "Luxe Manicure & Pedicure (90 min, $135); Bridal Beauty Package (from $650)"),
    "hours": "Mon-Fri 9am-8pm, Sat 9am-6pm, Sun 10am-4pm",
    "phone": "+1 (555) 010-2468", "address": "120 Example Avenue, Suite 4, New York, NY (fictional)",
    "faqs": ("Complimentary valet parking. Walk-ins welcome when available, appointments recommended. "
             "Gift cards available in any amount. 24-hour cancellation policy. "
             "Monthly membership: one 60-minute service plus 15% off retail for $149/month."),
    "ai_tone": "warm, elegant and attentive",
    "ai_greeting": "Thank you for calling Aura Luxury Spa. How may I pamper you today?",
    "chat_enabled": True, "phone_reception_enabled": True, "follow_up_consent": True,
}

DEMO_SCHEDULING = {
    "scheduling": {"timezone": "America/New_York", "capacity": 3, "slot_minutes": 30, "default_duration": 60,
                   "weekly": {"mon": ["09:00", "20:00"], "tue": ["09:00", "20:00"], "wed": ["09:00", "20:00"],
                              "thu": ["09:00", "20:00"], "fri": ["09:00", "20:00"], "sat": ["09:00", "18:00"],
                              "sun": ["10:00", "16:00"]}},
    "service_catalog": [
        {"name": "Signature Aura Facial", "duration_min": 60, "price": "$185"},
        {"name": "Hydra-Glow Facial", "duration_min": 75, "price": "$220"},
        {"name": "Deep Tissue Massage", "duration_min": 60, "price": "$160"},
        {"name": "Hot Stone Ritual", "duration_min": 90, "price": "$240"},
        {"name": "Couples Massage", "duration_min": 60, "price": "$340"},
        {"name": "Precision Cut & Style", "duration_min": 60, "price": "$120"},
        {"name": "Balayage Color", "duration_min": 150, "price": "from $280"},
        {"name": "Luxe Manicure & Pedicure", "duration_min": 90, "price": "$135"},
        {"name": "Bridal Beauty Package", "duration_min": 180, "price": "from $650"},
    ],
}

DEMO_CUSTOMERS = [
    {"name": "Olivia Chen", "email": "olivia.chen@example.com", "phone": "+1 555 010 1001", "notes": "VIP · prefers Hydra-Glow Facial"},
    {"name": "Marcus Webb", "email": "marcus.webb@example.com", "phone": "+1 555 010 1002", "notes": "Monthly massage member"},
    {"name": "Priya Raman", "email": "priya.raman@example.com", "phone": "+1 555 010 1003", "notes": "Balayage every 8 weeks"},
    {"name": "Elena Rossi", "email": "elena.rossi@example.com", "phone": "+1 555 010 1004", "notes": "Bridal package · June wedding"},
]


async def seed_demo_records(bid):
    biz = await db.businesses.find_one({"business_id": bid}, {"_id": 0})
    if not biz.get("scheduling"):
        biz = {**biz, **DEMO_SCHEDULING}
    tz = sch.config(biz)["timezone"]
    day = lambda d: (datetime.now(ZoneInfo(tz)) + timedelta(days=d)).strftime("%Y-%m-%d")  # noqa: E731
    leads = [
        {"lead_id": new_id("lead"), "business_id": bid, "name": "Isabella Moreau", "email": "isabella.m@example.com",
         "phone": "+1 555 010 2001", "source": "website chat", "status": "new", "notes": "Asked about the Bridal Beauty Package",
         "service_interests": ["Bridal Beauty Package"], "summary": "Fictional sample: asked about the Bridal Beauty Package for a June wedding.",
         "follow_ups": [], "created_at": now_utc().isoformat()},
        {"lead_id": new_id("lead"), "business_id": bid, "name": "James Carter", "email": "james.c@example.com",
         "phone": "+1 555 010 2002", "source": "phone", "status": "contacted", "notes": "Interested in monthly membership",
         "consent": {"email": {"granted": True, "text": "Fictional sample consent (demo data).", "source": "demo seed", "at": now_utc().isoformat()}, "sms": None},
         "follow_ups": [{"id": new_id("fu"), "channel": "email", "message": "Hi James, thank you for calling Aura. Here are our membership details.",
                         "status": "simulated-sent", "simulated": True, "delivered": False, "sent_at": now_utc().isoformat()}],
         "created_at": now_utc().isoformat()},
        {"lead_id": new_id("lead"), "business_id": bid, "name": "Sofia Alvarez", "email": "", "phone": "+1 555 010 2003",
         "source": "website chat", "status": "qualified", "notes": "Wants a couples massage for an anniversary",
         "service_interests": ["Couples Massage"], "follow_ups": [], "created_at": now_utc().isoformat()},
    ]
    await db.leads.insert_many([{**ld, **leads_engine.backfill_fields(ld)} for ld in leads])
    await db.bookings.insert_many([
        sch.booking_doc(new_id, biz, name, svc, sch.local_to_utc(day(d), t, tz), sch.duration_for(biz, svc), status=st, notes=n)
        for name, svc, d, t, st, n in [
            ("Olivia Chen", "Hydra-Glow Facial", 1, "14:00", "confirmed", "VIP client"),
            ("Marcus Webb", "Deep Tissue Massage", 2, "16:00", "confirmed", "Prefers afternoon"),
            ("Priya Raman", "Balayage Color", 4, "11:00", "pending", ""),
        ]])


@app.on_event("shutdown")
async def shutdown():
    client.close()
