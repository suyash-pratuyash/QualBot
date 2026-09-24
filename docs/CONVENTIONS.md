# Engineering conventions

- Keep the MVP a modular monolith with API/application, domain, integration, and persistence boundaries.
- Use snake_case for Python modules and names; use domain-neutral names until feature phases begin.
- Add type hints to Python functions and keep business rules in domain/service modules, not HTTP handlers.
- Use React function components and ES modules; keep presentation code under `frontend/src/`.
- Read configuration from environment variables; never commit secrets. Vite `VITE_` values are public client configuration.
- Use UTC timestamps and UUID identifiers when persistence is introduced. Use SQLAlchemy 2.x and Alembic, SQLite locally, PostgreSQL in deployment.
- Format/lint Python with Ruff; keep tests deterministic and focused. Add tests with each feature in later phases.
- Follow the frozen API contract at `/api/v1` and WebSocket prefix `/ws/v1`; all error responses follow its shared envelope.
- Do not add future-scope integrations or alter scoring, qualification, schema, or architecture without an explicit decision.
