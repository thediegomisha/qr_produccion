import re

import pytest

from app.services import zpl_service


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
