import sys
from types import ModuleType
from datetime import date, datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

from app_modules.session_cookies import (
    COOKIE_NAME,
    delete_cookie_script,
    inactivity_logout_script,
    read_refresh_cookie,
    set_cookie_script,
)
from app.db.models import Lote, ScanEvent, Trabajador


# -------------------------
# Session cookies / inactividad
# -------------------------
def _fake_st(cookies: dict):
    class _Context:
        pass

    module = ModuleType("fake_st")
    ctx = _Context()
    ctx.cookies = cookies
    module.context = ctx
    return module


def test_read_refresh_cookie_returns_token_and_handles_missing_context():
    st_mod = _fake_st({COOKIE_NAME: "  abc.def.ghi  "})
    assert read_refresh_cookie(st_mod) == "abc.def.ghi"
    assert read_refresh_cookie(_fake_st({})) is None
    assert read_refresh_cookie(_fake_st({COOKIE_NAME: "   "})) is None

    class _Broken:
        @property
        def context(self):
            raise RuntimeError("sin contexto")

    assert read_refresh_cookie(_Broken()) is None


def test_set_and_delete_cookie_scripts_target_parent_window():
    set_js = set_cookie_script("tok-123")
    assert COOKIE_NAME in set_js and "tok-123" in set_js
    assert "window.parent.document.cookie" in set_js
    assert "SameSite=Lax" in set_js
    assert "Max-Age" not in set_js  # sesión por defecto

    persistent_js = set_cookie_script("tok-123", max_age_days=7)
    assert "Max-Age=604800" in persistent_js

    delete_js = delete_cookie_script()
    assert "Max-Age=0" in delete_js
    assert COOKIE_NAME in delete_js


def test_inactivity_monitor_watches_user_activity_and_expires_session():
    js = inactivity_logout_script(120)
    assert "IDLE_MS = 7200000" in js  # 120 min en ms
    # Escucha actividad real de teclado/mouse en la ventana principal.
    for evento in ("mousemove", "keydown", "mousedown", "touchstart"):
        assert f"'{evento}'" in js
    assert "window.parent" in js
    # Al expirar: borra la cookie de sesión y recarga -> vuelve al login.
    assert "Max-Age=0" in js
    assert "P.location.reload()" in js
    # Marcador compartido entre pestañas + guarda anti-duplicados.
    assert "localStorage" in js
    assert "__qrIdleWatch" in js


def test_inactivity_minutes_are_configurable():
    assert "IDLE_MS = 300000" in inactivity_logout_script(5)


# -------------------------
# Backend: reportes por rango de fechas
# -------------------------
SCRIPT_REPORTES = None  # los reportes de API se prueban directo con TestClient


@pytest.fixture
def reportes_app(engine, client, session_factory, user):
    """Crea dos lotes con lecturas en días distintos para probar los filtros."""
    if engine.dialect.name != "postgresql":
        pytest.skip("Los reportes con rango de fechas requieren PostgreSQL")
    user["rol"] = "ROOT"
    with session_factory() as db:
        db.add(Trabajador(dni="11111111", nombre="ANA", apellido_paterno="PEREZ",
                          apellido_materno=None, rol="EMPACADOR", num_orden=1,
                          cod_letra="A001", activo=True))
        lot_a = Lote(codigo="REP-A", estado="ABIERTO")
        lot_b = Lote(codigo="REP-B", estado="ABIERTO")
        db.add_all([lot_a, lot_b])
        db.flush()
        d1 = datetime(2026, 3, 5, 17, 0, tzinfo=timezone.utc).astimezone(timezone.utc).replace(tzinfo=None)
        d2 = datetime(2026, 3, 10, 17, 0, tzinfo=timezone.utc).astimezone(timezone.utc).replace(tzinfo=None)
        db.add(ScanEvent(token="r1", dni="11111111", lote_id=lot_a.id, scanned_at=d1,
                        raw={"id": "12", "p": "PALTA"}, user_id="op1", session_uuid="s1"))
        db.add(ScanEvent(token="r2", dni="11111111", lote_id=lot_b.id, scanned_at=d2,
                        raw={"id": "AB", "p": "PALTA"}, user_id="op2", session_uuid="s2"))
        db.commit()
    return client


def test_dni_summary_by_date_range_covers_all_lotes(reportes_app):
    data = reportes_app.get("/api/reports/dni-summary",
                            params={"date_from": "2026-03-01", "date_to": "2026-03-31"}).json()
    assert data["totals"]["total_lecturas"] == 2
    assert {r["dni"] for r in data["rows"]} == {"11111111"}
    assert data["date_from"] == "2026-03-01"

    solo_d1 = reportes_app.get("/api/reports/dni-summary",
                               params={"date_from": "2026-03-05", "date_to": "2026-03-05"}).json()
    assert solo_d1["totals"]["total_lecturas"] == 1
    assert solo_d1["totals"]["emp_lecturas"] == 1

    vacio = reportes_app.get("/api/reports/dni-summary",
                             params={"date_from": "2026-01-01", "date_to": "2026-01-31"}).json()
    assert vacio["totals"]["total_lecturas"] == 0


def test_dni_summary_by_lote_and_combined_filters(reportes_app):
    por_lote = reportes_app.get("/api/reports/dni-summary",
                               params={"lote_codigo": "REP-B"}).json()
    assert por_lote["totals"]["total_lecturas"] == 1
    assert por_lote["totals"]["sel_lecturas"] == 1

    combinado = reportes_app.get("/api/reports/dni-summary",
                                 params={"lote_codigo": "REP-B",
                                         "date_from": "2026-03-05", "date_to": "2026-03-05"}).json()
    assert combinado["totals"]["total_lecturas"] == 0  # REP-B es del día 10


def test_operator_summary_accepts_date_range(reportes_app):
    data = reportes_app.get("/api/reports/operator-summary",
                            params={"date_from": "2026-03-10", "date_to": "2026-03-10"}).json()
    rows = {r["user_id"]: r for r in data["rows"]}
    assert rows["op2"]["total"] == 1
    assert "op1" not in rows


def test_reports_reject_partial_or_invalid_dates(reportes_app):
    assert reportes_app.get("/api/reports/dni-summary",
                            params={"date_from": "2026-03-01"}).status_code == 400
    assert reportes_app.get("/api/reports/dni-summary",
                            params={"date_from": "2026-03-09", "date_to": "2026-03-01"}).status_code == 400
    assert reportes_app.get("/api/reports/dni-summary",
                            params={"date_from": "31-03-2026", "date_to": "2026-03-31"}).status_code == 400
    assert reportes_app.get("/api/reports/operator-summary",
                            params={"date_to": "2026-03-31"}).status_code == 400
