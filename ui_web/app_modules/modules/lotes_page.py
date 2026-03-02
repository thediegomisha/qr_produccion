import pandas as pd

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
        st.subheader("Gestión de lotes")

        rol_lotes = (st.session_state.auth.get("rol") or "").upper()

        c1, c2 = st.columns([1.2, 1])
        with c1:
            codigo = st.text_input("Código de lote (ej: 1234-2026)", value="").strip().upper()
        with c2:
            st.caption("Estado se controla en el servidor")

        a1, a2, a3 = st.columns(3)

        if a1.button("Crear / Asegurar lote", type="primary"):
            if not codigo:
                st.warning("Ingrese un código")
            else:
                r = api_post("/lotes/ensure", json={"codigo": codigo})
                if r.status_code == 200:
                    st.success(f"OK: {r.json().get('codigo')} ({r.json().get('estado')})")
                else:
                    st.error(f"Error {r.status_code}")
                    st.code(r.text)

        if a2.button("Cerrar lote"):
            if not codigo:
                st.warning("Ingrese un código")
            else:
                r = api_post(f"/lotes/{codigo}/close")
                if r.status_code == 200:
                    st.success(f"Lote {codigo} cerrado")
                else:
                    st.error(f"Error {r.status_code}")
                    st.code(r.text)

        if a3.button("Reabrir lote (ROOT)"):
            if rol_lotes != "ROOT":
                st.error("Solo ROOT puede reabrir")
            elif not codigo:
                st.warning("Ingrese un código")
            else:
                r = api_post(f"/lotes/{codigo}/open")
                if r.status_code == 200:
                    st.success(f"Lote {codigo} reabierto")
                else:
                    st.error(f"Error {r.status_code}")
                    st.code(r.text)

                b1, b2 = st.columns([1, 3])
                with b1:
                    if st.button("✅ Usar como lote activo"):
                        if not codigo:
                            st.warning("Ingrese un código")
                        else:
                            # opcional: validar en servidor que exista
                            rr = api_get("/lotes", params={"limit": 200})
                            if rr.status_code == 200:
                                items = (rr.json() or {}).get("items", [])
                                existe = any((it.get("codigo") or "").strip().upper() == codigo for it in items)
                                if not existe:
                                    st.warning("Ese lote no aparece en la lista. Cree/asegure primero.")
                                else:
                                    st.session_state.active_lote_codigo = codigo
                                    st.success(f"Lote activo: {codigo}")
                            else:
                                # si no puede listar, igual setea localmente
                                st.session_state.active_lote_codigo = codigo
                                st.success(f"Lote activo: {codigo} (sin validar)")
                with b2:
                    activo = (st.session_state.get("active_lote_codigo") or "").strip().upper()
                    st.caption(f"Lote activo actual: **{activo or '-'}**")


        st.divider()
        st.markdown("### Últimos lotes")
        r = api_get("/lotes", params={"limit": 50})
        if r.status_code == 200:
            items = (r.json() or {}).get("items", [])
            df = pd.DataFrame(items)
            if df.empty:
                st.info("No hay lotes")
            else:
                st.dataframe(df, width="stretch")
        else:
            st.error(f"No se pudo listar lotes ({r.status_code})")
