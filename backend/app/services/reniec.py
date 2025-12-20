# app/services/reniec_service.py
import requests
import os

API_KEY = os.getenv("APIPERU_TOKEN")
BASE_URL = "https://apiperu.dev/api"

def consultar_dni(dni: str):
    if not API_KEY:
        print("❌ APIPERU_TOKEN no configurado")
        return None

    r = requests.get(
        f"{BASE_URL}/dni/{dni}",
        headers={
            "Authorization": f"Bearer {API_KEY}"
        },
        timeout=10
    )

    print("🔁 STATUS APIPERU:", r.status_code)
    print("📦 BODY APIPERU:", r.text)

    if r.status_code != 200:
        return None

    payload = r.json()

    # 🔑 VALIDAR FORMATO REAL
    if not payload.get("success"):
        return None

    data = payload.get("data")
    if not data:
        return None

    return {
        "dni": data.get("numero"),
        "nombre": data.get("nombres"),
        "apellido_paterno": data.get("apellido_paterno"),
        "apellido_materno": data.get("apellido_materno"),
    }
