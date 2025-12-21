from fastapi import FastAPI, HTTPException
from agent.printers import printer_provider

app = FastAPI(title="Agente de impresion de QR")

@app.get("/printers")
def list_printers():
    return printer_provider.list_printers()

@app.post("/print")
def print_label(printer: str, raw: str):
    try:
        printer_provider.print_raw(printer, raw.encode())
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
