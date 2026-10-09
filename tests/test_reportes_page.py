import io
import sys
from types import ModuleType

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app_modules.modules.reportes_page import (
    _excel_bytes,
    _printable_html,
    _report_subtitle,
    _safe_filename,
)


SCRIPT = '''
import streamlit as st
from app_modules.modules.reportes_page import render
from lotes_test_api import api_get, api_post, api_put, api_delete, ROLE

def flash_set(tab, kind, msg): ...
def flash_show(tab): ...

st.session_state.auth = {"rol": ROLE}
render(
    st=st, tabs=None, selected_tab="reportes", rol=ROLE, API="http://mock-api",
    auth_headers=None, api_get=api_get, api_post=api_post, api_put=api_put,
    api_delete=api_delete, flash_show=flash_show, flash_set=flash_set,
    get_jwt=lambda: "test-jwt", show_printers_panel=None,
    COLUMNAS_LISTADO=None, COLUMNAS_IMPRESION=None,
)
'''


# -------------------------
# Funciones puras
# -------------------------
def _sample_df():
    return pd.DataFrame([
        {"dni": "11111111", "persona": "PEREZ RUIZ ANA", "empacador": 12, "seleccionador": 0, "total": 12},
        {"dni": "22222222", "persona": "SOTO LUIS", "empacador": 0, "seleccionador": 8, "total": 8},
    ])


def test_excel_bytes_generates_valid_xlsx_with_header_and_rows():
    sub = _report_subtitle("LOTE-1", "", "PALTA")
    data = _excel_bytes(sub, _sample_df())
    assert data[:2] == b"PK"  # firma ZIP/XLSX
    from openpyxl import load_workbook
    book = load_workbook(io.BytesIO(data))
    sheet = book["Reporte"]
    assert sheet["A1"].value == "Sistema de Etiquetas QR — Reporte de producción"
    assert sheet["A2"].value == "Lote: LOTE-1"
    assert sheet["A3"].value == "Producto: PALTA"
    # La tabla arranca tras el bloque de detalle: encabezados y filas en su lugar.
    # (startrow es 0-based: con 4 líneas de detalle, la tabla empieza en la fila 7.)
    assert sheet["A7"].value == "dni"
    assert sheet["A8"].value == "11111111"


def test_printable_html_contains_title_totals_and_table():
    sub = _report_subtitle("LOTE-1", "", "")
    html = _printable_html("Reporte de producción por DNI", sub,
                           [("Total lecturas", 20)], _sample_df())
    assert html.startswith("<!DOCTYPE html>")
    assert "Reporte de producción por DNI" in html
    assert "LOTE-1" in html
    assert "PEREZ RUIZ ANA" in html
    assert "11111111" in html
    assert "<table" in html and "<th>" in html
    # No debe haber etiquetas rotas: el documento cierra correctamente.
    assert html.rstrip().endswith("</html>")


def test_safe_filename_sanitizes_lote_codes():
    assert "/" not in _safe_filename("reporte_dni", "LO/TE 1-2")
    assert "\\" not in _safe_filename("reporte_dni", "LO\\TE")
    assert _safe_filename("reporte_dni", "ABC").startswith("reporte_dni_ABC")
    assert _safe_filename("reporte_dni", "ABC").endswith(".xlsx")


# -------------------------
# Página completa (AppTest)
# -------------------------
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


class _FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


def _patch_reports(monkeypatch, payload):
    import app_modules.modules.reportes_page as page
    monkeypatch.setattr(
        page.requests, "get",
        lambda url, **kwargs: _FakeResponse(payload),
    )


def test_dni_report_renders_and_offers_excel_and_print(ui_api, client, monkeypatch):
    client.post("/api/lotes", json={"codigo": "REP-1"})
    payload = {
        "producto": None, "lote_codigo": "REP-1",
        "totals": {"total_lecturas": 20, "emp_lecturas": 12, "sel_lecturas": 8},
        "rows": [{"dni": "11111111", "persona": "PEREZ RUIZ ANA",
                  "empacador": 12, "seleccionador": 0, "total": 12}],
    }
    _patch_reports(monkeypatch, payload)

    at = AppTest.from_string(SCRIPT).run(timeout=20)
    assert not at.exception
    next(b for b in at.button if b.label == "Generar reporte DNI").click()
    at = at.run(timeout=20)
    assert not at.exception

    # El reporte queda persistido y visible junto a las acciones de exportación
    # (download_button no es capturado por AppTest; su generación es _excel_bytes,
    # cubierta por las pruebas unitarias — si fallara, la página lanzaría excepción).
    assert at.session_state["rep_dni_data"]["totals"]["total_lecturas"] == 20
    assert any("Reporte por DNI" in m.value for m in at.markdown)
    assert len(at.dataframe) >= 1

    # Una segunda re-ejecución (p. ej. al descargar) conserva el reporte.
    at = at.run(timeout=20)
    assert at.session_state["rep_dni_data"] is not None
    assert any("Reporte por DNI" in m.value for m in at.markdown)


def test_operators_report_renders_and_offers_excel(ui_api, client, monkeypatch):
    client.post("/api/lotes", json={"codigo": "REP-2"})
    payload = {
        "producto": None, "lote_codigo": "REP-2", "rows": [
            {"user_id": "op1", "total": 15, "dnis_distintos": 3, "ultima_lectura": "2026-01-05"},
        ],
    }
    _patch_reports(monkeypatch, payload)

    at = AppTest.from_string(SCRIPT).run(timeout=20)
    next(b for b in at.button if b.label == "Generar reporte Operadores").click()
    at = at.run(timeout=20)
    assert not at.exception
    assert at.session_state["rep_op_data"]["rows"][0]["user_id"] == "op1"
    assert any("Reporte por operadores" in m.value for m in at.markdown)
    assert len(at.dataframe) >= 1


def test_report_buttons_stay_disabled_without_lotes(ui_api, monkeypatch):
    _patch_reports(monkeypatch, {"rows": []})
    at = AppTest.from_string(SCRIPT).run(timeout=20)
    assert not at.exception
    generate = next(b for b in at.button if b.label == "Generar reporte DNI")
    assert generate.disabled
    assert "rep_dni_data" not in at.session_state
