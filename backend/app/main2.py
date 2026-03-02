import streamlit as st
from app.pages.impresion import pestaña_impresion  # Importa la página de Impresión
from app.pages.agente_vigilancia import pestaña_agente  # Importa la página de Agente de Vigilancia

# Configuración de la página principal
st.set_page_config(page_title="Sistema de Asistencia", layout="wide")

# Crear pestañas según el rol del usuario
tabs = []

# Definir las pestañas según el rol del usuario (esto puede cambiar)
rol = st.session_state.auth.get("rol", "")  # Se asume que el rol está en el estado de la sesión

if rol == "ROOT":
    tabs = ["Usuarios", "Listar", "🖨️ Impresión", "👤 Agente de Vigilancia", "🖨️ Impresoras"]
elif rol == "SUPERVISOR":
    tabs = ["Listar", "🖨️ Impresión", "👤 Agente de Vigilancia", "🖨️ Impresoras"]
else:
    tabs = ["🖨️ Impresión", "👤 Agente de Vigilancia"]

# Crear las pestañas
tab_objs = st.tabs(tabs)

# Lógica para cada pestaña
if "Usuarios" in tabs:
    with tab_objs[tabs.index("Usuarios")]:
        # Lógica de la pestaña de Usuarios
        pass

if "Listar" in tabs:
    with tab_objs[tabs.index("Listar")]:
        # Lógica de la pestaña Listar
        pass

if "🖨️ Impresión" in tabs:
    with tab_objs[tabs.index("🖨️ Impresión")]:
        pestaña_impresion()  # Llamar a la página de impresión

if "👤 Agente de Vigilancia" in tabs:
    with tab_objs[tabs.index("👤 Agente de Vigilancia")]:
        pestaña_agente()  # Llamar a la página del agente de vigilancia
