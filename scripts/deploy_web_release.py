#!/usr/bin/env python3
"""Deploy backend/frontend independently of the original print-agent installation."""

import argparse
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

try:
    from scripts.package_web_release import MANIFEST, validate_release
except ModuleNotFoundError:
    from package_web_release import MANIFEST, validate_release


def run_command(args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def wait_for_health(backend_port, frontend_port):
    last_error = None
    for _ in range(30):
        try:
            with urlopen(f"http://127.0.0.1:{backend_port}/api/setup/status", timeout=3) as response:
                data = json.load(response)
                if not isinstance(data.get("initialized"), bool):
                    raise ValueError("El backend no respondió con el estado esperado")
            with urlopen(f"http://127.0.0.1:{frontend_port}/_stcore/health", timeout=3) as response:
                if response.read().strip() != b"ok":
                    raise ValueError("Streamlit no respondió con su estado esperado")
            return
        except Exception as failure:
            last_error = failure
            time.sleep(1)
    raise RuntimeError("La nueva versión no superó la verificación de backend/frontend") from last_error


def replace_link(link, destination):
    pending = link.with_name(f".{link.name}-{uuid.uuid4().hex}")
    pending.symlink_to(destination, target_is_directory=True)
    try:
        pending.replace(link)
    finally:
        pending.unlink(missing_ok=True)


def deploy(archive_path, target, *, backend_service="qr-backend.service",
           frontend_service="qr-frontend.service", backend_port=8000, frontend_port=8501,
           python="python3", unit_root=Path("/etc/systemd/system"),
           runner=run_command, health_check=wait_for_health):
    target, unit_root = Path(target).resolve(), Path(unit_root)
    services = (backend_service, frontend_service)
    if not all(1 <= port <= 65535 for port in (backend_port, frontend_port)):
        raise ValueError("Los puertos web deben estar entre 1 y 65535")
    if any(char in str(target) for char in '\n\r"%'):
        raise ValueError("El destino contiene caracteres incompatibles con systemd")
    for service in services:
        if not re.fullmatch(r"[A-Za-z0-9@_.-]+\.service", service) or "agent" in service.lower():
            raise ValueError("Solo se pueden desplegar servicios web, no servicios de impresión")
    if backend_service == frontend_service:
        raise ValueError("Backend y frontend necesitan servicios distintos")
    current = target / "current"
    if current.exists() and not current.is_symlink():
        raise ValueError("La carpeta current debe ser un enlace administrado por este despliegue")
    if current.is_symlink() and not current.exists():
        raise ValueError("El enlace current apunta a una versión que no existe")
    previous = current.readlink() if current.is_symlink() else None

    def property_of(service, name):
        return runner(["systemctl", "show", service, f"--property={name}", "--value"]).stdout.strip()

    info = {}
    for service in services:
        if property_of(service, "LoadState") != "loaded":
            raise ValueError(f"No existe el servicio web {service}")
        for relation in ("ConsistsOf", "BoundBy"):
            if any("agent" in related.lower() for related in property_of(service, relation).split()):
                raise ValueError("Separe primero las dependencias systemd entre web y agente de impresión")
        info[service] = {
            "user": property_of(service, "User") or "root",
            "working_directory": property_of(service, "WorkingDirectory"),
        }
    original_backend = Path(info[backend_service]["working_directory"])
    # A deployment must not turn the legacy agent tree into its release directory.
    legacy_root = original_backend.parent
    has_legacy_agent = (original_backend / "app/print_agent/agent_app.py").is_file()
    if has_legacy_agent and (target == legacy_root or legacy_root in target.parents or target in legacy_root.parents):
        raise ValueError("El destino web debe ser una carpeta separada de la instalación original")

    with ZipFile(archive_path) as archive:
        manifest = validate_release(archive)
        release = target / "releases" / manifest["version"]
        if release.exists():
            raise ValueError("Esa versión ya está preparada; genere el paquete con una nueva versión")
        target.mkdir(parents=True, exist_ok=True)
        release.mkdir(parents=True)
        try:
            for item in manifest["files"]:
                output = release / item["path"]
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(archive.read(item["path"]))
            (release / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            # Per-release Python environment: installing web dependencies never updates the agent's venv.
            runner([python, "-m", "venv", str(release / ".venv")])
            interpreter = release / ".venv/bin/python"
            runner([str(interpreter), "-m", "pip", "install", "-r", str(release / "requirements.txt")])

            shared = target / "shared"
            shared.mkdir(exist_ok=True)
            persistent_env = shared / "backend.env"
            legacy_env = original_backend / ".env"
            if not persistent_env.exists() and legacy_env.is_file():
                shutil.copy2(legacy_env, persistent_env)
                persistent_env.chmod(0o600)
                owner = pwd.getpwnam(info[backend_service]["user"])
                if os.geteuid() == 0:
                    os.chown(persistent_env, owner.pw_uid, owner.pw_gid)
            if persistent_env.exists():
                (release / "backend/.env").symlink_to(persistent_env)
            # Project-local Streamlit secrets must also survive the move to versioned releases.
            frontend_settings = shared / "frontend-secrets.toml"
            old_frontend = Path(info[frontend_service]["working_directory"])
            old_secrets = old_frontend / ".streamlit/secrets.toml"
            if not frontend_settings.exists() and old_secrets.is_file():
                shutil.copy2(old_secrets, frontend_settings)
                frontend_settings.chmod(0o600)
                owner = pwd.getpwnam(info[frontend_service]["user"])
                if os.geteuid() == 0:
                    os.chown(frontend_settings, owner.pw_uid, owner.pw_gid)
            if frontend_settings.exists():
                settings_folder = release / "ui_web/.streamlit"
                settings_folder.mkdir(exist_ok=True)
                (settings_folder / "secrets.toml").symlink_to(frontend_settings)
        except Exception:
            shutil.rmtree(release)
            raise

    overrides = {}
    for service in services:
        path = unit_root / f"{service}.d/70-qr-web-release.conf"
        overrides[path] = path.read_bytes() if path.exists() else None
    try:
        for service, folder, port in (
            (backend_service, "backend", backend_port),
            (frontend_service, "ui_web", frontend_port),
        ):
            working_directory = target / "current" / folder
            executable = target / "current/.venv/bin/python"
            if folder == "backend":
                command = f'"{executable}" -m uvicorn app.main:app --host 0.0.0.0 --port {port}'
            else:
                command = (f'"{executable}" -m streamlit run "{working_directory / "streamlit_app.py"}" '
                           f'--server.address 0.0.0.0 --server.port {port} --server.headless true')
            override = unit_root / f"{service}.d/70-qr-web-release.conf"
            override.parent.mkdir(parents=True, exist_ok=True)
            override.write_text(
                f'[Service]\nType=simple\nWorkingDirectory="{working_directory}"\nExecStart=\nExecStart={command}\n',
                encoding="utf-8",
            )
        replace_link(current, release)
        runner(["systemctl", "daemon-reload"])
        runner(["systemctl", "restart", backend_service, frontend_service])
        health_check(backend_port, frontend_port)
    except Exception:
        if previous is not None:
            replace_link(current, previous)
        else:
            current.unlink(missing_ok=True)
        for path, content in overrides.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        runner(["systemctl", "daemon-reload"])
        runner(["systemctl", "restart", backend_service, frontend_service])
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--target", type=Path, default=Path("/opt/qr_produccion-web"))
    parser.add_argument("--backend-service", default="qr-backend.service")
    parser.add_argument("--frontend-service", default="qr-frontend.service")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=8501)
    parser.add_argument("--python", default="python3")
    args = parser.parse_args()
    if os.name != "posix" or os.geteuid() != 0:
        parser.error("Este actualizador del servidor Linux se ejecuta con sudo")
    # Code/venv must be readable by the original service users, even under a restrictive sudo umask.
    os.umask(0o022)
    try:
        result = deploy(args.archive, args.target, backend_service=args.backend_service,
                        frontend_service=args.frontend_service, backend_port=args.backend_port,
                        frontend_port=args.frontend_port, python=args.python)
    except subprocess.CalledProcessError as failure:
        # Do not echo pip/environment output that could contain server configuration.
        print(f"Falló un paso del despliegue (código {failure.returncode}).", file=sys.stderr)
        raise SystemExit(1)
    print(f"Web actualizada: {result['version']}. Backend y frontend verificados.")


if __name__ == "__main__":
    main()
