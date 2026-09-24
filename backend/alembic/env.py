"""Alembic migration environment for QualBot.

This file is executed by Alembic for every migration command.  It wires up:

* The application's ``Base.metadata`` so that ``alembic revision --autogenerate``
  can diff the current database state against the ORM model definitions.
* The application's ``engine_from_settings()`` factory so that migrations always
  connect to the same database URL that the running application uses.  The URL is
  resolved from ``QUALBOT_DATABASE_URL`` / the ``.env`` file via Pydantic Settings,
  not from the ``sqlalchemy.url`` key in alembic.ini.

Usage
-----
Online migration (default)::

    alembic upgrade head          # apply all pending migrations
    alembic downgrade -1          # roll back the most recent migration
    alembic revision --autogenerate -m "describe change"

Offline migration (SQL script generation)::

    alembic upgrade head --sql    # emit raw SQL without connecting
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

# ---------------------------------------------------------------------------
# Alembic config object — provides access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import models so that Base.metadata is fully populated before autogenerate.
# ---------------------------------------------------------------------------
import app.domain.models  # noqa: F401, E402
from app.domain.base import Base  # noqa: E402

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Helper: resolve the database URL from application Settings
# ---------------------------------------------------------------------------


def _get_url() -> str:
    """Return the database URL to use for migrations.

    Priority:
    1. ``sqlalchemy.url`` from the Alembic config (allows tests and CLI to override).
    2. ``QUALBOT_DATABASE_URL`` via Pydantic Settings (normal application path).
    3. Hard-coded SQLite fallback.

    The Alembic config takes priority so that callers like ``cfg.set_main_option(
    "sqlalchemy.url", "sqlite:///test.db")`` work correctly in test fixtures.
    """
    # Check if the Alembic config has a non-default URL set (tests override this)
    try:
        cfg_url = config.get_main_option("sqlalchemy.url")
        if cfg_url and not cfg_url.startswith("sqlite:///./qualbot_dev.db"):
            return cfg_url
    except Exception:
        pass

    try:
        from app.core.config import get_settings

        return get_settings().database_url
    except Exception:  # pragma: no cover — fallback when settings unavailable
        return config.get_main_option("sqlalchemy.url", "sqlite:///./qualbot.db")



# ---------------------------------------------------------------------------
# Offline mode — emits SQL without a live DB connection
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script output).

    Configures the context with a URL only; no DBAPI connection is created.
    Useful for generating SQL scripts to review before applying to production.
    """
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Emit CHECK constraints rendered inline in CREATE TABLE
        render_as_batch=url.startswith("sqlite"),
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connects to the live database
# ---------------------------------------------------------------------------


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a live database connection.

    Uses the Alembic config URL if explicitly set (e.g. by tests), otherwise
    falls back to the application's ``engine_from_settings`` factory so that
    the engine configuration is identical to what the application uses at runtime.
    """
    url = _get_url()
    from sqlalchemy import create_engine, event

    from app.persistence.database import _set_sqlite_pragma

    is_sqlite = url.startswith("sqlite")
    connectable = create_engine(
        url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    if is_sqlite:
        event.listen(connectable, "connect", _set_sqlite_pragma)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Use batch mode for SQLite, which does not support ALTER TABLE.
            render_as_batch=is_sqlite,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

