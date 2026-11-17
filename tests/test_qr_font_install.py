import hashlib
from pathlib import Path
import stat

import pytest

from scripts import install_qr_font


def test_installs_external_font_without_overwriting_or_download(tmp_path, monkeypatch):
    data = b"test-font-bytes-not-for-production"
    monkeypatch.setattr(install_qr_font, "FONT_SHA256", hashlib.sha256(data).hexdigest())
    source = tmp_path / "source.ttf"
    source.write_bytes(data)
    destination = tmp_path / "shared/fonts/arialbd.ttf"
    assert install_qr_font.install_font(destination, source)
    assert destination.read_bytes() == data
    assert stat.S_IMODE(destination.stat().st_mode) == 0o644
    assert not install_qr_font.install_font(destination, Path("/missing.ttf"))


def test_rejects_unexpected_font_and_preserves_existing_file(tmp_path):
    source = tmp_path / "source.ttf"
    source.write_bytes(b"unexpected")
    destination = tmp_path / "arialbd.ttf"
    with pytest.raises(ValueError, match="SHA-256"):
        install_qr_font.install_font(destination, source)
    assert not destination.exists()
    destination.write_bytes(b"original")
    with pytest.raises(ValueError):
        install_qr_font.install_font(destination, source)
    assert destination.read_bytes() == b"original"


def test_rejects_symbolic_link_destination(tmp_path):
    original = tmp_path / "original"
    original.write_bytes(b"untouched")
    destination = tmp_path / "arialbd.ttf"
    destination.symlink_to(original)
    with pytest.raises(ValueError, match="enlace"):
        install_qr_font.install_font(destination)
    assert original.read_bytes() == b"untouched"
