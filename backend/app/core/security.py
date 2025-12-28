import hmac, hashlib, base64
from app.config import SECRET_KEY

# 16 bytes = 128 bits (~22 chars en base64url sin '=')
SIG_BYTES = 16

def sign(payload: str) -> str:
    mac = hmac.new(SECRET_KEY, payload.encode("utf-8"), hashlib.sha256).digest()
    mac = mac[:SIG_BYTES]  # <-- truncado
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")
