import json
from app.core.security import sign

def generar_zpl_qr( token: str, dni: str, visible: str, producto: str,):
    
    # --------------------------------------------------
    # Payload QR
    # --------------------------------------------------
    base = f"{token}|{dni}|{visible}|{producto}|1"

    payload = {
        "t": token,
        "dni": dni,
        "id": visible,
        "p": producto,
        "v": 1,
        "sig": sign(base)
    }

    qr_data = json.dumps(payload, separators=(",", ":"))

    # --------------------------------------------------
    # ZPL
    # --------------------------------------------------
    zpl = f"""
        ^XA
        ^PW199
        ^LL199

        ^FO5,2
        ^BQN,2,3
        ^FDHA,{qr_data}^FS

        ^FO55,71
        ^GB70,40,40,W,0^FS

        ^FO68,80
        ^A0N,30,30
        ^FD{visible}^FS

        ^XZ
        """
    return zpl.strip()
