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
    routes_session,
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
)

app = FastAPI(title="QR Producción", root_path="/api")
init_db()

app.include_router(routes_setup.router)
app.include_router(routes_session.router, prefix="/session")
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
