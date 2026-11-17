from dotenv import load_dotenv
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.db.base import init_db
from app.api import (
    routes_setup,
    routes_users,
    routes_trabajadores,
    routes_qr,
    routes_auth,
    routes_admin,
    routes_impresoras,
    routes_reniec,
    routes_scans,
    routes_reports,
    routes_dashboard,
    routes_lotes,
    routes_vigilancia,
    routes_productos,
    routes_health,
)

app = FastAPI(
    title="QR Producción", root_path="/api",
    docs_url=None, redoc_url=None, openapi_url=None,
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    if not request.url.path.startswith(("/movil", "/updates")):
        response.headers["Cache-Control"] = "no-store"
    return response

init_db()

# El bootstrap se habilita explícitamente solo durante la instalación.
if os.getenv("ENABLE_BOOTSTRAP", "").lower() == "true":
    app.include_router(routes_setup.router)
app.include_router(routes_trabajadores.router, prefix="/trabajadores")
app.include_router(routes_qr.router, prefix="/qr")
app.include_router(routes_users.router, prefix="/usuarios")
app.include_router(routes_auth.router)
app.include_router(routes_admin.router)
app.include_router(routes_impresoras.router)
app.include_router(routes_reniec.router)
app.include_router(routes_scans.router)
app.include_router(routes_reports.router)
app.include_router(routes_dashboard.router)
app.include_router(routes_lotes.router)
app.include_router(routes_vigilancia.router)
app.include_router(routes_productos.router)
app.include_router(routes_health.router)

# Actualizaciones de la APK: /api/updates/qrlector/version.json (LAN y WAN).
# La carpeta es persistente y queda fuera de releases/ para sobrevivir despliegues.
UPDATES_DIR = Path(os.getenv("UPDATES_DIR", "/opt/qr_produccion-web/shared/updates"))
try:
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
if UPDATES_DIR.is_dir():
    app.mount("/updates", StaticFiles(directory=str(UPDATES_DIR)), name="updates")

# PWA para iPhone y Android: /api/movil/
# Se sirve desde el mismo origen que la API, así que no requiere configuración
# adicional de nginx ni del túnel. La cámara de Safari exige HTTPS (URL WAN).
MOBILE_DIR = Path(__file__).resolve().parent / "mobile"
if MOBILE_DIR.is_dir():
    app.mount("/movil", StaticFiles(directory=str(MOBILE_DIR), html=True), name="movil")
