import platform

OS = platform.system()

if OS == "Windows":
    from agent.printers.windows import WindowsPrinterProvider as Provider
elif OS == "Linux":
    from agent.printers.linux import LinuxPrinterProvider as Provider
else:
    raise RuntimeError("Sistema operativo no soportado")

printer_provider = Provider()

def list_printers():
    return printer_provider.list_printers()
