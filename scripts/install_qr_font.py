#!/usr/bin/env python3
"""Instala la fuente externa elegida por el usuario, sin incluirla en Git/ZIP."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

FONT_URL = "https://raw.githubusercontent.com/RedBalloonShenanigans/MonitorDarkly/master/fonts/arialbd.ttf"
FONT_SHA256 = "df70597f0bdf49da3af270138f8a34396e4f5618c671a1db3480e626f38aaece"
MAX_FONT_BYTES = 1024 * 1024
DEFAULT_DESTINATION = Path("/opt/qr_produccion-web/shared/fonts/arialbd.ttf")


def _verify(data: bytes):
    if len(data) > MAX_FONT_BYTES or hashlib.sha256(data).hexdigest() != FONT_SHA256:
        raise ValueError("La fuente no coincide con el SHA-256 verificado; no se instala")


def install_font(destination: Path, source: Path | None = None) -> bool:
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError("El destino no puede ser un enlace simbolico")
    if destination.exists():
        with destination.open("rb") as handle:
            _verify(handle.read(MAX_FONT_BYTES + 1))
        return False
    if source is None:
        with urlopen(FONT_URL, timeout=30) as response:
            data = response.read(MAX_FONT_BYTES + 1)
    else:
        with Path(source).open("rb") as handle:
            data = handle.read(MAX_FONT_BYTES + 1)
    _verify(data)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o644)
        # Publicación atómica sin sobrescribir un archivo preexistente.
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Archivo local; evita descargarlo de nuevo")
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    changed = install_font(args.destination, args.source)
    print("Fuente instalada y verificada." if changed else "La fuente verificada ya estaba instalada; sin cambios.")
    print(f"Destino: {args.destination}")


if __name__ == "__main__":
    main()
