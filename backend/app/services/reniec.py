# app/services/reniec_service.py
import os
import requests

BASE_URL = "https://api.perudevs.com/api/v1/dni/complete"

def consultar_dni(dni: str):
    api_key = os.getenv("APIPERU_TOKEN")  # leer en runtime, no en import

    if not api_key:
        print("❌ APIPERU_TOKEN no configurado")
        return None

    try:
        r = requests.get(
            BASE_URL,
            params={"document": dni, "key": api_key},
            timeout=10,
        )
    except requests.RequestException as e:
        print("❌ Error de red consultando PeruDevs:", str(e))
        return None

    print("🔁 STATUS APIPERU:", r.status_code)
    print("📦 BODY APIPERU:", r.text)

    if r.status_code != 200:
        return None

    payload = r.json()

    # PeruDevs: estado: true/false, resultado: {...}
    if not payload.get("estado"):
        return None

    data = payload.get("resultado") or {}
    if not data:
        return None

    nombres = (
        data.get("nombres")
        or data.get("nombre")
        or data.get("prenombres")
        or ""
    )

    ap_pat = (
        data.get("apellido_paterno")
        or data.get("apellidoPaterno")
        or data.get("ape_paterno")
        or ""
    )

    ap_mat = (
        data.get("apellido_materno")
        or data.get("apellidoMaterno")
        or data.get("ape_materno")
        or ""
    )

    fecha_nacimiento = (
        data.get("fecha_nacimiento")
        or data.get("fecha_de_nacimiento")
        or data.get("nacimiento")
        or data.get("fec_nacimiento")
    )

    return {
        "dni": data.get("id") or dni,
        "nombre": nombres,
        "apellido_paterno": ap_pat,
        "apellido_materno": ap_mat,
        "fecha_nacimiento": fecha_nacimiento,
    }

def consultar_dni_fullname(dni: str):
    r = consultar_dni(dni)
    if not r:
        return None

    nombres = (r.get("nombre") or "").strip()
    ap_pat = (r.get("apellido_paterno") or "").strip()
    ap_mat = (r.get("apellido_materno") or "").strip()

    apellidos = " ".join([x for x in [ap_pat, ap_mat] if x]).strip()

    return {
        "dni": r.get("dni") or dni,
        "nombres": nombres,
        "apellidos": apellidos,
        "fuente": "PERUDEVS",
    }
