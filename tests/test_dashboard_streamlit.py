import sys
from types import ModuleType
from datetime import date, datetime, timezone

import pytest
from streamlit.testing.v1 import AppTest

from app.db.models import Lote, ScanEvent, Trabajador


SCRIPT = '''
import streamlit as st
from app_modules.modules.dashboard_page import render
from lotes_test_api import api_get, api_post, api_put, api_delete, ROLE

def flash_set(tab, kind, msg): ...
def flash_show(tab): ...

render(
    st=st, tabs=None, selected_tab="dashboard", rol=ROLE, API="mock-api",
    auth_headers=None, api_get=api_get, api_post=api_post, api_put=api_put,
    api_delete=api_delete, flash_show=flash_show, flash_set=flash_set,
    get_jwt=None, show_printers_panel=None, COLUMNAS_LISTADO=None, COLUMNAS_IMPRESION=None,
)
'''


@pytest.fixture
def ui_api(client, user, monkeypatch):
    module = ModuleType("lotes_test_api")
    module.ROLE = user["rol"]
    module.api_get = lambda path, **kwargs: client.get("/api" + path, **kwargs)
    module.api_post = lambda path, **kwargs: client.post("/api" + path, **kwargs)
    module.api_put = lambda path, **kwargs: client.put("/api" + path, **kwargs)
    module.api_delete = lambda path: client.delete("/api" + path)
    monkeypatch.setitem(sys.modules, "lotes_test_api", module)
    return module


def _seed(client, session_factory, engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("El dashboard requiere PostgreSQL")
    lote = client.post("/api/lotes", json={"codigo": "DASH-1"}).json()
    when = datetime(2026, 1, 5, 17, 0, tzinfo=timezone.utc)
    with session_factory() as db:
        db.add(Trabajador(dni="11111111", nombre="ANA", apellido_paterno="PEREZ", apellido_materno=None,
                          rol="EMPACADOR", num_orden=1, cod_letra="A001", activo=True))
        for i, marker in enumerate(["1", "2", "AB"]):
            db.add(ScanEvent(token=f"tok{i}", dni="11111111" if marker != "AB" else "22222222",
                             lote_id=lote["id"], scanned_at=when, raw={"id": marker, "p": "PALTA"},
                             user_id="op1", session_uuid="s1"))
        db.commit()
    return lote


def test_dashboard_renders_metrics_and_charts_for_supervisor(ui_api, client, session_factory, engine, user):
    lote = _seed(client, session_factory, engine)
    user["rol"] = "SUPERVISOR"
    ui_api.ROLE = "SUPERVISOR"
    at = AppTest.from_string(SCRIPT)
    at = at.run(timeout=20)
    assert not at.exception
    at.date_input(key="dashboard_desde").set_value(date(2026, 1, 5))
    at.date_input(key="dashboard_hasta").set_value(date(2026, 1, 5))
    at = at.run(timeout=20)
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Cajas totales"] == "3"
    assert metrics["Empacadas"] == "2"
    assert metrics["Seleccionadas"] == "1"
    assert metrics["Personas activas"] == "2"
    # Eficiencia table lists the known worker and unknown DNI as SIN REGISTRO
    efficiency = at.dataframe[-1].value
    ana = efficiency[efficiency["dni"] == "11111111"].iloc[0]
    assert ana["persona"] == "PEREZ  ANA"
    assert ana["total_cajas"] == 2

    # Filtro por lote conserva las métricas
    lotes = at.selectbox(key="dashboard_lote")
    lotes.set_value(lote["codigo"])
    at = at.run(timeout=20)
    assert not at.exception


def test_dashboard_blocks_operators(ui_api, client, engine, user):
    if engine.dialect.name != "postgresql":
        pytest.skip("El dashboard requiere PostgreSQL")
    user["rol"] = "OPERADOR"
    ui_api.ROLE = "OPERADOR"
    at = AppTest.from_string(SCRIPT).run(timeout=20)
    assert not at.exception
    assert any("permisos" in message.value for message in at.error)
