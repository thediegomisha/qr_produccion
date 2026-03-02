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
        flash_show("Usuarios")
        st.subheader("Administración de usuarios del sistema")

        if rol not in ("ROOT", "GERENCIA"):
            st.error("No tienes permisos para administrar usuarios.")
            st.stop()

        # ----------------------------
        # LISTAR USUARIOS + SELECCIÓN (✏️)
        # ----------------------------
        st.markdown("### Usuarios registrados")

        r_list = api_get("/admin/usuarios")
        if r_list.status_code != 200:
            st.error("No se pudo listar usuarios")
            st.code(r_list.text)
            st.stop()

        users = (r_list.json() or {}).get("items", []) or []
        df_users = pd.DataFrame(users)

        if df_users.empty:
            st.info("No hay usuarios.")
        else:
            # índice estable (evita que selecciones edite mal)
            df_ui = df_users.reset_index(drop=True).copy()
            if "creado_en" not in df_ui.columns:
                df_ui["creado_en"] = "-"
            else:
                df_ui["creado_en"] = df_ui["creado_en"].map(lambda v: v if pd.notna(v) else "-")

            # checkbox editor
            df_ui["✏️"] = False

            cols_show = ["✏️", "usuario", "nombre", "rol", "activo", "creado_en"]

            edited = st.data_editor(
                df_ui[cols_show],
                hide_index=True,
                num_rows="fixed",
                disabled=[c for c in cols_show if c != "✏️"],
                width="stretch",
                key="tabla_usuarios_editar"
            )

            seleccionados = edited[edited["✏️"] == True]

            # comportamiento igual a Trabajadores
            if len(seleccionados) == 1:
                fila_idx = int(seleccionados.index[0])  # por reset_index(drop=True)
                user_row = df_ui.iloc[fila_idx].to_dict()

                usuario_id = user_row["usuario"]
                rol_target = str(user_row.get("rol") or "").upper()

                # Regla: GERENCIA no edita ROOT/GERENCIA (seguridad + UX)
                if rol == "GERENCIA" and rol_target in ("ROOT", "GERENCIA"):
                    st.warning("GERENCIA no puede editar usuarios ROOT o GERENCIA.")
                    st.session_state.show_user_modal = False
                    st.session_state.edit_user_usuario = None
                    st.session_state._edit_user_row = None
                else:
                    st.session_state.edit_user_usuario = usuario_id
                    st.session_state.show_user_modal = True
                    st.session_state._edit_user_row = user_row
            else:
                st.session_state.show_user_modal = False
                st.session_state.edit_user_usuario = None
                st.session_state._edit_user_row = None

        st.divider()

        # ----------------------------
        # CREAR USUARIO
        # ROOT: puede crear SUPERVISOR/OPERADOR/GERENCIA
        # GERENCIA: solo SUPERVISOR/OPERADOR (backend debe bloquear GERENCIA->GERENCIA igual)
        # ----------------------------
        st.markdown("### Crear nuevo usuario")

        roles_create = ["SUPERVISOR", "OPERADOR"]
        if rol == "ROOT":
            roles_create = ["SUPERVISOR", "OPERADOR", "GERENCIA", "AGENTE"]

        c1, c2 = st.columns(2)
        with c1:
            nuevo_usuario = st.text_input("Usuario (login)", key="new_user_username")
            nombre_user = st.text_input("Nombre completo", key="new_user_full_name")
        with c2:
            password_user = st.text_input("Contraseña", type="password", key="new_user_password")
            rol_nuevo = st.selectbox("Rol", roles_create, key="new_user_role")

        if st.button("Crear usuario", key="btn_crear_usuario"):
            if not nuevo_usuario.strip() or not nombre_user.strip() or not password_user.strip():
                flash_set("Usuarios", "err", "Complete todos los campos")
                st.rerun()

            r_create = api_post("/admin/usuarios", json={
                "usuario": nuevo_usuario.strip(),
                "nombre": nombre_user.strip(),
                "password": password_user.strip(),
                "rol": rol_nuevo
            })

            if r_create.status_code == 200:
                flash_set("Usuarios", "ok", "Usuario creado correctamente")

                # limpiar inputs
                for k in ("new_user_username", "new_user_full_name", "new_user_password", "new_user_role"):
                    st.session_state.pop(k, None)

                # limpiar selección tabla para evitar reabrir modal
                st.session_state._reset_user_editor = True
                st.rerun()
            else:
                flash_set("Usuarios", "err", f"Error al crear usuario: {r_create.text}")
                st.rerun()

        # ----------------------------
        # MODAL EDITAR USUARIO (igual a trabajadores)
        # ----------------------------
        if st.session_state.show_user_modal and st.session_state.edit_user_usuario:
            usuario_id = st.session_state.edit_user_usuario
            user_row = st.session_state._edit_user_row or {}

            @st.dialog("Editar usuario")
            def modal_editar_usuario():
                with st.form(key=f"form_editar_usuario_{usuario_id}"):
                    nombre_e = st.text_input("Nombre", value=user_row.get("nombre") or "")
                    activo_e = st.checkbox("Activo", value=bool(user_row.get("activo", True)))

                    # Roles editables
                    roles_edit = ["SUPERVISOR", "OPERADOR", "GERENCIA", "AGENTE"]
                    if rol == "GERENCIA":
                        roles_edit = ["SUPERVISOR", "OPERADOR", "AGENTE"]

                    current_rol = (user_row.get("rol") or "OPERADOR").upper()
                    if current_rol not in roles_edit:
                        current_rol = roles_edit[0]

                    rol_e = st.selectbox("Rol", roles_edit, index=roles_edit.index(current_rol))

                    st.markdown("#### Cambiar contraseña (opcional)")
                    new_pass = st.text_input("Nueva contraseña", type="password")

                    confirmar_eliminacion = st.checkbox(
                        "Confirmo eliminación permanente del usuario",
                        value=False,
                        key=f"confirm_delete_user_{usuario_id}",
                    )

                    b1, b2, b3 = st.columns(3)
                    guardar = b1.form_submit_button("💾 Guardar")
                    eliminar = b2.form_submit_button("🗑️ Eliminar")
                    cancelar = b3.form_submit_button("❌ Cancelar")

                if cancelar:
                    st.session_state.show_user_modal = False
                    st.session_state.edit_user_usuario = None
                    st.session_state._edit_user_row = None
                    st.session_state.pop("tabla_usuarios_editar", None)
                    st.rerun()

                if guardar:
                    # 1) update datos generales
                    r_upd = api_put(f"/admin/usuarios/{usuario_id}", json={
                        "nombre": nombre_e.strip(),
                        "rol": rol_e,
                        "activo": activo_e
                    })

                    if r_upd.status_code != 200:
                        st.error("Error actualizando usuario")
                        st.code(r_upd.text)
                        st.stop()

                    # 2) update password si escribió algo
                    if new_pass.strip():
                        r_pwd = api_put(f"/admin/usuarios/{usuario_id}/password", json={
                            "password": new_pass.strip()
                        })
                        if r_pwd.status_code != 200:
                            st.error("Error cambiando contraseña")
                            st.code(r_pwd.text)
                            st.stop()

                    flash_set("Usuarios", "ok", "Usuario actualizado")
                    st.session_state.show_user_modal = False
                    st.session_state.edit_user_usuario = None
                    st.session_state._edit_user_row = None
                    st.session_state.pop("tabla_usuarios_editar", None)
                    st.rerun()

                if eliminar:
                    if not confirmar_eliminacion:
                        st.warning("Marque la confirmación para eliminar el usuario")
                        st.stop()

                    r_del = api_delete(f"/admin/usuarios/{usuario_id}")
                    if r_del.status_code != 200:
                        st.error("Error eliminando usuario")
                        st.code(r_del.text)
                        st.stop()

                    flash_set("Usuarios", "ok", "Usuario eliminado correctamente")
                    st.session_state.show_user_modal = False
                    st.session_state.edit_user_usuario = None
                    st.session_state._edit_user_row = None
                    st.session_state.pop("tabla_usuarios_editar", None)
                    st.rerun()

            modal_editar_usuario()
