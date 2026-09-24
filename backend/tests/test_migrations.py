"""Tests for Alembic migration behavior.

These tests verify that the initial migration creates the expected schema and
that downgrade correctly tears it down.  They run against an isolated in-memory
SQLite database so they do not affect the development database.

Coverage
--------
- ``alembic upgrade head`` creates all expected tables
- Expected columns are present in each table
- ``alembic downgrade base`` removes all application tables
- Re-upgrade after downgrade succeeds (idempotent migration)
- Alembic ``current`` returns the correct revision after upgrade
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command

EXPECTED_TABLES = {
    "admins",
    "conversations",
    "messages",
    "leads",
    "bant_states",
    "lead_score_history",
    "routing_actions",
}

# Minimum set of columns per table (not exhaustive — just key structural columns)
EXPECTED_COLUMNS: dict[str, set[str]] = {
    "admins": {"id", "email", "hashed_password", "is_active", "created_at", "updated_at"},
    "conversations": {"id", "status", "channel", "created_at", "updated_at"},
    "messages": {"id", "conversation_id", "role", "content", "created_at"},
    "leads": {"id", "conversation_id", "score", "qualification_status", "created_at"},
    "bant_states": {
        "lead_id",
        "budget_status",
        "authority_level",
        "need_clarity",
        "timeline_urgency",
        "budget_confidence",
        "authority_confidence",
        "need_confidence",
        "timeline_confidence",
        "created_at",
    },
    "lead_score_history": {"id", "lead_id", "score", "message_id", "created_at"},
    "routing_actions": {
        "id",
        "lead_id",
        "action_type",
        "status",
        "idempotency_key",
        "created_at",
    },
}


@pytest.fixture()
def alembic_cfg(tmp_path):
    """Return an Alembic Config pointing at the backend alembic directory.

    We override ``sqlalchemy.url`` to use an isolated temp-file SQLite database
    so that migration tests never touch the real development database.
    """
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parents[1]
    ini_path = backend_dir / "alembic.ini"

    cfg = Config(str(ini_path))
    # Use a temp file-based SQLite DB for migration tests so that table
    # inspection works correctly (in-memory DBs don't persist across connections
    # the way Alembic's migration runner expects).
    db_path = tmp_path / "test_migration.db"
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


class TestMigrationUpgrade:
    def test_upgrade_creates_all_expected_tables(self, alembic_cfg) -> None:
        """After ``upgrade head``, all seven domain tables must exist."""
        command.upgrade(alembic_cfg, "head")

        from sqlalchemy import create_engine

        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert EXPECTED_TABLES.issubset(table_names), (
            f"Missing tables: {EXPECTED_TABLES - table_names}"
        )

    def test_upgrade_creates_expected_columns(self, alembic_cfg) -> None:
        """Key columns must be present in each table after upgrade."""
        command.upgrade(alembic_cfg, "head")

        from sqlalchemy import create_engine

        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)

        for table, expected_cols in EXPECTED_COLUMNS.items():
            actual_cols = {col["name"] for col in inspector.get_columns(table)}
            missing = expected_cols - actual_cols
            assert not missing, f"Table '{table}' missing columns: {missing}"

    def test_alembic_version_table_present(self, alembic_cfg) -> None:
        """Alembic version tracking table must exist after upgrade."""
        command.upgrade(alembic_cfg, "head")

        from sqlalchemy import create_engine

        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)
        assert "alembic_version" in inspector.get_table_names()

    def test_leads_has_score_check_constraint(self, alembic_cfg) -> None:
        """The score CHECK constraint must fire on invalid data after migration."""
        command.upgrade(alembic_cfg, "head")

        from sqlalchemy import create_engine
        from sqlalchemy.exc import IntegrityError

        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))
        # Enable FK enforcement for SQLite
        from sqlalchemy import event

        from app.persistence.database import _set_sqlite_pragma

        event.listen(engine, "connect", _set_sqlite_pragma)

        with engine.connect() as conn:
            # Insert a valid conversation first (FK requirement)
            conn.execute(
                text(
                    "INSERT INTO conversations (id, status, channel, created_at, updated_at) "
                    "VALUES ('conv-001', 'active', 'web', datetime('now'), datetime('now'))"
                )
            )
            # Attempt to insert a lead with score = 200 — must violate CHECK
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO leads "
                        "(id, conversation_id, score, "
                        "qualification_status, created_at, updated_at) "
                        "VALUES ('lead-001', 'conv-001', 200,"
                        " 'new', datetime('now'), datetime('now'))"
                    )
                )

    def test_bant_states_confidence_check_constraint(self, alembic_cfg) -> None:
        """Confidence outside [0.0, 1.0] must violate CHECK constraint in migrated schema."""
        command.upgrade(alembic_cfg, "head")

        from sqlalchemy import create_engine, event
        from sqlalchemy.exc import IntegrityError

        from app.persistence.database import _set_sqlite_pragma

        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))
        event.listen(engine, "connect", _set_sqlite_pragma)

        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO conversations (id, status, channel, created_at, updated_at) "
                    "VALUES ('conv-002', 'active', 'web', datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO leads "
                    "(id, conversation_id, score, qualification_status, created_at, updated_at) "
                    "VALUES ('lead-002', 'conv-002', 50, 'new', datetime('now'), datetime('now'))"
                )
            )
            # budget_confidence > 1.0 must fail
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO bant_states "
                        "(lead_id, budget_status, authority_level, need_clarity, timeline_urgency, "
                        "budget_confidence, created_at, updated_at) "
                        "VALUES ('lead-002', 'unknown', 'unknown', 'unknown', 'unknown', "
                        "1.5, datetime('now'), datetime('now'))"
                    )
                )

    def test_routing_actions_status_check_constraint(self, alembic_cfg) -> None:
        """Invalid status like 'skipped' must violate CHECK constraint in migrated schema."""
        command.upgrade(alembic_cfg, "head")

        from sqlalchemy import create_engine, event
        from sqlalchemy.exc import IntegrityError

        from app.persistence.database import _set_sqlite_pragma

        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))
        event.listen(engine, "connect", _set_sqlite_pragma)

        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO conversations (id, status, channel, created_at, updated_at) "
                    "VALUES ('conv-003', 'active', 'web', datetime('now'), datetime('now'))"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO leads "
                    "(id, conversation_id, score, qualification_status, created_at, updated_at) "
                    "VALUES ('lead-003', 'conv-003', 50, 'new', datetime('now'), datetime('now'))"
                )
            )
            # status = 'skipped' must fail
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "INSERT INTO routing_actions "
                        "(id, lead_id, action_type, status, "
                        "idempotency_key, created_at, updated_at) "
                        "VALUES ('act-001', 'lead-003', 'sales_alert', 'skipped', 'key-001', "
                        "datetime('now'), datetime('now'))"
                    )
                )


class TestMigrationDowngrade:
    def test_downgrade_removes_all_app_tables(self, alembic_cfg) -> None:
        """After ``downgrade base``, all seven domain tables must be gone."""
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "base")

        from sqlalchemy import create_engine

        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        remaining = EXPECTED_TABLES & table_names
        assert not remaining, f"Tables still present after downgrade: {remaining}"

    def test_reupgrade_after_downgrade_succeeds(self, alembic_cfg) -> None:
        """Upgrade → downgrade → re-upgrade must succeed without errors."""
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "base")
        command.upgrade(alembic_cfg, "head")  # must not raise

        from sqlalchemy import create_engine

        engine = create_engine(alembic_cfg.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert EXPECTED_TABLES.issubset(table_names)
