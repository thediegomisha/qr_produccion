from fastapi import APIRouter
from sqlalchemy import text
from app.db.base import SessionLocal

router = APIRouter()

@router.get("/status")
def status():
    with SessionLocal() as db:
        count = db.execute(text("SELECT COUNT(*) FROM usuarios")).scalar_one()
        return {
            "initialized": count > 0,
            "users_count": int(count)
        }

@router.post("/init-supervisor")
def init_supervisor(data: dict):
    usuario = (data.get("usuario") or "").strip()
    nombre = (data.get("nombre") or "").strip()

    if not usuario:
        return {"error": "usuario es obligatorio"}
    if not nombre:
        return {"error": "nombre es obligatorio"}

    with SessionLocal() as db:
        count = db.execute(text("SELECT COUNT(*) FROM usuarios")).scalar_one()
        if count > 0:
            return {"error": "Sistema ya inicializado"}

        db.execute(
            text("""
                INSERT INTO usuarios (usuario, nombre, rol, activo)
                VALUES (:u, :n, 'SUPERVISOR', true)
            """),
            {"u": usuario, "n": nombre}
        )
        db.commit()

    return {"ok": True}
