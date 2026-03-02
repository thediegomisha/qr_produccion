import socket

def enviar_zpl(ip: str, puerto: int, zpl: str):
    """
    Envío ZPL por TCP/IP (RAW 9100).
    Funciona para:
    - Zebra/TSC con red nativa
    - USB compartida como red (CUPS/Windows/PrintServer)
    """
    data = zpl.encode("utf-8")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect((ip, puerto))
        s.sendall(data)
