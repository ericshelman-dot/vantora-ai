"""Appointment scheduling engine: hours, durations, time zones, capacity and conflict checks."""
import asyncio
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_SCHEDULING = {
    "timezone": "America/New_York", "capacity": 1, "slot_minutes": 30, "default_duration": 60,
    "weekly": {"mon": ["09:00", "18:00"], "tue": ["09:00", "18:00"], "wed": ["09:00", "18:00"],
               "thu": ["09:00", "18:00"], "fri": ["09:00", "18:00"], "sat": None, "sun": None},
}
ACTIVE = {"status": {"$nin": ["cancelled", "canceled"]}}
_locks: dict = {}


class SchedulingError(Exception):
    pass


def lock_for(business_id):
    return _locks.setdefault(business_id, asyncio.Lock())


def config(biz):
    cfg = {**DEFAULT_SCHEDULING, **(biz.get("scheduling") or {})}
    cfg["weekly"] = {**DEFAULT_SCHEDULING["weekly"], **((biz.get("scheduling") or {}).get("weekly") or {})}
    cfg["capacity"] = max(1, int(cfg["capacity"]))
    return cfg


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def parse_iso(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def local_to_utc(date_str, time_str, tz):
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def match_service(biz, name):
    catalog = biz.get("service_catalog") or []
    if not name:
        return None
    n = name.lower().strip()
    for s in catalog:
        if s["name"].lower() == n:
            return s
    words = set(re.findall(r"[a-z]+", n)) - {"the", "a", "an", "and", "service", "appointment"}
    best, score = None, 0
    for s in catalog:
        sc = len(words & set(re.findall(r"[a-z]+", s["name"].lower())))
        if sc > score:
            best, score = s, sc
    return best


def duration_for(biz, service):
    s = match_service(biz, service)
    return int(s["duration_min"]) if s else config(biz)["default_duration"]


def hours_for(cfg, local_dt):
    span = cfg["weekly"].get(DAYS[local_dt.weekday()])
    if not span:
        return None
    o = datetime.strptime(span[0], "%H:%M").time()
    c = datetime.strptime(span[1], "%H:%M").time()
    return local_dt.replace(hour=o.hour, minute=o.minute, second=0, microsecond=0), local_dt.replace(hour=c.hour, minute=c.minute, second=0, microsecond=0)


def within_hours(cfg, start_utc, end_utc):
    tz = ZoneInfo(cfg["timezone"])
    ls, le = start_utc.astimezone(tz), end_utc.astimezone(tz)
    h = hours_for(cfg, ls)
    return bool(h) and ls >= h[0] and le <= h[1]


async def overlap_count(db, business_id, start_utc, end_utc, exclude_id=None):
    q = {"business_id": business_id, **ACTIVE, "start_utc": {"$lt": iso(end_utc)}, "end_utc": {"$gt": iso(start_utc)}}
    if exclude_id:
        q["booking_id"] = {"$ne": exclude_id}
    return await db.bookings.count_documents(q)


async def is_free(db, biz, start_utc, end_utc, exclude_id=None):
    return await overlap_count(db, biz["business_id"], start_utc, end_utc, exclude_id) < config(biz)["capacity"]


async def free_slots(db, biz, date_str, duration, limit=6, after=None):
    cfg = config(biz)
    tz = ZoneInfo(cfg["timezone"])
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    h = hours_for(cfg, day)
    if not h:
        return []
    out, t, now = [], h[0], datetime.now(timezone.utc) + timedelta(minutes=30)
    while t + timedelta(minutes=duration) <= h[1] and len(out) < limit:
        su = t.astimezone(timezone.utc)
        if su >= now and (after is None or su >= after) and await is_free(db, biz, su, su + timedelta(minutes=duration)):
            out.append(t.strftime("%H:%M"))
        t += timedelta(minutes=cfg["slot_minutes"])
    return out


async def alternatives(db, biz, date_str, duration, around_utc=None, limit=5):
    tz = ZoneInfo(config(biz)["timezone"])
    start = datetime.strptime(date_str, "%Y-%m-%d").date()
    out = []
    for d in range(0, 8):
        ds = (start + timedelta(days=d)).isoformat()
        slots = await free_slots(db, biz, ds, duration, limit=60)
        if d == 0 and around_utc:
            target = around_utc.astimezone(tz)
            slots.sort(key=lambda s: abs((datetime.strptime(f"{ds} {s}", "%Y-%m-%d %H:%M").replace(tzinfo=tz) - target).total_seconds()))
        out += [{"date": ds, "time": s} for s in slots[: limit - len(out)]]
        if len(out) >= limit:
            break
    return out


def describe(biz, start_utc):
    return start_utc.astimezone(ZoneInfo(config(biz)["timezone"])).strftime("%A, %B %-d, %Y at %-I:%M %p")


def booking_doc(new_id, biz, customer_name, service, start_utc, duration, status="confirmed", notes="", source="manual", **extra):
    return {"booking_id": new_id("bk"), "business_id": biz["business_id"], "customer_name": customer_name,
            "service": service, "datetime": iso(start_utc), "start_utc": iso(start_utc),
            "end_utc": iso(start_utc + timedelta(minutes=duration)), "duration_min": duration,
            "timezone": config(biz)["timezone"], "status": status, "notes": notes, "source": source,
            "created_at": iso(datetime.now(timezone.utc)), **extra}


async def reserve(db, biz, doc):
    """Atomically (per business) re-check capacity and insert. Raises SchedulingError on conflict."""
    start, end = parse_iso(doc["start_utc"]), parse_iso(doc["end_utc"])
    async with lock_for(biz["business_id"]):
        if not await is_free(db, biz, start, end):
            raise SchedulingError("unavailable")
        await db.bookings.insert_one(doc)
    doc.pop("_id", None)
    saved = await db.bookings.find_one({"booking_id": doc["booking_id"], "business_id": biz["business_id"]}, {"_id": 0})
    if not saved:
        raise SchedulingError("not_saved")
    return saved
