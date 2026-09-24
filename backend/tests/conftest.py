"""Shared pytest fixtures for the QualBot backend test suite.

Provides:
  - ``engine``  : in-memory SQLite engine with FK enforcement (session-scoped).
  - ``tables``  : creates all ORM-defined tables once per session, drops on teardown.
  - ``db``      : a fresh SQLAlchemy Session per test function, rolled back on teardown.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.persistence.database import init_db, make_test_engine


@pytest.fixture(scope="session")
def engine():
    """Session-scoped in-memory SQLite engine with FK enforcement enabled."""
    _engine = make_test_engine()
    init_db(_engine)
    yield _engine
    _engine.dispose()


@pytest.fixture()
def db(engine) -> Session:
    """Function-scoped database session.

    Each test gets a clean session backed by a connection-level transaction that
    is rolled back after the test, keeping tests isolated without truncating
    tables between runs.

    We use a SAVEPOINT (nested transaction) so that IntegrityError-raising tests
    can roll back to the savepoint and continue, without invalidating the outer
    connection-level transaction.
    """
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    trans.rollback()
    connection.close()

