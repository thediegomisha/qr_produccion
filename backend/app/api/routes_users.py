"""Alias legado: conserva la URL, pero usa las mismas reglas de administración."""
from fastapi import APIRouter

from app.api.routes_admin import crear_usuario

router = APIRouter(prefix="/admin")
router.add_api_route("/usuarios", crear_usuario, methods=["POST"])
