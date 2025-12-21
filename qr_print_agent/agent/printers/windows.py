class WindowsPrinterProvider:
    def list_printers(self):
        import win32print
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        printers = win32print.EnumPrinters(flags)
        return [p[2] for p in printers]

    def print_raw(self, printer, data: bytes):
        import win32print
        h = win32print.OpenPrinter(printer)
        try:
            win32print.StartDocPrinter(h, 1, ("Etiqueta", None, "RAW"))
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, data)
            win32print.EndPagePrinter(h)
            win32print.EndDocPrinter(h)
        finally:
            win32print.ClosePrinter(h)
