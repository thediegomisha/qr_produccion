from fastapi import FastAPI, HTTPException
from printers import listar_impresoras
from zpl_sender import enviar_zpl

app = FastAPI(title="QR Printer Agent")

@app.get("/printers")
def printers():
    return listar_impresoras()


@app.post("/print")
def print_label(data: dict):
    printer = data.get("printer")
    zpl = data.get("zpl")

    if not printer or not zpl:
        raise HTTPException(400, "printer y zpl son obligatorios")

    enviar_zpl(printer, zpl)
    return {"ok": True}