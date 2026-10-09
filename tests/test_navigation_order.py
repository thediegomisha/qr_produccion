from app_modules.modules.navigation import (
    SECTION_DASHBOARD,
    sections_for_role,
)


def test_dashboard_is_the_first_tab_for_manager_roles():
    for role in ("ROOT", "GERENCIA", "SUPERVISOR"):
        assert sections_for_role(role)[0] == SECTION_DASHBOARD, role


def test_dashboard_is_first_and_all_sections_are_still_present():
    gerencia = sections_for_role("GERENCIA")
    assert gerencia[0] == SECTION_DASHBOARD
    assert len(gerencia) == 11  # no se perdió ninguna sección al reordenar
    supervisor = sections_for_role("SUPERVISOR")
    assert supervisor[0] == SECTION_DASHBOARD
    assert len(supervisor) == 8


def test_vigilancia_and_operador_keep_their_own_tabs():
    assert sections_for_role("VIGILANCIA")[0] == "vigilancia"
    assert SECTION_DASHBOARD not in sections_for_role("VIGILANCIA")
    assert SECTION_DASHBOARD not in sections_for_role("OPERADOR")
    assert sections_for_role("OPERADOR")[0] == "impresion"
