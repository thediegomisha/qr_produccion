import pandas as pd
import requests
def render(
    st,
    tabs,
    selected_tab,
    rol,
    API,
    auth_headers,
    api_get,
    api_post,
    api_put,
    api_delete,
    flash_show,
    flash_set,
    get_jwt,
    show_printers_panel,
    COLUMNAS_LISTADO,
    COLUMNAS_IMPRESION,
):
    r = requests.get(f"{API}/trabajadores/?activos=true", headers=auth_headers(), timeout=10)
    if r.status_code == 200:
        payload = r.json() or []
        if not isinstance(payload, list):
            st.error("Formato de respuesta inesperado al listar trabajadores")
            st.json(payload)
            return

        trabajadores = sorted(payload, key=lambda t: int((t or {}).get("num_orden") or 0))
        st.subheader(f"Listado de trabajadores activos ({len(trabajadores)})")

        if trabajadores:
            df = pd.DataFrame(trabajadores)
            cols = [c for c in COLUMNAS_LISTADO if c in df.columns]
            if not cols:
                st.warning("No hay columnas esperadas para mostrar")
                st.dataframe(df, width="stretch")
            else:
                st.dataframe(df[cols], width="stretch")
        else:
            st.info("No hay trabajadores registrados")
    else:
        st.error("Error cargando trabajadores")
        st.code(r.text)
