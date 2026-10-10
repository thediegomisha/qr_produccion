import bcrypt

# bcrypt limita las contraseñas a 72 bytes; passlib truncaba silenciosamente,
# así que mantenemos ese comportamiento para no romper contraseñas existentes.
_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return (password or "").encode("utf-8")[:_MAX_BYTES]


def hash_password(password: str) -> str:
    """Genera un hash bcrypt estándar ($2b$...), compatible con los hashes
    creados anteriormente por passlib."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verifica la contraseña contra el hash almacenado; nunca lanza excepción."""
    try:
        return bcrypt.checkpw(_prepare(password), (hashed or "").encode("utf-8"))
    except ValueError:
        return False
