"""Utilidades compartidas para exportar e imprimir desde cualquier pestaña.

Toda exportación incluye el usuario que la generó y la fecha/hora para trazabilidad.
"""
import io
import json
from datetime import datetime

import pandas as pd


def get_user(st) -> str:
    """Usuario autenticado para trazabilidad en documentos exportados."""
    auth = st.session_state.get("auth") or {}
    return (auth.get("usuario") or auth.get("sub") or "desconocido").strip()


def footer(user: str) -> str:
    """Línea de trazabilidad."""
    return f"Generado por: {user} — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"


def excel_bytes(title: str, subtitle: list[str], df: pd.DataFrame, user: str) -> bytes:
    """Excel con título, bloque de detalle, tabla y pie de trazabilidad."""
    lineas = [title] + subtitle + ["", footer(user)]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        info = pd.DataFrame({"Detalle": lineas})
        info.to_excel(writer, sheet_name="Reporte", index=False, header=False, startrow=0)
        df.to_excel(writer, sheet_name="Reporte", index=False, startrow=len(lineas) + 1)
    return buf.getvalue()


def _table_html(df: pd.DataFrame) -> str:
    return df.to_html(index=False, border=0, classes="tabla")


def printable_html(title: str, subtitle: list[str], tables: list[tuple[str, pd.DataFrame]], user: str) -> str:
    """Documento HTML listo para imprimir o guardar como PDF desde el navegador."""
    subs = "".join(f"<p>{s}</p>" for s in subtitle)
    secciones = ""
    for heading, df in tables:
        if df is not None and not df.empty:
            secciones += f"<h2>{heading}</h2>" + _table_html(df)
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #222; margin: 28px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  h2 {{ font-size: 15px; margin: 18px 0 6px; color: #0068b3; }}
  .sub p {{ margin: 2px 0; color: #555; font-size: 12px; }}
  table.tabla {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-bottom: 12px; }}
  table.tabla th {{ background: #00b3f4; color: #fff; padding: 6px 10px; text-align: left; }}
  table.tabla td {{ border-bottom: 1px solid #e3e6ea; padding: 5px 10px; }}
  table.tabla tr:nth-child(even) td {{ background: #f6f8fa; }}
  .trace {{ margin-top: 24px; padding: 10px 14px; border-top: 2px solid #00b3f4;
           color: #555; font-size: 12px; font-weight: 600; }}
  @media print {{ body {{ margin: 12px; }} .no-print {{ display: none; }} }}
</style></head>
<body>
  <h1>{title}</h1>
  <div class="sub">{subs}</div>
  {secciones}
  <div class="trace">{footer(user)}</div>
</body></html>"""


def print_button(html_doc: str, key_suffix: str, st, height: int = 44):
    """Botón que abre el documento en ventana nueva e imprime."""
    import streamlit as _streamlit
    script = f"""
    <script>
    function imprimirDoc{key_suffix}() {{
      var v = window.open('', '_blank', 'width=1000,height=720');
      v.document.open();
      v.document.write({json.dumps(html_doc)});
      v.document.close();
      v.focus();
      setTimeout(function() {{ v.print(); }}, 400);
    }}
    </script>
    <button onclick="imprimirDoc{key_suffix}()"
      style="width:100%;padding:6px 12px;border:1px solid #bbb;border-radius:8px;
             background:#fff;cursor:pointer;font-size:14px;font-weight:600;color:#333;">
      🖨️ Imprimir / PDF
    </button>
    """
    _streamlit.iframe(script, height=height)


def export_row(st, title: str, subtitle: list[str], df: pd.DataFrame, prefix: str, key: str):
    """Fila con botones de Excel e Imprimir/PDF, con trazabilidad del usuario."""
    user = get_user(st)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ Exportar a Excel",
            data=excel_bytes(title, subtitle, df, user),
            file_name=f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key}_excel",
        )
    with c2:
        print_button(printable_html(title, subtitle, [(title, df)], user), key, st)
