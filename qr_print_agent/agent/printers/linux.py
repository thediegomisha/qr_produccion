import subprocess

class LinuxPrinterProvider:
    def list_printers(self):
        out = subprocess.check_output(["lpstat", "-a"]).decode()
        return [line.split()[0] for line in out.splitlines()]

    def print_raw(self, printer, data: bytes):
        p = subprocess.Popen(
            ["lp", "-d", printer],
            stdin=subprocess.PIPE
        )
        p.communicate(input=data)
