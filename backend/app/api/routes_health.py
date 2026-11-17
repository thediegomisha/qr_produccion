from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import SessionLocal

router = APIRouter()


@router.get("/health", include_in_schema=False)
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "Servicio no disponible")
    return {"status": "ok"}
