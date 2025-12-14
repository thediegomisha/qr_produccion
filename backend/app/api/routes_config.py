from fastapi import APIRouter, HTTPException
from app.db.base import SessionLocal
from app.db.models import ConfiguracionSistema

router = APIRouter()

@router.get("/")
def get_config():
    with SessionLocal() as db:
        cfg = db.query(ConfiguracionSistema).filter_by(activo=True).first()
        return cfg

@router.post("/")
def save_config(data: dict):
    with SessionLocal() as db:
        db.query(ConfiguracionSistema).update({"activo": False})

        cfg = ConfiguracionSistema(
            empresa=data["empresa"],
            planta=data.get("planta"),
            producto_defecto=data.get("producto_defecto"),

            printer_tipo=data["printer_tipo"],
            printer_nombre=data.get("printer_nombre"),
            printer_ip=data.get("printer_ip"),
            printer_puerto=data.get("printer_puerto"),
            printer_driver=data["printer_driver"],
            activo=True
        )
        db.add(cfg)
        db.commit()
        return {"ok": True}
