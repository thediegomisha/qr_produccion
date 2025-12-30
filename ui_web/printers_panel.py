import os
import json
import base64
import requests
import streamlit as st
from pathlib import Path
from typing import List, Dict, Any

# ============================
# Persistencia por usuario
# ============================
def _current_user_key() -> str:
    auth = st.session_state.get("auth") or {}
    u = (auth.get("usuario") or "anon").strip()
    return u if u else "anon"

def _persist_dir() -> Path:
    p = Path.home() / ".streamlit"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _persist_path() -> Path:
    return _persist_dir() / f"printer_selection_{_current_user_key()}.json"

def _load_saved_selection() -> Dict[str, str]:
    path = _persist_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_selection(agent_url: str, printer_name: str) -> None:
    path = _persist_path()
    payload = {"agent_url": agent_url, "printer_name": printer_name}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

# ============================
# Bootstrap (para otras pestañas)
# ============================
def bootstrap_printer_selection() -> None:
    """
    Carga la selección guardada y la pone en st.session_state.
    Llamar 1 vez después del login.
    """
    saved = _load_saved_selection()
    if saved.get("printer_name") and not st.session_state.get("selected_printer_name"):
        st.session_state["selected_printer_name"] = saved["printer_name"]
    if saved.get("agent_url") and not st.session_state.get("selected_printer_agent_url"):
        st.session_state["selected_printer_agent_url"] = saved["agent_url"]

# ============================
# Config agent (url/token)
# ============================
def _get_agent_url_from_ui() -> str:
    # Prioridad: st.secrets -> env -> default local
    url = st.secrets.get("PRINT_AGENT_URL", None) if hasattr(st, "secrets") else None
    if not url:
        url = os.getenv("PRINT_AGENT_URL", "http://127.0.0.1:5000")
    return (url or "").rstrip("/")

def _get_agent_token_from_ui() -> str:
    token = st.secrets.get("PRINT_AGENT_TOKEN", None) if hasattr(st, "secrets") else None
    if not token:
        token = os.getenv("PRINT_AGENT_TOKEN", "")
    return token or ""

@st.cache_data(ttl=10)
def fetch_printers(agent_base_url: str, token: str, timeout: int = 5) -> List[Dict[str, Any]]:
    headers = {"X-Agent-Token": token} if token else {}
    resp = requests.get(f"{agent_base_url}/printers", headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

def send_test_print(agent_base_url: str, token: str, printer_name: str, zpl_bytes: bytes, copies: int = 1, timeout: int = 10):
    headers = {"X-Agent-Token": token, "Content-Type": "application/json"} if token else {"Content-Type": "application/json"}
    payload = {
        "printer": printer_name,
        "raw_base64": base64.b64encode(zpl_bytes).decode(),
        "copies": int(copies),
    }
    resp = requests.post(f"{agent_base_url}/jobs", json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

def show_printers_panel():
    st.markdown("## Impresoras (Print Agent)")

    saved = _load_saved_selection()
    bootstrap_printer_selection()

    col_left, col_right = st.columns([2, 1])
    with col_left:
        default_url = saved.get("agent_url") or st.session_state.get("selected_printer_agent_url") or _get_agent_url_from_ui()
        agent_url = st.text_input(
            "Agent base URL",
            value=default_url,
            help="Si el Print Agent corre en ESTA MISMA PC, usa http://127.0.0.1:5000",
            key="printer_agent_url_input",
        ).rstrip("/")

        agent_token = st.text_input(
            "Agent token (X-Agent-Token)",
            value=_get_agent_token_from_ui(),
            type="password",
            key="printer_agent_token_input",
        )

        remember = st.checkbox("Recordar selección", value=True, key="printer_remember_checkbox")

    with col_right:
        refresh = st.button("🔄 Refrescar lista", key="printer_refresh_btn")

    if not agent_url:
        st.warning("Ingrese la URL del Print Agent.")
        return

    try:
        if refresh:
            headers = {"X-Agent-Token": agent_token} if agent_token else {}
            r = requests.get(f"{agent_url}/printers", headers=headers, timeout=5)
            r.raise_for_status()
            printers = r.json()
        else:
            printers = fetch_printers(agent_url, agent_token)
    except requests.HTTPError as e:
        st.error(f"Agent HTTP error: {e} — {getattr(e.response, 'text', '')}")
        return
    except requests.RequestException as e:
        st.error(f"Error conectando al agente: {e}")
        return
    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return

    if not printers:
        st.info("No se encontraron impresoras en el agente.")
        return

    st.write(f"Encontradas {len(printers)} impresora(s):")

    names = [p.get("name") or f"<unnamed-{i}>" for i, p in enumerate(printers)]

    # Default seleccionado: session_state -> persistido -> primero
    default_selected = (
        st.session_state.get("selected_printer_name")
        or saved.get("printer_name")
        or names[0]
    )
    if default_selected not in names:
        default_selected = names[0]

    selected = st.selectbox(
        "Seleccionar impresora",
        names,
        index=names.index(default_selected),
        key="printer_selectbox",
    )

    # Guardar en session_state para otras pestañas
    st.session_state["selected_printer_name"] = selected
    st.session_state["selected_printer_agent_url"] = agent_url

    # Persistir a disco
    if remember:
        _save_selection(agent_url, selected)

    p = next((x for x in printers if x.get("name") == selected), printers[0])
    st.markdown("**Detalles de la impresora**")
    st.json(p)

    st.success(f"Impresora activa: {selected}")

    st.markdown("### Prueba de impresión (ZPL de ejemplo)")
    copies = st.number_input("Copias", min_value=1, max_value=20, value=1, step=1, key="test_copies")
    sample_text = st.text_input("Texto de etiqueta", value="PRUEBA", key="test_text")
    zpl_example = f"^XA^FO50,50^A0N,30,30^FD{sample_text}^FS^XZ".encode("utf-8")

    if st.button("🖨️ Enviar impresión de prueba", key="test_print_btn"):
        try:
            res = send_test_print(agent_url, agent_token, p["name"], zpl_example, copies=copies)
            st.success(f"Job encolado: {res.get('job_id') or res.get('id')} (status={res.get('status')})")
        except requests.HTTPError as e:
            st.error(f"Error del agente: {e} - {getattr(e.response, 'text', '')}")
        except Exception as e:
            st.error(f"Error enviando la impresión: {e}")

    st.caption("Si cambias de PC, recuerda: el Print Agent debe correr en ESA PC y el firewall debe permitir TCP 5000.")
