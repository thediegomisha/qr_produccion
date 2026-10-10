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
    when = datetime(2026, 1, 5, 17, 0, tzinfo=timezone.utc).astimezone(timezone.utc).replace(tzinfo=None)
    with session_factory() as db:
        db.add(Trabajador(dni="11111111", nombre="ANA", apellido_paterno="PEREZ", apellido_materno=None,
                          rol="EMPACADOR", num_orden=1, cod_letra="A001", activo=True))
        for i, marker in enumerate(["1", "2", "AB"]):
            db.add(ScanEvent(token=f"tok{i}", dni="11111111" if marker != "AB" else "22222222",
                             lote_id=lote["id"], scanned_at=when, raw={"id": marker, "p": "PALTA"},
                             user_id="op1", session_uuid="s1"))
        db.commit()
    return lote


def _run_with_dates(at, day: date):
    at.date_input(key="dashboard_desde").set_value(day)
    at.date_input(key="dashboard_hasta").set_value(day)
    at = at.run(timeout=20)
    assert not at.exception
    return at


def test_dashboard_is_lote_first_with_plecto_style_kpis(ui_api, client, session_factory, engine, user):
    lote = _seed(client, session_factory, engine)
    user["rol"] = "SUPERVISOR"
    ui_api.ROLE = "SUPERVISOR"
    at = AppTest.from_string(SCRIPT).run(timeout=20)
    assert not at.exception
    at = _run_with_dates(at, date(2026, 1, 5))

    values = [m.value for m in at.markdown]

    # Tarjetas KPI estilo Plecto: números grandes dentro de tarjetas HTML.
    kpis = {
        "Cajas totales": "3",
        "Empacadas": "2",
        "Seleccionadas": "1",
        "Personas activas": "2",
        "Días trabajados": "1",
    }
    for label, number in kpis.items():
        card = next(v for v in values if label in v)
        assert f">{number}<" in card, f"KPI {label} no muestra {number}"

    # La gráfica por LOTE es la sección principal y aparece antes que la vista por día.
    idx_lote = next(i for i, v in enumerate(values) if "Cajas por lote" in v)
    idx_dia = next(i for i, v in enumerate(values) if "Cajas por día" in v)
    assert idx_lote < idx_dia

    # El ranking estilo Plecto muestra medallas para el personal.
    assert "🥇" in "".join(values)

    # La tabla resumen por lote muestra el lote sembrado con sus totales.
    lote_table = next(df.value for df in at.dataframe if "lote" in df.value.columns)
    fila = lote_table[lote_table["lote"] == lote["codigo"]].iloc[0]
    assert fila["total"] == 3
    assert fila["empacadas"] == 2
    assert fila["seleccionadas"] == 1

    # La tabla de eficiencia lista al trabajador conocido.
    eff_table = next(df.value for df in at.dataframe if "persona" in df.value.columns)
    ana = eff_table[eff_table["dni"] == "11111111"].iloc[0]
    assert ana["persona"] == "PEREZ  ANA"
    assert ana["total_cajas"] == 2

    # Secciones del paquete completo: donut, ritmo horario, meta, heatmap y actividad.
    joined = "\n".join(values)
    assert "Distribución" in joined
    assert "Ritmo por hora del día" in joined
    assert "Tendencia diaria vs meta" in joined
    assert "Producción por persona y lote" in joined
    assert "Actividad reciente" in joined
    assert at.number_input(key="dashboard_meta") is not None

    # Filtrar por el lote mantiene la página funcionando.
    at.selectbox(key="dashboard_lote").set_value(lote["codigo"])
    at = at.run(timeout=20)
    assert not at.exception


def test_dashboard_empty_range_shows_info(ui_api, client, engine, user):
    if engine.dialect.name != "postgresql":
        pytest.skip("El dashboard requiere PostgreSQL")
    user["rol"] = "SUPERVISOR"
    ui_api.ROLE = "SUPERVISOR"
    at = AppTest.from_string(SCRIPT).run(timeout=20)
    assert not at.exception
    assert any("No hay lecturas registradas" in info.value for info in at.info)


def test_dashboard_empty_range_points_to_last_reading_and_jumps(ui_api, client, session_factory, engine, user):
    """Con lecturas fuera del rango por defecto, avisa la última fecha y salta a ella."""
    if engine.dialect.name != "postgresql":
        pytest.skip("El dashboard requiere PostgreSQL")
    _seed(client, session_factory, engine)  # lecturas del 05/01/2026
    user["rol"] = "SUPERVISOR"
    ui_api.ROLE = "SUPERVISOR"

    at = AppTest.from_string(SCRIPT).run(timeout=20)
    assert not at.exception

    # El rango por defecto (últimos 7 días) está vacío pero existe data histórica.
    warnings_text = [w.value for w in at.warning]
    assert any("última lectura" in w for w in warnings_text)
    assert any("05/01/2026" in w for w in warnings_text)

    # Atajos de rango visibles.
    labels = [b.label for b in at.button]
    for preset in ("Hoy", "7 días", "30 días", "90 días"):
        assert preset in labels

    # El botón de salto ajusta el rango y muestra los datos de ese día.
    next(b for b in at.button if b.label == "🔍 Ver el día de la última lectura").click()
    at = at.run(timeout=20)
    assert not at.exception
    values = [m.value for m in at.markdown]
    card = next(v for v in values if "Cajas totales" in v)
    assert ">3<" in card

    # El atajo "Hoy" limpia el rango de nuevo (hoy no tiene lecturas -> aviso).
    next(b for b in at.button if b.label == "Hoy").click()
    at = at.run(timeout=20)
    assert not at.exception
    assert any("última lectura" in w.value for w in at.warning)


def test_dashboard_blocks_operators(ui_api, client, engine, user):
    if engine.dialect.name != "postgresql":
        pytest.skip("El dashboard requiere PostgreSQL")
    user["rol"] = "OPERADOR"
    ui_api.ROLE = "OPERADOR"
    at = AppTest.from_string(SCRIPT).run(timeout=20)
    assert not at.exception
    assert any("permisos" in message.value for message in at.error)
