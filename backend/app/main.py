from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI
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
    routes_lotes,
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
app.include_router(routes_lotes.router)

