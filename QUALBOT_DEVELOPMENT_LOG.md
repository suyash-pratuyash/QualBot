# QualBot — Development Log

Historical record of completed project work. Update after each significant development day; distinguish design work from implementation and keep the GitHub state factual.

## Day 2 — API contract and Phase 0 repository foundation

**Status: FOUNDATION CORRECTIONS COMPLETE — AWAITING REVIEW**  
**Phase:** Phase 0 — repository foundation  
**Implementation:** Backend/frontend app shells, dependency manifests, typed Pydantic Settings, complete local API contract reference, and tests. No MVP feature logic implemented.  
**Git:** Local Git repository on `master`; initial foundation commit is being prepared after checks passed. No GitHub remote/repository supplied.

### Completed

- Completed `docs/API_CONTRACT_V1.md` from the frozen Day 2 contract and subsequent JWT admin-authentication decision, including REST/WebSocket schemas, validation, auth, status/error cases, and examples.
- Created modular-monolith backend package boundaries and React/Vite/Tailwind frontend shell.
- Declared FastAPI, Uvicorn, Pydantic Settings, SQLAlchemy, Alembic, Psycopg, pytest, HTTPX, and Ruff dependencies; declared React 19, Vite 7, and Tailwind 4 frontend dependencies.
- Added typed Pydantic Settings loading for `.env`, environment, API prefix, database URL, CORS origins, and the Vite API base URL. FastAPI uses the configured API prefix and CORS origins.
- Added environment example, ignore rules, coding conventions, repository setup instructions, and settings/application tests.
- Verified `python -m pytest` (7 passed), `python -m ruff check .` (passed), and `pnpm build` (passed).

### Decisions

- Backend supports Python 3.11+; frontend setup documents Node 22.12+ and pnpm. Dependency ranges are declared in manifests, with frontend resolution captured in `frontend/pnpm-lock.yaml`.
- Tailwind 4 uses its Vite plugin. The project workspace explicitly allows the `esbuild` setup script required by Vite's build toolchain.
- Pydantic Settings reads the repository-root `.env` using the `QUALBOT_` prefix; comma-separated CORS origins are parsed and URL-validated. `VITE_API_BASE_URL` is URL-validated as public frontend configuration.
- The frontend shell is a neutral foundation placeholder and contains no dashboard or widget behavior.

### Issues / open work

- No synopsis file was found under `sources/`; master context and submitted synopsis references remain the baseline.
- The Codex bundled Python runtime emitted script-path warnings during package installation; use a project virtual environment in normal developer setup.
- No synopsis file was found under `sources/`; master context and submitted synopsis references remain the baseline.
- No Phase 1 database models or MVP feature behavior have been implemented.

### Next

Await Phase 0 review and explicit approval. Do not begin Phase 1 database/domain modeling until approved.

## Day 1 — Requirements, architecture, and database design

**Status: COMPLETE**  
**Phase:** Pre-implementation system design  
**Implementation:** None  
**GitHub:** No repository, branch, commit, or issue activity was recorded for this design day.

### Completed

- Interpreted the submitted synopsis into the MVP spine: natural multi-turn chat, BANT extraction, algorithmic 0–100 lead scoring, qualification/routing, email alerts, calendar integration, embeddable widget, admin analytics, and AI safety/fallback.
- Set future scope aside: voice, CRM synchronization, WhatsApp/Instagram/Telegram, predictive forecasting.
- Selected a modular monolith and baseline stack: React/Vite/Tailwind, Python/FastAPI, WebSockets, Gemini, SQLAlchemy 2.x/Alembic, SQLite and PostgreSQL/Supabase, Calendly API, EmailJS.
- Established the boundary **“Gemini interprets; QualBot decides.”** Backend owns deterministic score, qualification, and actions.
- Defined persistent multi-turn BANT, evidence/confidence, unknown versus vague, reliable contradiction handling, separate completeness, v1.0 weights and bands, and the high-intent routing guard.
- Designed conceptual relational ERD and froze Database Schema v1.0 after schema, invariants, indexes, portability, and ten-scenario validation checkpoints.
- Recorded idempotent action routing so retries cannot duplicate external actions.
- Established the four-file documentation continuity system.

### Important decisions

See [QUALBOT_DECISION_LOG.md](QUALBOT_DECISION_LOG.md). No implementation choices beyond the v1.0 architecture/database baseline are authorized by this record.

### Issues / open work

- API contracts are not yet defined; no implementation should begin before that design is reviewed and frozen.
- No source files exist under the mirror's `sources/` directory at this time. The synopsis is referenced in the project conversation as the authoritative baseline.
- No GitHub repository state was provided or changed during Day 1.

### Next

Day 2 — API Contracts: conversation lifecycle, WebSocket protocol, message format, BANT/score/qualification response, lead endpoints, admin analytics, routing/action response, error format, validation, and versioning. Freeze API Contract v1.0 before coding.
