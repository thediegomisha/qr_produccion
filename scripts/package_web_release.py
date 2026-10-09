#!/usr/bin/env python3
"""Build a web-only release. Runtime settings and the print agent are never shipped."""

import argparse
import hashlib
import json
import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

MANIFEST = "qr-web-manifest.json"
TOOLS = {"scripts/package_web_release.py", "scripts/deploy_web_release.py", "scripts/install_web_updater.sh"}
DOCS = {"docs/despliegue-web.md"}
REQUIRED = {
    "requirements.txt", "backend/app/main.py", "backend/app/services/agent_client.py",
    "backend/app/services/zpl_service.py", "ui_web/streamlit_app.py", *TOOLS, *DOCS,
}
SKIP_DIRECTORIES = {"print_agent", "__pycache__", "venv", ".venv", ".streamlit", "backups", "tests"}
SKIP_SUFFIXES = (".pyc", ".pyo", ".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3", ".log", ".pid", ".tmp")


def valid_version(version):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", version):
        raise ValueError("La versión admite letras, números, puntos, guiones y guiones bajos")
    return version


def allowed_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or "\\" in name or ".." in path.parts or path.as_posix() != name:
        return False
    if any(part.startswith(".") or part in SKIP_DIRECTORIES for part in path.parts):
        return False
    if path.name.lower().endswith(SKIP_SUFFIXES):
        return False
    return (
        name == "requirements.txt" or name in TOOLS or name in DOCS
        or (len(path.parts) >= 3 and path.parts[:2] == ("backend", "app"))
        or (len(path.parts) >= 2 and path.parts[0] == "ui_web")
    )


def build_release(root, output, version):
    root, output = Path(root).resolve(), Path(output)
    version = valid_version(version)
    files = []
    candidates = [root / "requirements.txt", *(root / name for name in TOOLS | DOCS)]
    for folder in ("backend/app", "ui_web"):
        candidates.extend((root / folder).rglob("*"))
    for path in sorted(set(candidates)):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
            continue
        name = relative.as_posix()
        if allowed_path(name):
            data = path.read_bytes()
            files.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    missing = REQUIRED - {item["path"] for item in files}
    if missing:
        raise ValueError(f"Faltan archivos web: {', '.join(sorted(missing))}")

    def git_value(*args):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    manifest = {
        "format": 1, "version": version, "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_branch": git_value("branch", "--show-current"),
        "working_tree_dirty": bool(git_value("status", "--porcelain")),
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for item in files:
            archive.write(root / item["path"], item["path"])
        archive.writestr(MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def validate_release(archive):
    names = archive.namelist()
    if len(names) != len(set(names)) or MANIFEST not in names:
        raise ValueError("El paquete tiene entradas duplicadas o no incluye manifiesto")
    manifest = json.loads(archive.read(MANIFEST))
    if manifest.get("format") != 1:
        raise ValueError("Formato de paquete no soportado")
    valid_version(manifest["version"])
    entries = manifest["files"]
    paths = [item["path"] for item in entries]
    if len(paths) != len(set(paths)) or set(names) != {MANIFEST, *paths}:
        raise ValueError("Los archivos del paquete no coinciden con su manifiesto")
    if not REQUIRED.issubset(paths):
        raise ValueError("El paquete no contiene todos los archivos web requeridos")
    for item in entries:
        name = item["path"]
        if not allowed_path(name) or stat.S_ISLNK(archive.getinfo(name).external_attr >> 16):
            raise ValueError(f"Archivo no permitido en el paquete web: {name}")
        data = archive.read(name)
        if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"El archivo no coincide con su hash: {name}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    output = args.output or args.root / "dist/web" / f"qr-web-{args.version}.zip"
    manifest = build_release(args.root, output, args.version)
    print(f"Paquete web: {output.resolve()}")
    print(f"Versión: {manifest['version']} | Archivos: {len(manifest['files'])}")


if __name__ == "__main__":
    main()
