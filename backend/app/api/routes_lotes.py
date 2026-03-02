from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import List, Dict, Any

from app.db.base import SessionLocal
from app.core.auth_dep import get_current_user

router = APIRouter(prefix="/lotes", tags=["lotes"])
# router = APIRouter(prefix="/scans", tags=["scans"])


class EnsureLoteIn(BaseModel):
    codigo: str


def _norm(c: str) -> str:
    return (c or "").strip().upper()


@router.post("/ensure")
def ensure_lote(payload: EnsureLoteIn, user=Depends(get_current_user)):
    codigo = _norm(payload.codigo)
    if not codigo:
        raise HTTPException(400, "Código inválido")

    with SessionLocal() as db:
        r = db.execute(
            text("SELECT id, codigo, estado FROM lotes WHERE codigo = :c"),
            {"c": codigo},
        ).fetchone()

        if r is None:
            r = db.execute(
                text("""
                    INSERT INTO lotes (codigo, estado, creado_por)
                    VALUES (:c, 'ABIERTO', :u)
                    RETURNING id, codigo, estado
                """),
                {"c": codigo, "u": user.get("usuario")},
            ).fetchone()
            db.commit()

    return {"id": r.id, "codigo": r.codigo, "estado": r.estado}


@router.get("")
def list_lotes(limit: int = 50, user=Depends(get_current_user)):
    limit = min(max(limit, 10), 200)

    with SessionLocal() as db:
        rows = db.execute(
            text("""
                SELECT id, codigo, estado, creado_en,
                       cerrado_en, reabierto_en
                FROM lotes
                ORDER BY creado_en DESC
                LIMIT :l
            """),
            {"l": limit},
        ).fetchall()

    return {"items": [dict(r._mapping) for r in rows]}


@router.post("/{codigo}/close")
def close_lote(codigo: str, user=Depends(get_current_user)):
    c = _norm(codigo)

    with SessionLocal() as db:
        r = db.execute(
            text("SELECT id, estado FROM lotes WHERE codigo = :c"),
            {"c": c},
        ).fetchone()

        if r is None:
            raise HTTPException(404, "Lote no existe")

        if r.estado == "CERRADO":
            return {"codigo": c, "estado": "CERRADO"}

        db.execute(
            text("""
                UPDATE lotes
                SET estado = 'CERRADO',
                    cerrado_en = NOW(),
                    cerrado_por = :u
                WHERE id = :id
            """),
            {"id": r.id, "u": user.get("usuario")},
        )
        db.commit()

    return {"codigo": c, "estado": "CERRADO"}


@router.post("/{codigo}/open")
def open_lote(codigo: str, user=Depends(get_current_user)):
    if (user.get("rol") or "").upper() != "ROOT":
        raise HTTPException(403, "Solo ROOT puede reabrir")

    c = _norm(codigo)

    with SessionLocal() as db:
        r = db.execute(
            text("SELECT id, estado FROM lotes WHERE codigo = :c"),
            {"c": c},
        ).fetchone()

        if r is None:
            raise HTTPException(404, "Lote no existe")

        if r.estado == "ABIERTO":
            return {"codigo": c, "estado": "ABIERTO"}

        db.execute(
            text("""
                UPDATE lotes
                SET estado = 'ABIERTO',
                    reabierto_en = NOW(),
                    reabierto_por = :u
                WHERE id = :id
            """),
            {"id": r.id, "u": user.get("usuario")},
        )
        db.commit()

    return {"codigo": c, "estado": "ABIERTO"}
