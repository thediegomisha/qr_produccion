#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    printf 'Ejecute este instalador una sola vez con sudo.\n' >&2
    exit 1
fi

SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
DEST="/usr/local/lib/qr_produccion-web"
install -d -m 0755 "${DEST}"
install -m 0755 "${SCRIPT_DIR}/deploy_web_release.py" "${DEST}/deploy_web_release.py"
install -m 0755 "${SCRIPT_DIR}/package_web_release.py" "${DEST}/package_web_release.py"

cat > /usr/local/bin/actualizar-qr-web <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec python3 /usr/local/lib/qr_produccion-web/deploy_web_release.py "$@"
SH
chmod 0755 /usr/local/bin/actualizar-qr-web
printf 'Actualizador instalado. Uso: sudo actualizar-qr-web /ruta/qr-web-VERSION.zip\n'
