# vantora-ai
Source code and development resources for Vantora AI.

Imported from Emergent's **AI Business Automation → Localbiz 9** workspace on October 24, 2026. This is the business dashboard, lead management, appointments, and website chat application. The separate **Jessica Lead Merge** chat app is not this codebase.

See [IMPORT_NOTES.md](IMPORT_NOTES.md) for provenance, exclusions, validation limits, and the lead-capture code map.

## Development

Use a separate local development database. Backend startup seeds demo records, updates account passwords from environment variables, backfills records, and creates indexes. Never point a new development instance or integration test run at the existing Emergent database.

The backend uses Python 3.12 or newer (some existing test files use newer f-string syntax), FastAPI, MongoDB, and the Emergent integrations package. Install `backend/requirements.txt` in an isolated environment; the integrations package may require the platform's package source. Copy `backend/.env.example` to `backend/.env` and provide local development values. From `backend`, run `uvicorn server:app --host 127.0.0.1 --port 8001`.

The frontend uses React and Vite. From `frontend`, install with Yarn using `yarn.lock`, copy `.env.example` to `.env`, then run `yarn start` or `yarn build`. Check the installed Vite version's Node requirements before setup.

Secrets, database exports, saved conversations, and Emergent chat history are not stored in this repository. The existing application and data remain in Emergent; importing source does not migrate or back them up.
