import os
import time
from datetime import date, timedelta

import altair as alt
import pandas as pd

# Paleta estilo Plecto: números grandes en tarjetas y colores vivos.
# El EMPACADO es la métrica de producción (base para formar pallets);
# la SELECCIÓN es un concepto distinto y se muestra como referencia.
_COLOR_EMPACADAS = "#00b3f4"
_COLOR_SELECCION = "#ffe08a"  # ámbar claro: visible pero secundario
_COLOR_KPI = ["#00b3f4", "#ffb100", "#9947ff", "#58cf42", "#ff4747"]
_MEDALS = ["🥇", "🥈", "🥉"]
_LEADER_COLORS = ["#FFD700", "#C0C0C0", "#CD7F32"]
_TZ = "America/Lima"
# Intervalo del modo tablero, ajustable según la carga del servidor.
_REFRESH_SECONDS = max(5, int(os.getenv("DASHBOARD_REFRESH_SECONDS", "30")))
_LOTES_CACHE_TTL = 60  # el listado de lotes casi no cambia: refrescar 1 vez por minuto


def _lotes_cacheados(st, api_get):
    """Listado de lotes con caché por sesión para no consultarlo en cada tic."""
    cache = st.session_state.get("_dash_lotes_cache")
    if cache is not None and time.time() - cache[0] < _LOTES_CACHE_TTL:
        return cache[1]
    data = _request(st, api_get, "/lotes", {"limit": 200})
    lotes = (data or {}).get("items", []) if data else []
    st.session_state["_dash_lotes_cache"] = (time.time(), lotes)
    return lotes


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
    """Ranking estilo Plecto priorizando las cajas EMPACADAS (base de pallets);
    la selección se muestra como referencia secundaria."""
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
            f'<b style="font-size: 17px; color: {color};">{entry.empacadas}</b> empacadas'
            f'&nbsp;·&nbsp; <span style="color:#888;">{entry.seleccionadas} selección</span>'
            f'&nbsp;·&nbsp; {entry.cajas_por_hora}/h</div>'
            f'</div>'
        )
    return "".join(rows)


def _activity_html(rows: list) -> str:
    """Feed de actividad reciente estilo Plecto: hora local, persona, lote y tipo."""
    items = []
    for row in rows:
        color = _COLOR_EMPACADAS if row["tipo"] == "Empacada" else "#ffb100"
        hora = pd.to_datetime(row["scanned_at"], utc=True).tz_convert(_TZ).strftime("%H:%M:%S")
        items.append(
            f'<div style="display:flex;align-items:center;gap:10px;padding:6px 12px;margin:3px 0;'
            f'border-radius:8px;background:#f7f8fa;">'
            f'<span style="width:10px;height:10px;border-radius:50%;background:{color};'
            f'display:inline-block;flex-shrink:0;"></span>'
            f'<span style="color:#888;font-size:13px;min-width:72px;">{hora}</span>'
            f'<span style="font-size:14px;font-weight:600;">{row["persona"]}</span>'
            f'<span style="font-size:13px;color:#999;">·</span>'
            f'<span style="font-size:13px;color:#555;">{row["lote"]}</span>'
            f'<span style="margin-left:auto;font-size:12px;color:{color};font-weight:700;">{row["tipo"]}</span>'
            f'</div>'
        )
    return "".join(items)


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

    st.caption(f"⏱️ Actualización automática cada {_REFRESH_SECONDS} segundos (modo tablero).")

    @st.fragment(run_every=_REFRESH_SECONDS)
    def _body():
        today = date.today()

        # ---- Atajos de rango ----
        presets = [
            ("Hoy", today, today),
            ("7 días", today - timedelta(days=6), today),
            ("30 días", today - timedelta(days=29), today),
            ("90 días", today - timedelta(days=89), today),
        ]
        preset_columns = st.columns(4)
        for (label, preset_from, preset_to), column in zip(presets, preset_columns):
            if column.button(label, key=f"dash_preset_{label}", width="stretch"):
                # Rango pendiente: se aplica antes de instanciar los date_input.
                st.session_state["_dash_pending_range"] = (preset_from, preset_to)
                st.rerun()

        pending_range = st.session_state.pop("_dash_pending_range", None)
        if pending_range is not None:
            st.session_state["dashboard_desde"] = pending_range[0]
            st.session_state["dashboard_hasta"] = pending_range[1]

        col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
        with col_f1:
            date_from = st.date_input("Desde", value=today - timedelta(days=7), key="dashboard_desde")
        with col_f2:
            date_to = st.date_input("Hasta", value=today, key="dashboard_hasta")
        with col_f3:
            lotes_items = _lotes_cacheados(st, api_get)
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
        ritmo = _request(st, api_get, "/dashboard/cajas-por-hora", params)
        matriz = _request(st, api_get, "/dashboard/produccion-persona-lote", params)
        recientes = _request(
            st, api_get, "/dashboard/actividad-reciente",
            {"lote_codigo": params["lote_codigo"], "limit": 10},
        )
        if any(v is None for v in (cajas, efficiency, ritmo, matriz, recientes)):
            return

        cajas_rows = cajas.get("rows", [])
        eff_rows = efficiency.get("rows", [])
        ritmo_rows = ritmo.get("rows", [])
        matriz_rows = matriz.get("rows", [])
        recientes_rows = recientes.get("rows", [])
        df_dia = pd.DataFrame(cajas_rows) if cajas_rows else pd.DataFrame()
        df_eff = pd.DataFrame(eff_rows) if eff_rows else pd.DataFrame()
        df_horas = pd.DataFrame(ritmo_rows) if ritmo_rows else pd.DataFrame()
        df_matriz = pd.DataFrame(matriz_rows) if matriz_rows else pd.DataFrame()
        df_recientes = pd.DataFrame(recientes_rows) if recientes_rows else pd.DataFrame()

        total = int(df_dia["total"].sum()) if not df_dia.empty else 0
        emp = int(df_dia["empacadas"].sum()) if not df_dia.empty else 0
        sel = int(df_dia["seleccionadas"].sum()) if not df_dia.empty else 0
        personas = len(eff_rows)
        dias = df_dia["dia"].nunique() if not df_dia.empty else 0

        # ---------- 1. KPIs: el empacado lidera ----------
        kpis = [
            ("Cajas empacadas", emp),
            ("Selección", sel),
            ("Lecturas totales", total),
            ("Personas activas", personas),
            ("Días trabajados", int(dias)),
        ]
        kpi_columns = st.columns(5)
        for column, (label, value), color in zip(kpi_columns, kpis, _COLOR_KPI):
            column.markdown(_kpi_card(label, value, color), unsafe_allow_html=True)

        if df_dia.empty:
            if not df_recientes.empty:
                # Hay lecturas en el servidor, pero fuera del rango seleccionado:
                # indicar la última fecha registrada y ofrecer saltar hasta ella.
                ultima = pd.to_datetime(df_recientes.iloc[0]["scanned_at"], utc=True).tz_convert(_TZ)
                st.warning(
                    f"No hay lecturas entre el {date_from.strftime('%d/%m/%Y')} y el "
                    f"{date_to.strftime('%d/%m/%Y')}. La última lectura registrada es del "
                    f"**{ultima.strftime('%d/%m/%Y %H:%M')}** (hora Perú)."
                )
                c_go, _ = st.columns([1, 2])
                if c_go.button("🔍 Ver el día de la última lectura", key="dash_ir_ultima", width="stretch"):
                    st.session_state["_dash_pending_range"] = (ultima.date(), ultima.date())
                    st.rerun()
            else:
                st.info(
                    "No hay lecturas registradas todavía. Genere etiquetas en 🖨️ Impresión "
                    "y escanee cajas con la APK para poblar el dashboard."
                )
            return

        # ---------- 2. Gráfica principal: cajas EMPACADAS por lote ----------
        st.markdown("### Cajas empacadas por lote")
        st.caption(
            "El empacado es la base para formar pallets. La selección se muestra "
            "al lado (color claro) solo como referencia: son dos conceptos distintos."
        )
        per_lot = df_dia.groupby("lote", as_index=False)[["empacadas", "seleccionadas"]].sum()
        per_lot["total"] = per_lot["empacadas"] + per_lot["seleccionadas"]
        per_lot = per_lot.sort_values("empacadas", ascending=True)

        series = per_lot.melt(
            id_vars="lote",
            value_vars=["empacadas", "seleccionadas"],
            var_name="tipo",
            value_name="cajas",
        )
        series["tipo"] = series["tipo"].map({"empacadas": "Empacadas", "seleccionadas": "Selección"})

        chart_lot = (
            alt.Chart(series)
            .mark_bar()
            .encode(
                y=alt.Y("lote:N", sort=list(per_lot["lote"]), title="Lote"),
                x=alt.X("cajas:Q", title="Cajas"),
                yOffset=alt.YOffset("tipo:N", sort=["Empacadas", "Selección"]),
                color=alt.Color(
                    "tipo:N",
                    scale=alt.Scale(
                        domain=["Empacadas", "Selección"],
                        range=[_COLOR_EMPACADAS, _COLOR_SELECCION],
                    ),
                    title="Tipo",
                ),
                tooltip=["lote:N", "tipo:N", "cajas:Q"],
            )
            .properties(height=max(140, 34 * len(per_lot)))
        )
        st.altair_chart(chart_lot, width="stretch")
        st.dataframe(
            per_lot[["lote", "empacadas", "seleccionadas", "total"]]
            .sort_values("empacadas", ascending=False),
            hide_index=True,
            width="stretch",
        )

        # ---------- 3. Donut de distribución + ritmo por hora ----------
        col_donut, col_horas = st.columns([1, 2])
        with col_donut:
            st.markdown("#### Distribución")
            tipo_df = pd.DataFrame([
                {"tipo": "Empacadas", "cajas": emp},
                {"tipo": "Selección", "cajas": sel},
            ])
            donut = (
                alt.Chart(tipo_df)
                .mark_arc(innerRadius=64, outerRadius=100)
                .encode(
                    theta=alt.Theta("cajas:Q", stack=True),
                    color=alt.Color(
                        "tipo:N",
                        scale=alt.Scale(
                            domain=["Empacadas", "Selección"],
                            range=[_COLOR_EMPACADAS, _COLOR_SELECCION],
                        ),
                        legend=None,
                    ),
                    tooltip=["tipo:N", "cajas:Q"],
                )
            )
            centro = (
                alt.Chart(pd.DataFrame({"t": [f"{emp}"]}))
                .mark_text(fontSize=26, fontWeight="bold", color="#333")
                .encode(text="t:N")
            )
            st.altair_chart((donut + centro).properties(height=220), width="stretch")
            pct_emp = (emp / total * 100) if total else 0
            st.caption(f"🔵 **{emp}** empacadas ({pct_emp:.0f}%) · 🟠 {sel} selección")

        with col_horas:
            st.markdown("#### Ritmo por hora del día")
            if df_horas.empty:
                st.caption("Sin lecturas en el rango para mostrar el ritmo horario.")
            else:
                horas_series = df_horas.melt(
                    id_vars="hora",
                    value_vars=["empacadas", "seleccionadas"],
                    var_name="tipo",
                    value_name="cajas",
                )
                horas_series["tipo"] = horas_series["tipo"].map(
                    {"empacadas": "Empacadas", "seleccionadas": "Selección"}
                )
                chart_horas = (
                    alt.Chart(horas_series)
                    .mark_bar()
                    .encode(
                        x=alt.X(
                            "hora:O",
                            title="Hora del día (Perú)",
                            axis=alt.Axis(labelExpr="datum.value + ':00'"),
                        ),
                        y=alt.Y("cajas:Q", title="Cajas"),
                        xOffset=alt.XOffset("tipo:N", sort=["Empacadas", "Selección"]),
                        color=alt.Color(
                            "tipo:N",
                            scale=alt.Scale(
                                domain=["Empacadas", "Selección"],
                                range=[_COLOR_EMPACADAS, _COLOR_SELECCION],
                            ),
                            title="Tipo",
                        ),
                        tooltip=["hora:O", "tipo:N", "cajas:Q"],
                    )
                    .properties(height=220)
                )
                st.altair_chart(chart_horas, width="stretch")
                mejor = df_horas.loc[df_horas["empacadas"].idxmax()]
                st.caption(
                    f"🏷️ Hora pico de empacado: **{int(mejor['hora'])}:00** "
                    f"con {int(mejor['empacadas'])} cajas empacadas."
                )

        # ---------- 4. Tendencia de EMPACADAS vs meta ----------
        st.divider()
        head_meta, col_meta = st.columns([3, 1])
        head_meta.markdown("### Tendencia de empacadas vs meta")
        with col_meta:
            meta_diaria = st.number_input(
                "Meta empacadas/día", min_value=1, value=100, step=10, key="dashboard_meta"
            )

        df_dia["dia"] = pd.to_datetime(df_dia["dia"]).dt.date
        trend = df_dia.groupby("dia", as_index=False)["empacadas"].sum()
        linea = (
            alt.Chart(trend)
            .mark_line(point=True, color=_COLOR_EMPACADAS)
            .encode(
                x=alt.X("dia:T", title="Día"),
                y=alt.Y("empacadas:Q", title="Cajas empacadas"),
                tooltip=["dia:T", "empacadas:Q"],
            )
        )
        meta_rule = (
            alt.Chart(pd.DataFrame({"meta": [int(meta_diaria)]}))
            .mark_rule(color="#ff4747", strokeDash=[6, 4])
            .encode(y="meta:Q")
        )
        st.altair_chart((linea + meta_rule).properties(height=260), width="stretch")
        promedio = float(trend["empacadas"].mean())
        avance = (promedio / int(meta_diaria) * 100) if meta_diaria else 0
        st.caption(
            f"Promedio: **{promedio:.0f} empacadas/día** · Meta: **{int(meta_diaria)}** · "
            f"Avance: **{avance:.0f}%** — línea punteada roja = meta."
        )

        # ---------- 5. Heatmap: empacadas por persona y lote ----------
        st.markdown("### Empacadas por persona y lote")
        if df_matriz.empty:
            st.caption("Sin datos de persona/lote en el rango seleccionado.")
        else:
            lote_order = (
                df_matriz.groupby("lote")["empacadas"].sum().sort_values(ascending=False).index.tolist()
            )
            persona_order = (
                df_matriz.groupby("persona")["empacadas"].sum().sort_values(ascending=False).index.tolist()
            )
            heatmap = (
                alt.Chart(df_matriz)
                .mark_rect()
                .encode(
                    x=alt.X("lote:N", sort=lote_order, title="Lote"),
                    y=alt.Y("persona:N", sort=persona_order, title=None),
                    color=alt.Color(
                        "empacadas:Q",
                        scale=alt.Scale(scheme="yelloworangered"),
                        title="Empacadas",
                    ),
                    tooltip=["persona:N", "lote:N", "empacadas:Q", "seleccionadas:Q", "total:Q"],
                )
                .properties(height=max(140, 30 * len(persona_order)))
            )
            st.altair_chart(heatmap, width="stretch")
            st.caption("Intensidad = cajas empacadas por persona en cada lote (base de pallets).")

        # ---------- 6. Eficiencia: ranking por EMPACADAS ----------
        st.divider()
        st.markdown("### Eficiencia del personal")
        if df_eff.empty:
            st.info("Sin datos de eficiencia en el rango seleccionado.")
            return

        st.caption(
            "Ranking por cajas empacadas — la base para formar pallets. La selección se "
            "muestra como referencia. Eficiencia = cajas por hora activa (primera a última "
            "lectura de cada sesión, mínimo 1 minuto)."
        )
        top = df_eff.sort_values("empacadas", ascending=False).reset_index(drop=True)
        top["empacadas_por_hora"] = (top["empacadas"] / top["horas_activas"]).round(1)
        st.markdown(_leaderboard_html(top), unsafe_allow_html=True)

        st.markdown("#### Empacadas por hora")
        chart_rate = (
            alt.Chart(top)
            .mark_line(point=True, color=_COLOR_EMPACADAS)
            .encode(
                x=alt.X("persona:N", sort="-y", title="Trabajador"),
                y=alt.Y("empacadas_por_hora:Q", title="Empacadas/hora"),
                tooltip=["persona:N", "empacadas_por_hora:Q", "horas_activas:Q", "empacadas:Q"],
            )
            .properties(height=300)
        )
        st.altair_chart(chart_rate, width="stretch")

        st.dataframe(
            top[[
                "dni", "persona", "rol_trabajador", "empacadas", "seleccionadas", "total_cajas",
                "dias_trabajados", "sesiones", "horas_activas", "cajas_por_hora",
            ]],
            hide_index=True,
            width="stretch",
        )

        # ---------- 7. Actividad reciente ----------
        st.divider()
        st.markdown("### Actividad reciente")
        if df_recientes.empty:
            st.caption("Sin lecturas registradas todavía.")
        else:
            st.markdown(_activity_html(recientes_rows), unsafe_allow_html=True)

        # ---------- 8. Vista secundaria: cajas por día ----------
        st.divider()
        with st.expander("Cajas por día (vista secundaria)"):
            st.markdown("#### Cajas por día")
            st.caption("Distribución diaria de empacadas y selección en el rango filtrado.")
            per_day = (
                df_dia.groupby("dia", as_index=False)[["empacadas", "seleccionadas"]].sum()
                .melt("dia", var_name="tipo", value_name="cajas")
                .replace({"tipo": {"empacadas": "Empacadas", "seleccionadas": "Selección"}})
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
                            domain=["Empacadas", "Selección"],
                            range=[_COLOR_EMPACADAS, _COLOR_SELECCION],
                        ),
                        title="Tipo",
                    ),
                    xOffset="tipo:N",
                    tooltip=["dia:T", "tipo:N", "cajas:Q"],
                )
                .properties(height=320)
            )
            st.altair_chart(chart_day, width="stretch")

    _body()
