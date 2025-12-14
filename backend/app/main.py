from fastapi import FastAPI
from app.db.base import init_db
from app.api import (
    routes_setup,
    routes_users,
    routes_trabajadores,
    routes_qr,
    routes_session
)


app = FastAPI(title="QR Producción")
init_db()

app.include_router(routes_setup.router, prefix="/setup")
app.include_router(routes_session.router, prefix="/session")
app.include_router(routes_trabajadores.router, prefix="/trabajadores")
app.include_router(routes_qr.router, prefix="/qr")
app.include_router(routes_users.router, prefix="/usuarios")

