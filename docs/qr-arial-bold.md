# Arial Negrita en el centro del QR

## Diseño

- Arial **Bold** real, tamaño 24 puntos de la cuadrícula de impresión (antes 22).
  Son dots a 203 dpi, no puntos tipográficos de 1/72 de pulgada.
- Cuadro blanco de 48 × 30 dots; etiqueta 25 × 25 mm y cuatro columnas sin cambios.
- La altura de la fuente no se reduce para ajustar el texto. Los códigos anchos
  como `WWW` se condensan horizontalmente dentro del margen de dos dots.
- PNG e impresión usan un mismo panel monocromo de 1 bit, sin tramado.
- El texto se envía como `^GFA` ASCII, no como fuente residente `^A0N`.
  La impresora y el Print Agent de Windows no necesitan instalar Arial.
- El gráfico aumenta el tamaño del trabajo ZPL, no el payload del QR:
  se mantienen `t`, `dni`, `id` y `p`.

## Fuente externa

La fuente fue indicada por el usuario:

`https://github.com/RedBalloonShenanigans/MonitorDarkly/blob/master/fonts/arialbd.ttf`

El archivo revisado identifica su familia y estilo como **Arial / Bold**.
SHA-256:

`df70597f0bdf49da3af270138f8a34396e4f5618c671a1db3480e626f38aaece`

La disponibilidad del archivo en un repositorio público no concede una licencia
de redistribución. El administrador debe verificar que su uso esté autorizado.
No se incorpora el TTF al repositorio ni al paquete de actualización web.

## Instalar antes de desplegar

Copiar `scripts/install_qr_font.py` al servidor junto con el ZIP de actualización.
En el servidor:

```bash
sudo python3 "$HOME/qr-update/install_qr_font.py"
```

El instalador descarga únicamente el archivo indicado y verifica su SHA-256
antes de instalarlo en:

`/opt/qr_produccion-web/shared/fonts/arialbd.ttf`

Alternativamente, copiar el archivo descargado y usarlo sin acceso a Internet:

```bash
sudo python3 "$HOME/qr-update/install_qr_font.py" \
  --source "$HOME/qr-update/arialbd.ttf"
```

El archivo se publica atómicamente con permisos 644 y se conserva fuera de las
carpetas de releases. El instalador no reemplaza fuentes existentes distintas ni
sigue enlaces simbólicos en el archivo destino.

La ubicación predeterminada funciona sin variables nuevas. Para otra ubicación,
configurar `QR_FONT_PATH` en el entorno efectivo del backend. No hay sustitución
silenciosa por otra familia si falta el archivo configurado.

Después instalar el ZIP con el actualizador web habitual. No es necesario
reinstalar la APK ni el Print Agent, ni rotar tokens por este cambio.
Imprimir una fila y verificar visualmente negrita y lectura antes de uso masivo.

## Pruebas

Las pruebas de CI usan explícitamente una fuente Bold disponible en el sistema,
sin redistribuir Arial. La validación local de este cambio se ejecuta con el
archivo Arial Bold real montado en un sandbox sin red externa. Se comprueba que
el bitmap ZPL reconstruido sea idéntico al panel del PNG y que solo cambie el
área central; también se prueba la decodificación con el WASM de la PWA.

Resultado de esta validación: **150 pruebas Python aprobadas** con PostgreSQL
aislado y Arial real; **16 combinaciones de decodificación aprobadas** (UVA/PALTA,
códigos numéricos y de letras, 120/160 px sin desenfoque, 180 px con blur de 1 px,
y 220 px con blur de 1,5 px). La prueba física de impresión sigue siendo necesaria.
