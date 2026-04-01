# 📦 Sistema de Generación y Gestión de Códigos QR

Producto orientado a la **generación, administración y validación de códigos QR**, desarrollado como una **aplicación web en Python + Streamlit**, con persistencia en **PostgreSQL** y soporte para **lectura desde dispositivos móviles**.

El sistema permite asociar información estructurada a cada QR (por ejemplo: DNI, UID, fecha de proceso), facilitando su uso en escenarios de control, registro e impresión.

---

## 🚀 Características principales

- Generación de **códigos QR únicos**
- Asociación de información estructurada a cada QR
- Visualización y administración desde interfaz web
- Preparado para **lectura desde dispositivos móviles**
- Persistencia de datos en **PostgreSQL**
- Arquitectura escalable para nuevas reglas de validación

---

## 🧱 Arquitectura general

El producto se compone de los siguientes elementos:

- **Interfaz Web (Streamlit)**  
  Panel para creación, visualización y gestión de códigos QR.

- **Backend lógico (Python)**  
  Encargado de la generación, validación y reglas de negocio del QR.

- **Base de datos (PostgreSQL)**  
  Almacenamiento de la información asociada a cada QR y su estado.

- **Dispositivo móvil / lector QR**  
  Lectura y envío del contenido QR para validación.


## 🛠️ Tecnologías utilizadas

- **Python 3.10+**
- **Streamlit** (Interfaz web)
- **PostgreSQL** (Base de datos)
- **Librerías de generación QR**
- **Git & GitHub**

---

## ⚙️ Puesta en marcha y correcciones recomendadas

1. Cree su entorno virtual local (no reutilice `venv/` versionado):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copie variables de entorno:
   ```bash
   cp .env.example .env
   cp .env.example backend/.env
   ```
3. Ajuste credenciales reales de base de datos y secretos en `.env` y `backend/.env`.
   - Puede ajustar expiración de sesión con `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` y `REFRESH_COOKIE_DAYS`.
4. Levante backend y frontend:
   ```bash
   uvicorn backend.app.main:app --reload --port 8000
   streamlit run ui_web/streamlit_app.py
   ```

### Restaurar desde dump .sql

Si tiene un backup SQL de la base anterior, puede restaurarlo asi:

```bash
bash scripts/restore_from_sql.sh /ruta/al/dump.sql
```

Este script usa `DB_*` desde `backend/.env` (si existe) o `.env`.

Si desea sobreescribir todo (limpiar tablas y datos actuales):

```bash
bash scripts/restore_from_sql.sh --clean /ruta/al/dump.sql
```

Puede indicar destino manualmente:

```bash
bash scripts/restore_from_sql.sh --clean --host 127.0.0.1 --port 5432 --user postgres --name qr_produccion /ruta/al/dump.sql
```

Si desea forzar prompt de contrasena:

```bash
bash scripts/restore_from_sql.sh --prompt-pass /ruta/al/dump.sql
```

Si usa autenticacion peer (sin contrasena), indique:

```bash
sudo -u postgres bash scripts/restore_from_sql.sh --no-pass --clean --host 127.0.0.1 --port 5432 --user postgres /ruta/al/dump.sql
```

### Crear backup .sql

Para respaldar toda la base actual:

```bash
bash scripts/backup_to_sql.sh
```

Por defecto guarda en `backups/` con timestamp. Puede indicar ruta:

```bash
bash scripts/backup_to_sql.sh /ruta/al/backup.sql
```

Si desea incluir roles/privilegios globales:

```bash
bash scripts/backup_to_sql.sh --globals
```

Para respaldar una base anterior (otro host/puerto/usuario):

```bash
bash scripts/backup_to_sql.sh --host 10.0.0.5 --port 5432 --user antiguo --pass "MiClave" --name antigua_db /ruta/backup.sql
```

Si no pasa `--pass` y `DB_PASS` no esta definido, el script solicitara la contrasena por prompt.

Nota: los parametros `--host/--port/--user/--pass/--name` tienen prioridad sobre el `.env`.

Puede usar un .env especifico:

```bash
bash scripts/backup_to_sql.sh --env /ruta/otro.env /ruta/backup.sql
```

---

## 🖨️ Print Agent (deteccion automatica de impresoras)

El Print Agent detecta impresoras del sistema operativo:
- Linux: usa CUPS (lpstat)
- Windows: usa win32print (pywin32)

### Linux

```bash
bash scripts/run_print_agent_linux.sh
```

### Windows (PowerShell)

```powershell
.
scripts\run_print_agent_windows.ps1
```

### Windows como servicio (NSSM)

1) Instale NSSM desde https://nssm.cc/download y agregue `nssm` al PATH.
2) Ejecute:

```powershell
.
scripts\install_print_agent_windows_service.ps1
```

Servicio: `qr-print-agent`

Variables soportadas:
- `PRINT_AGENT_TOKEN` (o `AGENT_TOKEN`)
- `AGENT_ID`
- `AGENT_HOST`
- `AGENT_PORT`

La UI debe usar el mismo token en "Agent token (X-Agent-Token)".

También puede iniciar ambos con un solo comando:

```bash
bash scripts/run_dev.sh
```

### PostgreSQL nativo (sin contenedor)

Si desea trabajar con PostgreSQL instalado en su PC (servicio del sistema), use:

```bash
sudo bash scripts/install_postgres_native.sh
```

Si solo necesita (re)crear usuario/base del proyecto en PostgreSQL ya instalado:

```bash
bash scripts/create_qr_user.sh
```

Este script:
- instala `postgresql` y `postgresql-contrib`
- habilita el servicio `postgresql`
- crea usuario `qr_user` y base `qr_produccion`
- valida la conexion final

Verifique el puerto activo del cluster y use ese valor en `DB_PORT`:

```bash
pg_lsclusters
```

En Ubuntu puede quedar en `5433` si `5432` estaba ocupado durante la instalacion.

Si tiene un contenedor Docker ocupando el puerto `5432`, detengalo antes de ejecutar el script.

> Nota: si `venv/bin/python` falla con error de symlink (ej. `unsupported reparse tag`), elimine `venv/` y use un entorno nuevo como `.venv/`.

```bash
rm -rf venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

👤 Autor

Juan Luis Diaz Aylas
Ingeniero de Sistemas Computacionales
GitHub: https://github.com/thediegomisha
