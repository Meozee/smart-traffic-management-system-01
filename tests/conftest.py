"""Pytest configuration and shared fixtures for STMS backend tests."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from layer2_backend import database, dependencies, models
from layer2_backend.main import app, init_default_cameras
from layer2_backend.routers import auth


TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


class DummyScheduler:
    """Minimal scheduler replacement to avoid background job startup during tests."""

    def __init__(self):
        self.running = False

    def add_job(self, *args, **kwargs):
        return None

    def start(self):
        self.running = True

    def shutdown(self):
        self.running = False


@pytest.fixture(scope="session")
def sqlite_engine():
    """Create a single in-memory SQLite engine for the entire test session."""
    engine = create_engine(
        TEST_SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    models.Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(sqlite_engine):
    """Provide a SQLAlchemy session wrapped in a rollback transaction for isolation."""
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    SessionTesting = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False
    )
    session = SessionTesting()
    try:
        yield session
    finally:
        transaction.rollback()
        session.close()
        connection.close()


@pytest.fixture(scope="function")
def test_client(monkeypatch, sqlite_engine, db_session):
    """TestClient fixture using SQLite in-memory DB and overridden database dependency."""

    monkeypatch.setattr(database, "engine", sqlite_engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False))
    monkeypatch.setattr("layer2_backend.main.init_default_cameras", lambda: None)
    monkeypatch.setattr("layer2_backend.main.scheduler", DummyScheduler())

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[dependencies.get_db] = override_get_db
    app.dependency_overrides[auth.get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def create_user(db_session):
    """Factory fixture to create users with hashed passwords in the test database."""

    def _create(username: str, role: str, password: str = "testpassword"):
        user = models.UserAccount(
            user_id=f"USR-{username.upper()}",
            username=username,
            password_hash=auth.get_password_hash(password),
            role=role,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def admin_user(create_user):
    return create_user("admin", "admin")


@pytest.fixture
def supervisor_user(create_user):
    return create_user("supervisor", "supervisor")


@pytest.fixture
def management_user(create_user):
    return create_user("management", "management")


@pytest.fixture
def admin_token(admin_user):
    return auth.create_access_token(
        data={
            "sub": admin_user.username,
            "role": admin_user.role,
            "user_id": admin_user.user_id
        }
    )


@pytest.fixture
def supervisor_token(supervisor_user):
    return auth.create_access_token(
        data={
            "sub": supervisor_user.username,
            "role": supervisor_user.role,
            "user_id": supervisor_user.user_id
        }
    )


@pytest.fixture
def management_token(management_user):
    return auth.create_access_token(
        data={
            "sub": management_user.username,
            "role": management_user.role,
            "user_id": management_user.user_id
        }
    )


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def supervisor_headers(supervisor_token):
    return {"Authorization": f"Bearer {supervisor_token}"}


@pytest.fixture
def management_headers(management_token):
    return {"Authorization": f"Bearer {management_token}"}
