import pytest
from streamlit.testing.v1 import AppTest

import printers_panel


SCRIPT = '''
import streamlit as st
from printers_panel import show_printers_panel
st.session_state.auth = {"usuario": "usuario-prueba"}
show_printers_panel()
'''


@pytest.fixture
def printer_config(tmp_path, monkeypatch):
    monkeypatch.setattr(printers_panel, "_persist_dir", lambda: tmp_path)
    monkeypatch.setattr(printers_panel, "_get_agent_url_from_ui", lambda: "http://default-agent:5000")
    monkeypatch.setattr(printers_panel, "_get_agent_token_from_ui", lambda: "environment-test-token")
    calls = []
    def printers(url, token, timeout=5):
        calls.append((url, token))
        return [{"name": "TERMICA", "type": "network", "host": "192.168.1.50", "port": 9100}]
    monkeypatch.setattr(printers_panel, "fetch_printers", printers)
    return tmp_path, calls


def test_saved_agent_url_token_and_printer_survive_a_new_web_session(printer_config):
    folder, calls = printer_config
    (folder / "printer_selection_usuario-prueba.json").write_text(
        '{"agent_url":"http://configured-agent:5000","agent_token":"saved-test-token","printer_name":"TERMICA"}'
    )
    for _ in range(2):
        page = AppTest.from_string(SCRIPT).run(timeout=15)
        assert not page.exception
        assert page.text_input(key="printer_agent_url_input").value == "http://configured-agent:5000"
        assert page.text_input(key="printer_agent_token_input").value == "saved-test-token"
        assert page.selectbox(key="printer_selectbox").value == "TERMICA"
    assert calls == [("http://configured-agent:5000", "saved-test-token")] * 2


def test_environment_defaults_are_used_for_a_user_without_saved_settings(printer_config):
    _, calls = printer_config
    page = AppTest.from_string(SCRIPT).run(timeout=15)
    assert not page.exception
    assert page.text_input(key="printer_agent_token_input").value == "environment-test-token"
    assert calls == [("http://default-agent:5000", "environment-test-token")]
