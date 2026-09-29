# QualBot

QualBot is an intelligent conversational AI and lead qualification engine. This repository follows the frozen v1.0 project architecture: React + Vite + Tailwind CSS, FastAPI, SQLAlchemy 2.x/Alembic, SQLite for local work, and PostgreSQL/Supabase for deployment.

## Phase 0: foundation

This phase establishes repository structure, environment configuration, dependency declarations, conventions, documentation, and test scaffolding. It does not implement conversational AI, BANT extraction, scoring, routing, integrations, dashboard behavior, or widget behavior.

## Repository layout

- `backend/app/`: FastAPI modular-monolith package, organized into API, domain, integrations, persistence, and services.
- `backend/tests/`: backend test suite.
- `frontend/src/`: React application entry point and styles.
- `docs/`: project engineering docs, including API contract reference and development conventions.
- `sources/`: synced project references; read-only.

## Setup

Requirements: Python 3.11+, Node.js 22.12+ and pnpm 9+ (or compatible npm), Git.

1. Copy `.env.example` to `.env` and adjust local values as needed.
2. Backend: `cd backend`, create/activate a virtual environment, then `pip install -e ".[dev]"`.
3. Frontend: `cd frontend`, then `pnpm install`.
4. Run backend tests with `pytest`; frontend build with `pnpm build`.

Exact API and architecture decisions remain in `docs/API_CONTRACT_V1.md`, `QUALBOT_MASTER_CONTEXT.md`, and `QUALBOT_DECISION_LOG.md`.

## V1 live demo

The current V1 demonstrates the core qualification loop end-to-end: React chat UI → FastAPI/WebSocket → BANT extraction → deterministic 0–100 scoring → qualification state → SQLite persistence. Gemini is optional; when no API key is configured, a deterministic local extraction fallback keeps the demo runnable.

### Run locally

1. Copy `.env.example` to `.env` and change `QUALBOT_JWT_SECRET` for any non-demo environment.
2. Backend: `cd backend && python -m venv .venv && .venv\\Scripts\\activate` (Windows) or `source .venv/bin/activate` (macOS/Linux), then `pip install -e "[dev]"` and `uvicorn app.main:app --reload`.
3. Frontend: `cd frontend && pnpm install && pnpm dev`.
4. Open the Vite URL shown in the terminal. The default demo admin is `admin@qualbot.local` / `qualbot-demo`; change these values before any shared deployment.

For a high-intent demo, use a message containing a clear need, decision-maker authority, a concrete budget, and an immediate/short-term timeline. A configured `QUALBOT_CALENDLY_BOOKING_URL` enables the booking event; without it, the action remains explicitly unavailable rather than being fabricated.


### Admin console
The V1 UI includes an authenticated admin console for overview metrics and recent lead records. Use the demo administrator values documented in the local runbook when testing locally.
