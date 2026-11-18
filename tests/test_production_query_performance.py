from datetime import datetime

import pytest

from app.api import routes_dashboard, routes_reports
from app.db.models import Lote, ScanEvent, Trabajador
from app.services.production_sql import production_cte


def test_worker_lookup_is_not_correlated_per_scan():
    query = production_cte()
    assert "LATERAL" not in query
    assert "DISTINCT ON (TRIM(tw.dni))" in query
    assert "ORDER BY TRIM(tw.dni), tw.activo DESC, tw.id" in query
    assert "trabajadores" not in production_cte(include_workers=False)


@pytest.mark.parametrize("module,path", [
    (routes_reports, "/api/reports/operator-summary"),
    (routes_dashboard, "/api/dashboard/cajas-por-dia"),
    (routes_dashboard, "/api/dashboard/cajas-por-hora"),
])
def test_aggregate_routes_skip_worker_lookup(client, engine, monkeypatch, module, path):
    if engine.dialect.name != "postgresql":
        pytest.skip("Los reportes requieren PostgreSQL")
    calls = []
    def track(*, include_workers=True):
        calls.append(include_workers)
        return production_cte(include_workers=include_workers)
    monkeypatch.setattr(module, "production_cte", track)
    assert client.get(path).status_code == 200
    assert calls == [False]


def test_trimmed_worker_duplicates_preserve_active_first_and_do_not_multiply_reads(
    client, session_factory, engine,
):
    if engine.dialect.name != "postgresql":
        pytest.skip("DISTINCT ON requiere PostgreSQL")
    with session_factory() as db:
        lot = Lote(codigo="LEGACY-DNI", estado="ABIERTO")
        db.add(lot)
        db.flush()
        # DNIs antiguos de siete cifras: las variantes caben en VARCHAR(8).
        # La selección debe ser idéntica a ORDER BY activo DESC, id LIMIT 1.
        for index, dni, active, surname in [
            (1, "1234567", False, "ANTIGUA"),
            (2, "1234567 ", True, "ACTIVA"),
            (3, " 1234567", True, "POSTERIOR"),
        ]:
            db.add(Trabajador(
                dni=dni, nombre="ANA", apellido_paterno=surname,
                rol="EMPACADORA", num_orden=index, cod_letra=f"A{index}", activo=active,
            ))
        for index, code in enumerate(("001", "ABC")):
            db.add(ScanEvent(
                token=f"legacy-{index}", dni="1234567", lote_id=lot.id,
                scanned_at=datetime(2026, 1, 1, 12),
                raw={"id": code, "p": "UVA"},
            ))
        db.commit()
    response = client.get("/api/reports/dni-summary", params={
        "lote_codigo": "LEGACY-DNI", "producto": "UVA",
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["persona"].startswith("ACTIVA ")
    assert row["rol"] == "EMPACADORA"
    assert row["empacador"] == row["seleccionador"] == 1
    assert row["total"] == data["totals"]["total_lecturas"] == 2
