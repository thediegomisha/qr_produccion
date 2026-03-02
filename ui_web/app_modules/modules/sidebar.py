import streamlit as st


def render_user_sidebar(
    usuario: str,
    rol: str,
    section_ids: list[str],
    label_for_section,
    app_version: str,
) -> tuple[str, bool]:
    st.sidebar.markdown(
        f"""
        <div class="user-panel">
          <div class="user-label">Usuario activo</div>
          <div class="user-name">{usuario}</div>
          <div class="user-role">Rol: {rol}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not section_ids:
        st.sidebar.warning("No hay secciones disponibles para este rol")
        st.sidebar.markdown("---")
        logout_clicked = st.sidebar.button("Cerrar sesión", key="btn_logout_sidebar", type="primary")
        return "", logout_clicked

    current = st.session_state.get("main_sidebar_nav")
    if current not in section_ids:
        st.session_state.main_sidebar_nav = section_ids[0]

    selected = st.sidebar.radio(
        "Secciones",
        section_ids,
        key="main_sidebar_nav",
        format_func=label_for_section,
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div class='app-version'>Version: {app_version}</div>",
        unsafe_allow_html=True,
    )
    logout_clicked = st.sidebar.button("Cerrar sesión", key="btn_logout_sidebar", type="primary")
    return selected, logout_clicked
