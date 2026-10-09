from datetime import date, timedelta

import altair as alt
import pandas as pd

# Paleta estilo Plecto: números grandes en tarjetas y colores vivos.
_COLOR_EMPACADAS = "#00b3f4"
_COLOR_SELECCIONADAS = "#ffb100"
_COLOR_KPI = ["#00b3f4", "#58cf42", "#ffb100", "#9947ff", "#ff4747"]
_MEDALS = ["🥇", "🥈", "🥉"]
_LEADER_COLORS = ["#FFD700", "#C0C0C0", "#CD7F32"]


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


def _kpi_card(label: str, value, color: str) -> str:
    """Tarjeta KPI estilo Plecto: etiqueta pequeña y número grande resaltado."""
    return (
        f'<div style="background: linear-gradient(135deg, {color}1f 0%, {color}0d 100%);'
        f'border-left: 5px solid {color}; border-radius: 12px; padding: 14px 16px;">'
        f'<div style="color: #8a8f98; font-size: 12px; font-weight: 700;'
        f'text-transform: uppercase; letter-spacing: 0.6px;">{label}</div>'
        f'<div style="color: {color}; font-size: 34px; font-weight: 800;'
        f'line-height: 1.15; margin-top: 2px;">{value}</div>'
        f'</div>'
    )


def _leaderboard_html(top: pd.DataFrame, limit: int = 10) -> str:
    """Ranking estilo Plecto: medallas para el top 3 y cajas/cajas-hora destacados."""
    rows = []
    for rank, entry in enumerate(top.head(limit).itertuples()):
        medal = _MEDALS[rank] if rank < len(_MEDALS) else f"<b>{rank + 1}</b>"
        color = _LEADER_COLORS[rank] if rank < len(_LEADER_COLORS) else "#4e8df5"
        rows.append(
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'padding: 8px 14px; border-radius: 10px; margin: 3px 0;'
            f'background: {color}12; border-left: 4px solid {color};">'
            f'<div style="font-size: 15px;"><span style="margin-right: 8px;">{medal}</span>{entry.persona}</div>'
            f'<div style="font-size: 14px; color: #444;">'
            f'<b style="font-size: 17px; color: {color};">{entry.total_cajas}</b> cajas'
            f'&nbsp;·&nbsp; {entry.cajas_por_hora}/h</div>'
            f'</div>'
        )
    return "".join(rows)


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

    cajas = _request(st, api_get, "/dashboard/cajas-por-dia", params)
    efficiency = _request(st, api_get, "/dashboard/eficiencia-personal", params)
    if cajas is None or efficiency is None:
        return

    cajas_rows = cajas.get("rows", [])
    eff_rows = efficiency.get("rows", [])
    df_dia = pd.DataFrame(cajas_rows) if cajas_rows else pd.DataFrame()
    df_eff = pd.DataFrame(eff_rows) if eff_rows else pd.DataFrame()

    total = int(df_dia["total"].sum()) if not df_dia.empty else 0
    emp = int(df_dia["empacadas"].sum()) if not df_dia.empty else 0
    sel = int(df_dia["seleccionadas"].sum()) if not df_dia.empty else 0
    personas = len(eff_rows)
    dias = df_dia["dia"].nunique() if not df_dia.empty else 0

    # ---------- KPIs estilo Plecto ----------
    kpis = [
        ("Cajas totales", total),
        ("Empacadas", emp),
        ("Seleccionadas", sel),
        ("Personas activas", personas),
        ("Días trabajados", int(dias)),
    ]
    kpi_columns = st.columns(5)
    for column, (label, value), color in zip(kpi_columns, kpis, _COLOR_KPI):
        column.markdown(_kpi_card(label, value, color), unsafe_allow_html=True)

    if df_dia.empty:
        st.info("No hay lecturas en el rango seleccionado.")
        return

    # ---------- Gráfica principal: cajas por LOTE ----------
    st.markdown("### Cajas por lote")
    st.caption("Barras apiladas por lote: cajas empacadas y seleccionadas en el rango filtrado.")
    per_lot = df_dia.groupby("lote", as_index=False)[["empacadas", "seleccionadas"]].sum()
    per_lot["total"] = per_lot["empacadas"] + per_lot["seleccionadas"]
    per_lot = per_lot.sort_values("total", ascending=True)

    stacked = per_lot.melt(
        id_vars="lote",
        value_vars=["empacadas", "seleccionadas"],
        var_name="tipo",
        value_name="cajas",
    )
    stacked["tipo"] = stacked["tipo"].map({"empacadas": "Empacadas", "seleccionadas": "Seleccionadas"})
    stacked["orden"] = stacked["tipo"].map({"Empacadas": 0, "Seleccionadas": 1})

    chart_lot = (
        alt.Chart(stacked)
        .mark_bar()
        .encode(
            y=alt.Y("lote:N", sort=list(per_lot["lote"]), title="Lote"),
            x=alt.X("cajas:Q", title="Cajas"),
            color=alt.Color(
                "tipo:N",
                scale=alt.Scale(
                    domain=["Empacadas", "Seleccionadas"],
                    range=[_COLOR_EMPACADAS, _COLOR_SELECCIONADAS],
                ),
                title="Tipo",
            ),
            order=alt.Order("orden:Q", sort="ascending"),
            tooltip=["lote:N", "tipo:N", "cajas:Q"],
        )
        .properties(height=max(140, 34 * len(per_lot)))
    )
    st.altair_chart(chart_lot, width="stretch")
    st.dataframe(
        per_lot[["lote", "total", "empacadas", "seleccionadas"]]
        .sort_values("total", ascending=False),
        hide_index=True,
        width="stretch",
    )

    # ---------- Eficiencia del personal (ranking estilo Plecto) ----------
    st.divider()
    st.markdown("### Eficiencia del personal")
    if df_eff.empty:
        st.info("Sin datos de eficiencia en el rango seleccionado.")
        return

    st.caption(
        "Eficiencia = cajas por hora activa (tiempo entre la primera y última lectura de cada sesión, "
        "con un mínimo de 1 minuto por sesión escaneada)."
    )
    top = df_eff.sort_values("total_cajas", ascending=False).reset_index(drop=True)
    st.markdown(_leaderboard_html(top), unsafe_allow_html=True)

    st.markdown("#### Cajas por hora")
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
    st.altair_chart(chart_rate, width="stretch")

    st.dataframe(
        top[[
            "dni", "persona", "rol_trabajador", "total_cajas", "empacadas", "seleccionadas",
            "dias_trabajados", "sesiones", "horas_activas", "cajas_por_hora",
        ]],
        hide_index=True,
        width="stretch",
    )

    # ---------- Vista secundaria: cajas por día ----------
    st.divider()
    with st.expander("Cajas por día (vista secundaria)"):
        st.markdown("#### Cajas por día")
        st.caption("Distribución diaria de empacadas y seleccionadas en el rango filtrado.")
        df_dia["dia"] = pd.to_datetime(df_dia["dia"]).dt.date
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
                color=alt.Color(
                    "tipo:N",
                    scale=alt.Scale(
                        domain=["Empacadas", "Seleccionadas"],
                        range=[_COLOR_EMPACADAS, _COLOR_SELECCIONADAS],
                    ),
                    title="Tipo",
                ),
                xOffset="tipo:N",
                tooltip=["dia:T", "tipo:N", "cajas:Q"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart_day, width="stretch")
