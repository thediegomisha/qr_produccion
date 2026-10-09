import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "ui_web"))

# Route imports must never load the application entrypoint or production .env.
os.environ["DATABASE_URL"] = "sqlite://"

from app.api import routes_dashboard, routes_lotes, routes_scans
from app.core.auth_dep import get_current_user
from app.db.models import Base


@pytest.fixture(scope="session")
def engine():
    url = os.getenv("TEST_DATABASE_URL", "sqlite://")
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite" and parsed.database not in (None, "", ":memory:"):
        raise RuntimeError("Las pruebas SQLite deben utilizar una base en memoria")
    if parsed.get_backend_name() != "sqlite" and parsed.database != "qr_lotes_test":
        raise RuntimeError("Las pruebas PostgreSQL requieren una base aislada llamada qr_lotes_test")
    kwargs = {}
    if parsed.get_backend_name() == "sqlite":
        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    database = create_engine(url, **kwargs)
    if parsed.get_backend_name() == "sqlite":
        @event.listens_for(database, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(database)
    yield database
    Base.metadata.drop_all(database)
    database.dispose()


@pytest.fixture
def session_factory(engine, monkeypatch):
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    factory = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(routes_lotes, "SessionLocal", factory)
    monkeypatch.setattr(routes_scans, "SessionLocal", factory)
    monkeypatch.setattr(routes_dashboard, "SessionLocal", factory)
    return factory


@pytest.fixture
def user():
    return {"usuario": "usuario-prueba", "rol": "ROOT"}


@pytest.fixture
def app(session_factory, user):
    application = FastAPI()
    application.include_router(routes_lotes.router, prefix="/api")
    application.include_router(routes_scans.router, prefix="/api")
    application.include_router(routes_dashboard.router, prefix="/api")
    application.dependency_overrides[get_current_user] = lambda: user
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as api:
        yield api
