import json
import qrcode
from PIL import Image, ImageChops
from app.services.qr_service import (
    compact_payload, render_center_label, CENTER_BOX_WIDTH, CENTER_BOX_HEIGHT,
)


def _center_graphic_zpl(visible: str) -> str:
    """Texto rasterizado: no depende de fuentes instaladas en la impresora."""
    panel = render_center_label(visible)
    # PIL: 1=blanco. ZPL: bit 1=negro. El padding de fila debe quedar a cero.
    ink = ImageChops.invert(panel.convert("L")).convert("1", dither=Image.Dither.NONE)
    packed = ink.tobytes()
    row_bytes = (panel.width + 7) // 8
    return f"^GFA,{len(packed)},{len(packed)},{row_bytes},{packed.hex().upper()}^FS"


def generar_zpl_qr(token: str, dni: str, visible: str, producto: str):
    data = json.dumps(compact_payload(token, dni, visible, producto), separators=(",", ":"))
    modules = _qr_modules_count_H(data)
    mag = min(4, 199 // (modules + 8))
    if mag < 2:
        raise ValueError("El payload no cabe en la etiqueta")
    origin = (199 - modules * mag) // 2
    box_x = (199 - CENTER_BOX_WIDTH) // 2
    box_y = (199 - CENTER_BOX_HEIGHT) // 2
    return "\n".join([
        "^XA", "^PW199", "^LL199",
        f"^FO{origin},{origin}", f"^BQN,2,{mag}", f"^FDHA,{data}^FS",
        f"^FO{box_x},{box_y}",
        f"^GB{CENTER_BOX_WIDTH},{CENTER_BOX_HEIGHT},{CENTER_BOX_HEIGHT},W,0^FS",
        f"^FO{box_x},{box_y}", _center_graphic_zpl(visible),
        "^XZ",
    ])

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
    qr_mag: int = 4,
):
    # Medidas físicas
    label_w = _mm_to_dots(label_mm, dpi)   # ~200
    label_h = _mm_to_dots(label_mm, dpi)   # ~200
    gap = _mm_to_dots(gap_mm, dpi)
    margin = _mm_to_dots(margin_mm, dpi)

    total_w = (label_w * 4) + (gap * 3) + (margin * 2)
    total_h = label_h

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
            payload = compact_payload(it["token"], it["dni"], it["visible"], it["producto"])

        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

        # 1) Elegir magnificación que NO recorte el QR en 25x25
        modules = _qr_modules_count_H(data)
        # tamaño en módulos incluyendo quiet zone: (modules + 8)
        max_mag = min(label_w, label_h) // (modules + 8)
        mag = min(qr_mag, int(max_mag))
        if mag < 2:
            raise ValueError("El payload no cabe con zona de silencio en la etiqueta")

        # Centrar la matriz; el espacio blanco restante rodea el QR por igual.
        qr_size = modules * mag
        qr_x = x0 + (label_w - qr_size) // 2
        qr_y = (label_h - qr_size) // 2

        # 2) Imprimir QR con ECC H (CRÍTICO)
        zpl.append(f"^FO{qr_x},{qr_y}")
        zpl.append(f"^BQN,2,{mag}")
        zpl.append(f"^FDHA,{data}^FS")   # 👈 HA (H)

        # Recuadro fijo: no crece al aumentar el tamaño de los módulos.
        box_w = CENTER_BOX_WIDTH
        box_h = CENTER_BOX_HEIGHT

        box_x = qr_x + (qr_size - box_w) // 2
        box_y = qr_y + (qr_size - box_h) // 2

        # clamp (para que no se salga de la celda)
        box_x = max(x0, min(box_x, x0 + label_w - box_w))
        box_y = max(0,  min(box_y,       label_h - box_h))

        # 4) Rectángulo blanco relleno (thickness=box_h)
        zpl.append(f"^FO{box_x},{box_y}")
        zpl.append(f"^GB{box_w},{box_h},{box_h},W,0^FS")

        # 5) Arial Bold real rasterizada, idéntica a la vista previa.
        zpl.append(f"^FO{box_x},{box_y}")
        zpl.append(_center_graphic_zpl(it["visible"]))

    zpl.append("^XZ")
    return "\n".join(zpl)
