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
