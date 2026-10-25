# Sales & Marketing pilot

The authenticated `/dashboard/sales` page adds an isolated pilot to the existing Vantora application. Existing login, chat, lead matching, billing and appointment routes are retained. No automatic imports from existing customers or leads occur.

## Available now

- Owner-entered prospects with need, decision maker, timing, source and contact permission evidence.
- Explainable qualification: 25 points each for need, decision maker, timing this month and recorded permission; qualification threshold is 50. This is a prioritization aid, not a prediction.
- Free, deterministic personalized outreach templates, editing and approval of the saved revision. Approval records review only; nothing is delivered.
- Manual response recording and opt-out suppression, including invalidation of pending/approved drafts.
- Tentative appointment/demo proposals with future time validation and explicit timezone offset. Every proposal remains `awaiting_calendar_authorization`. No event is created and the booked stage is blocked.
- Manual conversion and recorded-value reporting. Won/all prospects is the conversion denominator. Values are USD cents entered by an owner, not revenue collected or attributed by an integration. Reports currently cover up to 1,000 records per tenant and mode.
- Authenticated, server-scoped tenant queries, separate demo/live collections, revision checks on updates and audit events committed with record changes.
- Live setup requires business name, consenting owner, services, timezone and explicit consent evidence. Owners can pause authorization; records are retained while live access/actions are blocked.

## Data boundaries and costs

Demo uses `sales_pilot_demo`; live uses `sales_pilot_live`; owner authorization uses `sales_pilot_consents`. Tenant scope is derived from existing authenticated identity. An administrator without a business can use a personal demo sandbox. An administrator in the existing demo-business mode cannot enable a live pilot. Demo contacts must use example.com; all names, company names and notes in demo should be fictional. The UI cannot verify that an operator has told the truth about consent or fictional text.

This module imports no LLM, messaging, calendar or payment client. There are no send, calendar-write or charge endpoints. Existing application's paid chat features are separate; this pilot does not invoke them. Storage/hosting costs remain those of the existing environment. No scheduler or background prospect crawler is installed.

## Required owner decisions before live use

1. Confirm whether the first objective is selling Vantora to salons or helping a consenting salon manage its own inquiries. The same draft pipeline can support either; service/offer text must match the chosen objective.
2. Obtain the salon owner's direct agreement. The user's daughter is a candidate only; no salon name, permission or account access is assumed.
3. Supply the approved business name, services/offer, contact person, timezone, permitted data sources and retention expectations. Enter prospect-specific contact permission evidence separately.
4. Choose a calendar provider and approve the exact account/scopes. OAuth, token storage, revocation, availability checks, collision handling, idempotent event creation and booking confirmation require a later implementation. Proposals are intentionally blocked from claiming a booking until that work is reviewed and authorized.
5. Choose a sending provider and per-message approval process only if delivery is desired later. This release remains draft-only. Do not connect accounts, send, charge or publish production without explicit authorization.

## Verification

Run only the isolated test file for this feature; it uses an in-memory test store and never opens MongoDB or calls providers:

```text
python -m pytest -c /dev/null backend/tests/test_sales_pilot.py -q
```

The tests exercise tenant/mode separation, live consent and pause gates, contact-permission checks, opt-out, stale approval, draft delivery state, booking authorization blocks, evidence-based outcome recording and anonymous rejection. The existing broad API suite must not be pointed at preview or production because it contains data-changing tests.

Audit entries preserve actor, timestamp and action alongside the record. They are application-level records, not cryptographically tamper-proof or an external compliance log. Production retention/export and audit-access policies remain owner decisions.
