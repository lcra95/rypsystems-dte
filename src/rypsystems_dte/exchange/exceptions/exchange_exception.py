"""
Exchange Exception - Excepción general del componente Exchange

Traducción de ExchangeException de LibreDTE PHP.
"""


class ExchangeException(Exception):
    """
    Excepción general del componente "billing.exchange".

    Se utiliza para errores relacionados con el intercambio de documentos
    tributarios electrónicos entre contribuyentes.
    """

    def __init__(self, message: str = "Error en el intercambio de documentos", code: int = 0):
        """
        Constructor de la excepción.

        Args:
            message: Mensaje descriptivo del error
            code: Código de error específico
        """
        super().__init__(message)
        self.code = code

    def __str__(self) -> str:
        """Representación string de la excepción."""
        if self.code:
            return f"[{self.code}] {super().__str__()}"
        return super().__str__()