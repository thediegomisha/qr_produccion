import sys
from types import ModuleType

import pytest
from requests import ConnectionError
from streamlit.testing.v1 import AppTest

from app.db.models import Lote, ScanEvent


SCRIPT = '''
import streamlit as st
from app_modules.modules.lotes_page import render
from lotes_test_api import api_get, api_post, api_put, api_delete, ROLE

def flash_set(tab, kind, msg):
    st.session_state["flash"] = {"kind": kind, "msg": msg}

def flash_show(tab):
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash["msg"])

render(
    st=st, tabs=None, selected_tab="lotes", rol=ROLE, API="mock-api",
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


def widget(elements, label):
    return next(item for item in elements if item.label == label)


def run(at):
    at.run(timeout=15)
    assert not at.exception
    return at


def open_lote(at, lote_id):
    widget(at.selectbox, "Seleccionar lote").set_value(lote_id)
    return run(at)


def test_create_and_duplicate_errors_are_visible(ui_api, client):
    at = run(AppTest.from_string(SCRIPT))
    widget(at.text_input, "Código del nuevo lote").set_value("  lote-1  ")
    widget(at.button, "Crear lote").click()
    run(at)
    assert client.get("/api/lotes").json()["items"][0]["codigo"] == "LOTE-1"
    assert any("creado correctamente" in message.value for message in at.success)
    widget(at.text_input, "Código del nuevo lote").set_value("lote-1")
    widget(at.button, "Crear lote").click()
    run(at)
    assert any("409" in message.value for message in at.error)
    assert client.get("/api/lotes").json()["total"] == 1


def test_select_active_lot_and_edit_updates_session_and_preserves_reads(ui_api, client, session_factory):
    lote = client.post("/api/lotes", json={"codigo": "ORIGINAL"}).json()
    with session_factory() as db:
        db.add(ScanEvent(token="existing-read", dni="12345678", lote_id=lote["id"]))
        db.commit()
    at = run(AppTest.from_string(SCRIPT))
    open_lote(at, lote["id"])
    widget(at.button, "Usar como lote activo").click()
    run(at)
    assert at.session_state["active_lote_codigo"] == "ORIGINAL"
    open_lote(at, lote["id"])
    widget(at.text_input, "Código").set_value("NUEVO")
    widget(at.button, "Guardar cambios").click()
    run(at)
    assert at.session_state["active_lote_codigo"] == "NUEVO"
    data = client.get(f"/api/lotes/{lote['id']}").json()
    assert data["codigo"] == "NUEVO"
    assert data["total_lecturas"] == 1
    assert not at.metric, [metric.label for metric in at.metric]
    open_lote(at, lote["id"])
    widget(at.button, "Cerrar lote").click()
    run(at)
    assert at.session_state["active_lote_codigo"] == ""
    open_lote(at, lote["id"])
    assert widget(at.button, "Usar como lote activo").disabled
    widget(at.button, "Reabrir lote (ROOT)").click()
    run(at)
    open_lote(at, lote["id"])
    assert not widget(at.button, "Usar como lote activo").disabled


def test_delete_requires_confirmation_and_clears_active_lot(ui_api, client, session_factory):
    lote = client.post("/api/lotes", json={"codigo": "ELIMINAR"}).json()
    with session_factory() as db:
        db.add(ScanEvent(token="existing-read", dni="12345678", lote_id=lote["id"]))
        db.commit()
    at = AppTest.from_string(SCRIPT)
    at.session_state["active_lote_codigo"] = "ELIMINAR"
    run(at)
    open_lote(at, lote["id"])
    widget(at.button, "Eliminar lote completo").click()
    run(at)
    assert client.get(f"/api/lotes/{lote['id']}").status_code == 200
    assert any("confirmación" in message.value for message in at.warning)
    widget(at.checkbox, "Confirmo eliminar el lote completo y sus lecturas").check()
    widget(at.button, "Eliminar lote completo").click()
    run(at)
    assert client.get(f"/api/lotes/{lote['id']}").status_code == 404
    assert at.session_state["active_lote_codigo"] == ""
    assert any("1 lecturas" in message.value for message in at.success)


def test_bulk_delete_selected_lots_from_grid_requires_confirmation(ui_api, client):
    one = client.post("/api/lotes", json={"codigo": "MAS-1"}).json()
    two = client.post("/api/lotes", json={"codigo": "MAS-2"}).json()
    keep = client.post("/api/lotes", json={"codigo": "MAS-3"}).json()
    at = AppTest.from_string(SCRIPT)
    at.session_state["active_lote_codigo"] = "MAS-1"
    run(at)

    # The editable grid is only available for ROOT; mark two lots for deletion.
    editor_state = {i: {"🗑️ Eliminar": (row["id"] == one["id"] or row["id"] == two["id"])} for i, row in enumerate([one, two, keep])}
    at.session_state["lotes_grilla_masiva"] = {"edited_rows": editor_state, "added_rows": [], "deleted_rows": []}
    run(at)

    # The grid shows the selection summary and the confirmation controls
    # (the API-level deletion behavior is covered by tests/test_lotes_api.py).
    assert any("Seleccionados 2 lote(s)" in message.value for message in at.warning)
    assert widget(at.checkbox, "Confirmo eliminar TODOS los lotes seleccionados junto con sus lecturas")
    remove = widget(at.button, "Eliminar lotes seleccionados")
    assert not remove.disabled


def test_supervisor_can_use_lot_without_edit_or_delete_forms(ui_api, user, client):
    user["rol"] = "SUPERVISOR"
    ui_api.ROLE = "SUPERVISOR"
    lote = client.post("/api/lotes", json={"codigo": "SUPERVISOR"}).json()
    at = run(AppTest.from_string(SCRIPT))
    open_lote(at, lote["id"])
    labels = [button.label for button in at.button]
    assert "Usar como lote activo" in labels
    assert "Guardar cambios" not in labels
    assert "Eliminar lote completo" not in labels
    assert widget(at.button, "Reabrir lote (ROOT)").disabled


def test_network_error_is_visible_without_crashing_the_page(ui_api):
    def unavailable(*args, **kwargs):
        raise ConnectionError("test-only-network-failure")
    ui_api.api_get = unavailable
    at = run(AppTest.from_string(SCRIPT))
    assert any("conectar con la API" in message.value for message in at.error)


def test_pagination_and_search_reset_selection_without_widget_errors(ui_api, session_factory):
    with session_factory() as db:
        db.add_all([Lote(codigo=f"LOTE-{i:03}", estado="ABIERTO") for i in range(1, 52)])
        db.commit()
    at = run(AppTest.from_string(SCRIPT))
    assert len(at.dataframe[0].value) == 50
    widget(at.number_input, "Página").set_value(2)
    run(at)
    assert len(at.dataframe[0].value) == 1
    widget(at.text_input, "Buscar código").set_value("LOTE-051")
    run(at)
    assert widget(at.number_input, "Página").value == 1
    assert at.dataframe[0].value.iloc[0]["codigo"] == "LOTE-051"


def test_gerencia_can_edit_a_closed_lot_without_reopening_it(ui_api, client, user):
    lote = client.post("/api/lotes", json={"codigo": "CERRADO"}).json()
    client.post("/api/lotes/CERRADO/close")
    user["rol"] = "GERENCIA"
    ui_api.ROLE = "GERENCIA"
    at = run(AppTest.from_string(SCRIPT))
    open_lote(at, lote["id"])
    assert widget(at.selectbox, "Estado").options == ["CERRADO"]
    widget(at.text_input, "Código").set_value("RENOMBRADO")
    widget(at.button, "Guardar cambios").click()
    run(at)
    data = client.get(f"/api/lotes/{lote['id']}").json()
    assert data["codigo"] == "RENOMBRADO"
    assert data["estado"] == "CERRADO"


def test_selection_opens_modal_and_closing_allows_reselecting_the_same_lot(ui_api, client):
    lote = client.post("/api/lotes", json={"codigo": "MODAL"}).json()
    at = run(AppTest.from_string(SCRIPT))
    assert widget(at.selectbox, "Seleccionar lote").value is None
    assert "Guardar cambios" not in [button.label for button in at.button]
    assert not at.metric
    open_lote(at, lote["id"])
    assert "Guardar cambios" in [button.label for button in at.button]
    assert widget(at.metric, "ID del lote").value == str(lote["id"])
    widget(at.text_input, "Código").set_value("NO-GUARDAR")
    widget(at.button, "Volver al listado").click()
    run(at)
    assert widget(at.selectbox, "Seleccionar lote").value is None
    assert "Guardar cambios" not in [button.label for button in at.button]
    assert not at.metric
    assert client.get(f"/api/lotes/{lote['id']}").json()["codigo"] == "MODAL"
    open_lote(at, lote["id"])
    assert widget(at.text_input, "Código").value == "MODAL"


def test_old_inline_selection_is_cleared_when_modal_ui_is_first_loaded(ui_api, client):
    lote = client.post("/api/lotes", json={"codigo": "EXISTENTE"}).json()
    at = AppTest.from_string(SCRIPT)
    at.session_state["lotes_seleccion"] = lote["id"]
    run(at)
    assert widget(at.selectbox, "Seleccionar lote").value is None
    assert "Guardar cambios" not in [button.label for button in at.button]
    open_lote(at, lote["id"])
    assert "Guardar cambios" in [button.label for button in at.button]
