import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest import mock


def passthrough_decorator(*args, **kwargs):
    """Passthrough decorator that doesn't do rate limiting"""

    def decorator(func):
        return func

    return decorator


class MockCryptoHandler:
    """mock crypto handler for testing"""

    def decrypt_password(self, encrypted_password: str) -> str:
        return encrypted_password


mock.patch("slowapi.Limiter.limit", passthrough_decorator).start()
mock.patch("slowapi.Limiter.shared_limit", passthrough_decorator).start()
mock.patch("app.core.crypto.CryptoHandler", MockCryptoHandler).start()

# ruff: noqa: E402
from app.main import app
from app.database import Base
from app.database import get_db as database_get_db
from app.dependencies import get_db as dependencies_get_db
from app.core.config import settings
from app import models
from app.core.hashing import Hasher

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """create a test client with overridden database dependency"""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[database_get_db] = override_get_db
    app.dependency_overrides[dependencies_get_db] = override_get_db

    async def passthrough_middleware(self, request, call_next):
        """passthrough middleware that doesnt do rate limiting"""
        response = await call_next(request)
        return response

    with (
        mock.patch("app.core.storage.create_minio_bucket_if_not_exists"),
        mock.patch("app.core.scheduler.init_scheduler"),
        mock.patch("app.core.scheduler.start_scheduler"),
        mock.patch("app.core.scheduler.shutdown_scheduler"),
        mock.patch("slowapi.middleware.SlowAPIMiddleware.dispatch", passthrough_middleware),
    ):
        with TestClient(app, base_url="http://localhost:8000") as test_client:
            yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db_session):
    """create a test user"""
    user = models.User(
        email="test@example.com",
        username="testuser",
        hashed_password=Hasher.get_password_hash("Test123!@#"),
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_superuser(db_session):
    """create a test superuser"""
    user = models.User(
        email="admin@example.com",
        username="adminuser",
        hashed_password=Hasher.get_password_hash("Admin123!@#"),
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def auth_headers(client, test_user):
    """get authentication headers for test user"""
    response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={
            "username": "testuser",
            "password": "Test123!@#",
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def admin_auth_headers(client, test_superuser):
    """get authentication headers for admin user"""
    response = client.post(
        f"{settings.API_V1_STR}/users/token",
        data={
            "username": "adminuser",
            "password": "Admin123!@#",
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
