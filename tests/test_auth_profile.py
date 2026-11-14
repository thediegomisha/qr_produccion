import pytest
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_auth
from app.db.models import Usuario
from app_modules.modules import sidebar


def test_sidebar_shows_name_and_nickname_as_escaped_text(monkeypatch):
    rendered = []
    fake_sidebar = SimpleNamespace(
        markdown=lambda text, **kwargs: rendered.append(text),
        warning=lambda *args: None,
        button=lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(sidebar, "st", SimpleNamespace(sidebar=fake_sidebar))
    sidebar.render_user_sidebar(
        "ana<admin>", "OPERADOR", [], lambda value: value, "test",
        nombre="Ana <script>alert(1)</script>",
    )
    panel = rendered[0]
    assert "Ana &lt;script&gt;alert(1)&lt;/script&gt;" in panel
    assert "@ana&lt;admin&gt;" in panel
    assert "<script>" not in panel


@pytest.mark.parametrize("nombre", ["Ana Pérez García", None, ""])
def test_login_refresh_and_profile_include_name_without_changing_nickname(
    session_factory, monkeypatch, nombre,
):
    monkeypatch.setattr(routes_auth, "SessionLocal", session_factory)
    monkeypatch.setattr(routes_auth, "verify_password", lambda supplied, stored: supplied == "test-password")
    with session_factory() as db:
        db.add(Usuario(usuario="anita", nombre=nombre, rol="OPERADOR", password_hash="test", activo=True))
        db.commit()
    app = FastAPI()
    app.include_router(routes_auth.router)
    with TestClient(app) as client:
        response = client.post("/auth/login", json={"usuario": "anita", "password": "test-password"})
        assert response.status_code == 200
        data = response.json()
        assert data["usuario"] == "anita"
        assert data["nombre"] == (nombre or "")
        renewed = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
        assert renewed.status_code == 200
        assert renewed.json()["nombre"] == (nombre or "")
        profile = client.get("/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert profile.status_code == 200
        assert profile.json() == {"usuario": "anita", "nombre": nombre or "", "rol": "OPERADOR"}
        assert "password_hash" not in profile.json()
