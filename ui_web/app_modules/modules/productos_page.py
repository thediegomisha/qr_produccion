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
    flash_show("Productos")
    st.subheader("Mantenimiento de productos")

    if rol not in ("ROOT", "GERENCIA"):
        st.error("No tienes permisos para administrar productos.")
        st.stop()

    r_list = api_get("/productos/all")
    if r_list.status_code != 200:
        st.error("No se pudo listar productos")
        st.code(r_list.text)
        st.stop()

    productos = r_list.json() or []
    df = pd.DataFrame(productos)

    st.markdown("### Productos registrados")
    if df.empty:
        st.info("No hay productos.")
    else:
        df_ui = df.reset_index(drop=True).copy()
        if "creado_en" not in df_ui.columns:
            df_ui["creado_en"] = "-"
        else:
            df_ui["creado_en"] = df_ui["creado_en"].map(lambda v: v if pd.notna(v) else "-")

        df_ui["✏️"] = False
        cols_show = ["✏️", "id", "nombre", "activo", "creado_en"]

        edited = st.data_editor(
            df_ui[cols_show],
            hide_index=True,
            num_rows="fixed",
            disabled=[c for c in cols_show if c != "✏️"],
            width="stretch",
            key="tabla_productos_editar",
        )

        seleccionados = edited[edited["✏️"] == True]
        if len(seleccionados) == 1:
            fila_idx = int(seleccionados.index[0])
            st.session_state.edit_producto_row = df_ui.iloc[fila_idx].to_dict()
            st.session_state.show_producto_modal = True
        else:
            st.session_state.show_producto_modal = False
            st.session_state.edit_producto_row = None

    st.divider()

    st.markdown("### Crear nuevo producto")
    with st.form("form_crear_producto", clear_on_submit=True):
        nuevo_nombre = st.text_input("Nombre", key="new_producto_nombre")
        submitted = st.form_submit_button("Crear producto")

    if submitted:
        if not nuevo_nombre.strip():
            flash_set("Productos", "err", "Ingrese un nombre")
            st.rerun()

        r_create = api_post("/productos", json={"nombre": nuevo_nombre.strip()})
        if r_create.status_code == 200:
            flash_set("Productos", "ok", "Producto creado")
            st.session_state.show_producto_modal = False
            st.session_state.edit_producto_row = None
            st.rerun()
        else:
            flash_set("Productos", "err", f"Error al crear: {r_create.text}")
            st.rerun()

    if st.session_state.get("show_producto_modal") and st.session_state.get("edit_producto_row"):
        row = st.session_state.get("edit_producto_row") or {}
        producto_id = row.get("id")

        @st.dialog("Editar producto")
        def modal_editar_producto():
            with st.form(key=f"form_editar_producto_{producto_id}"):
                nombre_e = st.text_input("Nombre", value=row.get("nombre") or "")
                activo_e = st.checkbox("Activo", value=bool(row.get("activo", True)))

                b1, b2 = st.columns(2)
                guardar = b1.form_submit_button("💾 Guardar")
                cancelar = b2.form_submit_button("❌ Cancelar")

            if cancelar:
                st.session_state.show_producto_modal = False
                st.session_state.edit_producto_row = None
                st.session_state.pop("tabla_productos_editar", None)
                st.rerun()

            if guardar:
                r_upd = api_put(
                    f"/productos/{producto_id}",
                    json={"nombre": nombre_e.strip(), "activo": activo_e},
                )
                if r_upd.status_code != 200:
                    st.error("Error actualizando producto")
                    st.code(r_upd.text)
                    st.stop()

                flash_set("Productos", "ok", "Producto actualizado")
                st.session_state.show_producto_modal = False
                st.session_state.edit_producto_row = None
                st.session_state.pop("tabla_productos_editar", None)
                st.rerun()

        modal_editar_producto()
