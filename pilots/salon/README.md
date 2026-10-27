# Isolated salon demonstration

Prepared October 26, 2026. This is a **repeatable offline engine demonstration**, not a deployed salon, a live calendar integration, or an AI conversation acceptance test.

## Existing work reused

Main was `49d97966b7e5e3c503f57c8206f888ed8e01e01b`. Open draft [PR #3](https://github.com/ericshelman-dot/vantora-ai/pull/3) already contains branding and separate Grow Vantora / Grow a Salon workflows. This work branches from its head `02022a8e9012ad0229ee34fd39853c138a23397d`, preserving that work. PR #3 reports earlier deployment checks; those were not independently repeated here.

This pilot calls the existing `leads_engine`, `booking_agent.execute`, and `scheduling` functions directly. It does not use, copy into, or mutate the sales-prospecting collections. No new application or parallel CRM was built.

## Run without Emergent credits

From the repository root, preferably inside a Python 3.12 virtual environment:

```sh
python -m pip install -r pilots/salon/requirements.txt
python pilots/salon/run_demo.py
python -m pytest -c /dev/null pilots/salon/test_salon.py pilots/salon/test_opt_out.py backend/tests/test_sales_pilot.py backend/tests/test_consent_parser_iter8.py -q
```

On Windows use `-c NUL` instead of `-c /dev/null`. The engine's existing Unix-style `strftime` directives (`%-d`, `%-I`) still require a portability check on native Windows; WSL is the known-compatible path for this Linux-tested runner.

`business.json` contains a fictional business, three example services, duration-based availability, capacity one, weekday hours, and an explicit timezone. These are demonstration assumptions, not the daughter's information. Prices, address, and phone are deliberately unprovided. All customer emails use example.com.

`run_demo.py` always constructs a fresh in-memory database. It accepts no database URL, does not import `server.py`, does not load `.env`, and makes no model or provider calls. There is no persistent seed/reset command. Ending the process discards all records; rerunning starts clean. Tests additionally block outbound socket connections. Do not point the broader repository API tests at any existing preview or production database.

`example_result.json` is actual output from the October 26 run. Its appointment date is November 2, 2026; reruns choose a future weekday. IDs/timestamps change. The existing engine labels the record `ai_chat`, but the input here is scripted, not model-generated. All `confirmed` and `simulated-sent` values in that output refer only to the in-memory demonstration. Neither proves a real appointment or delivered message.

## Synthetic customer journey

| Step | Script / action | Expected evidence |
| --- | --- | --- |
| Inquiry | Alex Sample: “Do you offer a haircut and finish? What does it cost?” | Service exists in fictional catalog; price requires owner review. No invented price. |
| Contact | “My name is Alex Sample, alex.salon@example.com” | One lead and linked customer; normalized contact; no booking yet. |
| Inquiry permission | Existing engine asks permission to email a personal reply. Alex: “Yes please.” | `inquiry_reply.granted=true`, email channel, question/answer, source and timestamp. |
| Optional marketing | Existing engine asks separately about offers. Alex: “No thanks.” | Email and SMS marketing both false; inquiry permission remains true. |
| Availability | Scripted intent asks for Haircut and Finish on the future weekday. | Existing scheduler returns actual available slots from the mock store; nothing booked. |
| Booking | Alex chooses 10:00. Script supplies name and email. | One 45-minute booking, linked lead/customer, local/UTC time and reference. Confirmation explicitly simulated. |
| Owner review | Owner reviews linked record, consent log, booking and an owner-written factual reply. | Existing approval function permits inquiry reply; records simulated follow-up; delivered=false. Marketing approval is separately tested and blocked. |
| Repeat / conflict | Repeat original request, then another customer requests that slot. | Original reference retained; one confirmation; other customer rejected with alternatives. |

Inquiry wording and intended assistant response are a walkthrough script, not a claim that the LLM produced them. Only the initial inquiry is stored as a chat message by the runner; consent questions/answers are retained in the consent log. Full chat-stream transcript behavior is a later acceptance check.

## Code inspection and minimum changes

| Area | Existing behavior / finding | Change in this branch |
| --- | --- | --- |
| Capture | Name plus normalized email/phone; business-scoped matching; customer/booking linking; archived contacts excluded. Startup creates contact uniqueness indexes. | Reused. No data migration. Mock tests do not validate real Mongo indexes. |
| Consent | Inquiry reply separate from marketing, explicit question/answer logs, one-shot answer windows, owner approval gates. | Reused. Known delivery gaps below remain blocked from live use. |
| Configuration | `BusinessUpdate`, `SchedulingConfig`, `CatalogService` already expose services, duration, price text, timezone, capacity, weekly hours, chat and phone flags. | Added a fictional JSON fixture; no business model expansion. |
| Booking retry | Original executor checks capacity before finding the session's saved reservation. At capacity one a retry incorrectly says unavailable. | Look up existing reservation before rejecting on capacity. Sequential retry regression now passes. |
| Contact validation | Original executor accepted any nonempty email/phone, potentially confirming without a valid linked lead. | Reuse the lead engine's existing normalizers before booking. This is syntax screening, not identity or deliverability verification. |
| SDK import | Engines eagerly required Emergent SDK even for deterministic functions. | Import the SDK only inside the three model-calling functions. Paid functions themselves are otherwise unchanged. |
| Owner UI | Existing Leads, LeadDetail, Appointments, SchedulingSettings screens exist. | No frontend changes; browser behavior not tested this turn. |

## Executed verification

- Python 3.12; pytest 9.1.1; mongomock-motor 0.0.36; pymongo 4.18.2; motor 3.7.1; FastAPI 0.110.1; httpx 0.27.2.
- Original October 26 report: **30 passed, 1 expected failure**: 17 passing salon checks plus 13 existing sales-pilot API checks. One dependency deprecation warning, not a functional failure.
- Existing booking execution logic reproduced **two failures**: retry returned `unavailable`; malformed contact returned `confirmed`. With the two fixes both pass. Baseline comparison deferred only the SDK import so it could execute offline.
- Tested journey, deduplication, tenant preservation with a synthetic sentinel, separate consent scopes, unanswered consent, marketing opt-out, invalid/missing contact, unknown service, outside hours, past/invalid date, planner-error result, storage failure, conflict alternatives, closed day, single-process competing reservations and winter/summer timezone conversion.
- Existing sales-pilot tests exercise its in-process FastAPI router with a fake store. They do not verify the full server or browser.
- October 27 STOP correction: **83 passed, no expected failures**, executed locally with the command above (one dependency deprecation warning). The former strict expected failure is now a normal passing regression. Against the unchanged parser/handler, the expanded suite produced 13 failures and 70 passes; all 13 pass after the fix.
- Standalone STOP accepts case variations, surrounding whitespace and trailing `.`, `!`, `?`. Whole-message anchors avoid suppressing ordinary inquiries such as “Can I stop by tomorrow?” Existing explicit withdrawal phrases remain supported. Withdrawal takes priority over same-request checkboxes and closes a pending marketing question. Repeated withdrawals retain audit entries; stale checked boxes do not restore consent.
- New offline coverage checks prior granted/declined/unknown decisions, withdrawal before contact capture, repeated requests, blocked marketing approval on both channels, preservation of separate inquiry permission, and tenant isolation with identical contact/session identifiers. This is not provider-level suppression or a production approval.
- No real MongoDB server, startup/index migration, full HTTP chat pipeline, model inference, browser, external calendar, email, SMS, or production acceptance test was executed. No deployment, main merge, existing customer changes, or paid model calls were made.

## What can be shown to a potential customer

**Demonstrated offline:** lead/contact linking and repeat-contact matching; explicit inquiry permission separate from declined marketing; duration/timezone/hours/capacity-based availability; saved internal reservation with reference; linked owner-review data; permission-gated simulated follow-up.

**Inspected but not verified live here:** natural-language planning, streamed replies, personalized AI draft generation, dashboard presentation, authentication/tenant authorization in the full application, actual Mongo persistence and indexes. The user's restored login is valuable prior evidence but not a new test here.

**Not ready to promise:** real confirmations, reliable booking against the salon's existing calendar, autonomous customer acquisition, or unattended production operation.

## Remaining work before any real salon pilot

1. Obtain the daughter's direct authorization and confirm business name, approved services/prices/durations, hours/timezone, stylist/resource capacity, buffers, breaks, holiday closures, cancellation/deposit rules, existing booking platform, contact channels, and retention expectations. No answers are assumed.
2. Agree whether the app's booking table is the authoritative calendar or connect the actual booking provider. The current scheduler only sees its own records. It has no stylist-level availability, processing-time model, external calendar synchronization or holiday exception model. Limit the first demo to one resource and simple services.
3. Run full UI/chat tests in a separately provisioned development environment with isolated credentials and database. `server.py` startup seeds/upgrades data and creates indexes, so a database-name change alone is not a sufficient production safeguard. No live seeding is provided here.
4. Validate malformed model outputs, ambiguous service matching, date-only invalid inputs, daylight-saving transition ambiguity, cancellation/reschedule, missing contact name, public chat session access and rate limits. Engine locks are process-local: cross-worker capacity races and concurrent same-session retries require database-level atomicity/idempotency before production. Sequential retry is the limited fix validated here.
5. Before sending, implement the delivery design in `DELIVERY.md`. Current opt-out covers marketing channels but not all inquiry-reply scopes; inquiry permission is stored per lead despite being requested per conversation. Introduce purpose/session-scoped authorization and withdrawal before using it for real delivery. Review concurrent draft approvals and consent rechecks as part of the same work.

The separate sales-pilot router still marks proposals `awaiting_calendar_authorization`; the original booking engine's in-memory `confirmed` result does not bypass that gate or establish a bridge between the two workflows.

## Rollback

This branch is unmerged and undeployed. Discard it to abandon the pilot, or revert its single commit if later adopted. No database cleanup, migration rollback, account revocation or customer notification is needed for work performed here.


## Branch review — October 27, 2026

PR #4 targets `feature/salon-sales-pilot` (PR #3), not main. Its original head was one commit ahead and zero behind PR #3 at `02022a8e9012ad0229ee34fd39853c138a23397d`. This correction stays on `pilot/isolated-salon-validation`. Keep both PRs draft pending their broader review. Recommended order: review/merge #3 first, then retarget #4 to main and inspect the resulting diff and rerun isolated checks (especially after squash/rebase). Do not merge #4 into main wholesale without reviewing its inherited #3 changes. Neither a merge nor deployment was performed for this correction.
