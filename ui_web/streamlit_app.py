import streamlit as st
import requests
import pandas as pd

API = "http://127.0.0.1:8000"

# ======================================================
# CONFIGURACIÓN DE COLUMNAS POR VISTA (SOLO UI)
# ======================================================

COLUMNAS_IMPRESION = [
    "seleccionar",
    "dni",
    "nombre",
    "apellido_paterno",
    "apellido_materno",
#    "rol",
    "num_orden",
#x    "cod_letra",
]

COLUMNAS_LISTADO = [
   # "id",
    "dni",
    "nombre",
    "apellido_paterno",
    "apellido_materno",
#    "rol",
    "num_orden",
    "cod_letra",
  #  "activo",
  #  "creado_en",
]

COLUMNAS_TRABAJADOR = [
   # "id",
    "dni",
    "nombre",
    "apellido_paterno",
    "apellido_materno",
    "rol",
    "num_orden",
    "cod_letra",
    "activo",
  #  "creado_en",
]

# --------------------------------------------------
# ESTADO DE AUTENTICACIÓN
# --------------------------------------------------
if "auth" not in st.session_state:
    st.session_state.auth = None

# --------------------------------------------------
# BOOTSTRAP DEL SISTEMA (ROOT)
# --------------------------------------------------
resp = requests.get(f"{API}/setup/status")

if resp.status_code == 200 and not resp.json().get("initialized"):
    st.title("Inicialización del sistema")
    st.info("Debe crear el usuario administrador (ROOT)")

    usuario = st.text_input("Usuario admin", key="root username")
    nombre = st.text_input("Nombre completo", key="root full name")
    password = st.text_input("Contraseña", type="password", key="root password")

    if st.button("Crear administrador"):
        r = requests.post(
            f"{API}/setup/init-root",
            json={
                "usuario": usuario,
                "nombre": nombre,
                "password": password
            }
        )

        if r.status_code == 200:
            st.success("Administrador creado. Recargue la página.")
            st.stop()
        else:
            st.error(r.text)

    st.stop()

# --------------------------------------------------
# LOGIN
# --------------------------------------------------
if not st.session_state.auth:
    st.set_page_config(page_title="Login - Sistema QR", layout="centered")
    st.title("Ingreso al Sistema de Etiquetas")

    usuario = st.text_input("Usuario", key="login username")
    password = st.text_input("Contraseña", type="password", key="login password")

    if st.button("Ingresar"):
        r = requests.post(
            f"{API}/auth/login",
            json={
                "usuario": usuario,
                "password": password
            }
        )

        if r.status_code == 200:
            st.session_state.auth = r.json()
            st.success("Ingreso correcto")            
            st.rerun()
            st.session_state.pop("Usuario", None)
            st.session_state.pop("Contraseña", None)
        else:
            st.error("Usuario o contraseña incorrectos")

    st.stop()

# --------------------------------------------------
# MOSTRAR USUARIO ACTIVO Y CERRAR SESIÓN
# --------------------------------------------------
rol = st.session_state.auth["rol"]
usuario = st.session_state.auth["usuario"]

st.sidebar.success(f"{usuario} ({rol})")

if st.sidebar.button("Cerrar sesión"):
    st.session_state.auth = None
    st.rerun()

# PESTAÑAS SEGÚN ROL
tabs = []

if rol == "ROOT":
    tabs = ["Usuarios", "Listar", "🖨️ Impresión", "👤 Trabajadores"]
elif rol == "SUPERVISOR":
    tabs = ["Listar", "🖨️ Impresión", "👤 Trabajadores"]
else:
    tabs = ["🖨️ Impresión"]

tab_objs = st.tabs(tabs)

# ======================================================
# 3) PESTAÑA USUARIOS (AUDITORÍA)
# ======================================================
if "Usuarios" in tabs:
    with tab_objs[tabs.index("Usuarios")]:
        st.subheader("Administración de usuarios del sistema")

        st.markdown("### Crear nuevo usuario")

        col1, col2 = st.columns(2)
        with col1:
            nuevo_usuario = st.text_input("Usuario (login)", key="new user username")
            nombre = st.text_input("Nombre completo", key="new user full name")

        with col2:
            password = st.text_input("Contraseña", type="password", key="new user password")
            rol_nuevo = st.selectbox(
                "Rol",
                ["SUPERVISOR", "OPERADOR"]
            )

        if st.button("Crear usuario"):
            if not nuevo_usuario or not password or not nombre:
                st.warning("Complete todos los campos")
            else:
                r = requests.post(
                    f"{API}/admin/usuarios",
                    json={
                        "usuario": nuevo_usuario,
                        "nombre": nombre,
                        "password": password,
                        "rol": rol_nuevo
                    }
                )

                if r.status_code == 200:
                    st.success("Usuario creado correctamente")
                    st.rerun()
                    st.session_state["Usuarios"]= None
                else:
                    st.error("Error al crear usuario")
                    st.code(r.text)

# ======================================================
# 4) PESTAÑA LISTAR
# ======================================================
if "Listar" in tabs:
    with tab_objs[tabs.index("Listar")]:
        st.subheader("Listado de trabajadores activos")
        r = requests.get(f"{API}/trabajadores?activos=true")
        if r.status_code == 200:
            trabajadores = r.json()
            if trabajadores:
                df = pd.DataFrame(trabajadores)
                df_listado = df[COLUMNAS_LISTADO]

                st.dataframe( df_listado, width="stretch")
            else:
                st.info("No hay trabajadores registrados")
        else:
            st.error("Error cargando trabajadores")

# ======================================================
# 5) PESTAÑA TRABAJADORES (ALTA)
# ======================================================
if "👤 Trabajadores" in tabs:
    with tab_objs[tabs.index("👤 Trabajadores")]:
        st.subheader("Alta de trabajador")
        col_dni, col_nom = st.columns([1,3])
        with col_dni:
            dni = st.text_input("DNI", max_chars=8, key="dni_trab")
        with col_nom:
            nombre = st.text_input("Nombres", key="nom_trab")
        col3, col4 = st.columns(2)  
        with col3:
            apellido_paterno = st.text_input("Apellido paterno", key="ap_pat")
        with col4:
            apellido_materno = st.text_input("Apellido materno", key="ap_mat")

        col_rol, col_btn = st.columns([1, 1])
        with col_rol:        
            rol = st.selectbox("Rol", ["EMPACADORA", "SELECCIONADOR"], key="rol_trab")



        if st.button("Crear trabajador"):
            r = requests.post(
                f"{API}/trabajadores",
                json={
                    "dni": dni,
                    "nombre": nombre,
                    "apellido_paterno": apellido_paterno,
                    "apellido_materno": apellido_materno,
                    "rol": rol
                }
            )
            if r.status_code == 200:
                data = r.json()
                st.toast(f"Trabajador creado → {nombre} {apellido_paterno} ({data['num_orden']}-{data['cod_letra']})",
                icon="✅"
                )
                # -------------------------
                # AUTO-LIMPIAR FORMULARIO
                # -------------------------
                for k in ("dni_trab", "nom_trab", "ap_pat", "ap_mat", "rol_trab"):
                    st.session_state.pop(k, None)


            else:
                st.error(r.text)

            st.divider()
        st.subheader("Trabajadores activos")
        r = requests.get(f"{API}/trabajadores?activos=true")
        if r.status_code == 200:
            trabajadores = r.json()
            if trabajadores:
                df = pd.DataFrame(trabajadores)
                df_listado = df[COLUMNAS_TRABAJADOR]

                st.dataframe(df_listado, width="stretch")

            else:
                st.info("No hay trabajadores registrados")
        else:
            st.error("Error cargando trabajadores")

# ======================================================
# 6) PESTAÑA 🖨️ IMPRESIÓN (SELECCIÓN POR FILA)
# ======================================================
if "🖨️ Impresión" in tabs:
    with tab_objs[tabs.index("🖨️ Impresión")]:
        st.subheader("Impresión de etiquetas")
        r = requests.get(f"{API}/trabajadores?activos=true")
        if r.status_code != 200:
            st.error("Error cargando trabajadores")
            st.stop()
        trabajadores = r.json()
        if not trabajadores:
            st.warning("No hay trabajadores registrados")
            st.stop()

        # --------------------------------------------------
        # Buscador
        # --------------------------------------------------
        busqueda = st.text_input(
            "Buscar por DNI o nombre",
            placeholder="Ejemplo: 40383794 o Anais"
        ).strip().lower()

        def coincide(t):
            if not busqueda:
                return True
            return (
                busqueda in (t.get("dni") or "").lower()
                or busqueda in (t.get("nombre") or "").lower()
                or busqueda in (t.get("apellido_paterno") or "").lower()
                or busqueda in (t.get("apellido_materno") or "").lower()
            )

        filtrados = [t for t in trabajadores if coincide(t)]
        if not filtrados:
            st.warning("No se encontraron trabajadores")
            st.stop()

        # --------------------------------------------------
        # Tabla seleccionable
        # --------------------------------------------------
        st.markdown("### Seleccione un trabajador")
        df = pd.DataFrame(filtrados)

        # Checkbox
        if "seleccionar" not in df.columns:
            df.insert(0, "seleccionar", False)

        # SOLO columnas necesarias para impresión
        df_impresion = df[COLUMNAS_IMPRESION]

        edited_df = st.data_editor(
            df_impresion,
            hide_index=True,
            width="stretch",
            disabled=[c for c in df_impresion.columns if c != "seleccionar"],
            num_rows="fixed",
            key="tabla_trabajadores_impresion"
        )


        seleccionados = edited_df[edited_df["seleccionar"] == True]

        if seleccionados.empty:
            st.info("Seleccione un trabajador marcando una sola fila")
            st.stop()

        if len(seleccionados) > 1:
            st.error("Solo se permite seleccionar un trabajador a la vez")
            st.info("Desmarque las filas adicionales")
            st.stop()

      #  trabajador = seleccionados.iloc[0]
        fila_idx = seleccionados.index[0]
        trabajador = filtrados[fila_idx]
      
        trabajador_id = int(trabajador["id"])
        num_orden = str(trabajador["num_orden"])
        cod_letra = str(trabajador["cod_letra"])

        st.success(
            f"Seleccionado: {trabajador['nombre']} "
            f"({trabajador['dni']}) "
            f"[{trabajador['num_orden']}-{trabajador['cod_letra']}]"
        )

        st.markdown("### Contenido visible en la etiqueta")

        opcion_mostrar = st.radio(
            "¿Qué desea imprimir en el centro del QR?",
            ["Número de orden", "Código de letra"],
            horizontal=True
        )

        if opcion_mostrar == "Número de orden":
            valor_visible = num_orden
        else:
            valor_visible = cod_letra

        # --------------------------------------------------
        # Producto + impresión
        # --------------------------------------------------
        producto = st.selectbox("Producto", ["UVA"])

        # --------------------------------------------------
        # CANTIDAD DE ETIQUETAS
        # --------------------------------------------------
        col_print = st.columns([1, 4])[0]
        with col_print:
            cantidad = st.number_input("Cantidad de etiquetas",
                min_value=1,
                max_value=5000,
                value=1,
                step=1
            )

        if st.button("Imprimir etiqueta"):
            r = requests.post(
            f"{API}/qr/print",
            json={
                "dni": trabajador["dni"],
                "nn": valor_visible,
                "producto": producto,
                "cantidad": cantidad
            }
        )


            if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
                st.image(r.content, caption="Etiqueta generada")
            else:
                st.error("Error al generar la etiqueta")
                st.code(r.text)
