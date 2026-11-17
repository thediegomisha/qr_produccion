import io
import json

import qrcode
from PIL import ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def compact_payload(token: str, dni: str, visible: str, producto: str) -> dict:
    """Conserva el producto para consultas directas de raw->>'p'."""
    return {"t": str(token), "dni": str(dni), "id": str(visible), "p": str(producto)}


def generar_qr_memoria(token: str, dni: str, numord: str, producto: str):
    data = json.dumps(compact_payload(token, dni, numord, producto), separators=(",", ":"), ensure_ascii=False)
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=4, border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr.box_size = min(4, 200 // (qr.modules_count + 8))
    if qr.box_size < 2:
        raise ValueError("El payload no cabe en la etiqueta")
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    draw = ImageDraw.Draw(img)
    # Mismo recuadro pequeño que en ZPL; sin interpolar los módulos.
    cx, cy = img.width // 2, img.height // 2
    draw.rectangle((cx - 22, cy - 13, cx + 21, cy + 12), fill="white")
    font_size = 20
    while True:
        font = ImageFont.truetype(FONT_PATH, font_size)
        bbox = draw.textbbox((0, 0), str(numord), font=font)
        if bbox[2] - bbox[0] <= 40 or font_size <= 8:
            break
        font_size -= 1
    draw.text((cx, cy), str(numord), font=font, fill="black", anchor="mm")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
