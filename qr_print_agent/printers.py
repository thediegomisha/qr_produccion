import platform
import subprocess

def listar_impresoras():
    sistema = platform.system()
    if sistema == "Windows":
        return _windows_printers()
    else:
        return _linux_printers()

def _windows_printers():
    # IMPORTANTE: La importación debe estar aquí dentro
    try:
        import win32print
        # EnumPrinters(2) corresponde a PRINTER_ENUM_LOCAL
        printers = win32print.EnumPrinters(2)
        return [p[2] for p in printers]
    except ImportError:
        return ["Error: pywin32 no instalado"]

def _linux_printers():
    try:
        # lpstat -p es el estándar en Linux/CUPS para 2025
        result = subprocess.check_output(["lpstat", "-p"], text=True, stderr=subprocess.DEVNULL)
        printers = []
        for line in result.splitlines():
            if line.startswith("printer"):
                printers.append(line.split()[1])
        return printers
    except Exception:
        return []
