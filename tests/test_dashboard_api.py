from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.models import Lote, ScanEvent, Trabajador


def _make_scan(db, token, dni, lote_id, scanned_at, marker, user_id="op1", session_uuid="s1"):
    # Igual que el backend: almacenar UTC explícito en columna sin zona horaria.
    scanned_at = scanned_at.astimezone(timezone.utc).replace(tzinfo=None)
    db.add(ScanEvent(
        token=token,
        dni=dni,
        lote_id=lote_id,
        scanned_at=scanned_at,
        raw={"id": marker, "p": "PALTA"},
        user_id=user_id,
        session_uuid=session_uuid,
    ))


@pytest.fixture
def seeded(engine, session_factory):
    """Escenario: dos lotes, dos días y dos trabajadores con medidas conocidas."""
    if engine.dialect.name != "postgresql":
        pytest.skip("El dashboard requiere PostgreSQL")

    with session_factory() as db:
        lot_a = Lote(codigo="LOTE-A", estado="CERRADO")
        lot_b = Lote(codigo="LOTE-B", estado="ABIERTO")
        db.add_all([lot_a, lot_b])
        db.flush()

        db.add(Trabajador(dni="11111111", nombre="ANA", apellido_paterno="PEREZ",
                          apellido_materno="RUIZ", rol="EMPACADOR", num_orden=1, cod_letra="A001", activo=True))
        db.add(Trabajador(dni="22222222", nombre="LUIS", apellido_paterno="SOTO",
                          apellido_materno=None, rol="SELECCIONADOR", num_orden=2, cod_letra="B001", activo=True))

        day1_noon = datetime(2026, 1, 5, 17, 0, tzinfo=timezone.utc)  # 12:00 Lima
        day1_late = datetime(2026, 1, 5, 19, 0, tzinfo=timezone.utc)  # 14:00 Lima
        day2 = datetime(2026, 1, 6, 17, 0, tzinfo=timezone.utc)

        _make_scan(db, "t1", "11111111", lot_a.id, day1_noon, "12", session_uuid="a-s1")
        _make_scan(db, "t2", "11111111", lot_a.id, day1_late, "13", session_uuid="a-s1")  # 2h activas
        _make_scan(db, "t3", "22222222", lot_a.id, day1_noon, "AB", session_uuid="b-s1")
        _make_scan(db, "t4", "11111111", lot_b.id, day2, "14", session_uuid="a-s2")
        db.commit()
        return {"lot_a": lot_a.id, "lot_b": lot_b.id}


def test_code_defines_classification_even_when_registered_role_differs(client, session_factory, engine):
    """Las letras cuentan como selección y los números como empacado."""
    if engine.dialect.name != "postgresql":
        pytest.skip("El dashboard requiere PostgreSQL")
    lot_a = Lote(codigo="MIX-A", estado="ABIERTO")
    with session_factory() as db:
        db.add(lot_a)
        db.flush()
        db.add_all([
            Trabajador(dni="11111111", nombre="ANA", apellido_paterno="PEREZ",
                       apellido_materno=None, rol="EMPACADORA", num_orden=1,
                       cod_letra="AAA", activo=True),
            Trabajador(dni="22222222", nombre="LUIS", apellido_paterno="SOTO",
                       apellido_materno=None, rol="SELECCIONADOR", num_orden=2,
                       cod_letra="AAB", activo=True),
        ])
        # Códigos de letra para la empacadora y numéricos para el seleccionador:
        # la forma del código debe definir la tarea, no el rol registrado.
        _make_scan(db, "mix1", "11111111", lot_a.id, datetime(2026, 1, 5, 17, 0, tzinfo=timezone.utc), "A001")
        _make_scan(db, "mix2", "11111111", lot_a.id, datetime(2026, 1, 5, 18, 0, tzinfo=timezone.utc), "M015")
        _make_scan(db, "mix3", "22222222", lot_a.id, datetime(2026, 1, 5, 17, 0, tzinfo=timezone.utc), "63")
        _make_scan(db, "mix4", "22222222", lot_a.id, datetime(2026, 1, 5, 17, 0, tzinfo=timezone.utc), "100")
        db.commit()

    rows = client.get("/api/dashboard/cajas-por-dia").json()["rows"]
    fila = next(r for r in rows if r["lote"] == "MIX-A")
    assert fila["total"] == 4
    assert fila["empacadas"] == 2
    assert fila["seleccionadas"] == 2
    assert fila["sin_rol"] == 0
    by_dni = {
        row["dni"]: row for row in client.get("/api/dashboard/eficiencia-personal").json()["rows"]
    }
    assert by_dni["11111111"]["seleccionadas"] == 2
    assert by_dni["11111111"]["empacadas"] == 0
    assert by_dni["22222222"]["empacadas"] == 2
    assert by_dni["22222222"]["seleccionadas"] == 0


def test_dashboard_rejects_operators(client, user):
    user["rol"] = "OPERADOR"
    assert client.get("/api/dashboard/cajas-por-dia").status_code == 403
    assert client.get("/api/dashboard/eficiencia-personal").status_code == 403
    assert client.get("/api/dashboard/eficiencia-por-dia").status_code == 403


def test_cajas_por_dia_groups_by_local_day_and_lote(client, seeded):
    result = client.get("/api/dashboard/cajas-por-dia")
    assert result.status_code == 200
    rows = result.json()["rows"]
    day1 = [r for r in rows if r["dia"] == "2026-01-05" and r["lote"] == "LOTE-A"][0]
    assert day1["total"] == 3
    assert day1["empacadas"] == 2
    assert day1["seleccionadas"] == 1
    day2 = [r for r in rows if r["dia"] == "2026-01-06" and r["lote"] == "LOTE-B"][0]
    assert day2["total"] == 1 and day2["empacadas"] == 1

    filtered = client.get("/api/dashboard/cajas-por-dia", params={"lote_codigo": "LOTE-B"}).json()["rows"]
    assert len(filtered) == 1 and filtered[0]["lote"] == "LOTE-B"
    dated = client.get("/api/dashboard/cajas-por-dia",
                       params={"date_from": "2026-01-06", "date_to": "2026-01-06"}).json()["rows"]
    assert len(dated) == 1 and dated[0]["dia"] == "2026-01-06"


def test_eficiencia_personal_computes_boxes_per_active_hour(client, seeded):
    rows = client.get("/api/dashboard/eficiencia-personal").json()["rows"]
    ana = next(r for r in rows if r["dni"] == "11111111")
    assert ana["persona"] == "PEREZ RUIZ ANA"
    assert ana["total_cajas"] == 3
    assert ana["empacadas"] == 3
    assert ana["dias_trabajados"] == 2
    assert ana["sesiones"] == 2
    # sesión 1: 2 cajas en 2 horas; sesión 2: 1 caja en 1 minuto (piso)
    assert abs(ana["horas_activas"] - (2.0 + 1.0 / 60.0)) < 0.01
    assert abs(ana["cajas_por_hora"] - (3.0 / (2.0 + 1.0 / 60.0))) < 0.05


def test_eficiencia_personal_separates_hours_for_both_tasks(client, session_factory, seeded):
    """Cada tarea conserva sus lecturas y horas aunque pertenezcan al mismo DNI."""
    with session_factory() as db:
        db.add(Trabajador(dni="33333333", nombre="CARLOS", apellido_paterno="QUISPE",
                          apellido_materno=None, rol="EMPACADORA", num_orden=30,
                          cod_letra="BDZ", activo=True))
        lot_a = db.get(Lote, seeded["lot_a"])
        base = datetime(2026, 1, 7, 17, 0, tzinfo=timezone.utc)  # 12:00 en Lima
        _make_scan(db, "m1", "33333333", lot_a.id, base, "10", session_uuid="mix-1")
        _make_scan(db, "m2", "33333333", lot_a.id, base + timedelta(hours=1), "11", session_uuid="mix-1")
        _make_scan(db, "m3", "33333333", lot_a.id, base + timedelta(hours=2), "AB", session_uuid="mix-1")
        _make_scan(db, "m4", "33333333", lot_a.id, base + timedelta(hours=3), "AC", session_uuid="mix-1")
        db.commit()

    rows = client.get("/api/dashboard/eficiencia-personal").json()["rows"]
    mixto = next(r for r in rows if r["dni"] == "33333333")
    assert mixto["rol_trabajador"] == "EMPACADORA"
    assert mixto["empacadas"] == 2 and mixto["seleccionadas"] == 2
    assert mixto["sin_rol"] == 0
    assert mixto["total_cajas"] == 4
    assert mixto["sesiones"] == 1 and mixto["dias_trabajados"] == 1
    assert abs(mixto["horas_empacado"] - 1.0) < 0.01
    assert abs(mixto["horas_seleccion"] - 1.0) < 0.01
    assert abs(mixto["horas_activas"] - 3.0) < 0.01
    assert abs(mixto["empacadas_por_hora"] - 2.0) < 0.05
    assert abs(mixto["seleccionadas_por_hora"] - 2.0) < 0.05


def test_eficiencia_personal_mantiene_a_quien_solo_selecciona(client, session_factory, seeded):
    """Quien solo selecciona tiene empacadas=0 pero debe seguir apareciendo con
    sus cajas y su ritmo de selección (el dashboard lo oculta si solo rankea empacadas)."""
    with session_factory() as db:
        db.add(Trabajador(dni="44444444", nombre="ROSA", apellido_paterno="FLORES",
                          apellido_materno=None, rol="SELECCIONADOR", num_orden=44,
                          cod_letra="BEA", activo=True))
        lot_a = db.get(Lote, seeded["lot_a"])
        base = datetime(2026, 1, 8, 17, 0, tzinfo=timezone.utc)  # 12:00 en Lima
        _make_scan(db, "s1", "44444444", lot_a.id, base, "AA", session_uuid="sel-1")
        _make_scan(db, "s2", "44444444", lot_a.id, base + timedelta(hours=1), "AB", session_uuid="sel-1")
        db.commit()

    rows = client.get("/api/dashboard/eficiencia-personal").json()["rows"]
    selector = next(r for r in rows if r["dni"] == "44444444")
    assert selector["rol_trabajador"] == "SELECCIONADOR"
    assert selector["empacadas"] == 0 and selector["seleccionadas"] == 2
    assert selector["total_cajas"] == 2
    assert abs(selector["horas_seleccion"] - 1.0) < 0.01
    assert abs(selector["seleccionadas_por_hora"] - 2.0) < 0.05


def test_eficiencia_por_dia_groups_rows(client, seeded):
    rows = client.get("/api/dashboard/eficiencia-por-dia",
                      params={"date_from": "2026-01-05", "date_to": "2026-01-05"}).json()["rows"]
    assert len(rows) == 2
    ana = next(r for r in rows if r["persona"] == "PEREZ RUIZ ANA")
    assert ana["total_cajas"] == 2 and ana["empacadas"] == 2
    luis = next(r for r in rows if r["persona"] == "SOTO  LUIS")
    assert luis["seleccionadas"] == 1


def test_eficiencia_por_dia_without_trabajador_for_dni(client, session_factory, seeded):
    with session_factory() as db:
        lot_a = db.get(Lote, seeded["lot_a"])
        _make_scan(db, "t9", "99999999", lot_a.id, datetime(2026, 1, 5, 18, 0, tzinfo=timezone.utc), "77")
        db.commit()
    rows = client.get("/api/dashboard/eficiencia-personal").json()["rows"]
    unknown = next(r for r in rows if r["dni"] == "99999999")
    assert unknown["persona"] == "SIN REGISTRO"
    assert unknown["rol_trabajador"] == "DESCONOCIDO"


def test_cajas_por_hora_groups_by_local_hour(client, seeded):
    rows = client.get("/api/dashboard/cajas-por-hora",
                      params={"date_from": "2026-01-05", "date_to": "2026-01-05"}).json()["rows"]
    por_hora = {r["hora"]: r for r in rows}
    assert por_hora[12]["total"] == 2
    assert por_hora[12]["empacadas"] == 1
    assert por_hora[12]["seleccionadas"] == 1
    assert por_hora[14]["total"] == 1 and por_hora[14]["empacadas"] == 1
    todos = client.get("/api/dashboard/cajas-por-hora").json()["rows"]
    assert sum(r["total"] for r in todos) == 4


def test_produccion_persona_lote_builds_matrix(client, seeded):
    rows = client.get("/api/dashboard/produccion-persona-lote").json()["rows"]
    matriz = {(r["persona"], r["lote"]): r for r in rows}
    ana_a = matriz[("PEREZ RUIZ ANA", "LOTE-A")]
    assert ana_a["total"] == 2 and ana_a["empacadas"] == 2 and ana_a["seleccionadas"] == 0
    luis_a = matriz[("SOTO  LUIS", "LOTE-A")]
    assert luis_a["total"] == 1 and luis_a["seleccionadas"] == 1
    ana_b = matriz[("PEREZ RUIZ ANA", "LOTE-B")]
    assert ana_b["total"] == 1 and ana_b["empacadas"] == 1
    filtrado = client.get("/api/dashboard/produccion-persona-lote",
                          params={"lote_codigo": "LOTE-B"}).json()["rows"]
    assert len(filtrado) == 1 and filtrado[0]["lote"] == "LOTE-B"


def test_actividad_reciente_returns_latest_first(client, seeded):
    rows = client.get("/api/dashboard/actividad-reciente").json()["rows"]
    assert len(rows) == 4
    assert rows[0]["token"] == "t4" and rows[0]["lote"] == "LOTE-B"
    assert rows[0]["tipo"] == "Empacada"
    assert rows[0]["persona"] == "PEREZ RUIZ ANA"
    por_lote = client.get("/api/dashboard/actividad-reciente",
                          params={"lote_codigo": "LOTE-A"}).json()["rows"]
    assert len(por_lote) == 3 and all(r["lote"] == "LOTE-A" for r in por_lote)
    limitado = client.get("/api/dashboard/actividad-reciente", params={"limit": 2}).json()["rows"]
    assert len(limitado) == 2
    fuera_de_rango = client.get("/api/dashboard/actividad-reciente", params={"limit": 0}).status_code == 422


def test_new_dashboard_endpoints_reject_operators(client, user, seeded):
    user["rol"] = "OPERADOR"
    for path in ("/api/dashboard/cajas-por-hora",
                 "/api/dashboard/produccion-persona-lote",
                 "/api/dashboard/actividad-reciente"):
        assert client.get(path).status_code == 403
