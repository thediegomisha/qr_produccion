import os
from urllib.parse import quote_plus


DB_USER = os.getenv("DB_USER", "qr_user")
DB_PASS = os.getenv("DB_PASS", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "qr_produccion")

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql+psycopg2://{DB_USER}:{quote_plus(DB_PASS)}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

def _required_secret(name: str) -> str:
    value = os.getenv(name, "")
    if len(value) < 32 or value.startswith("CAMBIA_"):
        raise RuntimeError(f"{name} debe configurarse con un secreto aleatorio de al menos 32 caracteres")
    return value


JWT_SECRET_KEY = _required_secret("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

QR_SIGNING_SECRET = _required_secret("QR_SIGNING_SECRET").encode("utf-8")

# Compatibilidad con código existente
SECRET_KEY = QR_SIGNING_SECRET
# ==============================
# Configuración de impresión
# ==============================
IMPRESORA_ACTIVA = {
    "agent_id": "agent-001",
    "printer": "ZEBRA_1"
}
