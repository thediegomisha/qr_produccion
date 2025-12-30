from printers_panel import show_printers_panel
import streamlit as st

st.set_page_config(
    page_title="Sistema de Etiquetas",
    page_icon="logo_empresa.png",
    layout="wide"
)

import requests
import pandas as pd

# ==============================
# ESTADO DEL MODAL
# ==============================
if "show_dni_modal" not in st.session_state:
    st.session_state.show_dni_modal = False
    st.session_state.modal_message = ""

if "reniec_ok" not in st.session_state:
    st.session_state.reniec_ok = False

if "last_dni_consultado" not in st.session_state:
    st.session_state.last_dni_consultado = None

if "modo_offline_trab" not in st.session_state:
    st.session_state.modo_offline_trab = False

if "reniec_error" not in st.session_state:
    st.session_state.reniec_error = None




API = "http://127.0.0.1:8000"

# ======================================================
# CONFIGURACIÓN DE COLUMNAS POR VISTA (SOLO UI)
# ======================================================

COLUMNAS_IMPRESION = [
    "seleccionar",
    "dni",
    "nombre",
    "apellido_paterno",
    "apellido_materno",
#    "rol",
    "num_orden",
#    "cod_letra",
]

COLUMNAS_LISTADO = [
   # "id",
    "dni",
    "nombre",
    "apellido_paterno",
    "apellido_materno",
#    "rol",
    "num_orden",
    "cod_letra",
  #  "activo",
  #  "creado_en",
]

COLUMNAS_TRABAJADOR = [
   # "id",
    "dni",
    "nombre",
    "apellido_paterno",
    "apellido_materno",
    "rol",
    "num_orden",
    "cod_letra",
    "activo",
  #  "creado_en",
]

# --------------------------------------------------
# ESTADO DE AUTENTICACIÓN
# --------------------------------------------------
if "auth" not in st.session_state:
    st.session_state.auth = None

# --------------------------------------------------
# BOOTSTRAP DEL SISTEMA (ROOT)
# --------------------------------------------------
resp = requests.get(f"{API}/setup/status")

if resp.status_code == 200 and not resp.json().get("initialized"):
    st.title("Inicialización del sistema")
    st.info("Debe crear el usuario administrador (ROOT)")

    usuario = st.text_input("Usuario admin", key="root username")
    nombre = st.text_input("Nombre completo", key="root full name")
    password = st.text_input("Contraseña", type="password", key="root password")

    if st.button("Crear administrador"):
        r = requests.post(
            f"{API}/setup/init-root",
            json={
                "usuario": usuario,
                "nombre": nombre,
                "password": password
            }
        )

        if r.status_code == 200:
            st.success("Administrador creado. Recargue la página.")
            st.stop()
        else:
            st.error(r.text)

    st.stop()

# --------------------------------------------------
# LOGIN (COLORES CORPORATIVOS DEL LOGO)
# --------------------------------------------------
if not st.session_state.auth:

    st.markdown("""
    <style>
    /* Fondo solo login */
    .login-overlay {
        position: fixed;
        inset: 0;
        background: linear-gradient(
            135deg,
            #e8f5e9 0%,
            #f5f7f6 60%
        );
        z-index: -1;
    }

    /* Modal */
    .login-modal {
        background: #ffffff;
        padding: 2.8rem 2.5rem 2.3rem 2.5rem;
        border-radius: 20px;
        box-shadow: 0 25px 50px rgba(0,0,0,0.25);
        border-top: 6px solid #2E7D32;
    }

    /* Logo */
    .login-logo {
        display: flex;
        justify-content: center;
        margin-bottom: 0.8rem;
    }

    /* Títulos */
    .login-title {
        text-align: center;
        font-size: 1.65rem;
        font-weight: 700;
        color: #1B5E20;
        margin-bottom: 0.2rem;
    }

    .login-subtitle {
        text-align: center;
        color: #6b7280;
        font-size: 0.9rem;
        margin-bottom: 2rem;
    }

    /* Inputs */
    .login-modal input {
        background-color: #f1f5f4;
        border-radius: 10px !important;
        border: 1px solid #c8e6c9;
    }

    .login-modal input:focus {
        border-color: #2E7D32;
        box-shadow: 0 0 0 1px #2E7D32;
    }

    /* Botón */
    .login-modal .stButton > button {
        width: 100%;
        background: linear-gradient(
            135deg,
            #2E7D32,
            #1B5E20
        );
        color: white;
        font-weight: 600;
        padding: 0.65rem;
        border-radius: 12px;
        border: none;
        margin-top: 0.8rem;
    }

    .login-modal .stButton > button:hover {
        background: linear-gradient(
            135deg,
            #1B5E20,
            #2E7D32
        );
    }
    </style>

    <div class="login-overlay"></div>
    """, unsafe_allow_html=True)

    # CENTRADO NATIVO
    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        st.markdown("""
        <div class="login-modal">
            <div class="login-logo">
                <img src="data:image/png;base64,LOGO_BASE64" width="95"/>
            </div>
            <div class="login-title">Sistema de Etiquetas</div>
            <div class="login-subtitle">Agrícola del Sur Pisco</div>
        """, unsafe_allow_html=True)

        usuario = st.text_input("Usuario", key="login_username")
        password = st.text_input("Contraseña", type="password", key="login_password")

        if st.button("Ingresar"):
            r = requests.post(
                f"{API}/auth/login",
                json={
                    "usuario": usuario,
                    "password": password
                }
            )

            if r.status_code == 200:
                st.session_state.auth = r.json()
                st.success("Ingreso correcto")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()



# --------------------------------------------------
# MOSTRAR USUARIO ACTIVO Y CERRAR SESIÓN
# --------------------------------------------------
rol = st.session_state.auth["rol"]
usuario = st.session_state.auth["usuario"]

st.sidebar.success(f"{usuario} ({rol})")

if st.sidebar.button("Cerrar sesión"):
    st.session_state.auth = None
    st.rerun()

# PESTAÑAS SEGÚN ROL
tabs = []

if rol == "ROOT":
    tabs = ["Usuarios", "Listar", "🖨️ Impresión", "👤 Trabajadores", "🖨️ Impresoras"]
elif rol == "SUPERVISOR":
    tabs = ["Listar", "🖨️ Impresión", "👤 Trabajadores", "🖨️ Impresoras"]
else:
    tabs = ["🖨️ Impresión"]

tab_objs = st.tabs(tabs)

# ======================================================
# 3) PESTAÑA USUARIOS (AUDITORÍA)
# ======================================================
if "Usuarios" in tabs:
    with tab_objs[tabs.index("Usuarios")]:
        st.subheader("Administración de usuarios del sistema")

        st.markdown("### Crear nuevo usuario")

        col1, col2 = st.columns(2)
        with col1:
            nuevo_usuario = st.text_input("Usuario (login)", key="new user username")
            nombre = st.text_input("Nombre completo", key="new user full name")

        with col2:
            password = st.text_input("Contraseña", type="password", key="new user password")
            rol_nuevo = st.selectbox(
                "Rol",
                ["SUPERVISOR", "OPERADOR"]
            )

        if st.button("Crear usuario"):
            if not nuevo_usuario or not password or not nombre:
                st.warning("Complete todos los campos")
            else:
                r = requests.post(
                    f"{API}/admin/usuarios",
                    json={
                        "usuario": nuevo_usuario,
                        "nombre": nombre,
                        "password": password,
                        "rol": rol_nuevo
                    }
                )

                if r.status_code == 200:
                    st.success("Usuario creado correctamente")
                    st.rerun()
                    st.session_state["Usuarios"]= None
                else:
                    st.error("Error al crear usuario")
                    st.code(r.text)

# ======================================================
# 4) PESTAÑA LISTAR
# ======================================================
if "Listar" in tabs:
    with tab_objs[tabs.index("Listar")]:
        
        r = requests.get(f"{API}/trabajadores?activos=true")
        if r.status_code == 200:
            trabajadores = r.json()
            # ORDENAR ASCENDENTE POR num_orden
            trabajadores = sorted(trabajadores, key=lambda t: t["num_orden"])
            total_trabajadores = len(trabajadores)

            st.subheader(f"Listado de trabajadores activos ({total_trabajadores})")

            if trabajadores:
                df = pd.DataFrame(trabajadores)
                df_listado = df[COLUMNAS_LISTADO]

                st.dataframe( df_listado, width="stretch")
            else:
                st.info("No hay trabajadores registrados")
        else:
            st.error("Error cargando trabajadores")

# ======================================================
# 5) PESTAÑA TRABAJADORES (ALTA)
# ======================================================
def modal_error_dni_registrado(mensaje):
    @st.dialog("⚠️ Registro no permitido")
    def _modal():
        st.error(mensaje)
        st.markdown("El DNI ingresado ya existe en el sistema.")

        if st.button("Aceptar"):
            # Limpiar campos del formulario
            for k in ("dni_trab", "nom_trab", "ap_pat", "ap_mat", "rol_trab"):
                st.session_state.pop(k, None)

            st.rerun()

    _modal()

def modal_dni_no_reniec(mensaje):
    @st.dialog("⚠️ DNI no válido")
    def _modal():
        st.warning(mensaje)
        st.markdown("El DNI no fue encontrado en RENIEC.")

        if st.button("Aceptar", type="primary"):
            # 🔑 LIMPIAR CAMPOS CLAVE
            for k in ("dni_trab", "nom_trab", "ap_pat", "ap_mat"):
                st.session_state.pop(k, None)

            # 🔑 RESETEAR ESTADO RENIEC
            st.session_state.reniec_ok = False

            # 🔑 MUY IMPORTANTE: evitar re-disparo inmediato
            st.session_state.pop("dni_trab", None)

            st.rerun()

    _modal()




if "👤 Trabajadores" in tabs:
    with tab_objs[tabs.index("👤 Trabajadores")]:
        st.subheader("Alta de trabajador")

        col_dni, col_nom = st.columns([1,3])
        with col_dni:
            st.session_state.modo_offline_trab = st.checkbox("Modo offline (sin RENIEC)",
            value=st.session_state.modo_offline_trab,
            help="Actívalo si no hay internet o RENIEC no responde. Te permite registrar manualmente."
        )

            dni = st.text_input("DNI", max_chars=8, key="dni_trab")

            # ==============================
            # 🔍 VALIDACIÓN RENIEC
            # ==============================
            
            # Si el DNI cambia, resetear estado RENIEC
            if dni != st.session_state.last_dni_consultado:
                st.session_state.reniec_ok = False
                st.session_state.reniec_error = None

            

            # 🔍 Consultar RENIEC solo si:
            # - No estamos en modo offline
            if (not st.session_state.modo_offline_trab) and dni and len(dni) == 8 and dni.isdigit() and not st.session_state.reniec_ok:
                try:
                    with st.spinner("Consultando RENIEC..."):
                        r_reniec = requests.get(f"{API}/reniec/dni/{dni}", timeout=6)

                    if r_reniec.status_code == 200:
                        data = r_reniec.json()

                        st.session_state.nom_trab = data["nombre"]
                        st.session_state.ap_pat = data["apellido_paterno"]
                        st.session_state.ap_mat = data["apellido_materno"]

                        st.session_state.reniec_ok = True
                        st.session_state.last_dni_consultado = dni

                        st.toast("Datos obtenidos de RENIEC", icon="🪪")

                    elif r_reniec.status_code == 404:
                        # DNI NO ENCONTRADO; PERMITIR INGRESO MANUAL
                        st.session_state.reniec_ok = False
                        st.session_state.reniec_error = "DNI no encontrado en RENIEC, puede ingresar los datos manualmente."
                        st.session_state.last_dni_consultado = dni                    
                        modal_dni_no_reniec("DNI no encontrado")

                    else:
                        st.session_state.reniec_ok = False
                        st.session_state.reniec_error = f"RENIEC respondio con error: {r_reniec.status_code}. Puedes registralo manualmente."
                except Exception as e:
                    st.session_state.reniec_ok = False
                    st.session_state.reniec_error = f"RENIEC no disponible: {str(e)}. Puedes registralo manualmente."

        with col_nom:
            nombre = st.text_input("Nombres", key="nom_trab")

        col3, col4 = st.columns(2)
        with col3:
            apellido_paterno = st.text_input("Apellido paterno", key="ap_pat")
        with col4:
            apellido_materno = st.text_input("Apellido materno", key="ap_mat")

        col_rol, col_btn = st.columns([1, 1])
        with col_rol:
            rol = st.selectbox("Rol", ["EMPACADORA", "SELECCIONADOR"], key="rol_trab")

        # ==============================
        #  CREAR TRABAJADOR
        # ==============================
        if st.button("Crear trabajador"):

            # 🔒 OBLIGAR VALIDACIÓN RENIEC
            if not dni or len(dni) != 8 or not dni.isdigit():
                st.warning("DNI inválido (8 dígitos)")
                st.stop()

            if not nombre.strip():
                st.warning("Nombres obligatorios.")
                st.stop()

            if not apellido_paterno.strip():
                st.warning("Apellido paterno obligatorio.")
                st.stop()

            r = requests.post(
                f"{API}/trabajadores",
                json={
                    "dni": dni,
                    "nombre": nombre,
                    "apellido_paterno": apellido_paterno,
                    "apellido_materno": apellido_materno,
                    "rol": rol
                },
                timeout=10
            )

            if r.status_code == 200:
                data = r.json()
                st.toast(
                    f"Trabajador creado → {nombre} {apellido_paterno} "
                    f"({data['num_orden']}-{data['cod_letra']})",
                    icon="✅"
                )

                # 🧹 LIMPIAR FORMULARIO
                for k in ("dni_trab", "nom_trab", "ap_pat", "ap_mat", "rol_trab"):
                    st.session_state.pop(k, None)

                st.session_state.reniec_ok = False
                st.session_state.reniec_error = None
                st.session_state.last_dni_consultado = None
                st.rerun()

            elif r.status_code == 409 and "DNI ya registrado" in r.text:
                modal_error_dni_registrado("DNI ya registrado")

            else:
                st.error("No se pudo crear el trabajador")
                st.code(r.text)

            st.divider()
        
        r = requests.get(f"{API}/trabajadores?activos=true")
        if r.status_code != 200:
            st.error("Error cargando trabajadores")
            # st.stop()
        else:
            trabajadores = r.json()
            # ORDENAR ASCENDENTE POR num_orden
            trabajadores = sorted(trabajadores, key=lambda t: t["num_orden"])
            total_trabajadores = len(trabajadores)

            if not trabajadores:
                st.info("No hay trabajadores registrados")
            # st.stop()
            else:
                df = pd.DataFrame(trabajadores)

                st.subheader(f"Listado de trabajadores activos ({total_trabajadores})")

                # --------------------------------------------------
                # TABLA CON ENCABEZADOS + ORDEN + ✏️
                # --------------------------------------------------
                df_ui = df.copy()

                # Columna acción
                df_ui["✏️"] = False

                # Columnas visibles (id NO se muestra, pero se mantiene en df_ui)
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
                    width='content',
                    key="tabla_trabajadores_editar"
                )

# ------------------------------
# Estado de edición (AGREGAR 1 VEZ antes, cerca de tus otros states)
# ------------------------------
if "edit_trabajador_id" not in st.session_state:
    st.session_state.edit_trabajador_id = None
if "show_edit_modal" not in st.session_state:
    st.session_state.show_edit_modal = False

# ------------------------------
# Selección desde data_editor
# ------------------------------
seleccionados = edited_df[edited_df["✏️"] == True]

selected_id = None
if len(seleccionados) == 1:
    fila_idx = seleccionados.index[0]
    tr = trabajadores[fila_idx]
    selected_id = tr["id"]

    # Abrir SOLO si cambió la selección (evita reapertura constante)
    if st.session_state.edit_trabajador_id != selected_id:
        st.session_state.edit_trabajador_id = selected_id
        st.session_state.show_edit_modal = True

# Si no hay selección, no mantener modal “pegado”
if selected_id is None and st.session_state.show_edit_modal:
    st.session_state.show_edit_modal = False
    st.session_state.edit_trabajador_id = None


# ------------------------------
# MODAL DE EDICIÓN (solo si está activo)
# ------------------------------
if st.session_state.show_edit_modal and st.session_state.edit_trabajador_id:

    tr = next(t for t in trabajadores if t["id"] == st.session_state.edit_trabajador_id)

    @st.dialog("Editar trabajador")
    def modal_editar_trabajador():
        # IMPORTANTE: el form necesita key única
        with st.form(key=f"form_editar_trabajador_{tr['id']}"):
            dni = st.text_input("DNI", value=tr["dni"], key=f"edit_dni_{tr['id']}")
            nombre = st.text_input("Nombre", value=tr["nombre"], key=f"edit_nom_{tr['id']}")
            ap_pat = st.text_input("Apellido paterno", value=tr["apellido_paterno"], key=f"edit_ap_pat_{tr['id']}")
            ap_mat = st.text_input("Apellido materno", value=tr["apellido_materno"], key=f"edit_ap_mat_{tr['id']}")
            rol = st.selectbox(
                "Rol",
                ["EMPACADORA", "SELECCIONADOR"],
                index=["EMPACADORA", "SELECCIONADOR"].index(tr["rol"]),
                key=f"edit_rol_{tr['id']}"
            )

            c1, c2 = st.columns(2)
            guardar = c1.form_submit_button("💾 Guardar")
            cancelar = c2.form_submit_button("❌ Cancelar")

        # ---- Guardar
        if guardar:
            r = requests.put(
                f"{API}/trabajadores/{tr['id']}",
                json={
                    "dni": dni,
                    "nombre": nombre,
                    "apellido_paterno": ap_pat,
                    "apellido_materno": ap_mat,
                    "rol": rol
                }
            )

            if r.status_code == 200:
                st.success("Trabajador actualizado correctamente")

                # Cerrar modal
                st.session_state.show_edit_modal = False
                st.session_state.edit_trabajador_id = None

                # 🔑 Limpiar estado del data_editor para desmarcar ✏️
                st.session_state.pop("tabla_trabajadores_editar", None)

                st.rerun()
            else:
                st.error(r.text)

        # ---- Cancelar
        if cancelar:
            # Cerrar modal
            st.session_state.show_edit_modal = False
            st.session_state.edit_trabajador_id = None

            # 🔑 Limpiar estado del data_editor para desmarcar ✏️
            st.session_state.pop("tabla_trabajadores_editar", None)

            st.rerun()

    modal_editar_trabajador()


                    
# ======================================================
# 6) PESTAÑA 🖨️ IMPRESIÓN (SELECCIÓN POR FILA)
# ======================================================
def generar_vista_previa():
    trabajador = st.session_state.get("trabajador_seleccionado")
    if not trabajador:
        st.session_state.preview_img = None
        st.session_state.preview_error = None
        return

    opcion = st.session_state.get("opcion_mostrar")
    producto = st.session_state.get("producto")
    cantidad = st.session_state.get("cantidad")

    valor_visible = (
        trabajador["num_orden"]
        if opcion == "Número de orden"
        else trabajador["cod_letra"]
    )
    try:

        r = requests.post(
            f"{API}/qr/preview",
            json={
                "dni": trabajador["dni"],
                "nn": valor_visible,
                "producto": producto,
                "cantidad": cantidad
            },
            timeout=10
        )
    except Exception as e:
        # error de red: limpiar preview y guardar error
        st.session_state.preview_img = None
        st.session_state.preview_error = str(e)
        return

    if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
        st.session_state.preview_img = r.content
        st.session_state.preview_error = None
    else:
        st.session_state.preview_img = None
        st.session_state.preview_error = r.text


if "🖨️ Impresión" in tabs:
    with tab_objs[tabs.index("🖨️ Impresión")]:
        
        st.subheader("Impresión de etiquetas")

        # ==============================
        # OBTENER TRABAJADORES
        # ==============================
        r = requests.get(f"{API}/trabajadores?activos=true")
        if r.status_code != 200:
            st.error("Error cargando trabajadores")
        #  st.stop()
        else:
            trabajadores = sorted(r.json(), key=lambda t: t["num_orden"])
            total_trabajadores = len(trabajadores)

            st.metric("👥 Trabajadores activos", total_trabajadores)

            if not trabajadores:
                st.warning("No hay trabajadores registrados")
           # st.stop()
            else:

        # ==============================
        # BUSCADOR
        # ==============================
                busqueda = st.text_input(
                    "Buscar por DNI o nombre",
                    placeholder="Ejemplo: 40383794 o Anais"
                ).strip().lower()

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
         #   st.stop()
        else:

        # ==============================
        # TABLA SELECCIONABLE
        # ==============================
            st.markdown("### Seleccione un trabajador")

            df = pd.DataFrame(filtrados)

            if "seleccionar" not in df.columns:
                df.insert(0, "seleccionar", False)

            df_impresion = df[COLUMNAS_IMPRESION]

            edited_df = st.data_editor(
                df_impresion,
                hide_index=True,
                disabled=[c for c in df_impresion.columns if c != "seleccionar"],
                num_rows="fixed",
                key="tabla_trabajadores_impresion"
            )

        seleccionados = edited_df[edited_df["seleccionar"] == True]

        if len(seleccionados) != 1:
            st.info("Seleccione un solo trabajador")
            st.session_state.pop("trabajador_seleccionado", None)
            st.session_state.preview_img = None
            st.session_state.preview_error = None
        # st.stop()
        else:
            fila_idx = seleccionados.index[0]
            trabajador = filtrados[fila_idx]
            st.session_state.trabajador_seleccionado = trabajador
            generar_vista_previa()

        # ==============================
        # OPCIONES DE ETIQUETA
        # ==============================
        st.markdown("### Contenido visible en la etiqueta")

        st.radio(
            "¿Qué desea imprimir en el centro del QR?",
            ["Número de orden", "Código de letra"],
            horizontal=True,
            key="opcion_mostrar",
            on_change=generar_vista_previa
        )

        col_prod, col_cant, _ = st.columns([1.2, 0.6, 3])

        with col_prod:
            st.selectbox(
                "Producto",
                ["UVA"],
                key="producto",
                on_change=generar_vista_previa
            )

        with col_cant:
            st.number_input(
                "Cantidad de etiquetas",
                min_value=1,
                max_value=5000,
                value=1,
                step=1,
                key="cantidad",
                on_change=generar_vista_previa
            )


        generar_vista_previa()

        # ==============================
        # MOSTRAR VISTA PREVIA
        # ==============================
        if st.session_state.get("preview_img"):
            st.image(
                st.session_state.preview_img,
                caption="Generated by Agricola del Sur Pisco EIRL",
            )

        # ==============================
        # IMPRESORA SELECCIONADA (desde pestaña Impresoras)
        # ==============================
        selected_printer = st.session_state.get("selected_printer_name")  # viene del printers_panel
        selected_agent_url = st.session_state.get("selected_printer_agent_url")  # opcional

        if selected_printer:
            st.caption(f"Impresora seleccionada: **{selected_printer}**")
        else:
            st.warning("No hay impresora seleccionada. Ve a la pestaña **🖨️ Impresoras** y selecciona una.")


        if st.session_state.get("preview_error"):
            st.error("Error al generar la vista previa")

        btn_label = f"🖨️ Imprimir etiquetas ({selected_printer})" if selected_printer else "🖨️ Imprimir etiquetas"

        # usar siempre el trabajador desde session_state para evitar variables fuera de scope
        trabajador_sel = st.session_state.get("trabajador_seleccionado")

        if st.button(btn_label, disabled=not bool(selected_printer)):
            if not trabajador_sel:
                st.error("Seleccione un trabajador antes de imprimir.")
                st.stop()

            nn_value = (
                trabajador_sel["num_orden"]
                if st.session_state.opcion_mostrar == "Número de orden"
                else trabajador_sel["cod_letra"]
            )


            printer = st.session_state.get("selected_printer_name")
            agent_url = st.session_state.get("selected_printer_agent_url")

            requests.post(
                    f"{API}/qr/print",
                    json={
                        "dni": trabajador_sel["dni"],
                        "nn": nn_value,
                        "producto": st.session_state.producto,
                        "cantidad": st.session_state.cantidad,
                        "printer": printer,
                        "agent_url": agent_url,
                    },
                    timeout=15
                )

            if r.status_code == 200:
                st.toast("Impresión enviada correctamente 🖨️", icon="✅")
            else:
                st.error("Error al imprimir")
                st.code(r.text)

                # 🧹 limpiar estado
                for k in (
                    "tabla_trabajadores_impresion",
                    "trabajador_seleccionado",
                    "preview_img",
                    "preview_error"
                ):
                    st.session_state.pop(k, None)


# ======================================================
# 6) PESTAÑA 🖨️ IMPRESORAS 
# ======================================================
if "🖨️ Impresoras" in tabs:
    with tab_objs[tabs.index("🖨️ Impresoras")]:
        show_printers_panel()
        st.subheader("Configuración de impresoras")

    




