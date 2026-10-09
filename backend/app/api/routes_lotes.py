from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.core.auth_dep import get_current_user
from app.db.base import SessionLocal
from app.db.models import Lote, ScanEvent

router = APIRouter(prefix="/lotes", tags=["lotes"])


def _norm(codigo: str) -> str:
    return codigo.strip().upper()


class EnsureLoteIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=64)

    @field_validator("codigo", mode="before")
    @classmethod
    def normalize_codigo(cls, value):
        if not isinstance(value, str):
            return value
        value = _norm(value)
        if any(ord(char) < 32 or ord(char) == 127 or char in "/\\" for char in value):
            raise ValueError("El código no admite barras ni caracteres de control")
        return value


class UpdateLoteIn(EnsureLoteIn):
    estado: Literal["ABIERTO", "CERRADO"]


class BulkDeleteIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


def _require_role(user: dict, *roles: str):
    if (user.get("rol") or "").upper() not in roles:
        raise HTTPException(403, "No tienes permisos para esta operación de lotes")


def _serialize(lote: Lote, total_lecturas: int = 0) -> dict:
    return {
        "id": lote.id,
        "codigo": lote.codigo,
        "estado": lote.estado,
        "creado_por": lote.creado_por,
        "creado_en": lote.creado_en,
        "cerrado_por": lote.cerrado_por,
        "cerrado_en": lote.cerrado_en,
        "reabierto_por": lote.reabierto_por,
        "reabierto_en": lote.reabierto_en,
        "total_lecturas": total_lecturas,
    }


def _by_id(db, lote_id: int, *, lock: bool = False) -> Lote:
    query = db.query(Lote).filter(Lote.id == lote_id)
    if lock:
        query = query.with_for_update()
    lote = query.first()
    if lote is None:
        raise HTTPException(404, "Lote no existe")
    return lote


def _set_estado(lote: Lote, estado: str, user: dict):
    if lote.estado == estado:
        return
    if estado == "ABIERTO":
        _require_role(user, "ROOT")
        lote.reabierto_en = datetime.utcnow()
        lote.reabierto_por = user.get("usuario")
    else:
        lote.cerrado_en = datetime.utcnow()
        lote.cerrado_por = user.get("usuario")
    lote.estado = estado


@router.post("/ensure")
def ensure_lote(payload: EnsureLoteIn, user=Depends(get_current_user)):
    # Preserve the idempotent endpoint used by existing Android clients.
    with SessionLocal() as db:
        lote = db.query(Lote).filter(Lote.codigo == payload.codigo).first()
        if lote is None:
            lote = Lote(codigo=payload.codigo, estado="ABIERTO", creado_por=user.get("usuario"))
            db.add(lote)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                # Another request may have ensured the same code concurrently.
                lote = db.query(Lote).filter(Lote.codigo == payload.codigo).first()
                if lote is None:
                    raise HTTPException(409, "No se pudo crear el lote")
        count = db.query(ScanEvent).filter(ScanEvent.lote_id == lote.id).count()
        return _serialize(lote, count)


@router.post("", status_code=201)
def create_lote(payload: EnsureLoteIn, user=Depends(get_current_user)):
    _require_role(user, "ROOT", "GERENCIA", "SUPERVISOR")
    with SessionLocal() as db:
        lote = Lote(codigo=payload.codigo, estado="ABIERTO", creado_por=user.get("usuario"))
        db.add(lote)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Ya existe un lote con ese código")
        return _serialize(lote)


@router.get("")
def list_lotes(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str = Query("", max_length=64),
    estado: Literal["ABIERTO", "CERRADO"] | None = None,
    user=Depends(get_current_user),
):
    with SessionLocal() as db:
        filters = []
        if q.strip():
            escaped = _norm(q).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(Lote.codigo.ilike(f"%{escaped}%", escape="\\"))
        if estado is not None:
            filters.append(Lote.estado == estado)
        total = db.query(Lote).filter(*filters).count()
        rows = (
            db.query(Lote, func.count(ScanEvent.token))
            .outerjoin(ScanEvent, ScanEvent.lote_id == Lote.id)
            .filter(*filters)
            .group_by(Lote.id)
            .order_by(Lote.creado_en.desc().nullslast(), Lote.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "items": [_serialize(lote, count) for lote, count in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get("/{lote_id}")
def get_lote(lote_id: int, user=Depends(get_current_user)):
    with SessionLocal() as db:
        lote = _by_id(db, lote_id)
        count = db.query(ScanEvent).filter(ScanEvent.lote_id == lote.id).count()
        return _serialize(lote, count)


@router.put("/{lote_id}")
def update_lote(lote_id: int, payload: UpdateLoteIn, user=Depends(get_current_user)):
    _require_role(user, "ROOT", "GERENCIA")
    with SessionLocal() as db:
        lote = _by_id(db, lote_id, lock=True)
        _set_estado(lote, payload.estado, user)
        lote.codigo = payload.codigo
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Ya existe un lote con ese código")
        count = db.query(ScanEvent).filter(ScanEvent.lote_id == lote.id).count()
        return _serialize(lote, count)


@router.post("/bulk-delete")
def bulk_delete_lotes(payload: BulkDeleteIn, user=Depends(get_current_user)):
    _require_role(user, "ROOT")
    ids = sorted(set(payload.ids))

    with SessionLocal() as db:
        lotes = (
            db.query(Lote)
            .filter(Lote.id.in_(ids))
            .with_for_update()
            .order_by(Lote.id)
            .all()
        )
        found = {lote.id for lote in lotes}
        missing = [i for i in ids if i not in found]
        if missing:
            raise HTTPException(404, f"Lotes no encontrados: {missing}")

        deleted_scans = db.query(ScanEvent).filter(ScanEvent.lote_id.in_(ids)).delete(
            synchronize_session=False
        )
        summary = [{"id": lote.id, "codigo": lote.codigo} for lote in lotes]
        try:
            for lote in lotes:
                db.delete(lote)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Hay lotes con otras referencias y no se pudieron eliminar")

    return {"ok": True, "deleted_lotes": len(lotes), "deleted_scans": deleted_scans, "items": summary}


@router.delete("/{lote_id}")
def delete_lote(lote_id: int, user=Depends(get_current_user)):
    _require_role(user, "ROOT", "GERENCIA")
    with SessionLocal() as db:
        lote = _by_id(db, lote_id, lock=True)
        codigo = lote.codigo
        try:
            deleted_scans = db.query(ScanEvent).filter(ScanEvent.lote_id == lote.id).delete(
                synchronize_session=False
            )
            db.delete(lote)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "El lote tiene otras referencias y no se pudo eliminar")
        return {"ok": True, "id": lote_id, "codigo": codigo, "deleted_scans": deleted_scans}


@router.post("/{codigo}/close")
def close_lote(codigo: str, user=Depends(get_current_user)):
    _require_role(user, "ROOT", "GERENCIA", "SUPERVISOR")
    with SessionLocal() as db:
        lote = db.query(Lote).filter(Lote.codigo == _norm(codigo)).with_for_update().first()
        if lote is None:
            raise HTTPException(404, "Lote no existe")
        _set_estado(lote, "CERRADO", user)
        db.commit()
        return {"codigo": lote.codigo, "estado": lote.estado}


@router.post("/{codigo}/open")
def open_lote(codigo: str, user=Depends(get_current_user)):
    _require_role(user, "ROOT")
    with SessionLocal() as db:
        lote = db.query(Lote).filter(Lote.codigo == _norm(codigo)).with_for_update().first()
        if lote is None:
            raise HTTPException(404, "Lote no existe")
        _set_estado(lote, "ABIERTO", user)
        db.commit()
        return {"codigo": lote.codigo, "estado": lote.estado}
