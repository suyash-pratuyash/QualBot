"""Shared SQLAlchemy 2.x declarative base and column mixins.

All models inherit from ``Base``.  Common columns (UUID PK, timestamps) are supplied by
the ``UUIDPrimaryKeyMixin`` and ``TimestampMixin`` so every table uses the same
conventions without repetition.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now_utc() -> datetime:
    """Return current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base.

    All ORM model classes must inherit from this.  SQLAlchemy 2.x uses the
    ``DeclarativeBase`` style which provides full ``Mapped`` / ``mapped_column``
    typing support.
    """


class UUIDPrimaryKeyMixin:
    """Adds an application-generated UUID4 primary key column named ``id``.

    The UUID is generated in Python (``uuid.uuid4``), not in the database, so
    it works identically on SQLite and PostgreSQL and is available before the
    row is flushed.
    """

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        sort_order=-10,
    )


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns to an ORM model.

    Both columns are timezone-aware UTC ``DATETIME`` / ``TIMESTAMPTZ`` values.
    ``created_at`` is set once on insert.  ``updated_at`` is set on insert and
    updated automatically on every subsequent flush via ``onupdate``.

    SQLAlchemy maps ``DateTime(timezone=True)`` to:
      - ``DATETIME`` on SQLite (stores the ISO string with offset; SQLite has no
        native timezone type but the value round-trips correctly with Python).
      - ``TIMESTAMPTZ`` on PostgreSQL (full server-side timezone support).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now_utc,
        sort_order=90,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now_utc,
        onupdate=_now_utc,
        sort_order=91,
    )
