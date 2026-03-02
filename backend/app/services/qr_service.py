import io
import json
import qrcode
from PIL import Image, ImageDraw, ImageFont
from app.core.security import sign

# Fuente robusta disponible en Linux
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def generar_qr_memoria(token: str, dni: str, numord: str, producto: str):
    """
    Genera un QR en memoria con:
    - Payload firmado
    - Número de orden (numord) visible en el centro
    - Cuadro blanco centrado
    - Texto perfectamente centrado dentro del cuadro
    """

    # ------------------------------------------------------------------
    # 1) Construcción del payload + firma
    # ------------------------------------------------------------------
    base = f"{token}|{dni}|{numord}|{producto}|1"

    payload = {
        "t": token,
        "dni": dni,
        "id": numord,      # número de orden visual (3 dígitos)
        "p": producto,
        "v": 1,
        "sig": sign(base)
    }

    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    # ------------------------------------------------------------------
    # 2) Generación del QR (alta tolerancia para overlay central)
    # ------------------------------------------------------------------
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # margen alto
        box_size=10,
        border=4
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # ------------------------------------------------------------------
    # 3) Preparación para dibujo
    # ------------------------------------------------------------------
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Centro geométrico exacto del QR
    cx, cy = w // 2, h // 2

    # Fuente proporcional al tamaño del QR
    font_size = int(w * 0.18)  # 18% del ancho total
    font = ImageFont.truetype(FONT_PATH, font_size)

    # ------------------------------------------------------------------
    # 4) Medición correcta del texto (centrado real)
    # ------------------------------------------------------------------
    # IMPORTANTE: usar anchor="mm" para medición y dibujo coherentes
    bbox = draw.textbbox((0, 0), numord, font=font, anchor="mm")
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Padding del cuadro blanco
    padding = int(font_size * 0.20)

    # ------------------------------------------------------------------
    # 5) Cuadro blanco perfectamente centrado
    # ------------------------------------------------------------------
    draw.rectangle(
        [
            cx - (text_width // 2) - padding,
            cy - (text_height // 2) - padding,
            cx + (text_width // 2) + padding,
            cy + (text_height // 2) + padding,
        ],
        fill="white"
    )

    # ------------------------------------------------------------------
    # 6) Texto perfectamente centrado dentro del cuadro
    # ------------------------------------------------------------------
    draw.text(
        (cx, cy),
        numord,
        fill="black",
        font=font,
        anchor="mm"   # 🔑 CLAVE ABSOLUTA DEL CENTRADO CORRECTO
    )

    # ------------------------------------------------------------------
    # 7) REDUCCIÓN DE TAMAÑO (20% menos, sin alterar contenido)
    # ------------------------------------------------------------------
    scale = 0.4  # 🔹 reducir 60%

    new_w = int(img.width * scale)
    new_h = int(img.height * scale)

    img = img.resize(
        (new_w, new_h),
        resample=Image.Resampling.LANCZOS  
    )

    # ------------------------------------------------------------------
    # 8) Retorno del QR en memoria
    # ------------------------------------------------------------------
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer

