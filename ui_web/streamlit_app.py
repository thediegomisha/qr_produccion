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
    st.set_page_config(page_title="Login - Sistema QR", layout="wide")
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
    tabs = ["Usuarios", "Listar", "🖨️ Impresión", "👤 Trabajadores", "🖨️ Impresoras"]
elif rol == "SUPERVISOR":
    tabs = ["Listar", "🖨️ Impresión", "👤 Trabajadores", "🖨️ Impresoras"]
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
            # ORDENAR ASCENDENTE POR num_orden
            trabajadores = sorted(trabajadores, key=lambda t: t["num_orden"])
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
        if r.status_code != 200:
            st.error("Error cargando trabajadores")
            st.stop()

        trabajadores = r.json()
        # ORDENAR ASCENDENTE POR num_orden
        trabajadores = sorted(trabajadores, key=lambda t: t["num_orden"])
        if not trabajadores:
            st.info("No hay trabajadores registrados")
            st.stop()

        df = pd.DataFrame(trabajadores)

        st.markdown("### Lista de trabajadores")

        # --------------------------------------------------
        # TABLA CON ENCABEZADOS + ORDEN + ✏️
        # --------------------------------------------------
        df_ui = df.copy()

        # Columna acción
        df_ui["✏️"] = False

        # Columnas visibles (id NO se muestra, pero se mantiene en df_ui)
        columnas_ui = [
            "✏️",
            "dni",
            "nombre",
            "apellido_paterno",
            "apellido_materno",
            "rol",
            "num_orden",
            "cod_letra",
        ]

        edited_df = st.data_editor(
            df_ui[columnas_ui],
            hide_index=True,
            num_rows="fixed",
            disabled=[c for c in columnas_ui if c != "✏️"],
            use_container_width=True,
            key="tabla_trabajadores_editar"
        )

        seleccionados = edited_df[edited_df["✏️"] == True]

        if len(seleccionados) == 1:
            fila_idx = seleccionados.index[0]

            # ⚠️ TOMAMOS EL REGISTRO ORIGINAL DEL BACKEND
            tr = trabajadores[fila_idx]

            st.session_state["editar_trabajador"] = tr
            st.session_state["abrir_modal"] = True
            st.session_state["modal_origen"] = "trabajadores"



        # --------------------------------------------------
        # MODAL DE EDICIÓN
        # --------------------------------------------------
        if (
            st.session_state.get("abrir_modal")
            and st.session_state.get("modal_origen") == "trabajadores"
            and "👤 Trabajadores" in tabs
        ):

            tr = st.session_state["editar_trabajador"]

            @st.dialog("Editar trabajador")
            def modal_editar_trabajador():
                with st.form("form_editar_trabajador"):
                    dni = st.text_input("DNI", tr["dni"])
                    nombre = st.text_input("Nombre", tr["nombre"])
                    ap_pat = st.text_input("Apellido paterno", tr["apellido_paterno"])
                    ap_mat = st.text_input("Apellido materno", tr["apellido_materno"])
                    rol = st.selectbox(
                        "Rol",
                        ["EMPACADORA", "SELECCIONADOR"],
                        index=["EMPACADORA", "SELECCIONADOR"].index(tr["rol"])
                    )

                    col1, col2 = st.columns(2)
                    guardar = col1.form_submit_button("💾 Guardar")
                    cancelar = col2.form_submit_button("❌ Cancelar")

                if guardar:
                    r = requests.put(
                        f"{API}/trabajadores/{tr['id']}",
                        json={
                            "dni": dni,
                            "nombre": nombre,
                            "apellido_paterno": ap_pat,
                            "apellido_materno": ap_mat,
                            "rol": rol
                        }
                    )

                    if r.status_code == 200:
                        st.success("Trabajador actualizado correctamente")
                        st.session_state.pop("editar_trabajador", None)
                        st.session_state.pop("abrir_modal", None)
                        st.rerun()
                    else:
                        st.error(r.text)

                if cancelar:
                    st.session_state.pop("editar_trabajador", None)
                    st.session_state.pop("abrir_modal", None)
                    st.rerun()

            modal_editar_trabajador()

                    
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
        # ORDENAR ASCENDENTE POR num_orden
        trabajadores = sorted(trabajadores, key=lambda t: t["num_orden"])
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

        if st.button("Vista previa "):
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
                st.image(r.content, caption="Etiqueta generada by Agricola del Sur Pisco")
        else:
                st.error("Error al generar la etiqueta")
                st.code(r.text)

                st.divider()

if st.button("🖨️ Imprimir etiquetas"):
    r = requests.post(
        f"{API}/qr/print-zpl",
        json={
            "dni": trabajador["dni"],
            "nn": valor_visible,
            "producto": producto,
            "cantidad": cantidad,
            "impresora_id": st.session_state.get("impresora_activa")
        }
    )

    if r.status_code == 200:
        st.toast("Impresión enviada correctamente 🖨️", icon="✅")
    else:
        st.error("Error al imprimir")
        st.code(r.text)
# ======================================================
# 6) PESTAÑA 🖨️ IMPRESORAS 
# ======================================================
if "🖨️ Impresoras" in tabs:
    with tab_objs[tabs.index("🖨️ Impresoras")]:
        st.subheader("Configuración de impresoras")

        st.markdown("### Registrar impresora")
        c1, c2, c3 = st.columns([2,1,1])
        nombre_imp = c1.text_input("Nombre", key="imp_nombre")
        marca = c2.selectbox("Marca", ["ZEBRA", "TSC"], key="imp_marca")
        conexion = c3.selectbox("Conexión", ["RED", "USB"], key="imp_conexion")

        c4, c5 = st.columns([2,1])
        ip = c4.text_input("IP (o host)", key="imp_ip", placeholder="192.168.1.50")
        puerto = c5.number_input("Puerto", min_value=1, max_value=65535, value=9100, step=1, key="imp_puerto")

        if st.button("Guardar impresora", key="btn_guardar_imp"):
            r = requests.post(f"{API}/impresoras", json={
                "nombre": nombre_imp,
                "marca": marca,
                "conexion": conexion,
                "ip": ip,
                "puerto": int(puerto),
            })
            if r.status_code == 200:
                st.toast("Impresora registrada ✅", icon="🖨️")
                st.rerun()
            else:
                st.error(r.text)

        st.divider()
        st.markdown("### Impresoras activas")

        r = requests.get(f"{API}/impresoras")
        if r.status_code == 200:
            st.dataframe(r.json(), width="stretch")
        else:
            st.error(r.text)



