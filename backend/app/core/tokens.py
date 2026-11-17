import secrets

def generar_token(prefijo: str) -> str:
    # 96 bits en 16 caracteres: evita el espacio de solo 32 bits anterior.
    return secrets.token_urlsafe(12)
