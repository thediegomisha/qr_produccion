from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import Event

import pytest
from sqlalchemy import text

from app.core.auth_dep import get_current_user
from app.db.models import Lote, Persona, QREmitido, ScanEvent


def create(client, codigo="LOTE-A"):
    response = client.post("/api/lotes", json={"codigo": codigo})
    assert response.status_code == 201, response.text
    return response.json()


def add_scan(factory, lote_id, token):
    with factory() as db:
        db.add(ScanEvent(token=token, dni="12345678", lote_id=lote_id, raw={"p": "PALTA"}))
        db.commit()


def test_create_normalizes_and_rejects_duplicate_without_changing_original(client, session_factory):
    lote = create(client, "  lote-a  ")
    assert lote["codigo"] == "LOTE-A"
    assert lote["creado_por"] == "usuario-prueba"
    assert lote["estado"] == "ABIERTO"
    assert lote["creado_en"]
    duplicate = client.post("/api/lotes", json={"codigo": "lote-a"})
    assert duplicate.status_code == 409
    with session_factory() as db:
        assert db.query(Lote).count() == 1


@pytest.mark.parametrize("codigo", ["", "   ", "A" * 65, "LOTE/1", "LOTE\\1", "A\nB"])
def test_invalid_codes_are_rejected(client, session_factory, codigo):
    assert client.post("/api/lotes", json={"codigo": codigo}).status_code == 422
    with session_factory() as db:
        assert db.query(Lote).count() == 0


def test_list_search_state_pagination_and_read_counts(client, session_factory):
    first = create(client, "PALTA-1")
    second = create(client, "PALTA-2")
    create(client, "UVA-1")
    add_scan(session_factory, first["id"], "scan1")
    add_scan(session_factory, first["id"], "scan2")
    assert client.post("/api/lotes/PALTA-2/close").status_code == 200
    result = client.get("/api/lotes", params={"q": "palta", "limit": 1}).json()
    assert result["total"] == 2
    assert result["items"][0]["id"] == second["id"]
    result = client.get("/api/lotes", params={"q": "palta", "limit": 1, "offset": 1}).json()
    assert result["items"][0]["total_lecturas"] == 2
    result = client.get("/api/lotes", params={"q": "palta", "estado": "CERRADO"}).json()
    assert [row["codigo"] for row in result["items"]] == ["PALTA-2"]
    assert client.get(f"/api/lotes/{first['id']}").json()["total_lecturas"] == 2


def test_search_treats_sql_wildcards_as_literal_characters(client):
    create(client, "LOTE_1")
    create(client, "LOTEX1")
    result = client.get("/api/lotes", params={"q": "_"}).json()
    assert result["total"] == 1
    assert result["items"][0]["codigo"] == "LOTE_1"


def test_rename_preserves_identity_reads_and_updates_audit_timestamps(client, session_factory):
    lote = create(client)
    add_scan(session_factory, lote["id"], "read-original")
    result = client.put(f"/api/lotes/{lote['id']}", json={"codigo": " lote-b ", "estado": "CERRADO"})
    assert result.status_code == 200
    data = result.json()
    assert data["codigo"] == "LOTE-B"
    assert data["id"] == lote["id"]
    assert data["total_lecturas"] == 1
    assert data["cerrado_por"] == "usuario-prueba"
    assert data["cerrado_en"]
    assert data["creado_en"] == lote["creado_en"]
    with session_factory() as db:
        assert db.get(ScanEvent, "read-original").lote_id == lote["id"]
    reopened = client.put(f"/api/lotes/{lote['id']}", json={"codigo": "LOTE-B", "estado": "ABIERTO"}).json()
    assert reopened["reabierto_en"]
    assert reopened["reabierto_por"] == "usuario-prueba"


def test_duplicate_rename_rolls_back_state_and_audit_changes(client):
    first = create(client)
    create(client, "LOTE-B")
    result = client.put(f"/api/lotes/{first['id']}", json={"codigo": "LOTE-B", "estado": "CERRADO"})
    assert result.status_code == 409
    original = client.get(f"/api/lotes/{first['id']}").json()
    assert original["codigo"] == "LOTE-A"
    assert original["estado"] == "ABIERTO"
    assert original["cerrado_en"] is None


def test_delete_removes_entire_lot_and_only_its_reads(client, session_factory):
    first = create(client)
    other = create(client, "LOTE-B")
    add_scan(session_factory, first["id"], "read1")
    add_scan(session_factory, first["id"], "read2")
    add_scan(session_factory, other["id"], "other-read")
    with session_factory() as db:
        db.add(QREmitido(token="read1", dni_trabajador="12345678"))
        db.add(Persona(tipo_doc="DNI", nro_doc="12345678"))
        db.commit()
    result = client.delete(f"/api/lotes/{first['id']}")
    assert result.status_code == 200
    assert result.json()["deleted_scans"] == 2
    assert client.get(f"/api/lotes/{first['id']}").status_code == 404
    with session_factory() as db:
        assert db.query(Lote).count() == 1
        assert db.query(ScanEvent).count() == 1
        assert db.get(ScanEvent, "other-read")
        assert db.get(QREmitido, "read1")
        assert db.query(Persona).count() == 1


def test_delete_rolls_back_reads_if_another_foreign_key_prevents_deletion(client, session_factory, engine):
    lote = create(client)
    add_scan(session_factory, lote["id"], "read1")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE test_lote_reference (id INTEGER PRIMARY KEY, lote_id INTEGER REFERENCES lotes(id))"))
        connection.execute(text("INSERT INTO test_lote_reference(id, lote_id) VALUES (1, :lote)"), {"lote": lote["id"]})
    try:
        assert client.delete(f"/api/lotes/{lote['id']}").status_code == 409
        with session_factory() as db:
            assert db.get(Lote, lote["id"])
            assert db.get(ScanEvent, "read1")
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE test_lote_reference"))


@pytest.mark.parametrize("role", ["SUPERVISOR", "OPERADOR", "AGENTE"])
def test_edit_and_delete_are_protected_in_the_api(client, user, role):
    lote = create(client)
    user["rol"] = role
    assert client.put(f"/api/lotes/{lote['id']}", json={"codigo": "B", "estado": "ABIERTO"}).status_code == 403
    assert client.delete(f"/api/lotes/{lote['id']}").status_code == 403
    assert client.get(f"/api/lotes/{lote['id']}").json()["codigo"] == "LOTE-A"


def test_gerencia_can_manage_but_cannot_bypass_root_reopening_rule(client, user):
    lote = create(client)
    client.post("/api/lotes/LOTE-A/close")
    user["rol"] = "GERENCIA"
    assert client.put(f"/api/lotes/{lote['id']}", json={"codigo": "B", "estado": "ABIERTO"}).status_code == 403
    assert client.get(f"/api/lotes/{lote['id']}").json()["codigo"] == "LOTE-A"
    assert client.put(f"/api/lotes/{lote['id']}", json={"codigo": "B", "estado": "CERRADO"}).status_code == 200
    assert client.delete(f"/api/lotes/{lote['id']}").status_code == 200


def test_supervisor_can_create_close_and_select_but_not_reopen(client, user):
    user["rol"] = "SUPERVISOR"
    lote = create(client)
    assert client.post("/api/lotes/LOTE-A/close").status_code == 200
    assert client.post("/api/lotes/LOTE-A/open").status_code == 403
    assert client.get(f"/api/lotes/{lote['id']}").status_code == 200


def test_legacy_android_ensure_close_and_open_remain_available(client, user):
    user["rol"] = "OPERADOR"
    first = client.post("/api/lotes/ensure", json={"codigo": " lote-a "})
    second = client.post("/api/lotes/ensure", json={"codigo": "LOTE-A"})
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    user["rol"] = "ROOT"
    assert client.post("/api/lotes/LOTE-A/close").json()["estado"] == "CERRADO"
    assert client.post("/api/lotes/LOTE-A/open").json()["estado"] == "ABIERTO"


def test_missing_auth_and_missing_lots_have_expected_errors(client, app):
    assert client.get("/api/lotes/999999").status_code == 404
    assert client.put("/api/lotes/999999", json={"codigo": "B", "estado": "ABIERTO"}).status_code == 404
    assert client.delete("/api/lotes/999999").status_code == 404
    app.dependency_overrides.pop(get_current_user)
    assert client.get("/api/lotes").status_code == 401


def test_delete_waits_for_in_flight_read_transaction(client, session_factory, engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("El bloqueo de filas requiere PostgreSQL")
    lote = create(client)
    started = Event()
    def remove():
        started.set()
        return client.delete(f"/api/lotes/{lote['id']}")
    with session_factory() as upload:
        upload.query(Lote).filter(Lote.id == lote["id"]).with_for_update().one()
        upload.add(ScanEvent(token="in-flight", dni="12345678", lote_id=lote["id"]))
        upload.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(remove)
            assert started.wait(2)
            try:
                # The delete cannot complete while the batch holds the lot lock.
                with pytest.raises(FutureTimeoutError):
                    future.result(timeout=0.2)
            finally:
                upload.commit()
            response = future.result(timeout=5)
    assert response.status_code == 200
    assert response.json()["deleted_scans"] == 1


def test_bulk_delete_requires_root_and_removes_selected_lots_with_reads(client, session_factory, user):
    first = create(client, "MASS-1")
    second = create(client, "MASS-2")
    keep = create(client, "CONSERVAR")
    add_scan(session_factory, first["id"], "m1")
    add_scan(session_factory, second["id"], "m2")
    add_scan(session_factory, keep["id"], "k1")

    for role in ("GERENCIA", "SUPERVISOR"):
        user["rol"] = role
        assert client.post("/api/lotes/bulk-delete", json={"ids": [first["id"], second["id"]]}).status_code == 403
    user["rol"] = "ROOT"
    assert client.post("/api/lotes/bulk-delete", json={"ids": [first["id"], 99999]}).status_code == 404
    result = client.post("/api/lotes/bulk-delete", json={"ids": [first["id"], second["id"], first["id"]]})
    assert result.status_code == 200
    data = result.json()
    assert data["deleted_lotes"] == 2
    assert data["deleted_scans"] == 2
    assert {i["codigo"] for i in data["items"]} == {"MASS-1", "MASS-2"}
    with session_factory() as db:
        assert db.query(Lote).count() == 1
        assert db.query(ScanEvent).count() == 1
        assert db.get(ScanEvent, "k1")


def test_bulk_delete_rejects_empty_or_repeated_duplicates(client):
    assert client.post("/api/lotes/bulk-delete", json={"ids": []}).status_code == 422
    assert client.post("/api/lotes/bulk-delete", json={"ids": [1] * 501}).status_code == 422


def test_android_batch_upload_still_works_and_closed_lots_reject_reads(client, session_factory, engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("El contrato de scans utiliza JSONB de PostgreSQL")
    payload = {
        "batch_uuid": "test-batch", "lote_codigo": "LOTE-A", "device_id": "test-device",
        "scans": [{"token": "android-read", "dni": "12345678", "scanned_at": "2026-01-01T12:00:00Z", "raw": {"p": "PALTA"}}],
    }
    result = client.post("/api/scans/batch", json=payload)
    assert result.status_code == 200
    assert result.json()["accepted_count"] == 1
    assert client.post("/api/scans/batch", json=payload).json()["duplicate_count"] == 1
    client.post("/api/lotes/LOTE-A/close")
    payload["scans"][0]["token"] = "must-not-insert"
    assert client.post("/api/scans/batch", json=payload).status_code == 409
    with session_factory() as db:
        assert db.get(ScanEvent, "must-not-insert") is None
