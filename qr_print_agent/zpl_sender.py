import platform
import socket
import subprocess
import tempfile
import os


def enviar_zpl(printer_name: str, zpl: str):
    sistema = platform.system()

    if sistema == "Windows":
        _send_windows(printer_name, zpl)
    else:
        _send_linux(printer_name, zpl)


def _send_windows(printer_name, zpl):
    import win32print

    hPrinter = win32print.OpenPrinter(printer_name)
    try:
        job = win32print.StartDocPrinter(hPrinter, 1, ("QR Label", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, zpl.encode("utf-8"))
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
    finally:
        win32print.ClosePrinter(hPrinter)


def _send_linux(printer_name, zpl):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(zpl.encode("utf-8"))
        temp_file = f.name

    subprocess.run(["lp", "-d", printer_name, temp_file])
    os.remove(temp_file)


def _send_network(ip: str, port: int, zpl: str):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))
        s.sendall(zpl.encode("utf-8"))
