import streamlit as st
import requests

API = "http://127.0.0.1:8000"  # URL de la API de FastAPI

# Función para manejar el registro de personal
def registro_personal():
    st.subheader("Ingreso de Personal a Planta")

    # Entrada de DNI
    dni = st.text_input("DNI del trabajador", max_chars=8, key="dni_personal")
    if dni:
        # Realizar la consulta para registrar la entrada del trabajador
        response = requests.post(f"{API}/registrar/", json={"dni": dni, "tipo": "entrada"})
        if response.status_code == 200:
            st.success(f"Ingreso registrado para el trabajador con DNI: {dni}")
        else:
            st.error("Error al registrar el ingreso")

# Función para mostrar la pestaña de Agente de Vigilancia
def pestaña_agente():
    st.title("Agente de Vigilancia")
    menu = ["Registrar Ingreso", "Ver Personal Registrado"]
    opcion = st.selectbox("Seleccione una opción", menu)

    if opcion == "Registrar Ingreso":
        registro_personal()
    elif opcion == "Ver Personal Registrado":
        # Lógica para mostrar el personal registrado
        st.write("Mostrar lista de personal ingresado")
