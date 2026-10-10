from math import ceil
from urllib.parse import quote

import pandas as pd
from requests import RequestException

from app_modules.modules.export_utils import export_row


def _request(st, api_method, path, **kwargs):
    try:
        response = api_method(path, **kwargs)
    except RequestException:
        st.error("No se pudo conectar con la API. Puede volver a intentar la operación.")
        return None
    try:
        data = response.json()
    except ValueError:
        st.error(f"La API no devolvió JSON (HTTP {response.status_code}). Revise la configuración de API_URL.")
        return None
    if not 200 <= response.status_code < 300:
        detail = data.get("detail", "No se pudo completar la operación") if isinstance(data, dict) else data
        st.error(f"Error {response.status_code}: {detail}")
        return None
    if not isinstance(data, dict):
        st.error("La API devolvió una respuesta inesperada.")
        return None
    return data


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
    flash_show("Lotes")
    st.subheader("Gestión de lotes")
    role = (rol or "").upper()
    if role not in ("ROOT", "GERENCIA", "SUPERVISOR"):
        st.error("No tienes permisos para gestionar lotes.")
        return
    can_manage = role in ("ROOT", "GERENCIA")
    modal_body = None

    reset_listing = st.session_state.pop("_lotes_reset", False)
    clear_selection = st.session_state.pop("_lotes_clear_selection", False)
    if "_lotes_modal_id" not in st.session_state:
        st.session_state["_lotes_modal_id"] = None
        clear_selection = True
    if reset_listing:
        st.session_state.pop("lotes_pagina", None)
    if reset_listing or clear_selection:
        st.session_state.pop("lotes_seleccion", None)
        st.session_state["_lotes_modal_id"] = None

    def dismiss_modal():
        st.session_state["_lotes_modal_id"] = None
        st.session_state["_lotes_clear_selection"] = True

    def select_lote():
        identifier = st.session_state.get("lotes_seleccion")
        st.session_state["_lotes_modal_id"] = identifier
        if identifier is not None:
            for prefix in ("lotes_codigo", "lotes_estado", "lotes_confirmar_eliminar"):
                st.session_state.pop(f"{prefix}_{identifier}", None)

    def refresh(message, *, reset=False):
        flash_set("Lotes", "ok", message)
        if modal_body is not None:
            # Remove dialog widgets before the full rerun refreshes the listing.
            modal_body.empty()
        dismiss_modal()
        if reset:
            st.session_state["_lotes_reset"] = True
        st.rerun()

    active = st.session_state.get("active_lote_codigo", "")
    st.caption(f"Lote activo actual: **{active or '-'}**")

    with st.expander("Crear nuevo lote"):
        with st.form("lotes_crear", clear_on_submit=True):
            new_code = st.text_input("Código del nuevo lote", max_chars=64, key="lotes_nuevo_codigo")
            create = st.form_submit_button("Crear lote", type="primary")
    if create:
        if not new_code.strip():
            st.warning("Ingrese un código de lote.")
        else:
            created = _request(st, api_post, "/lotes", json={"codigo": new_code.strip()})
            if created is not None:
                refresh(f"Lote {created['codigo']} creado correctamente.", reset=True)

    st.divider()
    st.markdown("### Lotes registrados")
    filter_code, filter_state = st.columns(2)
    with filter_code:
        search = st.text_input("Buscar código", max_chars=64, key="lotes_buscar").strip()
    with filter_state:
        state = st.selectbox("Filtrar estado", ["TODOS", "ABIERTO", "CERRADO"], key="lotes_estado_filtro")
    filters = (search, state)
    if st.session_state.get("_lotes_filters") != filters:
        st.session_state["_lotes_filters"] = filters
        st.session_state.pop("lotes_pagina", None)
        st.session_state.pop("lotes_seleccion", None)
        st.session_state["_lotes_modal_id"] = None

    page = int(st.number_input("Página", min_value=1, step=1, value=1, key="lotes_pagina"))
    page_size = 50
    params = {"limit": page_size, "offset": (page - 1) * page_size, "q": search}
    if state != "TODOS":
        params["estado"] = state
    listing = _request(st, api_get, "/lotes", params=params)
    if listing is None:
        return
    if "total" not in listing:
        st.error("La API de lotes necesita actualizarse para utilizar este mantenimiento.")
        return
    items = listing.get("items", [])
    total = int(listing["total"])
    st.caption(f"{total} lote(s). Página {page} de {max(1, ceil(total / page_size))}.")
    if st.button("Actualizar listado", key="lotes_actualizar"):
        st.rerun()
    if not items:
        st.info("No hay lotes en esta página para los filtros seleccionados.")
        return

    table = pd.DataFrame(items)
    columns = ["id", "codigo", "estado", "total_lecturas", "creado_por", "creado_en", "cerrado_en", "reabierto_en"]

    # Eliminación masiva: solo ROOT y con selección múltiple desde la grilla.
    if role == "ROOT":
        grid = table[columns].copy()
        grid["🗑️ Eliminar"] = False
        edited = st.data_editor(
            grid[["🗑️ Eliminar", *columns]],
            hide_index=True,
            num_rows="fixed",
            disabled=columns,
            width="stretch",
            key="lotes_grilla_masiva",
        )
        selected_rows = edited[edited["🗑️ Eliminar"] == True]
        selected_ids = [int(i) for i in selected_rows["id"].tolist()]
        selected_codes = selected_rows["codigo"].tolist()
        selected_scans = int(selected_rows["total_lecturas"].sum()) if len(selected_rows) else 0

        if selected_ids:
            st.warning(
                f"Seleccionados {len(selected_ids)} lote(s): {', '.join(selected_codes)} "
                f"({selected_scans} lecturas asociadas en total)."
            )
            confirm = st.checkbox(
                "Confirmo eliminar TODOS los lotes seleccionados junto con sus lecturas",
                key="lotes_confirmar_masivo",
            )
            delete_many = st.button("Eliminar lotes seleccionados", type="primary", key="lotes_eliminar_masivo")
            if delete_many:
                if not confirm:
                    st.warning("Marque la confirmación para eliminar los lotes seleccionados.")
                else:
                    result = _request(st, api_post, "/lotes/bulk-delete", json={"ids": selected_ids})
                    if result is not None:
                        active_code = st.session_state.get("active_lote_codigo")
                        if active_code and active_code in {item["codigo"] for item in result["items"]}:
                            st.session_state.active_lote_codigo = ""
                        refresh(
                            f"Se eliminaron {result['deleted_lotes']} lotes y {result['deleted_scans']} lecturas.",
                            reset=True,
                        )
    else:
        st.dataframe(
            table[columns],
            hide_index=True,
            width="stretch",
        )

    by_id = {item["id"]: item for item in items}
    if st.session_state.get("lotes_seleccion") not in (None, *by_id):
        st.session_state.pop("lotes_seleccion", None)
        st.session_state["_lotes_modal_id"] = None
    st.selectbox(
        "Seleccionar lote",
        options=[None, *by_id],
        format_func=lambda identifier: "Seleccione un lote para gestionarlo…" if identifier is None
        else f"{by_id[identifier]['codigo']} ({by_id[identifier]['estado']})",
        key="lotes_seleccion",
        on_change=select_lote,
    )
    st.caption("Seleccione un lote para abrir sus detalles y acciones en una ventana modal.")

    # Exportación del listado de lotes visible.
    if items:
        export_row(
            st,
            "Listado de lotes",
            [f"Filtro: {search or 'todos'} | Estado: {state} | Total: {total}"],
            table[["id", "codigo", "estado", "total_lecturas", "creado_por", "creado_en", "cerrado_en"]],
            "lotes",
            "lotes_export",
        )

    def render_lote_details(lote_id):
        if st.button("Volver al listado", key="lotes_modal_volver"):
            modal_body.empty()
            dismiss_modal()
            st.rerun()

        lote = _request(st, api_get, f"/lotes/{lote_id}")
        if lote is None:
            return
        code = lote["codigo"]
        st.markdown(f"### Lote {code}")
        m1, m2, m3 = st.columns(3)
        m1.metric("ID del lote", lote_id)
        m2.metric("Estado", lote["estado"])
        m3.metric("Lecturas asociadas", lote["total_lecturas"])

        use, close, reopen = st.columns(3)
        if use.button("Usar como lote activo", disabled=lote["estado"] != "ABIERTO", key="lotes_usar"):
            st.session_state.active_lote_codigo = code
            refresh(f"Lote activo: {code}.")
        if close.button("Cerrar lote", disabled=lote["estado"] == "CERRADO", key="lotes_cerrar"):
            result = _request(st, api_post, f"/lotes/{quote(code, safe='')}/close")
            if result is not None:
                if st.session_state.get("active_lote_codigo") == code:
                    st.session_state.active_lote_codigo = ""
                refresh(f"Lote {code} cerrado.")
        if reopen.button(
            "Reabrir lote (ROOT)", disabled=role != "ROOT" or lote["estado"] == "ABIERTO", key="lotes_reabrir"
        ):
            result = _request(st, api_post, f"/lotes/{quote(code, safe='')}/open")
            if result is not None:
                refresh(f"Lote {code} reabierto.")

        if not can_manage:
            st.caption("ROOT y GERENCIA pueden editar y eliminar lotes completos.")
            return

        with st.form(f"lotes_editar_{lote_id}"):
            st.markdown("#### Editar lote")
            code_column, state_column = st.columns([2, 1])
            with code_column:
                edited_code = st.text_input("Código", value=code, max_chars=64, key=f"lotes_codigo_{lote_id}")
            with state_column:
                states = ["ABIERTO", "CERRADO"] if role == "ROOT" or lote["estado"] == "ABIERTO" else ["CERRADO"]
                edited_state = st.selectbox("Estado", states, index=states.index(lote["estado"]), key=f"lotes_estado_{lote_id}")
            save = st.form_submit_button("Guardar cambios", type="primary")
        if save:
            if not edited_code.strip():
                st.warning("El código no puede quedar vacío.")
            else:
                updated = _request(st, api_put, f"/lotes/{lote_id}", json={"codigo": edited_code, "estado": edited_state})
                if updated is not None:
                    if st.session_state.get("active_lote_codigo") == code:
                        st.session_state.active_lote_codigo = updated["codigo"] if updated["estado"] == "ABIERTO" else ""
                    message = f"Lote {updated['codigo']} actualizado; conserva sus lecturas asociadas."
                    if updated["codigo"] != code:
                        message += " Seleccione el código actualizado en los lectores para los próximos envíos."
                    refresh(message)

        with st.expander("Eliminar lote completo"):
            st.write(f"Se eliminarán el lote **{code}** y sus **{lote['total_lecturas']} lecturas asociadas**.")
            st.caption("La eliminación también retira esas lecturas de los reportes de producción.")
            with st.form(f"lotes_eliminar_{lote_id}"):
                confirmed = st.checkbox("Confirmo eliminar el lote completo y sus lecturas", key=f"lotes_confirmar_eliminar_{lote_id}")
                delete = st.form_submit_button("Eliminar lote completo")
            if delete:
                if not confirmed:
                    st.warning("Marque la confirmación para eliminar el lote.")
                else:
                    deleted = _request(st, api_delete, f"/lotes/{lote_id}")
                    if deleted is not None:
                        if st.session_state.get("active_lote_codigo") == code:
                            st.session_state.active_lote_codigo = ""
                        refresh(
                            f"Lote {code} eliminado junto con {deleted['deleted_scans']} lecturas.",
                            reset=True,
                        )

    @st.dialog("Gestionar lote", width="medium", on_dismiss=dismiss_modal)
    def manage_lote(lote_id):
        nonlocal modal_body
        modal_body = st.empty()
        with modal_body.container():
            render_lote_details(lote_id)

    modal_id = st.session_state.get("_lotes_modal_id")
    if modal_id in by_id:
        manage_lote(modal_id)
