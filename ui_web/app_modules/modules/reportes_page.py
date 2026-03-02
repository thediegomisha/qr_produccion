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
        st.subheader("Reportes por DNI (por lote)")

        jwt = get_jwt()
        rol_rep = (st.session_state.auth.get("rol") or "").upper()
        headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}

        # ---- traer lotes para el combobox ----
        lotes_items = []
        try:
            r_lotes = api_get("/lotes", params={"limit": 200})
            if r_lotes.status_code == 200:
                lotes_items = (r_lotes.json() or {}).get("items", []) or []
            else:
                st.warning(f"No se pudo cargar lotes ({r_lotes.status_code})")
        except Exception as e:
            st.warning(f"Error cargando lotes: {e}")

        # ---- opciones selectbox ----
        opciones = []
        codigo_por_label = {}
        for it in lotes_items:
            c = (it.get("codigo") or "").strip().upper()
            e = (it.get("estado") or "ABIERTO").strip().upper()
            if not c:
                continue
            label = f"{c} [{e}]"
            opciones.append(label)
            codigo_por_label[label] = c

        # ---- UI selección lote ----
        colA, colB = st.columns([1.3, 2])
        with colA:
            if not opciones:
                st.warning("No hay lotes para seleccionar. Cree uno en la pestaña 📦 Lotes.")
                selected_label = None
            else:
                selected_label = st.selectbox(
                    "Selecciona lote",
                    opciones,
                    index=0,
                    key="rep_lote_select",
                )

        with colB:
            st.caption("Reportes ahora se generan SIN fecha. Se filtra solo por lote y filtros opcionales.")

        lote_codigo = ""
        if selected_label:
            lote_codigo = (codigo_por_label.get(selected_label) or "").strip().upper()

        # ---- filtros opcionales ----
        c1, c2 = st.columns([1, 1])
        with c1:
            producto = st.text_input("Producto (opcional)", value="", key="rep_producto")
        with c2:
            scanned_by = ""
            if rol_rep in ("ROOT", "SUPERVISOR"):
                scanned_by = st.text_input("Usuario que escaneó (opcional)", value="", key="rep_scanned_by")

        # ---- params al backend (SIN fechas) ----
        params = {"lote_codigo": lote_codigo}
        if producto.strip():
            params["producto"] = producto.strip()
        if rol_rep in ("ROOT", "SUPERVISOR") and scanned_by.strip():
            params["scanned_by"] = scanned_by.strip()

        btn_disabled = not bool(lote_codigo)

        b1, b2 = st.columns(2)

        # -------------------------
        # DNI SUMMARY
        # -------------------------
        if b1.button("Generar reporte DNI", type="primary", disabled=btn_disabled):
            r = requests.get(
                f"{API}/reports/dni-summary",
                params=params,
                headers=headers,
                timeout=20
            )
            if r.status_code != 200:
                st.error("Error en /reports/dni-summary")
                st.code(r.text)
            else:
                data = r.json()
                tot = data.get("totals", {}) or {}

                st.caption(f"Lote: {data.get('lote_codigo') or lote_codigo}")

                m1, m2, m3 = st.columns(3)
                m1.metric("Total lecturas", int(tot.get("total_lecturas", 0)))
                m2.metric("Empacador", int(tot.get("emp_lecturas", 0)))
                m3.metric("Seleccionador", int(tot.get("sel_lecturas", 0)))

                df = pd.DataFrame(data.get("rows", []))
                if df.empty:
                    st.info("Sin datos.")
                else:
                    st.dataframe(df, width="stretch")

        # -------------------------
        # OPERATOR SUMMARY (opcional)
        # -------------------------
        if b2.button("Generar reporte Operadores", disabled=btn_disabled):
            r = requests.get(
                f"{API}/reports/operator-summary",
                params=params,
                headers=headers,
                timeout=20
            )
            if r.status_code != 200:
                st.error("Error en /reports/operator-summary")
                st.code(r.text)
            else:
                data = r.json()
                st.caption(f"Lote: {data.get('lote_codigo') or lote_codigo}")

                df = pd.DataFrame(data.get("rows", []))
                if df.empty:
                    st.info("Sin datos.")
                else:
                    st.dataframe(df, width="stretch")
