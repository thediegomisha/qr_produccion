from printers_panel import show_printers_panel, bootstrap_printer_selection
import streamlit as st
import base64
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
import requests
import extra_streamlit_components as stx
from app_modules.modules import (
    apply_login_theme,
    label_for_section,
    apply_main_theme,
    render_sections,
    render_user_sidebar,
    sections_for_role,
    title_for_section,
)


# --------------------------------------------------
# CONFIG APP
# --------------------------------------------------
st.set_page_config(
    page_title="Sistema de Etiquetas",
    page_icon="logoappqr.png",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent.parent  # carpeta ui_web/
ASSETS_DIR = BASE_DIR / "assets"

API = os.getenv("API_URL", "http://127.0.0.1:8000/api")
APP_VERSION = os.getenv("APP_VERSION", "v1.0.0")
REMEMBER_LOGIN = os.getenv("REMEMBER_LOGIN", "1").strip().lower() not in ("0", "false", "no")
REMEMBER_LOGIN_PERSISTENT = os.getenv("REMEMBER_LOGIN_PERSISTENT", "0").strip().lower() in ("1", "true", "yes")
REFRESH_COOKIE_NAME = "qr_refresh_token"
REFRESH_COOKIE_DAYS = int(os.getenv("REFRESH_COOKIE_DAYS", "7"))
COOKIE_MANAGER = stx.CookieManager(key="auth_cookie_manager")
AUTH_RESTORE_TRIES_KEY = "_auth_restore_tries"
REFRESH_FALLBACK_FILE = Path.home() / ".streamlit" / "qr_refresh_token.txt"
REFRESH_FALLBACK_ENABLED = os.getenv("REFRESH_FALLBACK_ENABLED", "0").strip().lower() in ("1", "true", "yes")
FORCE_LOGOUT_KEY = "_force_logout"
FORCE_LOGOUT_FILE = Path.home() / ".streamlit" / "qr_force_logout.flag"

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


def api_delete(path: str):
    base = globals().get("API") or st.session_state.get("API")
    if not base:
        raise RuntimeError("Falta API")
    url = base.rstrip("/") + path
    return requests.delete(url, headers=auth_headers(), timeout=30)


def _get_refresh_cookie() -> str | None:
    cookies = COOKIE_MANAGER.get_all()
    if not cookies or not isinstance(cookies, dict):
        return None

    value = cookies.get(REFRESH_COOKIE_NAME)
    if not value:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _set_refresh_cookie(token: str) -> None:
    if REMEMBER_LOGIN_PERSISTENT:
        COOKIE_MANAGER.set(
            REFRESH_COOKIE_NAME,
            token,
            path="/",
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_COOKIE_DAYS),
            same_site="lax",
        )
    else:
        COOKIE_MANAGER.set(
            REFRESH_COOKIE_NAME,
            token,
            path="/",
            same_site="lax",
        )


def _clear_refresh_cookie() -> None:
    try:
        COOKIE_MANAGER.delete(REFRESH_COOKIE_NAME)
    except Exception:
        pass

    # Refuerzo: algunos navegadores/componentes mantienen la cookie
    # hasta el siguiente ciclo; max_age=0 fuerza expiración inmediata.
    try:
        COOKIE_MANAGER.set(
            REFRESH_COOKIE_NAME,
            "",
            path="/",
            max_age=0,
            same_site="lax",
        )
    except Exception:
        pass


def _load_refresh_token_from_disk() -> str | None:
    try:
        if not REFRESH_FALLBACK_FILE.exists():
            return None
        token = REFRESH_FALLBACK_FILE.read_text(encoding="utf-8").strip()
        return token or None
    except Exception:
        return None


def _save_refresh_token_to_disk(token: str) -> None:
    try:
        REFRESH_FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        REFRESH_FALLBACK_FILE.write_text(token, encoding="utf-8")
    except Exception:
        pass


def _clear_refresh_token_from_disk() -> None:
    try:
        if REFRESH_FALLBACK_FILE.exists():
            REFRESH_FALLBACK_FILE.unlink()
    except Exception:
        pass


def _set_force_logout_file(enabled: bool) -> None:
    try:
        FORCE_LOGOUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        if enabled:
            FORCE_LOGOUT_FILE.write_text("1", encoding="utf-8")
        elif FORCE_LOGOUT_FILE.exists():
            FORCE_LOGOUT_FILE.unlink()
    except Exception:
        pass


def _is_force_logout_active() -> bool:
    if st.session_state.get(FORCE_LOGOUT_KEY):
        return True
    try:
        return FORCE_LOGOUT_FILE.exists()
    except Exception:
        return False


def try_restore_auth_from_refresh_cookie() -> None:
    if not REMEMBER_LOGIN:
        return
    if _is_force_logout_active():
        return

    if st.session_state.get("auth"):
        st.session_state[AUTH_RESTORE_TRIES_KEY] = 0
        return

    if AUTH_RESTORE_TRIES_KEY not in st.session_state:
        st.session_state[AUTH_RESTORE_TRIES_KEY] = 0

    refresh_token = _get_refresh_cookie()
    if not refresh_token and REFRESH_FALLBACK_ENABLED:
        refresh_token = _load_refresh_token_from_disk()
    if not refresh_token:
        if st.session_state[AUTH_RESTORE_TRIES_KEY] < 2:
            st.session_state[AUTH_RESTORE_TRIES_KEY] += 1
            st.rerun()
        return

    try:
        r = requests.post(
            f"{API}/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=8,
        )
    except requests.RequestException:
        return

    if r.status_code != 200:
        _clear_refresh_cookie()
        _clear_refresh_token_from_disk()
        return

    data = r.json() or {}
    st.session_state.auth = data
    st.session_state[AUTH_RESTORE_TRIES_KEY] = 0
    st.session_state[FORCE_LOGOUT_KEY] = False
    _set_force_logout_file(False)
    new_refresh = (data.get("refresh_token") or "").strip()
    if new_refresh:
        _set_refresh_cookie(new_refresh)
        if REFRESH_FALLBACK_ENABLED:
            _save_refresh_token_to_disk(new_refresh)


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
resp = None
try:
    resp = requests.get(f"{API}/setup/status", timeout=10)
except requests.RequestException as e:
    st.title("Conexión con backend no disponible")
    st.error(f"No se pudo conectar a {API}: {e}")
    st.info("Verifique que el backend esté levantado y que API_URL apunte al host correcto.")
    st.stop()

if resp is not None and resp.status_code == 200 and not resp.json().get("initialized"):
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

if not REMEMBER_LOGIN:
    _clear_refresh_cookie()
    _clear_refresh_token_from_disk()
else:
    try_restore_auth_from_refresh_cookie()

# --------------------------------------------------
# LOGIN
# --------------------------------------------------
if not st.session_state.auth:
    apply_login_theme()

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

            with st.form("login_form", clear_on_submit=True):
                usuario_login = st.text_input("Usuario", key="login_username")
                password_login = st.text_input("Contraseña", type="password", key="login_password")
                submit = st.form_submit_button("Ingresar")

            if submit:
                if not (usuario_login or "").strip() or not (password_login or "").strip():
                    st.error("Ingrese usuario y contraseña.")
                    st.stop()

                r = requests.post(
                    f"{API}/auth/login",
                    json={"usuario": usuario_login, "password": password_login},
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json() or {}
                    st.session_state.auth = data
                    st.session_state[AUTH_RESTORE_TRIES_KEY] = 0
                    st.session_state[FORCE_LOGOUT_KEY] = False
                    _set_force_logout_file(False)
                    if REMEMBER_LOGIN:
                        refresh_token = (data.get("refresh_token") or "").strip()
                        if refresh_token:
                            _set_refresh_cookie(refresh_token)
                            if REFRESH_FALLBACK_ENABLED:
                                _save_refresh_token_to_disk(refresh_token)
                    st.session_state.pop("login_password", None)
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

# --------------------------------------------------
# TABS POR ROL
# --------------------------------------------------
section_ids = sections_for_role(rol)
apply_main_theme()
selected_tab, logout_clicked = render_user_sidebar(
    usuario,
    rol,
    section_ids,
    label_for_section,
    APP_VERSION,
)
if selected_tab not in section_ids and section_ids:
    selected_tab = section_ids[0]
if logout_clicked:
    st.session_state.auth = None
    st.session_state[AUTH_RESTORE_TRIES_KEY] = 0
    st.session_state[FORCE_LOGOUT_KEY] = True
    _set_force_logout_file(True)
    st.session_state.pop("login_username", None)
    st.session_state.pop("login_password", None)
    _clear_refresh_cookie()
    _clear_refresh_token_from_disk()
    st.rerun()

st.markdown(f"### {title_for_section(selected_tab)}")

render_sections(
    st=st,
    tabs=section_ids,
    selected_tab=selected_tab,
    rol=rol,
    API=API,
    auth_headers=auth_headers,
    api_get=api_get,
    api_post=api_post,
    api_put=api_put,
    api_delete=api_delete,
    flash_show=flash_show,
    flash_set=flash_set,
    get_jwt=get_jwt,
    show_printers_panel=show_printers_panel,
    COLUMNAS_LISTADO=COLUMNAS_LISTADO,
    COLUMNAS_IMPRESION=COLUMNAS_IMPRESION,
)
