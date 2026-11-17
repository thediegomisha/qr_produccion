import re
import json

import pytest
import qrcode
from PIL import Image, ImageChops

from app.services import zpl_service, qr_service
from app.services.qr_service import compact_payload, generar_qr_memoria, render_center_label


@pytest.mark.parametrize("modules", [41, 57, 73])
def test_four_column_qrs_and_number_boxes_are_centered(monkeypatch, modules):
    monkeypatch.setattr(zpl_service, "_qr_modules_count_H", lambda data: modules)
    items = [{"payload": {"id": str(i)}, "visible": str(i)} for i in range(4)]
    zpl = zpl_service.generar_zpl_qr_4cols(items, qr_mag=4)
    qrs = re.findall(r"\^FO(\d+),(\d+)\n\^BQN,2,(\d+)", zpl)
    boxes = re.findall(r"\^FO(\d+),(\d+)\n\^GB(\d+),(\d+),", zpl)
    assert len(qrs) == len(boxes) == 4
    for column, (qr, box) in enumerate(zip(qrs, boxes)):
        x, y, mag = map(int, qr)
        bx, by, bw, bh = map(int, box)
        x0 = 8 + column * 208
        size = modules * mag
        assert abs((x - x0) - (200 - (x - x0) - size)) <= 1
        assert abs(y - (200 - y - size)) <= 1
        assert abs((bx - x) - (size - (bx - x) - bw)) <= 1
        assert abs((by - y) - (size - (by - y) - bh)) <= 1
        assert x >= x0 and x + size <= x0 + 200
        assert y >= 0 and y + size <= 200


@pytest.mark.parametrize("visible", ["7", "007", "ABC", "WWW"])
def test_center_text_bitmap_matches_preview_in_both_zpl_formats(visible):
    single = zpl_service.generar_zpl_qr("AbCdEf0123_-XY89", "12345678", visible, "UVA")
    four = zpl_service.generar_zpl_qr_4cols([
        {"token": "AbCdEf0123_-XY89", "dni": "12345678", "visible": visible, "producto": "UVA"}
    ])
    for zpl in (single, four):
        assert "^GB48,30,30,W,0" in zpl
        match = re.search(r"\^GFA,(\d+),(\d+),(\d+),([0-9A-F]+)\^FS", zpl)
        assert match is not None
        assert tuple(map(int, match.groups()[:3])) == (180, 180, 6)
        packed = bytes.fromhex(match[4])
        assert len(packed) == 180
        # ZPL usa 1=negro: invertir al reconstruir para comparar con Pillow.
        ink = Image.frombytes("1", (48, 30), packed)
        panel = ImageChops.invert(ink.convert("L")).convert("1")
        assert panel.tobytes() == render_center_label(visible).tobytes()
        preview = Image.open(generar_qr_memoria("AbCdEf0123_-XY89", "12345678", visible, "UVA"))
        x, y = (preview.width - 48) // 2, (preview.height - 30) // 2
        assert preview.crop((x, y, x + 48, y + 30)).convert("1").tobytes() == panel.tobytes()
        assert "^A0N" not in zpl
    assert "^PW199" in single and "^LL199" in single
    assert "^PW840" in four and "^LL200" in four


@pytest.mark.parametrize("visible", ["007", "ABC", "WWW"])
def test_preview_only_changes_pixels_inside_center_rectangle(visible):
    data = json.dumps(
        compact_payload("AbCdEf0123_-XY89", "12345678", visible, "UVA"),
        separators=(",", ":"),
    )
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=4, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    qr.box_size = min(4, 200 // (qr.modules_count + 8))
    plain = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    preview = Image.open(generar_qr_memoria("AbCdEf0123_-XY89", "12345678", visible, "UVA")).convert("RGB")
    assert preview.size == plain.size
    bbox = ImageChops.difference(plain, preview).getbbox()
    x, y = preview.width // 2 - 24, preview.height // 2 - 15
    assert bbox is not None
    assert x <= bbox[0] < bbox[2] <= x + 48
    assert y <= bbox[1] < bbox[3] <= y + 30
    text_bbox = ImageChops.invert(preview.crop((x, y, x + 48, y + 30))).getbbox()
    assert text_bbox is not None
    assert 2 <= text_bbox[0] and text_bbox[2] <= 46
    assert 2 <= text_bbox[1] and text_bbox[3] <= 28


def test_center_font_uses_24_points_without_reducing_its_height(monkeypatch):
    sizes = []
    original = qr_service._center_font
    def capture(path, size):
        sizes.append(size)
        return original(path, size)
    monkeypatch.setattr(qr_service, "_center_font", capture)
    render_center_label("WWW")
    assert qr_service.CENTER_FONT_SIZE == 24
    assert sizes == [24]


def test_missing_configured_font_does_not_silently_use_another_font(monkeypatch):
    monkeypatch.setattr(qr_service, "FONT_PATH", "/nonexistent/arialbd.ttf")
    with pytest.raises(OSError):
        render_center_label("007")


def test_empty_center_graphic_does_not_print_any_black_pixels():
    graphic = zpl_service._center_graphic_zpl("")
    assert graphic == "^GFA,180,180,6," + "00" * 180 + "^FS"
