# QualBot — Decision Log

Record of accepted project-level decisions. Synopsis requirements and engineering choices are identified separately. Revisit a decision only through an explicit review; update dependent documents when it changes.

| ID | Decision | Rationale / consequence | Status |
|---|---|---|---|
| D-001 | Preserve synopsis capabilities as MVP baseline; exclude voice, CRM sync, social messaging integrations, and predictive forecasting from MVP. | Keeps the deliverable focused on the stated conversational qualification engine. | Accepted |
| D-002 | Use a modular monolith with explicit UI, API/application, domain, integration, and persistence boundaries. | Clear responsibilities and testability without MVP distributed-system overhead. | Accepted |
| D-003 | Gemini extracts evidence-grounded structured BANT; backend owns BANT validation/merge, scoring, qualification, and routing. | **Gemini interprets; QualBot decides.** Business outcomes remain deterministic and testable. | Accepted |
| D-004 | Preserve BANT across turns; unknown differs from vague; latest sufficiently reliable contradiction updates current state while snapshots retain history. | Supports gradual disclosure and auditability without discarding prior evidence. | Accepted |
| D-005 | Use v1.0 score weights B=25, A=20, N=30, T=25; bands Low 0–39, Medium 40–69, High 70–100. Keep BANT completeness separate. | Engineering model validated against ten conversational scenarios; exact weights/bands are project decisions, not synopsis wording. | Accepted for v1.0 |
| D-006 | High-intent action needs more than score: require sufficient credible BANT and no strong negative signal. | Avoids escalating a numerically high lead whose timeline or other evidence indicates low readiness. | Accepted |
| D-007 | Persist actions and protect each logical action with a unique idempotency key. | Retries and repeated processing must not duplicate email alerts or calendar actions. | Accepted |
| D-008 | Use React + Vite + Tailwind; Python + FastAPI; WebSockets; Gemini; Calendly API; EmailJS; SQLite locally and PostgreSQL/Supabase for deployment. | Follows baseline stack in project instructions/synopsis interpretation. | Accepted |
| D-009 | Use SQLAlchemy 2.x and Alembic across SQLite/PostgreSQL; UUID identifiers, UTC timestamps, string-backed enums, exact decimal budget values, and relational BANT. | One portable model/migration path, controlled application enums, and queryable core data. | Accepted |
| D-010 | Freeze conceptual ERD and Database Schema v1.0 as Lead, BANTProfile, Conversation, Message, BANTSnapshot, ScoreHistory, and Action entities with stated relationships. | Separates current state, conversation history, scoring history, and external side effects. | Superseded — Phase 1A (by D-013) |
| D-011 | Enforce score/status/value/relationship/idempotency invariants in application and database constraints where practical; use targeted indexes for dashboard and history queries. | Prevent invalid data and support known access patterns without indiscriminate indexes. | Accepted |
| D-012 | Establish four persistent docs and update them as work proceeds; do not begin implementation until API contracts are defined and reviewed. | Preserves cross-chat continuity and prevents coding agents from defining the system by accident. | Accepted |
| D-013 | Implemented Schema v1.0: Admin, Conversation (1→M Message), Lead (1→0..1 from Conversation), BANTState (1:1 with Lead via shared PK lead_id, typed dimension statuses, evidence, and nullable confidence fields [0.0, 1.0]), LeadScoreHistory (1→M from Lead), and RoutingAction (1→M from Lead, unique idempotency_key, action types: continue_chat/sales_alert/calendar_booking, statuses: pending/success/failed). | Authoritative implemented Schema v1.0 decision, superseding the pre-implementation conceptual ERD (D-010) for Phase 1A codebase. | Accepted (Phase 1A) |

## Database design record — Schema v1.0

### Authoritative Implemented Schema (Phase 1A — Decision D-013)

Implemented and committed Phase 1A relational schema:
- `Conversation` 1—N `Message`
- `Conversation` 1—0..1 `Lead`
- `Lead` 1—1 `BANTState` (shared PK `lead_id`, typed dimension status enums, evidence text, nullable `*_confidence` floats in [0.0, 1.0])
- `Lead` 1—N `LeadScoreHistory` (append-only score snapshots with optional `message_id`)
- `Lead` 1—N `RoutingAction` (unique `idempotency_key`, action types: `continue_chat`, `sales_alert`, `calendar_booking`, statuses: `pending`, `success`, `failed`)
- `Admin` (back-office account with bcrypt password hash and unique email)

### Pre-implementation Conceptual Baseline (Historical / Superseded D-010)

```text
Lead
 ├── 1:1 BANTProfile
 ├── 1:N Conversations ── 1:N Messages
 ├── 1:N BANTSnapshots
 ├── 1:N ScoreHistory
 └── 1:N Actions
```

The design checkpoint included relational schema, constraints/invariants, targeted indexes, SQLite/PostgreSQL portability, and ten-scenario validation. Core data is relational. UUID primary keys, UTC timestamps, string-backed enums plus application validation and practical `CHECK`s, exact decimal budget values, and unique action idempotency keys form the portability baseline.

## Governance

These are the v1.0 baseline decisions, not permission for implementation assistants to expand scope. A proposed major change must state the reason, affected requirements/contracts/data, and migration implications, and be explicitly discussed before adoption. Record accepted changes here and update Master Context and Handoff.
