from printers_panel import show_printers_panel, bootstrap_printer_selection
import streamlit as st
import base64
from pathlib import Path
import requests
import pandas as pd
from datetime import timedelta


# --------------------------------------------------
# CONFIG APP
# --------------------------------------------------
st.set_page_config(
    page_title="Sistema de Etiquetas",
    page_icon="logoappqr.png",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent  # carpeta ui_web/
ASSETS_DIR = BASE_DIR / "assets"

API = "http://127.0.0.1:8000/api"

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def _img_to_base64(filename: str) -> str:
    path = ASSETS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"No existe la imagen: {path}")
    return base64.b64encode(path.read_bytes()).decode("utf-8")

def get_jwt() -> str | None:
    auth = st.session_state.get("auth") or {}
    return auth.get("access_token") or auth.get("token")

def auth_headers() -> dict:
    jwt = get_jwt()
    if not jwt:
        return {}
    return {"Authorization": f"Bearer {jwt}"}

def api_get(path: str, params: dict | None = None):
    base = globals().get("API") or st.session_state.get("API")
    if not base:
        raise RuntimeError("Falta API (define API = 'http://...' o st.session_state['API'])")
    url = base.rstrip("/") + path
    return requests.get(url, params=params, headers=auth_headers(), timeout=30)

def api_post(path: str, json: dict | None = None):
    base = globals().get("API") or st.session_state.get("API")
    if not base:
        raise RuntimeError("Falta API (define API = 'http://...' o st.session_state['API'])")
    url = base.rstrip("/") + path
    return requests.post(url, json=json, headers=auth_headers(), timeout=30)

def api_put(path: str, json: dict | None = None):
    base = globals().get("API") or st.session_state.get("API")
    if not base:
        raise RuntimeError("Falta API")
    url = base.rstrip("/") + path
    return requests.put(url, json=json, headers=auth_headers(), timeout=30)


LOGIN_IMG_B64 = _img_to_base64("logoappqr.png")

def flash_set(tab: str, kind: str, msg: str):
    # kind: "ok" | "err"
    st.session_state["flash"] = {"tab": tab, "kind": kind, "msg": msg}

def flash_show(tab: str):
    """
    Muestra el flash SOLO si pertenece a este tab.
    Luego lo elimina para que no reaparezca.
    """
    flash = st.session_state.get("flash")
    if not flash:
        return

    if flash.get("tab") != tab:
        return

    # consumirlo (para que no salga otra vez)
    st.session_state.pop("flash", None)

    kind = flash.get("kind", "ok")
    msg = flash.get("msg", "")

    if kind == "ok":
        st.toast(msg, icon="✅")
        st.success(msg)
    else:
        st.toast(msg, icon="❌")
        st.error(msg)



# --------------------------------------------------
# SESSION STATE DEFAULTS
# --------------------------------------------------
if "auth" not in st.session_state:
    st.session_state.auth = None

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

# Lote activo (para reportes)
if "active_lote_codigo" not in st.session_state:
    st.session_state.active_lote_codigo = ""

    # Edit modal state (Usuarios)
if "edit_user_usuario" not in st.session_state:
    st.session_state.edit_user_usuario = None
if "show_user_modal" not in st.session_state:
    st.session_state.show_user_modal = False
if "_edit_user_row" not in st.session_state:
    st.session_state._edit_user_row = None



# Edit modal state
if "edit_trabajador_id" not in st.session_state:
    st.session_state.edit_trabajador_id = None
if "show_edit_modal" not in st.session_state:
    st.session_state.show_edit_modal = False

# --------------------------------------------------
# COLUMNAS UI
# --------------------------------------------------
COLUMNAS_IMPRESION = [
    "seleccionar",
    "dni",
    "nombre",
    "apellido_paterno",
    "apellido_materno",
    "num_orden",
    "cod_letra",
]

COLUMNAS_LISTADO = [
    "dni",
    "nombre",
    "apellido_paterno",
    "apellido_materno",
    "num_orden",
    "cod_letra",
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
# BOOTSTRAP SISTEMA ROOT
# --------------------------------------------------
resp = requests.get(f"{API}/setup/status")

if resp.status_code == 200 and not resp.json().get("initialized"):
    st.title("Inicialización del sistema")
    st.info("Debe crear el usuario administrador (ROOT)")

    usuario_root = st.text_input("Usuario admin", key="root_username")
    nombre_root = st.text_input("Nombre completo", key="root_full_name")
    password_root = st.text_input("Contraseña", type="password", key="root_password")

    if st.button("Crear administrador"):
        r = requests.post(
            f"{API}/setup/init-root",
            json={
                "usuario": usuario_root,
                "nombre": nombre_root,
                "password": password_root
            },
            timeout=10
        )

        if r.status_code == 200:
            st.success("Administrador creado. Recargue la página.")
            st.stop()
        else:
            st.error(r.text)

    st.stop()

# --------------------------------------------------
# LOGIN
# --------------------------------------------------
if not st.session_state.auth:

    st.markdown("""
    <style>
      .login-overlay{
        position: fixed; inset: 0;
        background: linear-gradient(135deg,#e8f5e9 0%,#f5f7f6 60%);
        z-index:-1;
      }

      div[data-testid="stContainer"]{
        background:#ffffff;
        padding: 1.8rem 1.6rem 1.4rem 1.6rem;
        border-radius: 20px;
        box-shadow: 0 25px 50px rgba(0,0,0,0.25);
        border-top: 6px solid #2E7D32;
      }

      .login-title{
        text-align:center;
        font-size:1.65rem;
        font-weight:700;
        color:#1B5E20;
        margin: 0.2rem 0 0.2rem 0;
      }
      .login-subtitle{
        text-align:center;
        color:#6b7280;
        font-size:0.9rem;
        margin: 0 0 1.0rem 0;
      }

      .stTextInput input{
        background-color:#f1f5f4 !important;
        border-radius:10px !important;
        border:1px solid #c8e6c9 !important;
      }
      .stTextInput input:focus{
        border-color:#2E7D32 !important;
        box-shadow:0 0 0 1px #2E7D32 !important;
      }

      div[data-testid="stFormSubmitButton"] > button{
        width:100%;
        background: linear-gradient(135deg,#2E7D32,#1B5E20) !important;
        color:white !important;
        font-weight:600 !important;
        padding:0.65rem !important;
        border-radius:12px !important;
        border:none !important;
        margin-top:0.4rem !important;
      }

      div[data-testid="stTextInput"] button{
        width:auto !important;
        padding:0.25rem 0.5rem !important;
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
      }
    </style>
    <div class="login-overlay"></div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        with st.container(border=True):
            st.markdown('<div class="login-title">Sistema de Etiquetas</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-subtitle">Agrícola del Sur Pisco</div>', unsafe_allow_html=True)

            st.markdown(
                f"""
                <div style="display:flex; justify-content:center; margin: 0.2rem 0 1.2rem 0;">
                  <img src="data:image/png;base64,{LOGIN_IMG_B64}"
                       style="max-width:260px; width:100%; height:auto; border-radius:14px;" />
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.form("login_form", clear_on_submit=False):
                usuario_login = st.text_input("Usuario", key="login_username")
                password_login = st.text_input("Contraseña", type="password", key="login_password")
                submit = st.form_submit_button("Ingresar")

            if submit:
                r = requests.post(
                    f"{API}/auth/login",
                    json={"usuario": usuario_login, "password": password_login},
                    timeout=10
                )
                if r.status_code == 200:
                    st.session_state.auth = r.json()
                    # Inicializa selección impresora solo si falta
                    if "selected_printer_name" not in st.session_state:
                        bootstrap_printer_selection()
                    st.success("Ingreso correcto")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")

    st.stop()

# --------------------------------------------------
# SIDEBAR / USER
# --------------------------------------------------
rol = (st.session_state.auth.get("rol") or "").upper()
usuario = st.session_state.auth.get("usuario") or st.session_state.auth.get("sub") or "?"

# No re-inicializar siempre; solo si falta
if "selected_printer_name" not in st.session_state:
    bootstrap_printer_selection()

st.sidebar.success(f"{usuario} ({rol})")

if st.sidebar.button("Cerrar sesión"):
    st.session_state.auth = None
    st.rerun()

# --------------------------------------------------
# TABS POR ROL
# --------------------------------------------------
if rol in ("ROOT", "GERENCIA"):
    tabs = ["Usuarios", "Listar", "🖨️ Impresión", "👤 Trabajadores", "🛡️ Vigilancia", "🖨️ Impresoras", "📊 Reportes", "📦 Lotes"]
elif rol == "SUPERVISOR":
    tabs = ["Listar", "🖨️ Impresión", "👤 Trabajadores","🖨️ Impresoras", "📊 Reportes", "📦 Lotes"]
elif rol == "VIGILANCIA":
    tabs = ["🛡️ Vigilancia"]
else:
    tabs = ["🖨️ Impresión"]

tab_objs = st.tabs(tabs)

# ======================================================
# TAB: USUARIOS (ROOT y GERENCIA) - LISTAR + CREAR + EDIT MODAL
# ======================================================
if "Usuarios" in tabs:
    with tab_objs[tabs.index("Usuarios")]:
        flash_show("Usuarios")
        st.subheader("Administración de usuarios del sistema")

        if rol not in ("ROOT", "GERENCIA"):
            st.error("No tienes permisos para administrar usuarios.")
            st.stop()

        # ----------------------------
        # LISTAR USUARIOS + SELECCIÓN (✏️)
        # ----------------------------
        st.markdown("### Usuarios registrados")

        r_list = api_get("/admin/usuarios")
        if r_list.status_code != 200:
            st.error("No se pudo listar usuarios")
            st.code(r_list.text)
            st.stop()

        users = (r_list.json() or {}).get("items", []) or []
        df_users = pd.DataFrame(users)

        if df_users.empty:
            st.info("No hay usuarios.")
        else:
            # índice estable (evita que selecciones edite mal)
            df_ui = df_users.reset_index(drop=True).copy()
            df_ui["creado_en"] = df_ui.get("creado_en", "-").fillna("-")

            # checkbox editor
            df_ui["✏️"] = False

            cols_show = ["✏️", "usuario", "nombre", "rol", "activo", "creado_en"]

            edited = st.data_editor(
                df_ui[cols_show],
                hide_index=True,
                num_rows="fixed",
                disabled=[c for c in cols_show if c != "✏️"],
                width="stretch",
                key="tabla_usuarios_editar"
            )

            seleccionados = edited[edited["✏️"] == True]

            # comportamiento igual a Trabajadores
            if len(seleccionados) == 1:
                fila_idx = int(seleccionados.index[0])  # por reset_index(drop=True)
                user_row = df_ui.iloc[fila_idx].to_dict()

                usuario_id = user_row["usuario"]
                rol_target = str(user_row.get("rol") or "").upper()

                # Regla: GERENCIA no edita ROOT/GERENCIA (seguridad + UX)
                if rol == "GERENCIA" and rol_target in ("ROOT", "GERENCIA"):
                    st.warning("GERENCIA no puede editar usuarios ROOT o GERENCIA.")
                    st.session_state.show_user_modal = False
                    st.session_state.edit_user_usuario = None
                    st.session_state._edit_user_row = None
                else:
                    st.session_state.edit_user_usuario = usuario_id
                    st.session_state.show_user_modal = True
                    st.session_state._edit_user_row = user_row
            else:
                st.session_state.show_user_modal = False
                st.session_state.edit_user_usuario = None
                st.session_state._edit_user_row = None

        st.divider()

        # ----------------------------
        # CREAR USUARIO
        # ROOT: puede crear SUPERVISOR/OPERADOR/GERENCIA
        # GERENCIA: solo SUPERVISOR/OPERADOR (backend debe bloquear GERENCIA->GERENCIA igual)
        # ----------------------------
        st.markdown("### Crear nuevo usuario")

        roles_create = ["SUPERVISOR", "OPERADOR"]
        if rol == "ROOT":
            roles_create = ["SUPERVISOR", "OPERADOR", "GERENCIA", "AGENTE"]

        c1, c2 = st.columns(2)
        with c1:
            nuevo_usuario = st.text_input("Usuario (login)", key="new_user_username")
            nombre_user = st.text_input("Nombre completo", key="new_user_full_name")
        with c2:
            password_user = st.text_input("Contraseña", type="password", key="new_user_password")
            rol_nuevo = st.selectbox("Rol", roles_create, key="new_user_role")

        if st.button("Crear usuario", key="btn_crear_usuario"):
            if not nuevo_usuario.strip() or not nombre_user.strip() or not password_user.strip():
                flash_set("Usuarios", "err", "Complete todos los campos")
                st.rerun()

            r_create = api_post("/admin/usuarios", json={
                "usuario": nuevo_usuario.strip(),
                "nombre": nombre_user.strip(),
                "password": password_user.strip(),
                "rol": rol_nuevo
            })

            if r_create.status_code == 200:
                flash_set("Usuarios", "ok", "Usuario creado correctamente")

                # limpiar inputs
                for k in ("new_user_username", "new_user_full_name", "new_user_password", "new_user_role"):
                    st.session_state.pop(k, None)

                # limpiar selección tabla para evitar reabrir modal
                st.session_state._reset_user_editor = True
                st.rerun()
            else:
                flash_set("Usuarios", "err", f"Error al crear usuario: {r_create.text}")
                st.rerun()

        # ----------------------------
        # MODAL EDITAR USUARIO (igual a trabajadores)
        # ----------------------------
        if st.session_state.show_user_modal and st.session_state.edit_user_usuario:
            usuario_id = st.session_state.edit_user_usuario
            user_row = st.session_state._edit_user_row or {}

            @st.dialog("Editar usuario")
            def modal_editar_usuario():
                with st.form(key=f"form_editar_usuario_{usuario_id}"):
                    nombre_e = st.text_input("Nombre", value=user_row.get("nombre") or "")
                    activo_e = st.checkbox("Activo", value=bool(user_row.get("activo", True)))

                    # Roles editables
                    roles_edit = ["SUPERVISOR", "OPERADOR", "GERENCIA", "AGENTE"]
                    if rol == "GERENCIA":
                        roles_edit = ["SUPERVISOR", "OPERADOR", "AGENTE"]

                    current_rol = (user_row.get("rol") or "OPERADOR").upper()
                    if current_rol not in roles_edit:
                        current_rol = roles_edit[0]

                    rol_e = st.selectbox("Rol", roles_edit, index=roles_edit.index(current_rol))

                    st.markdown("#### Cambiar contraseña (opcional)")
                    new_pass = st.text_input("Nueva contraseña", type="password")

                    b1, b2 = st.columns(2)
                    guardar = b1.form_submit_button("💾 Guardar")
                    cancelar = b2.form_submit_button("❌ Cancelar")

                if cancelar:
                    st.session_state.show_user_modal = False
                    st.session_state.edit_user_usuario = None
                    st.session_state._edit_user_row = None
                    st.session_state.pop("tabla_usuarios_editar", None)
                    st.rerun()

                if guardar:
                    # 1) update datos generales
                    r_upd = api_put(f"/admin/usuarios/{usuario_id}", json={
                        "nombre": nombre_e.strip(),
                        "rol": rol_e,
                        "activo": activo_e
                    })

                    if r_upd.status_code != 200:
                        st.error("Error actualizando usuario")
                        st.code(r_upd.text)
                        st.stop()

                    # 2) update password si escribió algo
                    if new_pass.strip():
                        r_pwd = api_put(f"/admin/usuarios/{usuario_id}/password", json={
                            "password": new_pass.strip()
                        })
                        if r_pwd.status_code != 200:
                            st.error("Error cambiando contraseña")
                            st.code(r_pwd.text)
                            st.stop()

                    flash_set("Usuarios", "ok", "Usuario actualizado")
                    st.session_state.show_user_modal = False
                    st.session_state.edit_user_usuario = None
                    st.session_state._edit_user_row = None
                    st.session_state.pop("tabla_usuarios_editar", None)
                    st.rerun()

            modal_editar_usuario()

# ======================================================
# TAB: LISTAR
# ======================================================
if "Listar" in tabs:
    with tab_objs[tabs.index("Listar")]:
        r = requests.get(f"{API}/trabajadores/?activos=true", headers=auth_headers(), timeout=10)
        if r.status_code == 200:
            trabajadores = sorted(r.json(), key=lambda t: t["num_orden"])
            st.subheader(f"Listado de trabajadores activos ({len(trabajadores)})")

            if trabajadores:
                df = pd.DataFrame(trabajadores)
                st.dataframe(df[COLUMNAS_LISTADO], width="stretch")
            else:
                st.info("No hay trabajadores registrados")
        else:
            st.error("Error cargando trabajadores")
            st.code(r.text)

# ======================================================
# TAB: TRABAJADORES (alta + edición)
# ======================================================
# Flash message (mostrar toast en el siguiente rerun)
flash = st.session_state.pop("flash_msg", None)
if flash:
    kind = flash.get("kind")
    msg = flash.get("msg", "")
    if kind == "ok":
        st.toast(msg, icon="✅")
    else:
        st.toast(msg, icon="❌")
        st.error(msg)


def modal_error_dni_registrado(mensaje: str):
    @st.dialog("⚠️ Registro no permitido")
    def _modal():
        st.error(mensaje)
        st.markdown("El DNI ingresado ya existe en el sistema.")
        if st.button("Aceptar"):
            for k in ("dni_trab", "nom_trab", "ap_pat", "ap_mat", "rol_trab"):
                st.session_state.pop(k, None)
            st.rerun()
    _modal()

def modal_dni_no_reniec(mensaje: str):
    @st.dialog("⚠️ DNI no válido")
    def _modal():
        st.warning(mensaje)
        st.markdown("El DNI no fue encontrado en RENIEC.")
        if st.button("Aceptar", type="primary"):
            for k in ("dni_trab", "nom_trab", "ap_pat", "ap_mat"):
                st.session_state.pop(k, None)
            st.session_state.reniec_ok = False
            st.session_state.pop("dni_trab", None)
            st.rerun()
    _modal()

if "👤 Trabajadores" in tabs:
    with tab_objs[tabs.index("👤 Trabajadores")]:
        flash_show("👤 Trabajadores")

        st.subheader("Alta de trabajador")

        col_dni, col_nom = st.columns([1, 3])
        with col_dni:
            st.session_state.modo_offline_trab = st.checkbox(
                "Modo offline (sin RENIEC)",
                value=st.session_state.modo_offline_trab,
                help="Actívalo si no hay internet o RENIEC no responde. Te permite registrar manualmente."
            )

            dni = st.text_input("DNI", max_chars=8, key="dni_trab")

            # Si el DNI cambia, resetear estado RENIEC
            if dni != st.session_state.last_dni_consultado:
                st.session_state.reniec_ok = False
                st.session_state.reniec_error = None

            if (not st.session_state.modo_offline_trab) and dni and len(dni) == 8 and dni.isdigit() and not st.session_state.reniec_ok:
                try:
                    with st.spinner("Consultando RENIEC..."):
                        r_reniec = requests.get(f"{API}/reniec/dni/{dni}", timeout=6)

                    # # ✅ AQUÍ MISMO VA EL DEBUG (justo después del GET)
                    # with st.expander("🔎 Debug RENIEC: respuesta /reniec/dni/{dni}", expanded=True):
                    #     st.write("DNI:", dni)
                    #     st.write("HTTP:", r_reniec.status_code)
                    #     st.write("Body (text):")
                    #     st.code(r_reniec.text)

                    #     try:
                    #         st.write("Body (json):")
                    #         st.json(r_reniec.json())
                    #     except Exception:
                    #         st.warning("No se pudo parsear JSON (respuesta no es JSON válido)")

                    # ✅ DESPUÉS SIGUE TU LÓGICA NORMAL
                    if r_reniec.status_code == 200:
                        data = r_reniec.json()
                        st.session_state.nom_trab = data["nombre"]
                        st.session_state.ap_pat = data["apellido_paterno"]
                        st.session_state.ap_mat = data["apellido_materno"]
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
                    timeout=10
                )

                st.write("STATUS:", r.status_code)
                st.code(r.text)

                if r.status_code == 200:
                    data = r.json()
                    flash_set("👤 Trabajadores", "ok",
                    f"Trabajador creado → {nombre} {apellido_paterno} ({data['num_orden']}-{data['cod_letra']})")
                    st.rerun()

                    
                    for k in ("dni_trab", "nom_trab", "ap_pat", "ap_mat", "rol_trab"):
                        st.session_state.pop(k, None)

                    st.session_state.reniec_ok = False
                    st.session_state.reniec_error = None
                    st.session_state.last_dni_consultado = None
                    st.rerun()
                else:
                    flash_set("👤 Trabajadores", "err", f"No se pudo crear trabajador: {r.text}")
                    st.rerun()

                    st.code(r.text)

            st.divider()

        # -------- LISTADO + EDIT --------
        r = requests.get(f"{API}/trabajadores/?activos=true", headers=auth_headers(), timeout=10)
        if r.status_code != 200:
            st.error("Error cargando trabajadores")
            st.code(r.text)
        else:
            trabajadores = sorted(r.json(), key=lambda t: t["num_orden"])
            st.subheader(f"Listado de trabajadores activos ({len(trabajadores)})")

            if not trabajadores:
                st.info("No hay trabajadores registrados")
            else:
                df = pd.DataFrame(trabajadores)

                df_ui = df.copy()
                df_ui["✏️"] = False

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
                    key="tabla_trabajadores_editar"
                )

                # Selección desde data_editor
                seleccionados = edited_df[edited_df["✏️"] == True]

                if len(seleccionados) == 1:
                    fila_idx = seleccionados.index[0]
                    selected_id = trabajadores[fila_idx]["id"]

                    if selected_id:
                        st.session_state.edit_trabajador_id = selected_id
                        st.session_state.show_edit_modal = True
                else:
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
                                key=f"edit_rol_{tr['id']}"
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
                                    "rol": rol_e
                                },
                                timeout=10
                            )
                            if r_upd.status_code == 200:
                                st.session_state.show_edit_modal = False
                                st.session_state.edit_trabajador_id = None
                                st.session_state.pop("tabla_trabajadores_editar", None)
                                st.rerun()
                            else:
                                st.error(r_upd.text)

                        if cancelar:
                            st.session_state.show_edit_modal = False
                            st.session_state.edit_trabajador_id = None
                            st.session_state.pop("tabla_trabajadores_editar", None)
                            st.rerun()

                    modal_editar_trabajador()

# ======================================================
# TAB: IMPRESIÓN
# ======================================================
def generar_vista_previa():
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
                "cantidad": cantidad
            },
            timeout=10
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

if "🖨️ Impresión" in tabs:
    with tab_objs[tabs.index("🖨️ Impresión")]:
        st.subheader("Impresión de etiquetas")

        r = requests.get(f"{API}/trabajadores/?activos=true", headers=auth_headers(),  timeout=10)
        if r.status_code != 200:
            st.error("Error cargando trabajadores")
            st.code(r.text)
        else:
            trabajadores = sorted(r.json(), key=lambda t: t["num_orden"])
            st.metric("👥 Trabajadores activos", len(trabajadores))

            if not trabajadores:
                st.warning("No hay trabajadores registrados")
            else:
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
                else:
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
                    else:
                        fila_idx = seleccionados.index[0]
                        trabajador_sel = filtrados[fila_idx]
                        st.session_state.trabajador_seleccionado = trabajador_sel
                        generar_vista_previa()

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

                    # NO llamar extra a generar_vista_previa aquí; ya se llama por selección/on_change

                    if st.session_state.get("preview_img"):
                        st.image(st.session_state.preview_img, caption="Generated by Agricola del Sur Pisco EIRL")

                    selected_printer = st.session_state.get("selected_printer_name")
                    selected_agent_url = st.session_state.get("selected_printer_agent_url")

                    if selected_printer:
                        st.caption(f"Impresora seleccionada: **{selected_printer}**")
                    else:
                        st.warning("No hay impresora seleccionada. Ve a la pestaña **🖨️ Impresoras** y selecciona una.")

                    btn_label = f"🖨️ Imprimir etiquetas ({selected_printer})" if selected_printer else "🖨️ Imprimir etiquetas"

                    if st.button(btn_label, disabled=not bool(selected_printer)):
                        trabajador_sel = st.session_state.get("trabajador_seleccionado")
                        if not trabajador_sel:
                            st.error("Seleccione un trabajador antes de imprimir.")
                            st.stop()

                        nn_value = trabajador_sel["num_orden"] if st.session_state.opcion_mostrar == "Número de orden" else trabajador_sel["cod_letra"]

                        try:
                            r_print = requests.post(
                                f"{API}/qr/print",
                                json={
                                    "dni": trabajador_sel["dni"],
                                    "nn": nn_value,
                                    "producto": st.session_state.producto,
                                    "cantidad": st.session_state.cantidad,
                                    "printer": selected_printer,
                                    "agent_url": selected_agent_url,
                                },
                                timeout=15
                            )
                        except Exception as e:
                            st.error(f"Error enviando impresión: {e}")
                            st.stop()

                        if r_print.status_code == 200:
                            st.toast("Impresión enviada correctamente 🖨️", icon="✅")
                        else:
                            st.error("Error al imprimir")
                            st.code(r_print.text)

# ======================================================
# TAB: IMPRESORAS
# ======================================================
if "🖨️ Impresoras" in tabs:
    with tab_objs[tabs.index("🖨️ Impresoras")]:
        show_printers_panel()
        st.subheader("Configuración de impresoras")

# ======================================================
# TAB: REPORTES (por lote) - SIN FECHAS
# ======================================================
if "📊 Reportes" in tabs:
    with tab_objs[tabs.index("📊 Reportes")]:
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



# ======================================================
# TAB: LOTES
# ======================================================
if "📦 Lotes" in tabs:
    with tab_objs[tabs.index("📦 Lotes")]:
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

## ======================================================
# TAB: 🛡️ VIGILANCIA
# ======================================================
TAB_VIG = "🛡️ Vigilancia"

def norm_dni(s: str) -> str:
    return "".join([c for c in (s or "") if c.isdigit()])

    # ✅ Reset diferido (antes de instanciar widgets)
if st.session_state.get("vig_reset"):
    st.session_state["vig_dni"] = ""
    st.session_state["vig_nombres"] = ""
    st.session_state["vig_apellido_paterno"] = ""
    st.session_state["vig_apellido_materno"] = ""
    st.session_state["vig_reset"] = False

    st.session_state["vig_preview"] = {
        "dni": "",
        "nombres": "",
        "apellido_paterno": "",
        "apellido_materno": "",
        "found": False,
        "offline": False,
        "detail": ""
    }


if TAB_VIG in tabs:
    with tab_objs[tabs.index(TAB_VIG)]:
        st.subheader("🛡️ Registro de Ingreso / Salida (Vigilancia)")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            dni_in = st.text_input("DNI", key="vig_dni", placeholder="8 dígitos")
        with col2:
            tipo = st.selectbox("Tipo", ["ENTRADA", "SALIDA"], key="vig_tipo")
        with col3:
            fecha = st.date_input("Fecha", key="vig_fecha")

        dni = norm_dni(dni_in)

        # Estado persistente
        if "vig_preview" not in st.session_state:
            st.session_state.vig_preview = {
                "dni": "",
                "nombres": "",
                "apellido Paterno": "",
                "apellido Materno": "",
                "fuente": "",
                "found": False,
                "offline": False,
                "detail": ""
            }

        # ---------- PREVIEW ----------
        # Solo consulta si hay 8 dígitos y cambió el DNI
        if len(dni) == 8 and dni != st.session_state.vig_preview.get("dni"):
            try:
                resp = api_get(f"/vigilancia/persona/?dni={dni}")

                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.vig_preview = data
                    st.session_state["vig_nombres"] = data.get("nombres", "")
                    st.session_state["vig_apellido_paterno"] = data.get("apellido_paterno", "")
                    st.session_state["vig_apellido_materno"] = data.get("apellido_materno", "")
                else:
                    # MUY IMPORTANTE: guardar detalle del error (para depurar)
                    st.session_state.vig_preview = {
                        "dni": dni,
                        "nombres": "",
                        "apellido_paterno": "",
                        "apellido_materno": "",
                        "fuente": f"ERROR_{resp.status_code}",
                        "found": False,
                        "offline": False,
                        "detail": resp.text
                    }
                    st.error(f"Error en /vigilancia/persona/?dni={dni}: {resp.status_code}")
                    st.code(resp.text)

            except Exception as e:
                st.session_state.vig_preview = {
                    "dni": dni,
                    "nombres": "",
                    "apellido_paterno": "",
                    "apellido_materno": "",
                    "fuente": "OFFLINE",
                    "found": False,
                    "offline": True,
                    "detail": str(e)
                }

        prev = st.session_state.vig_preview

        st.markdown("**Datos (antes de registrar)**")

        # Si found=True y no offline => mostrar bloqueado
        lock_fields = bool(prev.get("found")) and not bool(prev.get("offline"))


        cA, cB, cC = st.columns([2, 2, 1])
        with cA:
            nombres_ui = st.text_input("Nombres", key="vig_nombres", disabled=lock_fields)
        with cB:
            ap_pat_ui = st.text_input("Apellido Paterno", key="vig_apellido_paterno", disabled=lock_fields)
        with cC:
            ap_mat_ui = st.text_input("Apellido Materno", key="vig_apellido_materno", disabled=lock_fields)
     #   with cC:
     #       st.text_input("Fuente", value=prev.get("fuente", ""), disabled=True)

        manual_needed = (
            len(dni) == 8 and
            (
                not prev.get("found") or
                prev.get("fuente") in ("OFFLINE", "NO_ENCONTRADO") or
                str(prev.get("fuente", "")).startswith("ERROR_")
            )
        )

        if manual_needed and len(dni) == 8:
            st.info("Complete nombres y apellidos manualmente si no hay conectividad o no existe en PerúDevs.")

        # ---------- REGISTRAR ----------
        if st.button("Registrar", width='stretch', key="vig_btn_registrar"):
            if len(dni) != 8:
                st.error("DNI inválido")
            else:
                payload = {"dni": dni, "tipo": tipo}

                # Si requiere manual, valida y envía nombres/apellidos
                if manual_needed:
                    if not nombres_ui.strip() or not ap_pat_ui.strip() or not ap_mat_ui.strip():
                        st.error("Complete nombres y ambos apellidos para registrar manualmente.")
                        st.stop()

                    payload["nombres"] = nombres_ui.strip()
                    payload["apellido_paterno"] = ap_pat_ui.strip()
                    payload["apellido_materno"] = ap_mat_ui.strip()
                try:
                    resp = api_post("/vigilancia/visita", json=payload)

                    if resp.status_code == 200:
                        r = resp.json()
                        full = " ".join([
                        r.get("nombres", ""),
                        r.get("apellido_paterno", ""),
                        r.get("apellido_materno", ""),
                    ]).strip()

                        st.success(f"{tipo} registrada: {dni} — {full}")

                        # reset UI
                        st.session_state.vig_preview = {
                            "dni": "",
                            "nombres": "",
                            "apellido_paterno": "",
                            "apellido_materno": "",
                            "fuente": "",
                            "found": False,
                            "offline": False,
                            "detail": ""
                        }
                        # ✅ pedir reset y rerun
                        st.session_state["vig_reset"] = True
                        st.rerun()


                    elif resp.status_code == 409:
                        st.warning("Ya existe un registro de ese tipo para hoy.")
                    elif resp.status_code in (404, 503):
                        st.warning("No se pudo obtener datos automáticos. Complete manualmente e intente nuevamente.")
                        st.code(resp.text)
                    else:
                        st.error(f"API {resp.status_code}")
                        st.code(resp.text)

                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()
        st.caption("Registros del día (máx 500)")

        try:
            resp = api_get("/vigilancia/visitas", params={"fecha": str(fecha)})

            if resp.status_code == 200:
                data = resp.json() or {}
                items = data.get("items", []) or []

                if items:
                    df = pd.DataFrame(items)
                    cols = ["tipo", "dni", "nombres", "apellido_paterno", "apellido_materno"]
                    df = df[[c for c in cols if c in df.columns]]
                    st.dataframe(df, width='stretch', hide_index=True)
                else:
                    st.info("Sin registros para esa fecha.")
            else:
                st.error(f"No se pudo cargar registros: API {resp.status_code}")
                st.code(resp.text)

        except Exception as e:
            st.error(f"No se pudo cargar registros: {e}")


