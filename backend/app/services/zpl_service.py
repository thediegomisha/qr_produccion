import json
import qrcode
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

        ^FO0,2
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

def _mm_to_dots(mm: float, dpi: int = 203) -> int:
    return int(round(mm * dpi / 25.4))

def _qr_modules_count_H(data: str) -> int:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=1,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.modules_count

def generar_zpl_qr_4cols(
    items,
    dpi: int = 203,
    label_mm: float = 25.0,
    gap_mm: float = 1.0,
    margin_mm: float = 1.0,
    qr_mag: int = 3,   # 👈 empieza con 3 (como tu 1-col)
):
    # Medidas físicas
    label_w = _mm_to_dots(label_mm, dpi)   # ~200
    label_h = _mm_to_dots(label_mm, dpi)   # ~200
    gap = _mm_to_dots(gap_mm, dpi)
    margin = _mm_to_dots(margin_mm, dpi)

    total_w = (label_w * 4) + (gap * 3) + (margin * 2)
    total_h = label_h

    # Tamaños de referencia del recuadro y texto para magnificación 3.
    base_mag = 3
    base_box_w = 90
    base_box_h = 90
    base_font = 30

    zpl = []
    zpl.append("^XA")
    zpl.append("^CI28")
    zpl.append(f"^PW{total_w}")
    zpl.append(f"^LL{total_h}")
    zpl.append("^LH0,0")

    cols = list(items[:4]) + [None] * (4 - len(items))

    for i, it in enumerate(cols):
        x0 = margin + i * (label_w + gap)
        if not it:
            continue

        payload = it.get("payload")
        if payload is None:
            payload = {
                "t": it["token"],
                "dni": it["dni"],
                "id": it["visible"],
                "p": it["producto"],
                "v": 1,
                "sig": it["sig"],
            }

        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

        # 1) Elegir magnificación que NO recorte el QR en 25x25
        modules = _qr_modules_count_H(data)
        # tamaño en módulos incluyendo quiet zone: (modules + 8)
        max_mag = (min(label_w, label_h) - 2 * margin) // (modules + 8)
        mag = min(qr_mag, int(max_mag))
        if mag < 2:
            mag = 2  # mínimo razonable

        # Centrar la matriz; el espacio blanco restante rodea el QR por igual.
        qr_size = modules * mag
        qr_x = x0 + (label_w - qr_size) // 2
        qr_y = (label_h - qr_size) // 2

        # 2) Imprimir QR con ECC H (CRÍTICO)
        zpl.append(f"^FO{qr_x},{qr_y}")
        zpl.append(f"^BQN,2,{mag}")
        zpl.append(f"^FDHA,{data}^FS")   # 👈 HA (H)

        # 3) Escalar tu layout probado según magnificación
        scale = mag / base_mag

        box_w = int(round(base_box_w * scale))
        box_h = int(round(base_box_h * scale))
        font  = int(round(base_font  * scale))

        box_x = qr_x + (qr_size - box_w) // 2
        box_y = qr_y + (qr_size - box_h) // 2

        # clamp (para que no se salga de la celda)
        box_x = max(x0, min(box_x, x0 + label_w - box_w))
        box_y = max(0,  min(box_y,       label_h - box_h))

        # 4) Rectángulo blanco relleno (thickness=box_h)
        zpl.append(f"^FO{box_x},{box_y}")
        zpl.append(f"^GB{box_w},{box_h},{box_h},W,0^FS")

        # 5) Texto centrado dentro del rectángulo
        font = max(18, min(font, box_h - 6))
        text_y = box_y + max(0, (box_h - font) // 2)

        zpl.append(f"^FO{box_x},{text_y}")
        zpl.append(f"^A0N,{font},{font}")
        zpl.append(f"^FB{box_w},1,0,C,0")
        zpl.append(f"^FD{it['visible']}^FS")

    zpl.append("^XZ")
    return "\n".join(zpl)
