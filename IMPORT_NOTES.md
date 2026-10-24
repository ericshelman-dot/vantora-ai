# Vantora source import — October 24, 2026

## Origin and scope

Source: Emergent **AI Business Automation → Localbiz 9**, code-server workspace `/app`, associated with `55a6916c-1c1c-4990-80c9-7b5f25739829`. The separate **Jessica Lead Merge** application is a standalone chat app and was not imported.

The initial GitHub commit `5733d4e4f0a75ae2c741f1a01ec8501d74a1f885` contained only README.md. This import preserves that commit as its parent and copies the current working-tree source, without importing Emergent's earlier Git history. The source repository had no configured Git remote when inspected. Emergent's GitHub account connection was separately verified in its Save to GitHub dialog.

The snapshot contains tracked application source and existing tests, plus the current untracked `frontend/yarn.lock`. Repository README, environment templates, and ignore rules were added or adjusted for this import; application logic was not changed.

Excluded: actual environment files, database data, saved conversations, development memory, test reports, platform metadata, caches, dependencies, and generated builds. Original files and records remain in Emergent. This is a source import, not a database or saved-chat backup, and it does not establish automatic two-way synchronization.

## Jessica investigation

A read-only query of Localbiz 9's configured database confirmed three Jessica Miller lead records in the same business, with different email addresses. No merge, archive, delete, or update was performed. Record identifiers and database contents are intentionally omitted from this public repository.

Current code locations:

| File | Responsibility |
| --- | --- |
| `backend/server.py`, `chat_stream` | Extracts contact details and invokes lead capture after a chat turn. |
| `backend/leads_engine.py`, `upsert_lead` | Creates or updates a business's lead. Normalizes email/phone, looks for an existing record, and inserts only if none matches. |
| `backend/leads_engine.py`, `_find` | Matches active leads by normalized email, phone, session, or alternate contact details within a business. Does not match solely by name. |
| `backend/server.py`, startup index setup | Creates partial unique indexes on active lead email and phone keys. |
| `backend/lead_merge.py` | Implements duplicate grouping, merge preview/approval, and undo. |
| `frontend/src/dashboard/DuplicateReview.jsx` | User-facing duplicate review and merge approval. |

The current matching rules explain why three records sharing a name but using different contact details can remain separate. This does not by itself prove that repeated chats using the same email still create duplicates; the current source already includes normalization, locking, unique-key handling, and retry logic. Existing Jessica records were reported in the saved development history as reproductions, but the read-only database query cannot establish their creation history independently.

Resume investigation with an isolated database using the existing `test_lead_capture.py` and `test_iter10_jessica_capture.py` tests. Do not run API tests against the existing preview or production database: several tests create records, modify state, or delete test databases. Any merge of existing leads requires a separate explicit decision.

## Verification limits

The exported source was checked against current backend secret values in the source environment without printing those values; no matching secret value was found. Common credential patterns were also scanned locally. Actual `.env` files and prior Git history are excluded. These checks are not a comprehensive security audit.

All five backend application modules passed a Python syntax compilation check, all exported JSON files parsed, and 121 original source files were verified byte-for-byte against the export (README and ignore rules were intentionally adjusted). The frontend lockfile was copied separately from the current workspace. Application startup, integration tests, deployment, and a complete frontend build were not run as part of the import. No claim is made that authentication, duplicate capture, or deployment issues are resolved. A clean environment still needs dependencies, environment values, and an isolated MongoDB instance.
