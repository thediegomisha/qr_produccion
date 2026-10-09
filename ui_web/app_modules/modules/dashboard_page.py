from datetime import date, timedelta

import altair as alt
import pandas as pd


def _request(st, api_get, path, params):
    response = api_get(path, params=params)
    try:
        data = response.json()
    except ValueError:
        st.error(f"La API no devolvió JSON (HTTP {response.status_code}).")
        return None
    if not 200 <= response.status_code < 300:
        detail = data.get("detail", "Error") if isinstance(data, dict) else data
        st.error(f"Error {response.status_code}: {detail}")
        return None
    if not isinstance(data, dict):
        st.error("Respuesta inesperada de la API.")
        return None
    return data


def _empty(state_from: date, state_to: date):
    return pd.DataFrame(columns=["dia", "lote", "total", "empacadas", "seleccionadas"])


def render(
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
    st.subheader("Dashboard de producción")

    if (rol or "").upper() not in ("ROOT", "GERENCIA", "SUPERVISOR"):
        st.error("No tienes permisos para ver el dashboard.")
        return

    today = date.today()
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        date_from = st.date_input("Desde", value=today - timedelta(days=7), key="dashboard_desde")
    with col_f2:
        date_to = st.date_input("Hasta", value=today, key="dashboard_hasta")
    with col_f3:
        lotes_data = _request(st, api_get, "/lotes", {"limit": 200})
        lotes_items = (lotes_data or {}).get("items", [])
        codigos = [item["codigo"] for item in lotes_items]
        lote_filter = st.selectbox("Lote", ["TODOS", *codigos], key="dashboard_lote")

    if date_to < date_from:
        st.warning("La fecha final debe ser mayor o igual a la inicial.")
        return

    params = {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "lote_codigo": None if lote_filter == "TODOS" else lote_filter,
    }

    # ---------- KPIs ----------
    cajas = _request(st, api_get, "/dashboard/cajas-por-dia", params)
    efficiency = _request(st, api_get, "/dashboard/eficiencia-personal", params)
    if cajas is None or efficiency is None:
        return

    cajas_rows = cajas.get("rows", [])
    eff_rows = efficiency.get("rows", [])

    df_dia = pd.DataFrame(cajas_rows) if cajas_rows else _empty(date_from, date_to)
    df_eff = pd.DataFrame(eff_rows) if eff_rows else pd.DataFrame()

    total = int(df_dia["total"].sum()) if not df_dia.empty else 0
    emp = int(df_dia["empacadas"].sum()) if not df_dia.empty else 0
    sel = int(df_dia["seleccionadas"].sum()) if not df_dia.empty else 0
    personas = len(eff_rows)
    dias = df_dia["dia"].nunique() if not df_dia.empty else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Cajas totales", total)
    k2.metric("Empacadas", emp)
    k3.metric("Seleccionadas", sel)
    k4.metric("Personas activas", personas)
    k5.metric("Días trabajados", int(dias))

    if df_dia.empty:
        st.info("No hay lecturas en el rango seleccionado.")
        return

    df_dia["dia"] = pd.to_datetime(df_dia["dia"]).dt.date

    st.divider()
    st.markdown("### Cajas por día")
    per_day = (
        df_dia.groupby("dia", as_index=False)[["empacadas", "seleccionadas"]].sum()
        .melt("dia", var_name="tipo", value_name="cajas")
        .replace({"tipo": {"empacadas": "Empacadas", "seleccionadas": "Seleccionadas"}})
    )
    chart_day = (
        alt.Chart(per_day)
        .mark_bar()
        .encode(
            x=alt.X("dia:T", title="Día"),
            y=alt.Y("cajas:Q", title="Cajas"),
            color=alt.Color("tipo:N", title="Tipo"),
            xOffset="tipo:N",
            tooltip=["dia:T", "tipo:N", "cajas:Q"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart_day, use_container_width=True)

    st.markdown("### Cajas por lote")
    per_lot = df_dia.groupby("lote", as_index=False)[["total", "empacadas", "seleccionadas"]].sum().sort_values("total", ascending=False)
    chart_lot = (
        alt.Chart(per_lot)
        .mark_bar()
        .encode(
            x=alt.X("total:Q", title="Cajas"),
            y=alt.Y("lote:N", sort="-x", title="Lote"),
            tooltip=["lote:N", "total:Q", "empacadas:Q", "seleccionadas:Q"],
        )
        .properties(height=max(160, 32 * len(per_lot)))
    )
    st.altair_chart(chart_lot, use_container_width=True)
    st.dataframe(per_lot, hide_index=True, width="stretch")

    st.divider()
    st.markdown("### Eficiencia del personal")
    if df_eff.empty:
        st.info("Sin datos de eficiencia en el rango seleccionado.")
        return

    st.caption(
        "Eficiencia = cajas por hora activa (tiempo entre la primera y última lectura de cada sesión, "
        "con un mínimo de 1 minuto por sesión escaneada)."
    )

    top = df_eff.sort_values("total_cajas", ascending=False)
    chart_eff = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            x=alt.X("total_cajas:Q", title="Cajas procesadas"),
            y=alt.Y("persona:N", sort="-x", title="Trabajador"),
            color=alt.Color("rol_trabajador:N", title="Rol"),
            tooltip=["persona:N", "rol_trabajador:N", "total_cajas:Q", "cajas_por_hora:Q",
                     "empacadas:Q", "seleccionadas:Q", "dias_trabajados:Q", "horas_activas:Q"],
        )
        .properties(height=max(160, 28 * len(top)))
    )
    st.altair_chart(chart_eff, use_container_width=True)

    st.markdown("### Eficiencia (cajas por hora)")
    chart_rate = (
        alt.Chart(top)
        .mark_line(point=True)
        .encode(
            x=alt.X("persona:N", sort="-y", title="Trabajador"),
            y=alt.Y("cajas_por_hora:Q", title="Cajas/hora"),
            tooltip=["persona:N", "cajas_por_hora:Q", "horas_activas:Q", "total_cajas:Q"],
        )
        .properties(height=300)
    )
    st.altair_chart(chart_rate, use_container_width=True)

    st.dataframe(
        top[[
            "dni", "persona", "rol_trabajador", "total_cajas", "empacadas", "seleccionadas",
            "dias_trabajados", "sesiones", "horas_activas", "cajas_por_hora",
        ]],
        hide_index=True,
        width="stretch",
    )
