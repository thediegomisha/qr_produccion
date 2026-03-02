from .users_page import render as render_users
from .listar_page import render as render_listar
from .consultas_page import render as render_consultas
from .trabajadores_page import render as render_trabajadores
from .impresion_page import render as render_impresion
from .impresoras_page import render as render_impresoras
from .reportes_page import render as render_reportes
from .lotes_page import render as render_lotes
from .vigilancia_page import render as render_vigilancia
from .navigation import (
    SECTION_CONSULTAS,
    SECTION_IMPRESION,
    SECTION_IMPRESORAS,
    SECTION_LISTAR,
    SECTION_LOTES,
    SECTION_REPORTES,
    SECTION_TRABAJADORES,
    SECTION_USERS,
    SECTION_VIGILANCIA,
)

def render_sections(
    st,
    tabs,
    selected_tab,
    rol,
    API,
    auth_headers,
    api_get,
    api_post,
    api_put,
    api_delete,
    flash_show,
    flash_set,
    get_jwt,
    show_printers_panel,
    COLUMNAS_LISTADO,
    COLUMNAS_IMPRESION,
):
    kwargs = dict(
        st=st,
        tabs=tabs,
        selected_tab=selected_tab,
        rol=rol,
        API=API,
        auth_headers=auth_headers,
        api_get=api_get,
        api_post=api_post,
        api_put=api_put,
        api_delete=api_delete,
        flash_show=flash_show,
        flash_set=flash_set,
        get_jwt=get_jwt,
        show_printers_panel=show_printers_panel,
        COLUMNAS_LISTADO=COLUMNAS_LISTADO,
        COLUMNAS_IMPRESION=COLUMNAS_IMPRESION,
    )

    section_renderers = {
        SECTION_USERS: render_users,
        SECTION_LISTAR: render_listar,
        SECTION_CONSULTAS: render_consultas,
        SECTION_TRABAJADORES: render_trabajadores,
        SECTION_IMPRESION: render_impresion,
        SECTION_IMPRESORAS: render_impresoras,
        SECTION_REPORTES: render_reportes,
        SECTION_LOTES: render_lotes,
        SECTION_VIGILANCIA: render_vigilancia,
    }

    renderer = section_renderers.get(selected_tab)
    if renderer is None:
        st.warning("La sección seleccionada no está disponible para este usuario.")
        st.caption(f"Selección recibida: {selected_tab!r}")
        st.caption("Opciones válidas:")
        st.code("\n".join(repr(s) for s in section_renderers.keys()))
        return

    renderer(**kwargs)
