# backend/app/core/session.py

from typing import Optional

# Simulación de sesión en memoria (simple y válida para ahora)
_session = {
    "usuario": None,
    "rol": None,
}

# -----------------------------
# USUARIO
# -----------------------------
def set_usuario(usuario: str):
    _session["usuario"] = usuario

def get_usuario() -> Optional[str]:
    return _session.get("usuario")

# -----------------------------
# ROL
# -----------------------------
def set_rol(rol: str):
    _session["rol"] = rol

def get_rol() -> Optional[str]:
    return _session.get("rol")

# -----------------------------
# LOGOUT (opcional)
# -----------------------------
def clear_session():
    _session["usuario"] = None
    _session["rol"] = None
