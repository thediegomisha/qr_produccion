import io
import json
import os
from functools import lru_cache

import qrcode
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = os.getenv(
    "QR_FONT_PATH", "/opt/qr_produccion-web/shared/fonts/arialbd.ttf"
)
CENTER_BOX_WIDTH = 48
CENTER_BOX_HEIGHT = 30
CENTER_FONT_SIZE = 24


@lru_cache(maxsize=8)
def _center_font(path: str, size: int):
    """La fuente se instala fuera de releases y nunca se sustituye silenciosamente."""
    return ImageFont.truetype(path, size)


def render_center_label(visible: str):
    """Panel monocromo común para PNG y ZPL: Arial Bold a 24 puntos."""
    panel = Image.new("L", (CENTER_BOX_WIDTH, CENTER_BOX_HEIGHT), color=255)
    text = str(visible)
    if text:
        font = _center_font(FONT_PATH, CENTER_FONT_SIZE)
        left, top, right, bottom = font.getbbox(text)
        lettering = Image.new("L", (max(1, right - left), max(1, bottom - top)), color=255)
        ImageDraw.Draw(lettering).text((-left, -top), text, font=font, fill=0)
        # Mantener altura de fuente; condensar solo textos anchos como WWW.
        if lettering.width > CENTER_BOX_WIDTH - 4:
            lettering = lettering.resize(
                (CENTER_BOX_WIDTH - 4, lettering.height), Image.Resampling.LANCZOS
            )
        if lettering.height > CENTER_BOX_HEIGHT - 4:
            raise ValueError("El texto central supera la altura del recuadro")
        panel.paste(lettering, (
            (CENTER_BOX_WIDTH - lettering.width) // 2,
            (CENTER_BOX_HEIGHT - lettering.height) // 2,
        ))
    # Sin tramado: contornos negros nítidos para impresión térmica.
    return panel.convert("1", dither=Image.Dither.NONE)


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
    # Usar exactamente el mismo bitmap que se envía a la impresora.
    img.paste(render_center_label(numord).convert("RGB"), (
        (img.width - CENTER_BOX_WIDTH) // 2,
        (img.height - CENTER_BOX_HEIGHT) // 2,
    ))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
