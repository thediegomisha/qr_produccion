from collections import OrderedDict
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request

_attempts = OrderedDict()
_lock = Lock()


def auth_rate_limit(request: Request):
    """Límite por proceso; complementar con límite compartido en el proxy."""
    key = request.client.host if request.client else "unknown"
    now = monotonic()
    with _lock:
        start, count = _attempts.get(key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        if count >= 30:
            raise HTTPException(429, "Demasiados intentos", headers={"Retry-After": "60"})
        _attempts[key] = (start, count + 1)
        _attempts.move_to_end(key)
        while len(_attempts) > 10000:
            _attempts.popitem(last=False)
