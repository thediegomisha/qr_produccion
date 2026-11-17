import io
import json

import qrcode
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CENTER_BOX_WIDTH = 48
CENTER_BOX_HEIGHT = 30
CENTER_FONT_SIZE = 22


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
    # Mismas medidas centrales que ZPL; no interpolar los módulos del QR.
    cx, cy = img.width // 2, img.height // 2
    x, y = cx - CENTER_BOX_WIDTH // 2, cy - CENTER_BOX_HEIGHT // 2
    draw.rectangle(
        (x, y, x + CENTER_BOX_WIDTH - 1, y + CENTER_BOX_HEIGHT - 1), fill="white"
    )
    text = str(numord)
    if text:
        font = ImageFont.truetype(FONT_PATH, CENTER_FONT_SIZE)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        lettering = Image.new("RGBA", (max(1, right - left), max(1, bottom - top)))
        ImageDraw.Draw(lettering).text((-left, -top), text, font=font, fill="black")
        # Condensar solo el ancho del texto para mantener la altura de 22.
        if lettering.width > CENTER_BOX_WIDTH - 4:
            lettering = lettering.resize(
                (CENTER_BOX_WIDTH - 4, lettering.height), Image.Resampling.LANCZOS
            )
        img.paste(
            lettering,
            (cx - lettering.width // 2, cy - lettering.height // 2),
            lettering,
        )
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
