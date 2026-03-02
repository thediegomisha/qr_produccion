import secrets

def generar_token(prefijo: str) -> str:
    return f"{prefijo[:2].upper()}-{secrets.token_hex(4).upper()}"
