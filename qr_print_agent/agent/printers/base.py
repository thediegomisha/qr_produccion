from abc import ABC, abstractmethod

class PrinterProvider(ABC):

    @abstractmethod
    def list_printers(self) -> list[str]:
        pass

    @abstractmethod
    def print_raw(self, printer: str, data: bytes):
        pass
