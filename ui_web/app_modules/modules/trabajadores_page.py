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
    flash = st.session_state.pop("flash_msg", None)
    if flash:
        kind = flash.get("kind")
        msg = flash.get("msg", "")
        if kind == "ok":
            st.toast(msg, icon="✅")
        else:
            st.toast(msg, icon="❌")
            st.error(msg)

    def request_reset_trabajador_form() -> None:
        st.session_state["trabajador_form_reset_pending"] = True

    def request_clear_selection() -> None:
        st.session_state["clear_trabajador_selection_on_next_run"] = True

    if st.session_state.get("trabajador_form_reset_pending"):
        st.session_state["dni_trab"] = ""
        st.session_state["nom_trab"] = ""
        st.session_state["ap_pat"] = ""
        st.session_state["ap_mat"] = ""
        st.session_state["rol_trab"] = "EMPACADORA"
        st.session_state.reniec_ok = False
        st.session_state.reniec_error = None
        st.session_state.last_dni_consultado = None
        st.session_state["trabajador_form_reset_pending"] = False


    def modal_error_dni_registrado(mensaje: str):
        @st.dialog("⚠️ Registro no permitido")
        def _modal():
            st.error(mensaje)
            st.markdown("El DNI ingresado ya existe en el sistema.")
            if st.button("Aceptar"):
                request_reset_trabajador_form()
                st.rerun()
        _modal()

    def modal_dni_no_reniec(mensaje: str):
        @st.dialog("⚠️ DNI no válido")
        def _modal():
            st.warning(mensaje)
            st.markdown("El DNI no fue encontrado en RENIEC.")
            if st.button("Aceptar", type="primary"):
                request_reset_trabajador_form()
                st.rerun()
        _modal()

    flash_show("👤 Trabajadores")
    st.subheader("Alta de trabajador")

    col_dni, col_nom = st.columns([1, 3])
    with col_dni:
        st.session_state.modo_offline_trab = st.checkbox(
            "Modo offline (sin RENIEC)",
            value=st.session_state.modo_offline_trab,
            help="Actívalo si no hay internet o RENIEC no responde. Te permite registrar manualmente.",
        )

        dni = st.text_input("DNI", max_chars=8, key="dni_trab")

        if dni != st.session_state.last_dni_consultado:
            st.session_state.reniec_ok = False
            st.session_state.reniec_error = None

        if (
            (not st.session_state.modo_offline_trab)
            and dni
            and len(dni) == 8
            and dni.isdigit()
            and not st.session_state.reniec_ok
        ):
            try:
                with st.spinner("Consultando RENIEC..."):
                    r_reniec = requests.get(f"{API}/reniec/dni/{dni}", timeout=6)

                if r_reniec.status_code == 200:
                    data = r_reniec.json()
                    st.session_state.nom_trab = data.get("nombre", "")
                    st.session_state.ap_pat = data.get("apellido_paterno", "")
                    st.session_state.ap_mat = data.get("apellido_materno", "")
                    st.session_state.reniec_ok = True
                    st.session_state.last_dni_consultado = dni
                    st.toast("Datos obtenidos de RENIEC", icon="🪪")
                elif r_reniec.status_code == 404:
                    st.session_state.reniec_ok = False
                    st.session_state.reniec_error = "DNI no encontrado en RENIEC. Puede ingresar manualmente."
                    st.session_state.last_dni_consultado = dni
                    modal_dni_no_reniec("DNI no encontrado")
                else:
                    st.session_state.reniec_ok = False
                    st.session_state.reniec_error = f"RENIEC respondió {r_reniec.status_code}. Puede registrar manualmente."
            except Exception as e:
                st.session_state.reniec_ok = False
                st.session_state.reniec_error = f"RENIEC no disponible: {str(e)}. Puede registrar manualmente."

    with col_nom:
        nombre = st.text_input("Nombres", key="nom_trab")

    col3, col4 = st.columns(2)
    with col3:
        apellido_paterno = st.text_input("Apellido paterno", key="ap_pat")
    with col4:
        apellido_materno = st.text_input("Apellido materno", key="ap_mat")

    col_rol, _ = st.columns([1, 1])
    with col_rol:
        rol_trab = st.selectbox("Rol", ["EMPACADORA", "SELECCIONADOR"], key="rol_trab")

        if st.button("Crear trabajador"):
            if not dni or len(dni) != 8 or not dni.isdigit():
                st.warning("DNI inválido (8 dígitos)")
                st.stop()

            if not nombre.strip():
                st.warning("Nombres obligatorios.")
                st.stop()

            if not apellido_paterno.strip():
                st.warning("Apellido paterno obligatorio.")
                st.stop()

            jwt = get_jwt()
            if not jwt:
                st.session_state["flash_msg"] = {"kind": "err", "msg": "No hay token en sesión. Vuelve a iniciar sesión."}
                st.rerun()

            r = requests.post(
                f"{API}/trabajadores/",
                headers={"Authorization": f"Bearer {jwt}"},
                json={
                    "dni": dni,
                    "nombre": nombre,
                    "apellido_paterno": apellido_paterno,
                    "apellido_materno": apellido_materno,
                    "rol": rol_trab,
                },
                timeout=10,
            )

            if r.status_code == 200:
                data = r.json()
                request_reset_trabajador_form()

                flash_set(
                    "👤 Trabajadores",
                    "ok",
                    f"Trabajador creado → {nombre} {apellido_paterno} ({data['num_orden']}-{data['cod_letra']})",
                )
                st.rerun()
            else:
                flash_set("👤 Trabajadores", "err", f"No se pudo crear trabajador: {r.text}")
                st.rerun()

    st.divider()

    r = requests.get(f"{API}/trabajadores/?activos=true", headers=auth_headers(), timeout=10)
    if r.status_code != 200:
        st.error("Error cargando trabajadores")
        st.code(r.text)
        return

    if st.session_state.get("clear_trabajador_selection_on_next_run"):
        st.session_state["clear_trabajador_selection_on_next_run"] = False
        st.session_state["selected_trabajador_id"] = None
        st.session_state.show_edit_modal = False
        st.session_state.edit_trabajador_id = None
        st.session_state["trabajadores_table_nonce"] = st.session_state.get("trabajadores_table_nonce", 0) + 1

    if "trabajadores_table_nonce" not in st.session_state:
        st.session_state["trabajadores_table_nonce"] = 0

    trabajadores = sorted(r.json(), key=lambda t: t["num_orden"])
    st.subheader(f"Listado de trabajadores activos ({len(trabajadores)})")

    filtro = st.text_input(
        "Buscar en trabajadores (DNI o nombre)",
        key="trabajadores_busqueda",
        placeholder="Ejemplo: 40383794 o Anais",
    ).strip().lower()

    if filtro:
        trabajadores = [
            t
            for t in trabajadores
            if filtro in (t.get("dni") or "").lower()
            or filtro in (t.get("nombre") or "").lower()
            or filtro in (t.get("apellido_paterno") or "").lower()
            or filtro in (t.get("apellido_materno") or "").lower()
        ]

    st.caption(f"Coincidencias: {len(trabajadores)}")

    if not trabajadores:
        st.info("No se encontraron trabajadores con ese filtro")
        st.session_state.edit_trabajador_id = None
        st.session_state.show_edit_modal = False
        st.session_state["selected_trabajador_id"] = None
        return

    df = pd.DataFrame(trabajadores)
    df_ui = df.copy()

    if "selected_trabajador_id" not in st.session_state:
        st.session_state["selected_trabajador_id"] = None

    selected_id = st.session_state.get("selected_trabajador_id")
    df_ui["✏️"] = df_ui["id"].apply(lambda v: bool(selected_id) and v == selected_id)

    columnas_ui = [
        "✏️",
        "dni",
        "nombre",
        "apellido_paterno",
        "apellido_materno",
        "rol",
        "num_orden",
        "cod_letra",
    ]

    edited_df = st.data_editor(
        df_ui[columnas_ui],
        hide_index=True,
        num_rows="fixed",
        disabled=[c for c in columnas_ui if c != "✏️"],
        width="content",
        key=f"tabla_trabajadores_editar_{st.session_state['trabajadores_table_nonce']}",
    )

    filas_seleccionadas = [int(i) for i in edited_df.index[edited_df["✏️"] == True].tolist()]

    if len(filas_seleccionadas) > 1:
        fila_idx = filas_seleccionadas[0]
        selected_id = trabajadores[fila_idx]["id"]
        st.session_state["selected_trabajador_id"] = selected_id
        st.session_state.edit_trabajador_id = selected_id
        st.session_state.show_edit_modal = True
        st.warning("Solo puede seleccionar un trabajador a la vez. Se mantuvo la primera selección.")
        request_clear_selection()
        st.rerun()
    elif len(filas_seleccionadas) == 1:
        fila_idx = filas_seleccionadas[0]
        selected_id = trabajadores[fila_idx]["id"]
        st.session_state["selected_trabajador_id"] = selected_id
        st.session_state.edit_trabajador_id = selected_id
        st.session_state.show_edit_modal = True
        request_clear_selection()
    else:
        st.session_state["selected_trabajador_id"] = None
        st.session_state.show_edit_modal = False
        st.session_state.edit_trabajador_id = None

    if st.session_state.show_edit_modal and st.session_state.edit_trabajador_id:
        tr = next(t for t in trabajadores if t["id"] == st.session_state.edit_trabajador_id)

        @st.dialog("Editar trabajador")
        def modal_editar_trabajador():
            with st.form(key=f"form_editar_trabajador_{tr['id']}"):
                dni_e = st.text_input("DNI", value=tr["dni"], key=f"edit_dni_{tr['id']}")
                nom_e = st.text_input("Nombre", value=tr["nombre"], key=f"edit_nom_{tr['id']}")
                ap_pat_e = st.text_input("Apellido paterno", value=tr["apellido_paterno"], key=f"edit_ap_pat_{tr['id']}")
                ap_mat_e = st.text_input("Apellido materno", value=tr["apellido_materno"], key=f"edit_ap_mat_{tr['id']}")
                rol_e = st.selectbox(
                    "Rol",
                    ["EMPACADORA", "SELECCIONADOR"],
                    index=["EMPACADORA", "SELECCIONADOR"].index(tr["rol"]),
                    key=f"edit_rol_{tr['id']}",
                )

                c1, c2 = st.columns(2)
                guardar = c1.form_submit_button("💾 Guardar")
                cancelar = c2.form_submit_button("❌ Cancelar")

            if guardar:
                r_upd = requests.put(
                    f"{API}/trabajadores/{tr['id']}",
                    json={
                        "dni": dni_e,
                        "nombre": nom_e,
                        "apellido_paterno": ap_pat_e,
                        "apellido_materno": ap_mat_e,
                        "rol": rol_e,
                    },
                    headers=auth_headers(),
                    timeout=10,
                )
                if r_upd.status_code == 200:
                    st.session_state.show_edit_modal = False
                    st.session_state.edit_trabajador_id = None
                    st.session_state["selected_trabajador_id"] = None
                    request_clear_selection()
                    st.rerun()
                else:
                    st.error(r_upd.text)

            if cancelar:
                st.session_state.show_edit_modal = False
                st.session_state.edit_trabajador_id = None
                st.session_state["selected_trabajador_id"] = None
                request_clear_selection()
                st.rerun()

        modal_editar_trabajador()
