"""Imprime secretos NUEVOS; redirigir a un archivo privado, nunca al repositorio."""
import secrets

if __name__ == "__main__":
    for name in ("JWT_SECRET_KEY", "QR_SIGNING_SECRET", "BOOTSTRAP_TOKEN"):
        print(f"{name}={secrets.token_urlsafe(48)}")
