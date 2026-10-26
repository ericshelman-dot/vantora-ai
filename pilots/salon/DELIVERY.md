# Replacing simulated confirmations — design only

No providers were connected and no messages were sent. Keep this separate from Vantora's business-prospecting workflow. A delivery adapter is a new integration, not a switch from `simulated=true` to false.

## Permissions and accounts

- Salon owner approval: sender identity, transactional confirmation purpose, allowed recipients, channel, message templates, budget and retention. Approval to demonstrate the software is not permission to contact salon customers.
- Customer choice: explicitly record confirmation channel/contact, purpose, disclosure text/version, timestamp and source. Inquiry replies, appointment confirmations and marketing are distinct purposes. Refusing marketing must not prevent booking. Handle withdrawal and suppression immediately before every send; do not infer permission from merely entering an email.
- Email: choose an owner-approved transactional email account (Resend is one candidate), verify an owned sending domain/subdomain with DNS authorization, configure SPF/DKIM and DMARC, use a scoped send-only API key and server-side secret storage. Preserve existing mailbox MX records. Set a monitored Reply-To. No DNS edits or account purchase made here.
- SMS: an owner-approved Twilio account/subaccount, Messaging Service and SMS-capable sender, credentials in server secrets, HTTPS status/inbound endpoints. US long-code application messaging requires A2P 10DLC registration; capture actual business/campaign details and opt-in evidence. Provider verification is additional to application consent. No number purchase, registration or billing activation performed.
- Calendar: separately authorize the selected calendar/booking account and minimum read-availability/write-event scopes. Store/revoke tokens securely. Reconcile external changes; never claim a real salon booking from internal availability alone.

## Reliable implementation

1. Persist reservation and a durable outbox intent with a unique `(business_id, booking_id, revision, purpose, channel)` key. Do not send inside the booking HTTP request. If atomic persistence is unavailable, make reconciliation recreate missing intents without duplicates.
2. Worker verifies tenant authorization, recipient/confirmation permission and suppression, current booking revision, approved template and budget. Demo mode always uses a sink and cannot select a live adapter. Keep a kill switch and an initial allowlist of owner-controlled test recipients.
3. Store provider ID and states `pending`, `sending`, `accepted`, `delivered`, `failed`, `suppressed`, `unknown`. API acceptance is not delivery. Email delivery means acceptance by the recipient mail server, not guaranteed inbox placement or reading.
4. Use provider-supported idempotency and a durable job claim. On network timeout after submission, reconcile provider status before retrying; do not blindly resend. Retry transient 429/5xx failures with bounded exponential backoff and jitter. Permanent invalid address, opt-out, bounce or blocked number goes to suppression/manual review. Exhausted retries alert the owner through the dashboard.
5. Verify webhook signatures against the raw request body; deduplicate event IDs, correlate tenant/provider IDs, tolerate out-of-order callbacks, and retain an audit trail. Periodically reconcile stale `accepted`/`unknown` records. Never treat missing callbacks as delivered.
6. Process provider opt-outs and inbound STOP/START/HELP as appropriate to the provider, with suppression checks on queued work. Bare STOP is currently a documented failing chat-parser test; broader withdrawal handling is also needed. Do not turn on SMS until these pass.
7. Keep appointment state separate from notification state: delivery failure does not cancel an otherwise saved appointment. Show “Appointment saved; confirmation not delivered—owner follow-up needed.” Cancellation/reschedule invalidates queued obsolete confirmations; each revision has its own idempotency key.
8. Validate sandbox/provider test outcomes, then an authorized owner-controlled recipient: success, decline, unsubscribe, timeout after acceptance, 429, invalid destination, duplicate/out-of-order/forged webhooks, worker restart and budget cap. No automated fallback to a different channel without permission.

## Costs checked October 26, 2026

| Component | Pilot now | Future live delivery |
| --- | --- | --- |
| Model inference | No calls in offline runner | Existing chat uses planner, response and sometimes summary/draft calls. Measure requests/tokens and set a hard budget before enabling. No reliable per-journey cost established here. |
| Email | No sending charge | Resend advertises a Free tier with 100/day limit. Confirm current monthly quota, paid tier and overages at selection time; its retrieved pricing page did not expose a dependable complete tier quote. |
| SMS | No sending charge | Twilio US long-code base $0.0083 per inbound/outbound SMS segment; carrier fees extra. Leased local number $1.15/month. Registration/campaign charges depend on sender type; failed-message processing fee $0.001 where applicable. |
| Storage/hosting | Local in-memory execution | Existing hosting/database plus queue/worker/log retention; no incremental hosted environment created. |
| Calendar | No connection | Provider plan/API availability and integration effort depend on the salon's actual system. |

Illustrative SMS calculation only: 100 outbound one-segment confirmations = $0.83 base, plus approximately $0.35–$0.50 carrier fees using listed major long-code carrier rates, plus $1.15 monthly number rental: **$2.33–$2.48 before registration/campaign fees, incoming replies, taxes, failures and additional segments**. Unicode/long messages can increase billed segments. This is not a total budget or a purchase recommendation. Owner must approve the actual quote and spending limit.

## Primary references

- [Resend pricing](https://resend.com/pricing)
- [Resend domain verification](https://resend.com/docs/dashboard/domains/introduction)
- [Resend webhook events and verification links](https://resend.com/docs/webhooks/introduction)
- [Twilio US SMS/number/carrier pricing](https://www.twilio.com/en-us/sms/pricing/us)
- [Twilio A2P 10DLC requirements](https://www.twilio.com/docs/messaging/compliance/a2p-10dlc)
- [Twilio delivery status callbacks](https://www.twilio.com/docs/messaging/guides/track-outbound-message-status)

These describe available provider capabilities. The durable worker/outbox, consent changes, security controls and failure UI above are proposed Vantora work, not already implemented integrations.
