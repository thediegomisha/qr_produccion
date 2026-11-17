import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_qr, routes_reniec, routes_impresoras, routes_vigilancia
from app.db.models import QREmitido, ScanEvent, Lote
from app.services.qr_service import compact_payload, generar_qr_memoria
from app.services.zpl_service import generar_zpl_qr_4cols
from app.services import agent_client
from app.api import routes_health
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from app.core.tokens import generar_token


def test_health_has_no_setup_information(monkeypatch, session_factory):
    monkeypatch.setattr(routes_health, "SessionLocal", session_factory)
    app = FastAPI()
    app.include_router(routes_health.router)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        def unavailable():
            raise OperationalError("private-details", {}, Exception())
        monkeypatch.setattr(routes_health, "SessionLocal", unavailable)
        response = client.get("/health")
        assert response.status_code == 503
        assert "private-details" not in response.text


@pytest.mark.parametrize("producto", ["UVA", "PALTA"])
def test_compact_label_keeps_product_and_four_25mm_cells(producto):
    token = generar_token("UVA")
    assert len(token) == 16
    item = {"token": token, "dni": "12345678", "visible": "123", "producto": producto}
    zpl = generar_zpl_qr_4cols([item] * 4)
    assert "^PW840" in zpl and "^LL200" in zpl
    assert zpl.count("^BQN,2,3") == 4
    assert zpl.count("^GB48,30,30,W,0") == 4
    assert zpl.count("^A0N,22,14") == 4
    for data in re.findall(r"\^FDHA,(.+)\^FS", zpl):
        assert json.loads(data) == compact_payload(item["token"], item["dni"], item["visible"], producto)
    assert generar_qr_memoria(item["token"], item["dni"], item["visible"], "UVA").getvalue().startswith(b"\x89PNG")


@pytest.mark.parametrize("path,method", [
    ("/qr/preview", "post"), ("/qr/print", "post"),
    ("/reniec/dni/12345678", "get"), ("/impresoras/", "get"),
    ("/vigilancia/visitas?fecha=2026-11-14", "get"),
])
def test_sensitive_routes_require_authentication(path, method):
    app = FastAPI()
    app.include_router(routes_qr.router, prefix="/qr")
    app.include_router(routes_reniec.router)
    app.include_router(routes_impresoras.router)
    app.include_router(routes_vigilancia.router)
    with TestClient(app) as client:
        response = getattr(client, method)(path, **({"json": {}} if method == "post" else {}))
        assert response.status_code == 401


@pytest.mark.parametrize("kind", ["unknown", "wrong-dni", "future"])
def test_invalid_scans_are_atomic_and_do_not_create_lots(client, session_factory, kind):
    with session_factory() as db:
        db.add(QREmitido(token="issued", dni_trabajador="12345678"))
        db.commit()
    scan = {"token": "issued", "dni": "12345678", "scanned_at": "2026-01-01T12:00:00Z"}
    if kind == "unknown":
        scan["token"] = "unknown"
    elif kind == "wrong-dni":
        scan["dni"] = "87654321"
    else:
        scan["scanned_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = client.post("/api/scans/batch", json={
        "batch_uuid": "bad", "lote_codigo": "NO-CREAR", "scans": [scan],
    })
    assert response.status_code == 400
    if kind != "future":
        reason = "QR_NO_EMITIDO" if kind == "unknown" else "DNI_EMISION_DISTINTO"
        assert reason in response.json()["detail"]
        assert "lectura 1" in response.json()["detail"]
    with session_factory() as db:
        assert db.query(ScanEvent).count() == 0
        assert db.query(Lote).count() == 0


def test_agent_url_must_be_configured(monkeypatch):
    monkeypatch.setattr(agent_client, "DEFAULT_AGENT_URL", "http://printer.test:5000")
    monkeypatch.setattr(agent_client, "AGENTS", [])
    monkeypatch.delenv("PRINT_AGENT_ALLOWED_URLS", raising=False)
    assert agent_client._resolve_agent_url("http://printer.test:5000/") == "http://printer.test:5000"
    with pytest.raises(Exception) as error:
        agent_client._resolve_agent_url("http://untrusted.test")
    assert error.value.status_code == 400


@pytest.mark.parametrize("producto", ["UVA", "PALTA"])
def test_uploaded_compact_qr_can_be_filtered_by_raw_product(client, session_factory, engine, producto):
    if engine.dialect.name != "postgresql":
        pytest.skip("El filtro raw->>'p' requiere PostgreSQL")
    token = generar_token(producto)
    with session_factory() as db:
        db.add(QREmitido(token=token, dni_trabajador="12345678", nn="007", producto=producto))
        db.commit()
    response = client.post("/api/scans/batch", json={
        "batch_uuid": "product-filter", "lote_codigo": "PRODUCTOS",
        "scans": [{
            "token": token, "dni": "12345678", "scanned_at": "2026-01-01T12:00:00Z",
            "raw": compact_payload(token, "12345678", "007", producto),
        }],
    })
    assert response.status_code == 200
    with session_factory() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM scan_events WHERE raw->>'p' = :producto"
        ), {"producto": producto}).scalar_one() == 1


def test_recorded_legacy_scan_is_duplicate_without_emission(client, session_factory, engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("El envío de lecturas requiere PostgreSQL")
    original_time = datetime(2026, 1, 1, 12)
    with session_factory() as db:
        old_lot = Lote(codigo="ORIGINAL", estado="ABIERTO")
        db.add(old_lot)
        db.flush()
        old_lot_id = old_lot.id
        db.add(ScanEvent(
            token="legacy-recorded", dni="12345678", lote_id=old_lot.id,
            scanned_at=original_time, raw={"id": "007", "p": "UVA"},
        ))
        db.add(QREmitido(token="new-issued", dni_trabajador="12345678", nn="ABC", producto="UVA"))
        db.commit()
    response = client.post("/api/scans/batch", json={
        "batch_uuid": "legacy-retry", "lote_codigo": "NUEVO",
        "scans": [
            {"token": "legacy-recorded", "dni": "12345678", "scanned_at": "2026-01-02T12:00:00Z"},
            {"token": "new-issued", "dni": "12345678", "scanned_at": "2026-01-02T12:00:00Z"},
        ],
    })
    assert response.status_code == 200
    assert response.json() == {"batch_uuid": "legacy-retry", "accepted_count": 1, "duplicate_count": 1}
    with session_factory() as db:
        assert db.query(ScanEvent).count() == 2
        original = db.get(ScanEvent, "legacy-recorded")
        assert original.lote_id == old_lot_id
        assert original.scanned_at == original_time
        assert original.raw == {"id": "007", "p": "UVA"}
        assert db.get(QREmitido, "legacy-recorded") is None


def test_recorded_token_with_different_dni_is_not_acknowledged(client, session_factory):
    with session_factory() as db:
        db.add(ScanEvent(token="legacy", dni="12345678"))
        db.commit()
    response = client.post("/api/scans/batch", json={
        "batch_uuid": "wrong-dni-retry", "lote_codigo": "NO-CREAR",
        "scans": [{"token": "legacy", "dni": "87654321", "scanned_at": "2026-01-01T12:00:00Z"}],
    })
    assert response.status_code == 400
    assert "DNI_LECTURA_DISTINTO" in response.json()["detail"]
    assert "12345678" not in response.text
    with session_factory() as db:
        assert db.query(Lote).count() == 0
        assert db.get(ScanEvent, "legacy").dni == "12345678"


def test_unknown_qr_keeps_valid_rows_in_same_batch_pending(client, session_factory):
    with session_factory() as db:
        db.add(QREmitido(token="valid", dni_trabajador="12345678"))
        db.commit()
    response = client.post("/api/scans/batch", json={
        "batch_uuid": "atomic", "lote_codigo": "NO-CREAR",
        "scans": [
            {"token": token, "dni": "12345678", "scanned_at": "2026-01-01T12:00:00Z"}
            for token in ("valid", "unknown")
        ],
    })
    assert response.status_code == 400
    assert "QR_NO_EMITIDO: lectura 2" in response.json()["detail"]
    with session_factory() as db:
        assert db.query(ScanEvent).count() == 0
        assert db.query(Lote).count() == 0


def test_emission_with_null_dni_returns_validation_error_not_server_error(client, session_factory):
    with session_factory() as db:
        db.add(QREmitido(token="no-dni", dni_trabajador=None))
        db.commit()
    response = client.post("/api/scans/batch", json={
        "batch_uuid": "null-dni", "lote_codigo": "NO-CREAR",
        "scans": [{"token": "no-dni", "dni": "12345678", "scanned_at": "2026-01-01T12:00:00Z"}],
    })
    assert response.status_code == 400
    assert "DNI_EMISION_DISTINTO" in response.json()["detail"]
