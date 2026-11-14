import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from scripts.package_web_release import allowed_path


MOBILE = Path(__file__).resolve().parents[1] / "backend/app/mobile"


def test_mobile_shell_and_local_assets_are_served_and_packaged():
    app = FastAPI()
    app.mount("/api/movil", StaticFiles(directory=MOBILE, html=True))
    with TestClient(app) as client:
        for name in (
            "", "index.html", "manifest.webmanifest", "sw.js", "css/app.css",
            "js/app.js", "js/api.js", "js/db.js", "js/scanner.js",
            "vendor/zxing.min.js", "icons/icon-180.png", "icons/icon-192.png",
            "icons/icon-512.png", "icons/maskable-512.png",
        ):
            response = client.get(f"/api/movil/{name}")
            assert response.status_code == 200, name
            assert response.content
            assert allowed_path(f"backend/app/mobile/{name or 'index.html'}")


def test_mobile_manifest_has_installable_local_icons():
    manifest = json.loads((MOBILE / "manifest.webmanifest").read_text())
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "./"
    for icon in manifest["icons"]:
        assert icon["src"].startswith("./")
        assert (MOBILE / icon["src"]).is_file()
