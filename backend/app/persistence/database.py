"""Database engine and session factory for the QualBot backend.

Usage
-----
In FastAPI route handlers, use the ``get_db`` dependency::

    @router.get("/example")
    def read_example(db: Session = Depends(get_db)):
        ...

In tests, create an in-memory SQLite engine via ``create_engine`` and override
the ``get_db`` dependency to inject a scoped test session.

The ``engine_from_settings`` helper is also imported by ``alembic/env.py`` so
that Alembic uses the exact same engine configuration as the application.

SQLite notes
------------
SQLite does not enforce foreign keys by default; the ``_set_sqlite_pragma``
listener emits ``PRAGMA foreign_keys = ON`` on every new connection so that
``ondelete`` constraints behave correctly in the test and development databases.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings

# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _set_sqlite_pragma(dbapi_conn: Any, _connection_record: Any) -> None:  # noqa: ANN401
    """Enable foreign-key enforcement on every new SQLite connection.

    This is a no-op on PostgreSQL connections because the driver will not have a
    ``cursor`` attribute with the SQLite pragma pattern; SQLAlchemy emits this
    event only for the matching dialect.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def engine_from_settings(settings: Settings | None = None) -> Engine:
    """Create and return a SQLAlchemy :class:`~sqlalchemy.Engine`.

    Parameters
    ----------
    settings:
        Application settings instance.  Defaults to the cached singleton
        returned by :func:`~app.core.config.get_settings`.

    Returns
    -------
    Engine
        Configured engine for the database described by ``settings.database_url``.
    """
    cfg = settings or get_settings()
    is_sqlite = cfg.database_url.startswith("sqlite")
    engine = create_engine(
        cfg.database_url,
        # SQLite does not support connection pooling; use StaticPool for in-memory
        # URLs or NullPool for file-based URLs.  For PostgreSQL the default pool
        # is appropriate.
        connect_args={"check_same_thread": False} if is_sqlite else {},
        echo=False,
    )
    if is_sqlite:
        event.listen(engine, "connect", _set_sqlite_pragma)
    return engine


# ---------------------------------------------------------------------------
# Module-level singletons (lazy initialisation via get_db)
# ---------------------------------------------------------------------------

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = engine_from_settings()
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal  # noqa: PLW0603
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=_get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy :class:`~sqlalchemy.orm.Session` for use in a request.

    The session is automatically closed (and any uncommitted transaction rolled
    back) when the request context exits, regardless of whether an exception was
    raised.

    Typical usage::

        from fastapi import Depends
        from app.persistence.database import get_db
        from sqlalchemy.orm import Session

        @router.get("/leads")
        def list_leads(db: Session = Depends(get_db)):
            ...
    """
    SessionLocal = _get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_test_engine(url: str = "sqlite:///:memory:") -> Engine:
    """Create an isolated in-memory SQLite engine for use in tests.

    Registers the foreign-key pragma listener automatically so tests exercise
    the same FK enforcement as the development database.

    Parameters
    ----------
    url:
        Database URL.  Defaults to an in-memory SQLite database.
    """
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _set_sqlite_pragma)
    return engine


def init_db(engine: Engine) -> None:
    """Create all tables defined by the ORM metadata.

    This is a convenience helper for tests and initial local setup.  In
    production, schema changes are managed exclusively through Alembic
    migrations.
    """
    # Import models to ensure they are registered on Base.metadata before
    # create_all is called.
    import app.domain.models  # noqa: F401
    from app.domain.base import Base

    Base.metadata.create_all(bind=engine)


def drop_db(engine: Engine) -> None:
    """Drop all tables — for test teardown only.  Never call in production."""
    import app.domain.models  # noqa: F401
    from app.domain.base import Base

    Base.metadata.drop_all(bind=engine)
