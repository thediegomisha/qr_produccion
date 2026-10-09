# Actualizaciones web independientes de la impresión

## Arquitectura

El servidor web ejecuta Streamlit y FastAPI. El Print Agent recibe trabajos ZPL mediante `/jobs` y permanece instalado como servicio independiente en Windows o en el equipo que alcanza la impresora Ethernet.

```text
Usuarios → Streamlit/FastAPI → Print Agent estable → Impresora Ethernet
```

Una modificación de lotes, reportes, usuarios o interfaces se despliega únicamente en el servidor web. El agente solo requiere una actualización propia cuando cambia su implementación o su protocolo. El formato actual de los trabajos (`printer`, `raw_base64`, `copies`) y su autenticación con `X-Agent-Token` se mantienen.

## Preparar el paquete

En el proyecto de desarrollo:

```bash
python3 scripts/package_web_release.py --version web-20261007-01
```

Resultado: `dist/web/qr-web-web-20261007-01.zip`. También puede utilizar una versión propia o dejar que se genere una fecha/hora automáticamente.

El paquete contiene código de backend/frontend, recursos, `requirements.txt` y las herramientas de actualización. Excluye el Print Agent, instaladores de impresión, `.env`, secretos de Streamlit, bases SQLite, colas de impresión, logs, entornos virtuales y archivos de pruebas. Cada archivo tiene un hash SHA-256 en el manifiesto. El manifiesto identifica la rama/commit y si incluye cambios locales pendientes.

## Preparación del servidor Linux: una sola vez

El actualizador está diseñado para el servidor `200.100.20.42`, cuyos servicios existentes son `qr-backend.service` y `qr-frontend.service`. Mantiene sus usuarios, permisos y archivos `EnvironmentFile` existentes, incluido `/etc/qr_produccion/qr-backend.env`.

1. Copiar estos tres archivos al servidor, en una carpeta temporal, sin reemplazar la instalación que imprime:
   - `scripts/install_web_updater.sh`
   - `scripts/deploy_web_release.py`
   - `scripts/package_web_release.py`
2. Desde esa carpeta ejecutar:

   ```bash
   sudo bash install_web_updater.sh
   ```

3. Copiar el primer ZIP web al servidor y ejecutar el comando de actualización indicado abajo.

No se ejecuta el instalador NSSM de impresión ni se cambia la configuración de la impresora. El backend debe tener ya configurada su dirección/token del agente. Los servicios de impresión deben ser independientes y no estar enlazados al reinicio de los servicios web mediante `PartOf`/`BindsTo`.

## Cada actualización: un comando

Copiar únicamente el ZIP web al servidor y ejecutar:

```bash
sudo actualizar-qr-web /ruta/qr-web-web-20261007-01.zip
```

El comando:

1. Valida el contenido y los hashes del paquete.
2. Prepara una versión en `/opt/qr_produccion-web/releases/VERSION`.
3. Instala las dependencias en un entorno Python propio de esa versión.
4. Conserva la configuración externa del servicio. En el primer despliegue, si el backend utiliza además un `.env` local, lo copia a `/opt/qr_produccion-web/shared/backend.env`; si Streamlit utiliza un `secrets.toml` local, lo conserva en `shared/frontend-secrets.toml`. Las siguientes versiones reutilizan esos archivos y no los sobrescriben.
5. Cambia el enlace `/opt/qr_produccion-web/current` y los overrides de los dos servicios web.
6. Reinicia **solo** `qr-backend.service` y `qr-frontend.service`.
7. Comprueba `/api/setup/status` y la salud de Streamlit. Si falla, restaura el enlace y los overrides anteriores y vuelve a iniciar los servicios con la configuración previa.

La instalación original `/opt/qr_produccion`, su agente y su entorno Python permanecen separados. El nuevo entorno web evita que instalar dependencias para una funcionalidad web cambie las librerías que utiliza la impresión. Los puertos predeterminados siguen siendo 8000 y 8501, por lo que se conservan las rutas LAN/WAN y Cloudflare existentes.

Las actualizaciones reinician brevemente la web. Si una funcionalidad nueva cambia la estructura de PostgreSQL, requiere su migración correspondiente: este actualizador no modifica ni restaura bases de datos.

## Verificación y soporte

```bash
systemctl status qr-backend.service qr-frontend.service --no-pager
journalctl -u qr-backend.service -u qr-frontend.service -n 80 --no-pager
curl http://127.0.0.1:8000/api/setup/status
```

La clave/dirección del agente, su ID, las impresoras y `DB_PATH` son configuración permanente del equipo que imprime. Se ajustan cuando cambia la infraestructura, no cada vez que se publica una mejora web.

El panel de impresoras restaura también el token guardado por usuario, además de URL y nombre de impresora. Las preferencias se conservan en el perfil del mismo usuario del servicio Streamlit (`~/.streamlit/printer_selection_USUARIO.json`), fuera de los archivos que actualiza el paquete.

Las pruebas del actualizador utilizan servicios simulados y carpetas temporales: verifican exclusiones, conservación de datos/configuración, entorno Python independiente y reversión ante fallos. No despliegan ni reinician servicios del servidor real.
