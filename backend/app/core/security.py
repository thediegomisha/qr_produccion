import hmac, hashlib, base64
from app.config import SECRET_KEY

def sign(payload: str) -> str:
    mac = hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")
