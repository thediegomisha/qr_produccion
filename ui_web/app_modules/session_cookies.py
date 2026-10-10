"""Sesión web: cookies nativas + monitor de inactividad (teclado/mouse).

Reemplaza al CookieManager de extra-streamlit-components:
- Lectura: st.context.cookies (nativo de Streamlit, síncrono y fiable en F5).
- Escritura/borrado: document.cookie en la ventana padre vía st.iframe.
- Inactividad: JS que escucha mouse/teclado y cierra la sesión tras N minutos.
"""
import json

COOKIE_NAME = "qr_refresh_token"
_STORAGE_KEY = "qr_last_activity"
_GUARD_FLAG = "__qrIdleWatch"


def read_refresh_cookie(st_module) -> str | None:
    """Lee la cookie de refresco con el API nativa; None si no existe."""
    try:
        cookies = st_module.context.cookies or {}
        value = cookies.get(COOKIE_NAME)
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:
        return None
    return None


def set_cookie_script(token: str, max_age_days: int | None = None) -> str:
    """JS que escribe la cookie en la ventana padre (sesión o persistente)."""
    parts = json.dumps(COOKIE_NAME) + "=" + json.dumps(token) + "; path=/; SameSite=Lax"
    if max_age_days:
        parts += f"; Max-Age={int(max_age_days) * 86400}"
    return f"<script>window.parent.document.cookie = {json.dumps(parts)};</script>"


def delete_cookie_script() -> str:
    """JS que borra la cookie de refresco en la ventana padre."""
    return (
        f"<script>window.parent.document.cookie = {json.dumps(COOKIE_NAME)}=; "
        "Max-Age=0; path=/; SameSite=Lax;</script>"
    )


def inactivity_logout_script(idle_minutes: int) -> str:
    """Monitor de inactividad: mouse/teclado renuevan el marcador; al superar
    el límite sin actividad se borra la cookie de sesión y se recarga la app
    (lo que muestra el login). El marcador vive en localStorage compartido
    entre pestañas, de modo que la actividad en cualquiera renueva la sesión."""
    idle_ms = int(idle_minutes) * 60 * 1000
    return f"""<script>
(function () {{
  var P = window.parent;
  if (P.{_GUARD_FLAG}) {{ return; }}  // evitar listeners duplicados en cada rerun
  P.{_GUARD_FLAG} = true;
  var IDLE_MS = {idle_ms};
  var KEY = {json.dumps(_STORAGE_KEY)};
  var COOKIE = {json.dumps(COOKIE_NAME)};
  function readLast() {{
    var v = parseInt(P.localStorage.getItem(KEY) || '0', 10);
    return v > 0 ? v : Date.now();
  }}
  if (!P.localStorage.getItem(KEY)) {{
    P.localStorage.setItem(KEY, String(Date.now()));
  }}
  var lastWrite = 0;
  function bump() {{
    var now = Date.now();
    if (now - lastWrite < 10000) {{ return; }}  // renovar como máximo cada 10s
    lastWrite = now;
    try {{ P.localStorage.setItem(KEY, String(now)); }} catch (e) {{}}
  }}
  ['mousemove', 'keydown', 'mousedown', 'touchstart', 'wheel'].forEach(function (ev) {{
    P.document.addEventListener(ev, bump, {{ passive: true }});
  }});
  setInterval(function () {{
    if (Date.now() - readLast() > IDLE_MS) {{
      try {{ P.document.cookie = COOKIE + '=; Max-Age=0; path=/; SameSite=Lax'; }} catch (e) {{}}
      P.location.reload();  // sin cookie -> la app muestra el login
    }}
  }}, 30000);
}})();
</script>"""
