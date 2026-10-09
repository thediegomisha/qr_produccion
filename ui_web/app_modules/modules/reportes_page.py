import io
import json
from datetime import datetime

import pandas as pd
import requests
import streamlit.components.v1 as components

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _report_subtitle(lote: str, extra: str, producto: str) -> list[str]:
    generado = datetime.now().strftime("%d/%m/%Y %H:%M")
    lineas = [
        "Sistema de Etiquetas QR — Reporte de producción",
        f"Lote: {lote or '-'}",
    ]
    if producto:
        lineas.append(f"Producto: {producto}")
    if extra:
        lineas.append(extra)
    lineas.append(f"Generado: {generado}")
    return lineas


def _excel_bytes(subtitle: list[str], df: pd.DataFrame) -> bytes:
    """Genera un archivo .xlsx con encabezado del reporte y la tabla de datos."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        info = pd.DataFrame({"Detalle": subtitle})
        info.to_excel(writer, sheet_name="Reporte", index=False, header=False, startrow=0)
        df.to_excel(writer, sheet_name="Reporte", index=False, startrow=len(subtitle) + 2)
    return buf.getvalue()


def _printable_html(title: str, subtitle: list[str], totals: list[tuple], df: pd.DataFrame) -> str:
    """Documento HTML independiente, listo para abrir e imprimir desde el navegador."""
    tarjetas = "".join(
        f'<div class="card"><div class="lbl">{label}</div><div class="val">{value}</div></div>'
        for label, value in totals
    )
    tabla = df.to_html(index=False, border=0, classes="tabla")
    subtitulo_html = "".join(f"<p>{linea}</p>" for linea in subtitle)
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #222; margin: 28px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub p {{ margin: 2px 0; color: #555; font-size: 12px; }}
  .cards {{ display: flex; gap: 10px; margin: 14px 0 18px; }}
  .card {{ border: 1px solid #ddd; border-left: 5px solid #00b3f4; border-radius: 8px;
          padding: 8px 14px; min-width: 120px; }}
  .lbl {{ color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; }}
  .val {{ font-size: 22px; font-weight: 700; color: #0068b3; }}
  table.tabla {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
  table.tabla th {{ background: #00b3f4; color: #fff; padding: 6px 10px; text-align: left; }}
  table.tabla td {{ border-bottom: 1px solid #e3e6ea; padding: 5px 10px; }}
  table.tabla tr:nth-child(even) td {{ background: #f6f8fa; }}
  footer {{ margin-top: 22px; color: #999; font-size: 11px; }}
  @media print {{ body {{ margin: 12px; }} }}
</style></head>
<body>
  <h1>{title}</h1>
  <div class="sub">{subtitulo_html}</div>
  <div class="cards">{tarjetas}</div>
  {tabla}
  <footer>Generado por el Sistema de Etiquetas QR — {datetime.now().strftime('%d/%m/%Y %H:%M')}</footer>
</body></html>"""


def _print_button(html_doc: str, key_suffix: str, height: int = 44):
    """Botón que abre el reporte en una ventana nueva e invoca el diálogo de impresión."""
    script = f"""
    <script>
    function imprimirReporte{key_suffix}() {{
      var ventana = window.open('', '_blank', 'width=980,height=700');
      ventana.document.open();
      ventana.document.write({json.dumps(html_doc)});
      ventana.document.close();
      ventana.focus();
      setTimeout(function() {{ ventana.print(); }}, 400);
    }}
    </script>
    <button onclick="imprimirReporte{key_suffix}()"
      style="width:100%;padding:6px 12px;border:1px solid #bbb;border-radius:8px;
             background:#fff;cursor:pointer;font-size:14px;font-weight:600;color:#333;">
      🖨️ Imprimir reporte
    </button>
    """
    components.html(script, height=height)


def _safe_filename(prefix: str, lote: str) -> str:
    lote_limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in (lote or "global"))
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{prefix}_{lote_limpio}_{fecha}.xlsx"


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
    st.subheader("Reportes por DNI (por lote)")

    jwt = get_jwt()
    rol_rep = (st.session_state.auth.get("rol") or "").upper()
    headers = {"Authorization": f"Bearer {jwt}"} if jwt else {}

    # ---- traer lotes para el combobox ----
    lotes_items = []
    try:
        r_lotes = api_get("/lotes", params={"limit": 200})
        if r_lotes.status_code == 200:
            lotes_items = (r_lotes.json() or {}).get("items", []) or []
        else:
            st.warning(f"No se pudo cargar lotes ({r_lotes.status_code})")
    except Exception as e:
        st.warning(f"Error cargando lotes: {e}")

    # ---- opciones selectbox ----
    opciones = []
    codigo_por_label = {}
    for it in lotes_items:
        c = (it.get("codigo") or "").strip().upper()
        e = (it.get("estado") or "ABIERTO").strip().upper()
        if not c:
            continue
        label = f"{c} [{e}]"
        opciones.append(label)
        codigo_por_label[label] = c

    # ---- UI selección lote ----
    colA, colB = st.columns([1.3, 2])
    with colA:
        if not opciones:
            st.warning("No hay lotes para seleccionar. Cree uno en la pestaña 📦 Lotes.")
            selected_label = None
        else:
            selected_label = st.selectbox(
                "Selecciona lote",
                opciones,
                index=0,
                key="rep_lote_select",
            )

    with colB:
        st.caption("Reportes ahora se generan SIN fecha. Se filtra solo por lote y filtros opcionales.")

    lote_codigo = ""
    if selected_label:
        lote_codigo = (codigo_por_label.get(selected_label) or "").strip().upper()

    # ---- filtros opcionales ----
    c1, c2 = st.columns([1, 1])
    with c1:
        producto = st.text_input("Producto (opcional)", value="", key="rep_producto")
    with c2:
        scanned_by = ""
        if rol_rep in ("ROOT", "SUPERVISOR"):
            scanned_by = st.text_input("Usuario que escaneó (opcional)", value="", key="rep_scanned_by")

    # ---- params al backend (SIN fechas) ----
    params = {"lote_codigo": lote_codigo}
    if producto.strip():
        params["producto"] = producto.strip()
    if rol_rep in ("ROOT", "SUPERVISOR") and scanned_by.strip():
        params["scanned_by"] = scanned_by.strip()

    btn_disabled = not bool(lote_codigo)

    b1, b2 = st.columns(2)

    # -------------------------
    # DNI SUMMARY
    # -------------------------
    if b1.button("Generar reporte DNI", type="primary", disabled=btn_disabled):
        r = requests.get(
            f"{API}/reports/dni-summary",
            params=params,
            headers=headers,
            timeout=20
        )
        if r.status_code != 200:
            st.error("Error en /reports/dni-summary")
            st.code(r.text)
        else:
            st.session_state["rep_dni_data"] = r.json()

    # -------------------------
    # OPERATOR SUMMARY (opcional)
    # -------------------------
    if b2.button("Generar reporte Operadores", disabled=btn_disabled):
        r = requests.get(
            f"{API}/reports/operator-summary",
            params=params,
            headers=headers,
            timeout=20
        )
        if r.status_code != 200:
            st.error("Error en /reports/operator-summary")
            st.code(r.text)
        else:
            st.session_state["rep_op_data"] = r.json()

    st.divider()

    # ---- Reporte DNI persistido (sobrevive re-ejecuciones de descarga/impresión) ----
    dni_data = st.session_state.get("rep_dni_data")
    if dni_data:
        st.markdown("### Reporte por DNI")
        tot = dni_data.get("totals", {}) or {}
        lote_dni = dni_data.get("lote_codigo") or lote_codigo
        st.caption(f"Lote: {lote_dni}")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total lecturas", int(tot.get("total_lecturas", 0)))
        m2.metric("Empacador", int(tot.get("emp_lecturas", 0)))
        m3.metric("Seleccionador", int(tot.get("sel_lecturas", 0)))

        df_dni = pd.DataFrame(dni_data.get("rows", []))
        if df_dni.empty:
            st.info("Sin datos para el reporte por DNI.")
        else:
            st.dataframe(df_dni, width="stretch")

            x1, x2 = st.columns(2)
            with x1:
                sub = _report_subtitle(lote_dni, "", dni_data.get("producto") or "")
                st.download_button(
                    "⬇️ Exportar a Excel",
                    data=_excel_bytes(sub, df_dni),
                    file_name=_safe_filename("reporte_dni", lote_dni),
                    mime=_XLSX_MIME,
                    key="rep_dni_excel",
                )
            with x2:
                totals = [
                    ("Total lecturas", int(tot.get("total_lecturas", 0))),
                    ("Empacador", int(tot.get("emp_lecturas", 0))),
                    ("Seleccionador", int(tot.get("sel_lecturas", 0))),
                ]
                _print_button(
                    _printable_html("Reporte de producción por DNI", sub, totals, df_dni),
                    key_suffix="Dni",
                )

    # ---- Reporte de operadores persistido ----
    op_data = st.session_state.get("rep_op_data")
    if op_data:
        st.markdown("### Reporte por operadores")
        lote_op = op_data.get("lote_codigo") or lote_codigo
        st.caption(f"Lote: {lote_op}")

        df_op = pd.DataFrame(op_data.get("rows", []))
        if df_op.empty:
            st.info("Sin datos para el reporte por operadores.")
        else:
            st.dataframe(df_op, width="stretch")

            y1, y2 = st.columns(2)
            with y1:
                sub = _report_subtitle(lote_op, "Resumen por operador (usuario que escaneó)", op_data.get("producto") or "")
                st.download_button(
                    "⬇️ Exportar a Excel",
                    data=_excel_bytes(sub, df_op),
                    file_name=_safe_filename("reporte_operadores", lote_op),
                    mime=_XLSX_MIME,
                    key="rep_op_excel",
                )
            with y2:
                _print_button(
                    _printable_html("Reporte de producción por operadores", sub, [], df_op),
                    key_suffix="Op",
                )
