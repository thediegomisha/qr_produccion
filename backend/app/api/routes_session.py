from fastapi import APIRouter
from app.core.session import set_usuario

router = APIRouter()

@router.post("/set")
def set_session(data: dict):
    set_usuario(data["usuario"])
    return {"ok": True}
