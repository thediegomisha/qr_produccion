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
    def generar_vista_previa() -> None:
        trabajador = st.session_state.get("trabajador_seleccionado")
        if not trabajador:
            st.session_state.preview_img = None
            st.session_state.preview_error = None
            return

        opcion = st.session_state.get("opcion_mostrar") or "Número de orden"
        producto = st.session_state.get("producto") or "UVA"
        cantidad = st.session_state.get("cantidad") or 1
        valor_visible = trabajador["num_orden"] if opcion == "Número de orden" else trabajador["cod_letra"]

        try:
            r = requests.post(
                f"{API}/qr/preview",
                json={
                    "dni": trabajador["dni"],
                    "nn": valor_visible,
                    "producto": producto,
                    "cantidad": cantidad,
                },
                timeout=10,
            )
        except Exception as e:
            st.session_state.preview_img = None
            st.session_state.preview_error = str(e)
            return

        if r.status_code == 200 and "image" in (r.headers.get("content-type") or ""):
            st.session_state.preview_img = r.content
            st.session_state.preview_error = None
        else:
            st.session_state.preview_img = None
            st.session_state.preview_error = r.text

    def request_clear_impresion_selection() -> None:
        st.session_state["clear_impresion_selection_on_next_run"] = True

    if st.session_state.get("clear_impresion_selection_on_next_run"):
        st.session_state["clear_impresion_selection_on_next_run"] = False
        st.session_state["selected_trabajador_impresion_id"] = None
        st.session_state.pop("trabajador_seleccionado", None)
        st.session_state.preview_img = None
        st.session_state.preview_error = None
        st.session_state["impresion_table_nonce"] = st.session_state.get("impresion_table_nonce", 0) + 1

    if "impresion_table_nonce" not in st.session_state:
        st.session_state["impresion_table_nonce"] = 0
    if "selected_trabajador_impresion_id" not in st.session_state:
        st.session_state["selected_trabajador_impresion_id"] = None
    if "impresion_prev_search" not in st.session_state:
        st.session_state["impresion_prev_search"] = ""

    st.subheader("Impresión de etiquetas")

    r = requests.get(f"{API}/trabajadores/?activos=true", headers=auth_headers(), timeout=10)
    if r.status_code != 200:
        st.error("Error cargando trabajadores")
        st.code(r.text)
        return

    trabajadores = sorted(r.json(), key=lambda t: t["num_orden"])
    st.metric("👥 Trabajadores activos", len(trabajadores))

    if not trabajadores:
        st.warning("No hay trabajadores registrados")
        return

    busqueda = st.text_input(
        "Buscar por DNI o nombre",
        key="impresion_busqueda",
        placeholder="Ejemplo: 40383794 o Anais",
    ).strip().lower()

    if st.session_state.get("impresion_prev_search") and not busqueda and st.session_state.get("selected_trabajador_impresion_id"):
        request_clear_impresion_selection()
        st.session_state["impresion_prev_search"] = busqueda
        st.rerun()

    st.session_state["impresion_prev_search"] = busqueda
    st.caption("Tip: al limpiar el buscador (Esc), se limpia la selección actual.")

    def coincide(t):
        if not busqueda:
            return True
        return (
            busqueda in (t.get("dni") or "").lower()
            or busqueda in (t.get("nombre") or "").lower()
            or busqueda in (t.get("apellido_paterno") or "").lower()
            or busqueda in (t.get("apellido_materno") or "").lower()
        )

    filtrados = [t for t in trabajadores if coincide(t)]
    if not filtrados:
        st.warning("No se encontraron trabajadores")
        return

    st.markdown("### Seleccione un trabajador")
    df = pd.DataFrame(filtrados)
    if "seleccionar" not in df.columns:
        df.insert(0, "seleccionar", False)

    selected_id = st.session_state.get("selected_trabajador_impresion_id")
    df["seleccionar"] = df["id"].apply(lambda v: bool(selected_id) and v == selected_id)

    df_impresion = df[COLUMNAS_IMPRESION]
    edited_df = st.data_editor(
        df_impresion,
        hide_index=True,
        disabled=[c for c in df_impresion.columns if c != "seleccionar"],
        num_rows="fixed",
        key=f"tabla_trabajadores_impresion_{st.session_state['impresion_table_nonce']}",
    )

    seleccionados = edited_df[edited_df["seleccionar"] == True]
    if len(seleccionados) > 1:
        fila_idx = int(seleccionados.index.tolist()[0])
        trabajador_sel = filtrados[fila_idx]
        st.session_state["selected_trabajador_impresion_id"] = trabajador_sel["id"]
        st.session_state.trabajador_seleccionado = trabajador_sel
        st.warning("Solo puede seleccionar un trabajador a la vez. Se mantuvo la primera selección.")
        request_clear_impresion_selection()
        st.rerun()
    elif len(seleccionados) != 1:
        st.info("Seleccione un solo trabajador")
        st.session_state["selected_trabajador_impresion_id"] = None
        st.session_state.pop("trabajador_seleccionado", None)
        st.session_state.preview_img = None
        st.session_state.preview_error = None
    else:
        fila_idx = int(seleccionados.index[0])
        trabajador_sel = filtrados[fila_idx]
        st.session_state["selected_trabajador_impresion_id"] = trabajador_sel["id"]
        st.session_state.trabajador_seleccionado = trabajador_sel
        generar_vista_previa()

    st.markdown("### Contenido visible en la etiqueta")
    st.radio(
        "¿Qué desea imprimir en el centro del QR?",
        ["Número de orden", "Código de letra"],
        horizontal=True,
        key="opcion_mostrar",
        on_change=generar_vista_previa,
    )

    col_prod, col_cant, _ = st.columns([1.2, 0.6, 3])
    with col_prod:
        productos = ["UVA"]
        r_prod = api_get("/productos")
        if r_prod.status_code == 200:
            items = r_prod.json() or []
            nombres = [p.get("nombre") for p in items if p.get("nombre")]
            if nombres:
                productos = nombres
        else:
            st.warning("No se pudo cargar productos. Usando lista por defecto.")

        current_prod = st.session_state.get("producto")
        if current_prod in productos:
            idx = productos.index(current_prod)
        else:
            idx = 0

        st.selectbox(
            "Producto",
            productos,
            index=idx,
            key="producto",
            on_change=generar_vista_previa,
        )
    with col_cant:
        st.number_input(
            "Cantidad de etiquetas",
            min_value=1,
            max_value=5000,
            value=1,
            step=1,
            key="cantidad",
            on_change=generar_vista_previa,
        )

    if st.session_state.get("preview_img"):
        st.image(st.session_state.preview_img, caption="Generated by Agricola del Sur Pisco EIRL")

    selected_printer = st.session_state.get("selected_printer_name")
    selected_agent_url = st.session_state.get("selected_printer_agent_url")
    if selected_printer:
        st.caption(f"Impresora seleccionada: **{selected_printer}**")
    else:
        st.warning("No hay impresora seleccionada. Ve a la sección 🖨️ Impresoras y selecciona una.")

    btn_label = f"🖨️ Imprimir etiquetas ({selected_printer})" if selected_printer else "🖨️ Imprimir etiquetas"
    if st.button(btn_label, disabled=not bool(selected_printer)):
        trabajador_sel = st.session_state.get("trabajador_seleccionado")
        if not trabajador_sel:
            st.error("Seleccione un trabajador antes de imprimir.")
            st.stop()

        nn_value = (
            trabajador_sel["num_orden"]
            if st.session_state.opcion_mostrar == "Número de orden"
            else trabajador_sel["cod_letra"]
        )

        r_print = None
        try:
            selected_agent_token = st.session_state.get("selected_printer_agent_token")
            r_print = requests.post(
                f"{API}/qr/print",
                json={
                    "dni": trabajador_sel["dni"],
                    "nn": nn_value,
                    "producto": st.session_state.producto,
                    "cantidad": st.session_state.cantidad,
                    "printer": selected_printer,
                    "agent_url": selected_agent_url,
                    "agent_token": selected_agent_token,
                },
                headers=auth_headers(),
                timeout=15,
            )
        except Exception as e:
            st.error(f"Error enviando impresión: {e}")
            st.stop()

        if r_print is not None and r_print.status_code == 200:
            st.toast("Impresión enviada correctamente 🖨️", icon="✅")
        else:
            st.error("Error al imprimir")
            if r_print is not None:
                st.code(r_print.text)
