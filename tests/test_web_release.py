import getpass
import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.deploy_web_release import deploy
from scripts.package_web_release import MANIFEST, REQUIRED, build_release, validate_release


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    for name in REQUIRED:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# source file\n", encoding="utf-8")
    (root / "requirements.txt").write_text("fastapi==0.124.4\n", encoding="utf-8")
    asset = root / "ui_web/assets/logo.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"test-image")
    for name in (
        ".env", "backend/.env", "backend/print_agent_jobs.db",
        "backend/app/print_agent/agent_app.py", "backend/app/print_agent/jobs.db-wal",
        "backend/app/__pycache__/module.pyc", "ui_web/.streamlit/secrets.toml",
        "ui_web/local.db", "ui_web/frontend.log",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("local-state-not-to-ship", encoding="utf-8")
    return root


def package(source, tmp_path, version="test-1"):
    archive = tmp_path / f"{version}.zip"
    build_release(source, archive, version)
    return archive


def test_package_contains_web_code_and_assets_but_no_print_service_or_runtime_settings(source, tmp_path):
    archive = package(source, tmp_path)
    with ZipFile(archive) as bundle:
        manifest = validate_release(bundle)
        names = bundle.namelist()
    assert REQUIRED.issubset(names)
    assert "ui_web/assets/logo.png" in names
    assert manifest["version"] == "test-1"
    assert not any("print_agent" in name or ".env" in name or "secrets.toml" in name for name in names)
    assert not any(name.endswith((".db", ".db-wal", ".pyc", ".log")) for name in names)


def test_package_does_not_follow_links_to_external_data(source, tmp_path):
    secret = tmp_path / "private.txt"
    secret.write_text("private")
    (source / "ui_web/linked.py").symlink_to(secret)
    external = tmp_path / "external"
    external.mkdir()
    (external / "private.py").write_text("private")
    (source / "ui_web/linked-folder").symlink_to(external, target_is_directory=True)
    with ZipFile(package(source, tmp_path)) as bundle:
        assert not any("linked" in name for name in bundle.namelist())


@pytest.mark.parametrize("version", ["../escape", "", "bad/version", "name\nother"])
def test_invalid_versions_cannot_escape_the_release_folder(source, tmp_path, version):
    with pytest.raises(ValueError):
        build_release(source, tmp_path / "bad.zip", version)


def test_modified_or_unlisted_entries_are_rejected(source, tmp_path):
    archive = package(source, tmp_path)
    altered = tmp_path / "altered.zip"
    with ZipFile(archive) as original, ZipFile(altered, "w") as destination:
        for name in original.namelist():
            destination.writestr(name, b"changed" if name == "backend/app/main.py" else original.read(name))
    with ZipFile(altered) as bundle, pytest.raises(ValueError, match="hash"):
        validate_release(bundle)
    unexpected = tmp_path / "unexpected.zip"
    with ZipFile(archive) as original, ZipFile(unexpected, "w") as destination:
        for name in original.namelist():
            destination.writestr(name, original.read(name))
        destination.writestr("backend/.env", "settings")
    with ZipFile(unexpected) as bundle, pytest.raises(ValueError, match="manifiesto"):
        validate_release(bundle)


def test_forbidden_manifest_path_is_rejected_even_with_matching_hash(source, tmp_path):
    archive = package(source, tmp_path)
    unsafe = tmp_path / "unsafe.zip"
    data = b"unexpected"
    with ZipFile(archive) as original, ZipFile(unsafe, "w") as destination:
        manifest = json.loads(original.read(MANIFEST))
        for name in original.namelist():
            if name != MANIFEST:
                destination.writestr(name, original.read(name))
        manifest["files"].append({"path": "backend/app/../../escape.py", "size": len(data),
                                  "sha256": hashlib.sha256(data).hexdigest()})
        destination.writestr("backend/app/../../escape.py", data)
        destination.writestr(MANIFEST, json.dumps(manifest))
    with ZipFile(unsafe) as bundle, pytest.raises(ValueError, match="no permitido"):
        validate_release(bundle)


class FakeSystem:
    def __init__(self, legacy, fail_pip=False):
        self.legacy = legacy
        self.calls = []
        self.fail_pip = fail_pip

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["systemctl", "show"]:
            property_name = args[3].split("=", 1)[1]
            value = {
                "LoadState": "loaded", "User": getpass.getuser(),
                "WorkingDirectory": str(self.legacy / ("ui_web" if args[2] == "qr-frontend.service" else "backend")),
                "ConsistsOf": "", "BoundBy": "",
            }[property_name]
            return subprocess.CompletedProcess(args, 0, stdout=value, stderr="")
        if args[1:3] == ["-m", "venv"]:
            binary = Path(args[3]) / "bin/python"
            binary.parent.mkdir(parents=True)
            binary.write_text("isolated-interpreter")
        if "pip" in args and self.fail_pip:
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


@pytest.fixture
def legacy(tmp_path):
    root = tmp_path / "original"
    files = {
        "backend/.env": "PRINT_AGENT_URL=http://printer-host:5000\n",
        "backend/app/print_agent/agent_app.py": "# original agent\n",
        "backend/print_agent_jobs.db": "job-queue-state",
        ".venv/bin/python": "original-interpreter",
        "ui_web/.streamlit/secrets.toml": "PRINT_AGENT_TOKEN='saved-test-config'\n",
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


def test_deploy_uses_new_python_env_and_only_restarts_web_services(source, legacy, tmp_path):
    before = {path: path.read_bytes() for path in legacy.rglob("*") if path.is_file()}
    system = FakeSystem(legacy)
    target = tmp_path / "web"
    units = tmp_path / "units"
    result = deploy(package(source, tmp_path), target, unit_root=units, runner=system,
                    health_check=lambda *ports: None)
    assert result["version"] == "test-1"
    assert (target / "current").resolve() == target / "releases/test-1"
    assert (target / "current/backend/.env").resolve() == target / "shared/backend.env"
    assert (target / "shared/backend.env").read_text() == (legacy / "backend/.env").read_text()
    assert (target / "current/ui_web/.streamlit/secrets.toml").resolve() == target / "shared/frontend-secrets.toml"
    assert (target / "shared/frontend-secrets.toml").read_text() == (legacy / "ui_web/.streamlit/secrets.toml").read_text()
    assert not (target / "current/backend/app/print_agent").exists()
    assert all(path.read_bytes() == original for path, original in before.items())
    assert ["systemctl", "restart", "qr-backend.service", "qr-frontend.service"] in system.calls
    assert not any("qr-agent" in " ".join(call) or "nssm" in call for call in system.calls)
    assert "/current/.venv/bin/python" in (units / "qr-backend.service.d/70-qr-web-release.conf").read_text()


def test_subsequent_release_keeps_persistent_settings(source, legacy, tmp_path):
    target, units = tmp_path / "web", tmp_path / "units"
    system = FakeSystem(legacy)
    deploy(package(source, tmp_path, "first"), target, unit_root=units, runner=system, health_check=lambda *p: None)
    settings = target / "shared/backend.env"
    settings.write_text("PRINT_AGENT_URL=http://configured-once:5000\n")
    system.legacy = target / "current"
    deploy(package(source, tmp_path, "second"), target, unit_root=units, runner=system, health_check=lambda *p: None)
    assert (target / "current").resolve() == target / "releases/second"
    assert settings.read_text() == "PRINT_AGENT_URL=http://configured-once:5000\n"


def test_persistent_frontend_secrets_are_not_replaced_by_later_updates(source, legacy, tmp_path):
    target, units = tmp_path / "web", tmp_path / "units"
    system = FakeSystem(legacy)
    deploy(package(source, tmp_path, "first"), target, unit_root=units, runner=system, health_check=lambda *p: None)
    settings = target / "shared/frontend-secrets.toml"
    settings.write_text("PRINT_AGENT_TOKEN='permanent-test-config'\n")
    system.legacy = target / "current"
    deploy(package(source, tmp_path, "second"), target, unit_root=units, runner=system, health_check=lambda *p: None)
    assert settings.read_text() == "PRINT_AGENT_TOKEN='permanent-test-config'\n"


def test_failed_health_restores_previous_version_and_service_overrides(source, legacy, tmp_path):
    target, units = tmp_path / "web", tmp_path / "units"
    target.mkdir()
    previous = target / "old"
    previous.mkdir()
    (target / "current").symlink_to(previous, target_is_directory=True)
    existing = units / "qr-backend.service.d/70-qr-web-release.conf"
    existing.parent.mkdir(parents=True)
    existing.write_text("[Service]\n# previous override\n")
    system = FakeSystem(legacy)
    def fail_health(*ports):
        raise RuntimeError("test-only-health-failure")
    with pytest.raises(RuntimeError, match="health-failure"):
        deploy(package(source, tmp_path), target, unit_root=units, runner=system, health_check=fail_health)
    assert (target / "current").resolve() == previous
    assert existing.read_text() == "[Service]\n# previous override\n"
    assert not (units / "qr-frontend.service.d/70-qr-web-release.conf").exists()
    assert sum(call[:2] == ["systemctl", "restart"] for call in system.calls) == 2


def test_dependency_failure_keeps_running_services_unchanged(source, legacy, tmp_path):
    system = FakeSystem(legacy, fail_pip=True)
    target = tmp_path / "web"
    with pytest.raises(subprocess.CalledProcessError):
        deploy(package(source, tmp_path), target, unit_root=tmp_path / "units", runner=system)
    assert not (target / "current").exists()
    assert not (target / "releases/test-1").exists()
    assert not any(call[:2] == ["systemctl", "restart"] for call in system.calls)


def test_original_agent_folder_cannot_be_used_as_web_destination(source, legacy, tmp_path):
    with pytest.raises(ValueError, match="separada"):
        deploy(package(source, tmp_path), legacy, unit_root=tmp_path / "units", runner=FakeSystem(legacy))


def test_agent_service_cannot_be_selected_for_restart(source, legacy, tmp_path):
    with pytest.raises(ValueError, match="impresión"):
        deploy(package(source, tmp_path), tmp_path / "web", backend_service="qr-agent.service",
               unit_root=tmp_path / "units", runner=FakeSystem(legacy))
