import pytest


@pytest.mark.parametrize("role", ["ROOT", "GERENCIA", "SUPERVISOR", "OPERADOR", "AGENTE", "VIGILANCIA"])
def test_all_users_see_consolidated_lot_and_new_uploads(client, user, role):
    def upload(operator, token, lot="LOTE-COMPARTIDO"):
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
    assert response.json()["rows"][0]["total"] == 2
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


def test_lot_report_without_dates_includes_all_days_and_distinct_worker_codes(client):
    for token, codigo, date in [("numeric", "007", "2026-11-13"), ("letter", "A", "2026-11-14")]:
        response = client.post("/api/scans/batch", json={
            "batch_uuid": token, "lote_codigo": "LOTE-MULTIDIA",
            "scans": [{
                "token": token, "dni": "12345678", "scanned_at": f"{date}T15:00:00Z",
                "raw": {"id": codigo, "p": "UVA"},
            }],
        })
        assert response.status_code == 200
    data = client.get("/api/reports/dni-summary", params={"lote_codigo": "LOTE-MULTIDIA"}).json()
    assert data["date_from"] is None and data["date_to"] is None
    assert data["totals"]["total_lecturas"] == 2
    assert data["rows"][0]["codigo"] == "007, A"
    assert data["rows"][0]["empacador"] == 1
    assert data["rows"][0]["seleccionador"] == 1
