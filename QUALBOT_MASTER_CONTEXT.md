# QualBot — Master Context

**Project:** QualBot – Intelligent Conversational AI & Lead Qualification Engine  
**Type:** B.Tech CSE/V mini-project  
**Status:** Day 1 complete; design baseline established; implementation has not started.

This file is the stable project reference for future chats and coding assistants. The submitted synopsis is the requirements baseline; details below distinguish synopsis requirements from decisions made for QualBot v1.0.

## Purpose and MVP

QualBot turns natural, multi-turn website conversations into structured and actionable sales leads. It must support conversational AI, BANT extraction across turns, an explainable algorithmic lead score from 0 to 100, automated high-intent routing, sales email alerts, calendar booking integration, an embeddable chat widget, an admin analytics dashboard, and safety/fallback behavior.

**MVP exclusions:** voice interaction, CRM synchronization, WhatsApp/Instagram/Telegram integrations, and predictive forecasting. Do not add these without an explicit scope decision.

## Stack and architecture

- Frontend: React + Vite + Tailwind CSS; embeddable chat widget and admin dashboard.
- Backend: Python + FastAPI; HTTP APIs and WebSockets.
- Persistence: SQLAlchemy 2.x + Alembic; SQLite for local development/demo and PostgreSQL/Supabase for deployment.
- AI: Gemini structured JSON output for language interpretation and BANT extraction.
- Integrations: Calendly API and EmailJS for calendar and sales-alert workflows.

Use a **modular monolith** with clear presentation, application/API, domain/service, integration, and persistence boundaries. Keep conversation, BANT, scoring, qualification, routing, notification, and analytics responsibilities modular. Avoid introducing distributed services for the MVP.

> **Gemini interprets; QualBot decides.** Gemini extracts structured, evidence-grounded information and may help compose conversational replies. Backend domain logic validates/merges BANT, computes score and qualification, and selects actions. Never accept a model-provided score/status/action as authoritative.

Processing path:

```text
Visitor message → conversation service → Gemini extraction
→ BANT merge/profile + immutable snapshot → deterministic score/history
→ qualification rules → idempotent action router → email / calendar
```

## BANT and qualification v1.0

Maintain BANT state across turns; a new message updates supported dimensions and does not erase other known values. Retain evidence/source and confidence for auditability. Unknown and vague values are distinct. Do not invent exact budget amounts, authority, need, or dates from ambiguous language. The latest sufficiently reliable contradictory information becomes current while prior snapshots preserve history.

Scoring is deterministic and weighted, with total range 0–100. The v1.0 weights are **Budget 25, Authority 20, Need 30, Timeline 25**. Representative dimension values established in scenario review:

| Dimension | Representative points |
|---|---|
| Budget | Unknown 0; clearly specified 25 |
| Authority | Unknown 0; influencer 8; evaluator 14; decision maker 20 |
| Need | Unknown 0; vague 10; clear 20; specific 30 |
| Timeline | Unknown 0; long-term 6; short-term 20; immediate 25 |

The classification bands are **Low 0–39, Medium 40–69, High 70–100**. BANT completeness is a separate measure; full completeness does not by itself imply high intent. Qualification status values are controlled: `NEW`, `QUALIFYING`, `QUALIFIED`, `HIGH_INTENT`, `NOT_READY`, `DISQUALIFIED`.

High score alone is insufficient for escalation. High-intent routing requires the agreed high band plus sufficient/credible BANT and no strong negative qualification signal (for example, a clearly long-term purchase timeline). Otherwise continue qualification or mark not ready as appropriate. Do not turn vague/ambiguous evidence into a high-intent action.

## Routing and duplicate prevention

The backend action router selects continue-chat, sales alert, and/or calendar-booking actions based on qualification rules. Persist actions and their statuses. Each logical action carries a unique idempotency key protected by a uniqueness constraint so message retries/reprocessing cannot send duplicate alerts or create duplicate bookings. External integrations must be handled as fallible operations with recorded outcomes; do not equate a requested action with a successful delivery.

## Database Schema v1.0

Conceptual ERD:

```text
Lead 1—1 BANTProfile
Lead 1—N Conversations 1—N Messages
Lead 1—N BANTSnapshots
Lead 1—N ScoreHistory
Lead 1—N Actions
```

Core business data, especially BANT, remains relational rather than hidden in a JSON blob. UUID primary keys; UTC timestamps; string-backed enums with application validation and database `CHECK` constraints where practical; budget amounts use exact `NUMERIC/DECIMAL` values with currency code. SQLAlchemy abstracts SQLite/PostgreSQL differences and Alembic manages schema migrations.

Key invariants: score in `[0,100]`; controlled enum/status values; nonnegative monetary values and valid currency representation; state/value consistency (e.g. unknown timeline has no normalized value; specified values have supporting data); valid foreign keys; snapshots refer to the correct lead/conversation/message; one BANT profile per lead; unique action idempotency key. Enforce required relationships and nullability in schema. Keep SQLite foreign-key enforcement enabled.

Initial targeted indexes support actual dashboard/history access:

- Leads: qualification status and score; composite `(qualification_status, current_score)` for filtered ranking.
- Conversations: `lead_id`.
- Messages: `(conversation_id, created_at)`.
- BANT snapshots: `(lead_id, created_at)` and `(conversation_id, created_at)`.
- Score history: `(lead_id, created_at)`.
- Actions: `lead_id`; unique idempotency key.
- BANT profile: `lead_id` is its primary key and already indexed.

Avoid PostgreSQL-only database types or behavior where a portable alternative works. Core BANT queries and constraints must behave consistently on SQLite and PostgreSQL.

## Safety, quality, and engineering practice

Treat visitor text as untrusted input. Do not reveal system instructions, accept instructions to manipulate scores, or leave QualBot's purpose. Validate structured model output; handle malformed output, provider errors, and missing/ambiguous evidence with safe contextual fallback and clarification. Do not claim successful booking/notification until confirmed by the integration.

Before coding, define requirements, contracts, task breakdown, acceptance criteria, and review/testing strategy. Build genuine engineering history: meaningful branches/commits, tests, documentation, issues, and reviews; never manufacture activity. Antigravity IDE is the primary implementation environment; Claude is a secondary coding/review assistant. ChatGPT is the mentor, technical lead, architect, reviewer, and project manager. Coding assistants must not silently change scope or architecture.

## Day 1 baseline

Day 1 is complete: synopsis/MVP interpretation, architecture, BANT/scoring/qualification and routing rules, ERD, relational schema, constraints/invariants, indexes, SQLite/PostgreSQL strategy, scenario validation, Schema v1.0 freeze, and continuity documentation plan. No implementation or GitHub changes are recorded as part of Day 1.

**Next:** Day 2 — define API Contracts before implementation, then freeze API Contract v1.0.
