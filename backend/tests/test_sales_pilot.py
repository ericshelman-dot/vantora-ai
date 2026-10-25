"""Isolated pilot safety tests. No network, MongoDB, model, or customer records."""
import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sales_pilot import router


class Collection:
    def __init__(self):
        self.rows = []

    def matching(self, query):
        def matches(row, q):
            for k, v in q.items():
                if k == "$or":
                    if not any(matches(row, child) for child in v):
                        return False
                elif isinstance(v, dict) and "$exists" in v:
                    if (k in row) != v["$exists"]:
                        return False
                elif row.get(k) != v:
                    return False
            return True
        return [r for r in self.rows if matches(r, query)]

    def find(self, query, projection=None):
        rows = copy.deepcopy(self.matching(query))
        async def result(n):
            return rows[:n]
        return SimpleNamespace(to_list=result)

    async def find_one(self, query, projection=None):
        rows = self.matching(query)
        return copy.deepcopy(rows[0]) if rows else None

    async def insert_one(self, row):
        self.rows.append(copy.deepcopy(row))

    async def update_one(self, query, change, upsert=False):
        rows = self.matching(query)
        if not rows and upsert:
            self.rows.append(dict(query))
            rows = [self.rows[-1]]
        if rows:
            rows[0].update(copy.deepcopy(change.get("$set", {})))
            for k, v in change.get("$push", {}).items():
                rows[0].setdefault(k, []).append(copy.deepcopy(v))
        return SimpleNamespace(matched_count=len(rows))


@pytest.fixture
def pilot():
    db = SimpleNamespace(sales_pilot_demo=Collection(), sales_pilot_live=Collection(), sales_pilot_consents=Collection())
    identity = {"user_id": "owner-a", "business_id": "salon-a"}
    async def auth():
        return identity
    app = FastAPI()
    app.include_router(router(db, auth))
    with TestClient(app) as client:
        yield client, db, identity


def add(c, **overrides):
    body = dict(name="Alex", company="Fictional Salon", service="Inquiry demo", source="Synthetic", email="alex@example.com",
                need="Missed inquiries", permission="granted", permission_evidence="Synthetic permission", decision_maker=True)
    body.update(overrides)
    return c.post("/api/sales-pilot/prospects", json=body)


def act(c, p, kind, **values):
    return c.post(f"/api/sales-pilot/prospects/{p['prospect_id']}/actions", json={"kind": kind, "expected_revision": p["revision"], **values})


def test_draft_edit_approval_never_sends_and_stale_approval_rejected(pilot):
    c, db, _ = pilot
    p = add(c).json()
    draft = act(c, p, "draft").json()
    assert "Fictional Salon" in draft["draft"]["message"]
    edited = act(c, draft, "edit_draft", text="Owner reviewed message").json()
    assert act(c, draft, "approve_draft").status_code == 409
    approved = act(c, edited, "approve_draft").json()
    assert approved["draft"]["delivery"] == "not_sent"
    assert approved["draft"]["approved_by"] == "owner-a"
    assert len(approved["audit"]) == 4
    assert act(c, approved, "approve_draft").status_code == 409


@pytest.mark.parametrize("permission", ["unknown", "opted_out"])
def test_outreach_blocked_without_permission(pilot, permission):
    c, _, _ = pilot
    p = add(c, permission=permission).json()
    assert act(c, p, "draft").status_code == 409
    assert act(c, p, "stage", stage="contacted", text="called").status_code == 409


def test_opt_out_invalidates_draft_and_blocks_approval(pilot):
    c, _, _ = pilot
    p = act(c, add(c).json(), "draft").json()
    p = act(c, p, "response", text="Please stop contacting me", outcome="opt_out").json()
    assert p["draft"]["status"] == "blocked_opt_out"
    assert act(c, p, "approve_draft").status_code == 409
    assert act(c, p, "draft").status_code == 409


def test_live_gate_demo_separation_and_tenant_isolation(pilot):
    c, db, identity = pilot
    p = add(c).json()
    body = {k: p[k] for k in ["name", "company", "service", "source"]}
    assert c.post("/api/sales-pilot/prospects?mode=live", json=body).status_code == 403
    assert not db.sales_pilot_live.rows
    identity["business_id"] = "salon-b"
    assert c.get("/api/sales-pilot").json()["prospects"] == []
    assert act(c, p, "draft").status_code == 404


def test_explicit_live_setup_and_no_calendar_shortcut(pilot):
    c, db, identity = pilot
    setup = dict(business_name="Authorized Test Salon", owner_name="Owner", services="Approved demo",
                 timezone="America/New_York", consent_evidence="Owner explicitly agreed in test fixture", owner_consented=True)
    assert c.post("/api/sales-pilot/setup", json={**setup, "owner_consented": False}).status_code == 422
    assert c.post("/api/sales-pilot/setup", json=setup).status_code == 200
    assert db.sales_pilot_consents.rows[0]["audit"][0]["actor"] == "owner-a"
    assert c.get("/api/sales-pilot?mode=live").json()["ready"]
    assert c.get("/api/sales-pilot?mode=live").json()["prospects"] == []
    live = c.post("/api/sales-pilot/prospects?mode=live", json={"name": "Approved Example", "company": "Authorized Test", "source": "Fixture", "service": "Demo"})
    assert live.status_code == 200
    assert c.post("/api/sales-pilot/pause").status_code == 200
    assert not c.get("/api/sales-pilot?mode=live").json()["ready"]
    assert c.get("/api/sales-pilot?mode=live").json()["prospects"] == []
    assert len(db.sales_pilot_live.rows) == 1
    p = add(c).json()
    assert act(c, p, "booking_proposal", starts_at="2030-01-01T10:00:00").status_code == 422
    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    p = act(c, p, "booking_proposal", starts_at=start).json()
    assert p["booking_proposal"]["calendar_event_created"] is False
    assert act(c, p, "stage", stage="booked").status_code == 409
    identity["demo_mode"] = True
    assert c.post("/api/sales-pilot/setup", json=setup).status_code == 403


def test_reporting_requires_evidence_and_separates_revenue(pilot):
    c, _, _ = pilot
    p = add(c).json()
    assert act(c, p, "stage", stage="won", revenue_cents=20000).status_code == 422
    p = act(c, p, "stage", stage="won", text="Owner confirmed agreement", revenue_cents=20000).json()
    report = c.get("/api/sales-pilot").json()["report"]
    assert (report["conversion_percent"], report["recorded_revenue_cents"]) == (100, 20000)
    act(c, p, "stage", stage="lost", text="Cancelled")
    assert c.get("/api/sales-pilot").json()["report"]["recorded_revenue_cents"] == 0


def test_validation_and_no_send_or_calendar_routes(pilot):
    c, _, _ = pilot
    assert add(c, email="real@some-salon.com").status_code == 422
    assert add(c, permission_evidence="").status_code == 422
    assert add(c, tenant_id="salon-b").status_code == 422
    assert c.post("/api/sales-pilot/send", json={}).status_code == 404
    assert c.post("/api/sales-pilot/calendar/connect", json={}).status_code == 404


def test_unauthenticated_access_is_denied():
    from fastapi import HTTPException
    async def reject():
        raise HTTPException(401, "Not authenticated")
    app = FastAPI()
    app.include_router(router(None, reject))
    with TestClient(app) as c:
        assert c.get("/api/sales-pilot").status_code == 401


def test_workflows_isolate_records_actions_reports_and_templates(pilot):
    c, _, _ = pilot
    sales = add(c).json()
    customer = c.post("/api/sales-pilot/prospects?workflow=salon_customers", json={
        "name": "Jamie Example", "company": "Fictional Salon", "service": "Haircut consultation",
        "source": "Synthetic", "need": "Consultation next week", "request_confirmed": True,
        "permission": "granted", "permission_evidence": "Synthetic permission", "timing": "this_month"
    }).json()
    customer_url = f"/api/sales-pilot/prospects/{customer['prospect_id']}/actions?workflow=salon_customers"
    assert c.get("/api/sales-pilot").json()["report"]["total"] == 1
    customers = c.get("/api/sales-pilot?workflow=salon_customers").json()
    assert customers["report"]["total"] == 1
    assert customers["prospects"][0]["qualification"]["score"] == 100
    assert "Customer request confirmed" in customers["prospects"][0]["qualification"]["reasons"]
    assert act(c, customer, "draft").status_code == 404
    assert c.post(f"/api/sales-pilot/prospects/{sales['prospect_id']}/actions?workflow=salon_customers", json={"kind": "draft", "expected_revision": 0}).status_code == 404
    drafted = c.post(customer_url, json={"kind": "draft", "expected_revision": 0}).json()
    assert "Haircut consultation at Fictional Salon" in drafted["draft"]["message"]
    assert "Vantora" not in drafted["draft"]["message"]
    won = c.post(customer_url, json={"kind": "stage", "stage": "won", "text": "Synthetic service conversion", "revenue_cents": 5000, "expected_revision": 1})
    assert won.status_code == 200
    assert c.get("/api/sales-pilot?workflow=salon_customers").json()["report"]["recorded_revenue_cents"] == 5000
    assert c.get("/api/sales-pilot").json()["report"]["recorded_revenue_cents"] == 0


def test_legacy_records_remain_only_in_vantora_sales(pilot):
    c, db, _ = pilot
    legacy = add(c).json()
    del db.sales_pilot_demo.rows[0]["workflow"]
    assert c.get("/api/sales-pilot").json()["prospects"][0]["prospect_id"] == legacy["prospect_id"]
    assert c.get("/api/sales-pilot?workflow=salon_customers").json()["prospects"] == []
    assert act(c, legacy, "draft").status_code == 200


def test_live_consent_and_pause_are_specific_to_each_workflow(pilot):
    c, db, _ = pilot
    setup = dict(business_name="Authorized Test Salon", owner_name="Owner", services="Approved workflow",
                 timezone="America/New_York", consent_evidence="Owner explicitly agreed to this workflow", owner_consented=True)
    assert c.post("/api/sales-pilot/setup", json=setup).status_code == 200
    assert not c.get("/api/sales-pilot?mode=live&workflow=salon_customers").json()["ready"]
    payload = dict(name="Jamie", company="Authorized Test Salon", service="Haircut", source="Approved test")
    assert c.post("/api/sales-pilot/prospects?mode=live&workflow=salon_customers", json=payload).status_code == 403
    assert c.post("/api/sales-pilot/setup?workflow=salon_customers", json=setup).status_code == 200
    assert c.post("/api/sales-pilot/prospects?mode=live&workflow=salon_customers", json=payload).status_code == 200
    assert c.post("/api/sales-pilot/pause?workflow=salon_customers").status_code == 200
    assert not c.get("/api/sales-pilot?mode=live&workflow=salon_customers").json()["ready"]
    assert c.get("/api/sales-pilot?mode=live").json()["ready"]
    assert len(db.sales_pilot_live.rows) == 1


def test_unknown_workflow_is_rejected(pilot):
    c, _, _ = pilot
    assert c.get("/api/sales-pilot?workflow=anything").status_code == 422
