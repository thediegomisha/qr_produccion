import pandas as pd

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
    TAB_VIG = "🛡️ Vigilancia"

    def norm_dni(s: str) -> str:
        return "".join([c for c in (s or "") if c.isdigit()])

        # ✅ Reset diferido (antes de instanciar widgets)
    if st.session_state.get("vig_reset"):
        st.session_state["vig_dni"] = ""
        st.session_state["vig_nombres"] = ""
        st.session_state["vig_apellido_paterno"] = ""
        st.session_state["vig_apellido_materno"] = ""
        st.session_state["vig_reset"] = False

        st.session_state["vig_preview"] = {
            "dni": "",
            "nombres": "",
            "apellido_paterno": "",
            "apellido_materno": "",
            "found": False,
            "offline": False,
            "detail": ""
        }


    st.subheader("🛡️ Registro de Ingreso / Salida (Vigilancia)")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        dni_in = st.text_input("DNI", key="vig_dni", placeholder="8 dígitos")
    with col2:
        tipo = st.selectbox("Tipo", ["ENTRADA", "SALIDA"], key="vig_tipo")
    with col3:
        fecha = st.date_input("Fecha", key="vig_fecha")

    dni = norm_dni(dni_in)

    # Estado persistente
    if "vig_preview" not in st.session_state:
        st.session_state.vig_preview = {
            "dni": "",
            "nombres": "",
            "apellido Paterno": "",
            "apellido Materno": "",
            "fuente": "",
            "found": False,
            "offline": False,
            "detail": ""
        }

    # ---------- PREVIEW ----------
    # Solo consulta si hay 8 dígitos y cambió el DNI
    if len(dni) == 8 and dni != st.session_state.vig_preview.get("dni"):
        try:
            resp = api_get(f"/vigilancia/persona/?dni={dni}")

            if resp.status_code == 200:
                data = resp.json()
                st.session_state.vig_preview = data
                st.session_state["vig_nombres"] = data.get("nombres", "")
                st.session_state["vig_apellido_paterno"] = data.get("apellido_paterno", "")
                st.session_state["vig_apellido_materno"] = data.get("apellido_materno", "")
            else:
                # MUY IMPORTANTE: guardar detalle del error (para depurar)
                st.session_state.vig_preview = {
                    "dni": dni,
                    "nombres": "",
                    "apellido_paterno": "",
                    "apellido_materno": "",
                    "fuente": f"ERROR_{resp.status_code}",
                    "found": False,
                    "offline": False,
                    "detail": resp.text
                }
                st.error(f"Error en /vigilancia/persona/?dni={dni}: {resp.status_code}")
                st.code(resp.text)

        except Exception as e:
            st.session_state.vig_preview = {
                "dni": dni,
                "nombres": "",
                "apellido_paterno": "",
                "apellido_materno": "",
                "fuente": "OFFLINE",
                "found": False,
                "offline": True,
                "detail": str(e)
            }

    prev = st.session_state.vig_preview

    st.markdown("**Datos (antes de registrar)**")

    # Si found=True y no offline => mostrar bloqueado
    lock_fields = bool(prev.get("found")) and not bool(prev.get("offline"))


    cA, cB, cC = st.columns([2, 2, 1])
    with cA:
        nombres_ui = st.text_input("Nombres", key="vig_nombres", disabled=lock_fields)
    with cB:
        ap_pat_ui = st.text_input("Apellido Paterno", key="vig_apellido_paterno", disabled=lock_fields)
    with cC:
        ap_mat_ui = st.text_input("Apellido Materno", key="vig_apellido_materno", disabled=lock_fields)
 #   with cC:
 #       st.text_input("Fuente", value=prev.get("fuente", ""), disabled=True)

    manual_needed = (
        len(dni) == 8 and
        (
            not prev.get("found") or
            prev.get("fuente") in ("OFFLINE", "NO_ENCONTRADO") or
            str(prev.get("fuente", "")).startswith("ERROR_")
        )
    )

    if manual_needed and len(dni) == 8:
        st.info("Complete nombres y apellidos manualmente si no hay conectividad o no existe en PerúDevs.")

    # ---------- REGISTRAR ----------
    if st.button("Registrar", width='stretch', key="vig_btn_registrar"):
        if len(dni) != 8:
            st.error("DNI inválido")
        else:
            payload = {"dni": dni, "tipo": tipo}

            # Si requiere manual, valida y envía nombres/apellidos
            if manual_needed:
                if not nombres_ui.strip() or not ap_pat_ui.strip() or not ap_mat_ui.strip():
                    st.error("Complete nombres y ambos apellidos para registrar manualmente.")
                    st.stop()

                payload["nombres"] = nombres_ui.strip()
                payload["apellido_paterno"] = ap_pat_ui.strip()
                payload["apellido_materno"] = ap_mat_ui.strip()
            try:
                resp = api_post("/vigilancia/visita", json=payload)

                if resp.status_code == 200:
                    r = resp.json()
                    full = " ".join([
                    r.get("nombres", ""),
                    r.get("apellido_paterno", ""),
                    r.get("apellido_materno", ""),
                ]).strip()

                    st.success(f"{tipo} registrada: {dni} — {full}")

                    # reset UI
                    st.session_state.vig_preview = {
                        "dni": "",
                        "nombres": "",
                        "apellido_paterno": "",
                        "apellido_materno": "",
                        "fuente": "",
                        "found": False,
                        "offline": False,
                        "detail": ""
                    }
                    # ✅ pedir reset y rerun
                    st.session_state["vig_reset"] = True
                    st.rerun()


                elif resp.status_code == 409:
                    st.warning("Ya existe un registro de ese tipo para hoy.")
                elif resp.status_code in (404, 503):
                    st.warning("No se pudo obtener datos automáticos. Complete manualmente e intente nuevamente.")
                    st.code(resp.text)
                else:
                    st.error(f"API {resp.status_code}")
                    st.code(resp.text)

            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    st.caption("Registros del día (máx 500)")

    try:
        resp = api_get("/vigilancia/visitas", params={"fecha": str(fecha)})

        if resp.status_code == 200:
            data = resp.json() or {}
            items = data.get("items", []) or []

            if items:
                df = pd.DataFrame(items)
                cols = ["tipo", "dni", "nombres", "apellido_paterno", "apellido_materno"]
                df = df[[c for c in cols if c in df.columns]]
                st.dataframe(df, width='stretch', hide_index=True)
            else:
                st.info("Sin registros para esa fecha.")
        else:
            st.error(f"No se pudo cargar registros: API {resp.status_code}")
            st.code(resp.text)

    except Exception as e:
        st.error(f"No se pudo cargar registros: {e}")
