from fastapi import APIRouter
from sqlalchemy import text
from app.db.base import SessionLocal

router = APIRouter()

@router.get("/")
def list_users():
    with SessionLocal() as db:
        rows = db.execute(
            text(""" SELECT usuario, nombre, rol
                FROM usuarios
                WHERE activo = true
                ORDER BY rol, nombre """)
        ).mappings().all()

        return list(rows)
