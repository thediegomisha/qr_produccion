from datetime import datetime

import pytest

from app.db.models import Trabajador, QREmitido, Lote, ScanEvent


@pytest.mark.parametrize("role", ["ROOT", "GERENCIA", "SUPERVISOR", "OPERADOR", "AGENTE", "VIGILANCIA"])
def test_all_users_see_consolidated_lot_and_new_uploads(client, user, role, session_factory):
    def upload(operator, token, lot="LOTE-COMPARTIDO"):
        with session_factory() as db:
            db.add(QREmitido(token=token, dni_trabajador="12345678", nn="12", producto="UVA"))
            db.commit()
        user.update(usuario=operator, rol="OPERADOR")
        response = client.post("/api/scans/batch", json={
            "batch_uuid": f"batch-{token}", "lote_codigo": lot,
            "scans": [{
                "token": token, "dni": "12345678", "scanned_at": "2026-11-14T15:00:00Z",
                "raw": {"id": "12", "p": "UVA"},
            }],
        })
        assert response.status_code == 200
        assert response.json()["accepted_count"] == 1

    upload("angel", "angel-1")
    upload("ddiaz", "ddiaz-1")
    upload("otro", "other-lot", "OTRO-LOTE")
    params = {"lote_codigo": "LOTE-COMPARTIDO", "date_from": "2026-11-14", "date_to": "2026-11-14"}
    user.update(usuario="angel", rol=role)
    response = client.get("/api/reports/dni-summary", params=params)
    assert response.status_code == 200
    assert response.json()["scanned_by"] is None
    assert response.json()["totals"]["total_lecturas"] == 2
    assert response.json()["totals"]["emp_lecturas"] == 2
    assert response.json()["totals"]["sin_rol_lecturas"] == 0
    assert response.json()["rows"][0]["total"] == 2
    assert response.json()["rows"][0]["empacador"] == 2
    assert response.json()["rows"][0]["sin_rol"] == 0
    assert response.json()["rows"][0]["codigo"] == "12"
    operators = client.get("/api/reports/operator-summary", params=params).json()
    assert {row["user_id"] for row in operators["rows"]} == {"angel", "ddiaz"}

    # A subsequent query must include newly committed work from another user.
    upload("ddiaz", "ddiaz-2")
    user.update(usuario="angel", rol=role)
    assert client.get("/api/reports/dni-summary", params=params).json()["totals"]["total_lecturas"] == 3
    # Explicit filters are still available, but never applied implicitly.
    filtered = client.get("/api/reports/dni-summary", params={**params, "scanned_by": "ddiaz"}).json()
    assert filtered["totals"]["total_lecturas"] == 2


def _worker(session_factory, dni, rol, num_orden, cod_letra, nombre="ANA", apellido="PEREZ"):
    with session_factory() as db:
        db.add(Trabajador(
            dni=dni, nombre=nombre, apellido_paterno=apellido,
            apellido_materno=None, rol=rol,
            num_orden=num_orden, cod_letra=cod_letra, activo=True,
        ))
        db.commit()


def _upload(client, session_factory, token, dni, codigo, lot, scanned_at="2026-11-14T15:00:00Z", raw=True):
    with session_factory() as db:
        db.add(QREmitido(token=token, dni_trabajador=dni, nn=codigo.strip(), producto="UVA"))
        db.commit()
    payload = {
        "batch_uuid": f"batch-{token}", "lote_codigo": lot,
        "scans": [{
            "token": token, "dni": dni, "scanned_at": scanned_at,
            "raw": {"id": codigo, "p": "UVA"} if raw else None,
        }],
    }
    response = client.post("/api/scans/batch", json=payload)
    assert response.status_code == 200
    assert response.json()["accepted_count"] == 1


def test_lot_report_without_dates_includes_all_days_and_distinct_worker_codes(client, session_factory):
    _worker(session_factory, "12345678", "EMPACADORA", 1, "AAA")

    for token, codigo, date in [("numeric", "007", "2026-11-13"), ("letter", "A", "2026-11-14")]:
        _upload(client, session_factory, token, "12345678", codigo, "LOTE-MULTIDIA", f"{date}T15:00:00Z")

    data = client.get("/api/reports/dni-summary", params={"lote_codigo": "LOTE-MULTIDIA"}).json()
    assert data["date_from"] is None and data["date_to"] is None
    assert data["totals"]["total_lecturas"] == 2
    assert data["totals"]["emp_lecturas"] == 1
    assert data["totals"]["sel_lecturas"] == 1
    assert data["totals"]["sin_rol_lecturas"] == 0
    assert data["rows"][0]["codigo"] == "007, A"
    assert data["rows"][0]["rol"] == "EMPACADORA"
    assert data["rows"][0]["empacador"] == 1
    assert data["rows"][0]["seleccionador"] == 1
    assert data["rows"][0]["sin_rol"] == 0


def test_printed_code_classifies_both_tasks_for_each_registered_role(client, session_factory):
    """Un mismo DNI debe conservar empacado y selección, cualquiera sea su rol."""
    _worker(session_factory, "11111111", "EMPACADORA", 1, "AAA", nombre="ANA")
    _worker(session_factory, "22222222", "SELECCIONADOR", 2, "AAB", nombre="LUIS", apellido="SOTO")

    _upload(client, session_factory, "ana-num", "11111111", "001", "LOTE-ROLES")
    _upload(client, session_factory, "ana-letra", "11111111", "AAA", "LOTE-ROLES")
    _upload(client, session_factory, "luis-num", "22222222", "002", "LOTE-ROLES")
    _upload(client, session_factory, "luis-letra", "22222222", "AAB", "LOTE-ROLES")

    data = client.get("/api/reports/dni-summary", params={"lote_codigo": "LOTE-ROLES"}).json()
    assert data["totals"] == {
        "total_lecturas": 4,
        "emp_lecturas": 2,
        "sel_lecturas": 2,
        "sin_rol_lecturas": 0,
    }
    by_dni = {row["dni"]: row for row in data["rows"]}
    assert by_dni["11111111"]["empacador"] == 1
    assert by_dni["11111111"]["seleccionador"] == 1
    assert by_dni["22222222"]["empacador"] == 1
    assert by_dni["22222222"]["seleccionador"] == 1

    # Totales y tabla deben salir del mismo conjunto.
    assert sum(row["total"] for row in data["rows"]) == data["totals"]["total_lecturas"]
    assert sum(row["empacador"] for row in data["rows"]) == data["totals"]["emp_lecturas"]
    assert sum(row["seleccionador"] for row in data["rows"]) == data["totals"]["sel_lecturas"]

    operators = client.get("/api/reports/operator-summary", params={"lote_codigo": "LOTE-ROLES"}).json()
    assert sum(row["total"] for row in operators["rows"]) == data["totals"]["total_lecturas"]


def test_missing_raw_is_counted_and_codes_are_trimmed(client, session_factory):
    _worker(session_factory, "12345678", "EMPACADORA", 1, "AAA")

    _upload(client, session_factory, "sin-raw", "12345678", "", "LOTE-NORMALIZA", raw=False)
    _upload(client, session_factory, "con-espacios", "12345678", " 001 ", "LOTE-NORMALIZA")

    data = client.get("/api/reports/dni-summary", params={"lote_codigo": "LOTE-NORMALIZA"}).json()
    assert data["totals"]["total_lecturas"] == 2
    assert data["totals"]["emp_lecturas"] == 1
    assert data["totals"]["sin_rol_lecturas"] == 1
    assert data["rows"][0]["codigo"] == "001"

    operators = client.get("/api/reports/operator-summary", params={"lote_codigo": "LOTE-NORMALIZA"}).json()
    assert sum(row["total"] for row in operators["rows"]) == data["totals"]["total_lecturas"]


def test_all_views_classify_codes_without_worker_record_and_keep_unknowns(client, session_factory, engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("Los reportes requieren PostgreSQL")
    with session_factory() as db:
        lot = Lote(codigo="CODIGOS", estado="ABIERTO")
        db.add(lot)
        db.flush()
        for index, marker in enumerate([" 001 ", " aa ", "B9", "?", "", None]):
            db.add(ScanEvent(
                token=f"class-{index}", dni="87654321", lote_id=lot.id,
                raw={"id": marker, "p": "UVA"}, scanned_at=datetime(2026, 1, 5, 17),
                user_id="op", session_uuid="codes",
            ))
        db.commit()
    result = client.get("/api/reports/dni-summary", params={"lote_codigo": "CODIGOS", "producto": "UVA"}).json()
    assert result["totals"] == {
        "total_lecturas": 6, "emp_lecturas": 1, "sel_lecturas": 2, "sin_rol_lecturas": 3,
    }
    for endpoint in (
        "cajas-por-dia", "cajas-por-hora", "eficiencia-personal",
        "eficiencia-por-dia", "produccion-persona-lote",
    ):
        response = client.get(f"/api/dashboard/{endpoint}", params={"lote_codigo": "CODIGOS"})
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert sum(row["empacadas"] for row in rows) == 1
        assert sum(row["seleccionadas"] for row in rows) == 2
        assert sum(row["sin_rol"] for row in rows) == 3
        assert sum(row.get("total", row.get("total_cajas", 0)) for row in rows) == 6
    recent = client.get("/api/dashboard/actividad-reciente", params={"lote_codigo": "CODIGOS"}).json()["rows"]
    assert [row["tipo"] for row in recent].count("Empacada") == 1
    assert [row["tipo"] for row in recent].count("Seleccionada") == 2
    assert [row["tipo"] for row in recent].count("Sin rol") == 3
