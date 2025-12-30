# app/services/reniec_service.py
import os
import requests

BASE_URL = "https://api.perudevs.com/api/v1/dni/simple"

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

    return {
        "dni": data.get("id") or dni,
        "nombre": data.get("nombres"),
        "apellido_paterno": data.get("apellido_paterno"),
        "apellido_materno": data.get("apellido_materno"),
    }
