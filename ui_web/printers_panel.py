import os
import base64
import requests
import streamlit as st
from typing import List, Dict, Any

# UI panel para listar impresoras desde un Print Agent y probar impresión ZPL simple.
# Uso:
# from backend.app.ui_web.printers_panel import show_printers_panel
# show_printers_panel()  # dentro de tu layout/tab correspondiente


def _get_agent_url_from_ui() -> str:
    # Prioridades: st.secrets -> env -> input control default
    url = st.secrets.get("PRINT_AGENT_URL", None) if hasattr(st, "secrets") else None
    if not url:
        url = os.getenv("PRINT_AGENT_URL", "http://127.0.0.1:5000")
    return url.rstrip("/")


def _get_agent_token_from_ui() -> str:
    token = st.secrets.get("PRINT_AGENT_TOKEN", None) if hasattr(st, "secrets") else None
    if not token:
        token = os.getenv("PRINT_AGENT_TOKEN", "")
    return token


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
        "copies": int(copies)
    }
    resp = requests.post(f"{agent_base_url}/jobs", json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def show_printers_panel():
    st.markdown("## Impresoras (Print Agent)")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        agent_url = st.text_input("Agent base URL", value=_get_agent_url_from_ui(), help="Ej: http://192.168.1.59:5000")
        agent_token = st.text_input("Agent token (X-Agent-Token)", value=_get_agent_token_from_ui(), type="password")
    with col_right:
        refresh = st.button("🔄 Refrescar lista")

    if not agent_url:
        st.warning("Ingrese la URL del Print Agent.")
        return

    # Fetch printers (cache_data will dedupe frequent calls)
    try:
        if refresh:
            # clear cache manual (simple approach: call fetch_printers with different param not supported easily)
            # So we call requests directly to force fetch (bypass cache)
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

    # Mostrar lista y permitir seleccionar
    names = [p.get("name") or f"<unnamed-{i}>" for i, p in enumerate(printers)]
    selected = st.selectbox("Seleccionar impresora", names, index=0)

    # Mostrar detalles de la impresora seleccionada
    p = next((x for x in printers if x.get("name") == selected), printers[0])
    st.markdown("**Detalles de la impresora**")
    st.json(p)

    # Controles para test print
    st.markdown("### Prueba de impresión (ZPL de ejemplo)")
    copies = st.number_input("Copias", min_value=1, max_value=20, value=1, step=1)
    sample_text = st.text_input("Texto de etiqueta", value="PRUEBA")
    zpl_example = f"^XA^FO50,50^A0N,30,30^FD{sample_text}^FS^XZ".encode("utf-8")

    if st.button("🖨️ Enviar impresión de prueba"):
        try:
            res = send_test_print(agent_url, agent_token, p["name"], zpl_example, copies=copies)
            st.success(f"Job encolado: {res.get('job_id')} (status={res.get('status')})")
        except requests.HTTPError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            st.error(f"Error del agente: {e} - {detail}")
        except Exception as e:
            st.error(f"Error enviando la impresión: {e}")

    st.markdown("---")
    st.caption("Si no aparecen las impresoras locales, asegúrate de que el agente corre en la misma máquina que CUPS y que el usuario del agente puede ejecutar `lpstat` y `lp`.")