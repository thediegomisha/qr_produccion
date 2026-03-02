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
    st.subheader("🔎 Consulta por DNI")
    st.caption("Consulta en línea desde RENIEC y visualización en modo lectura.")

    if "consulta_reniec_ok" not in st.session_state:
        st.session_state.consulta_reniec_ok = False
    if "consulta_reniec_error" not in st.session_state:
        st.session_state.consulta_reniec_error = None
    if "consulta_last_dni" not in st.session_state:
        st.session_state.consulta_last_dni = None

    def buscar_dni() -> None:
        dni_local = (st.session_state.get("consulta_dni") or "").strip()

        if len(dni_local) != 8 or not dni_local.isdigit():
            st.session_state.consulta_reniec_ok = False
            st.session_state.consulta_reniec_error = "DNI inválido (8 dígitos)."
            return

        try:
            with st.spinner("Consultando RENIEC..."):
                r = api_get(f"/reniec/dni/{dni_local}")

            if r.status_code == 200:
                data = r.json() or {}
                st.session_state.consulta_nombre = data.get("nombre", "")
                st.session_state.consulta_ap_pat = data.get("apellido_paterno", "")
                st.session_state.consulta_ap_mat = data.get("apellido_materno", "")
                st.session_state.consulta_fecha_nac = data.get("fecha_nacimiento", "")
                st.session_state.consulta_reniec_ok = True
                st.session_state.consulta_reniec_error = None
                st.session_state.consulta_last_dni = dni_local
            elif r.status_code == 404:
                st.session_state.consulta_reniec_ok = False
                st.session_state.consulta_reniec_error = "DNI no encontrado en RENIEC/ApiPeru."
                st.session_state.consulta_last_dni = dni_local
            else:
                st.session_state.consulta_reniec_ok = False
                st.session_state.consulta_reniec_error = f"Servicio respondió {r.status_code}."
                st.session_state.consulta_last_dni = dni_local
        except Exception as e:
            st.session_state.consulta_reniec_ok = False
            st.session_state.consulta_reniec_error = f"Error de conexión: {e}"

    col_dni, col_btn = st.columns([2, 1])
    with col_dni:
        dni_q = st.text_input(
            "DNI",
            max_chars=8,
            key="consulta_dni",
            placeholder="Ingrese 8 dígitos",
            on_change=buscar_dni,
        ).strip()
    with col_btn:
        buscar = st.button("Buscar", key="consulta_buscar_btn", type="primary")

    if dni_q != st.session_state.consulta_last_dni:
        st.session_state.consulta_reniec_ok = False
        st.session_state.consulta_reniec_error = None

    if buscar:
        buscar_dni()

    if st.session_state.consulta_reniec_error:
        st.warning(st.session_state.consulta_reniec_error)

    if not st.session_state.consulta_reniec_ok:
        st.info("Ingrese un DNI de 8 dígitos y presione Enter para buscar.")
        return

    st.success("Datos encontrados")

    c1, c2, c3 = st.columns(3)
    c1.text_input("DNI", value=st.session_state.consulta_last_dni or "", disabled=True)
    c2.text_input("Nombres", value=st.session_state.get("consulta_nombre", ""), disabled=True)
    c3.text_input("Fecha de nacimiento", value=st.session_state.get("consulta_fecha_nac") or "(No disponible)", disabled=True)

    c4, c5 = st.columns(2)
    c4.text_input("Apellido paterno", value=st.session_state.get("consulta_ap_pat", ""), disabled=True)
    c5.text_input("Apellido materno", value=st.session_state.get("consulta_ap_mat", ""), disabled=True)

    with st.expander("Ver detalle JSON"):
        st.json(
            {
                "dni": st.session_state.consulta_last_dni,
                "nombre": st.session_state.get("consulta_nombre"),
                "apellido_paterno": st.session_state.get("consulta_ap_pat"),
                "apellido_materno": st.session_state.get("consulta_ap_mat"),
                "fecha_nacimiento": st.session_state.get("consulta_fecha_nac"),
            }
        )
