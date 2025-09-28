"""
Document Type Enum - Tipos de documentos para intercambio

Traducción del enum DocumentType de LibreDTE PHP.
Define los tipos de documentos que se pueden intercambiar con LibreDTE.
"""

from enum import Enum
from typing import List, Optional, Dict
from .process_type import ProcessType


class DocumentType(Enum):
    """
    Define los tipos de documentos que se pueden intercambiar con LibreDTE.

    Este enum lista los tipos de documentos que se pueden intercambiar en los
    sobres. Como un sobre debe contener documentos del mismo tipo, este atributo
    se asigna al sobre, no al documento.
    """

    # Documento de cotización
    QUOTATION = 'urn:fdc:libredte.cl:2025:doc:quotation'

    # Propuesta
    PROPOSAL = 'urn:fdc:libredte.cl:2025:doc:proposal'

    # Oferta a licitación
    BID = 'urn:fdc:libredte.cl:2025:doc:bid'

    # Contrato
    CONTRACT = 'urn:fdc:libredte.cl:2025:doc:contract'

    # Catálogo
    CATALOGUE = 'urn:fdc:libredte.cl:2025:doc:catalogue'

    # Orden de compra
    ORDER = 'urn:fdc:libredte.cl:2025:doc:order'

    # Aviso de despacho
    DISPATCH_ADVICE = 'urn:fdc:libredte.cl:2025:doc:dispatch_advice'

    # Nota de entrega
    DELIVERY_NOTE = 'urn:fdc:libredte.cl:2025:doc:delivery_note'

    # Factura
    INVOICE = 'urn:fdc:libredte.cl:2025:doc:invoice'

    # Nota de crédito
    CREDIT_NOTE = 'urn:fdc:libredte.cl:2025:doc:credit_note'

    # Nota de débito
    DEBIT_NOTE = 'urn:fdc:libredte.cl:2025:doc:debit_note'

    # Respuesta de aplicación
    APPLICATION_RESPONSE = 'urn:fdc:libredte.cl:2025:doc:application_response'

    # Acuse de recibo
    RECEIPT_ADVICE = 'urn:fdc:libredte.cl:2025:doc:receipt_advice'

    # Recordatorio
    REMINDER = 'urn:fdc:libredte.cl:2025:doc:reminder'

    # Ticket de soporte
    TICKET = 'urn:fdc:libredte.cl:2025:doc:ticket'

    # Reporte
    REPORT = 'urn:fdc:libredte.cl:2025:doc:report'

    # Libro de registros contables o tributarios
    BOOK = 'urn:fdc:libredte.cl:2025:doc:book'

    # Cualquier DTE, menos boletas
    B2B = 'urn:fdc:libredte.cl:2025:doc:b2b'

    # Boletas
    B2C = 'urn:fdc:libredte.cl:2025:doc:b2c'

    def get_id(self) -> str:
        """
        Obtiene el ID del tipo de documento.

        El ID tiene la estructura de una URN según RFC 4198.
        Ejemplo: `urn:fdc:libredte.cl:2025:doc:invoice`

        Returns:
            ID del tipo de documento
        """
        return self.value

    def is_valid_for_process(self, process: ProcessType) -> bool:
        """
        Verifica si un tipo de documento es válido para un proceso específico.

        Args:
            process: Tipo de proceso a validar

        Returns:
            True si el documento es válido para el proceso, False en caso contrario
        """
        return process in _MAP_TO_PROCESSES.get(self.value, [])

    def get_reference_code(self) -> Optional[str]:
        """
        Entrega el código de referencia (TpoDocRef), si existe, para ser
        utilizado en la sección de referencias de un DTE.

        Returns:
            Código de referencia o None si no existe
        """
        return _MAP_TO_REFERENCE.get(self.value)

    @classmethod
    def try_from_dte(cls, code: int) -> Optional['DocumentType']:
        """
        Intenta obtener un tipo de documento a partir de un código DTE chileno.

        Args:
            code: Código del DTE. Ejemplo: 33 para factura electrónica

        Returns:
            El tipo de documento correspondiente o None si no existe un mapeo
        """
        return _MAP_FROM_DTE.get(code)


# Mapa que define en qué procesos pueden ser usados los documentos
_MAP_TO_PROCESSES: Dict[str, List[ProcessType]] = {
    'urn:fdc:libredte.cl:2025:doc:quotation': [ProcessType.QUOTING, ProcessType.SOURCING],
    'urn:fdc:libredte.cl:2025:doc:proposal': [ProcessType.QUOTING, ProcessType.TENDERING],
    'urn:fdc:libredte.cl:2025:doc:bid': [ProcessType.TENDERING],
    'urn:fdc:libredte.cl:2025:doc:contract': [ProcessType.CONTRACTING],
    'urn:fdc:libredte.cl:2025:doc:catalogue': [ProcessType.SOURCING],
    'urn:fdc:libredte.cl:2025:doc:order': [ProcessType.ORDERING],
    'urn:fdc:libredte.cl:2025:doc:dispatch_advice': [ProcessType.FULFILLMENT],
    'urn:fdc:libredte.cl:2025:doc:delivery_note': [ProcessType.FULFILLMENT],
    'urn:fdc:libredte.cl:2025:doc:invoice': [ProcessType.BILLING],
    'urn:fdc:libredte.cl:2025:doc:credit_note': [ProcessType.BILLING],
    'urn:fdc:libredte.cl:2025:doc:debit_note': [ProcessType.BILLING],
    'urn:fdc:libredte.cl:2025:doc:application_response': [ProcessType.BILLING],
    'urn:fdc:libredte.cl:2025:doc:receipt_advice': [ProcessType.BILLING],
    'urn:fdc:libredte.cl:2025:doc:reminder': [ProcessType.PAYMENT],
    'urn:fdc:libredte.cl:2025:doc:ticket': [ProcessType.SUPPORT],
    'urn:fdc:libredte.cl:2025:doc:report': [ProcessType.REPORTING],
    'urn:fdc:libredte.cl:2025:doc:book': [ProcessType.REPORTING],
    'urn:fdc:libredte.cl:2025:doc:b2b': [ProcessType.BILLING, ProcessType.FULFILLMENT, ProcessType.REPORTING],
    'urn:fdc:libredte.cl:2025:doc:b2c': [ProcessType.BILLING, ProcessType.REPORTING],
}

# Mapa que relaciona un tipo de documento con un código referencia
_MAP_TO_REFERENCE: Dict[str, str] = {
    'urn:fdc:libredte.cl:2025:doc:quotation': 'COT',
    'urn:fdc:libredte.cl:2025:doc:proposal': 'PRO',
    'urn:fdc:libredte.cl:2025:doc:bid': '805',
    'urn:fdc:libredte.cl:2025:doc:contract': '803',
    'urn:fdc:libredte.cl:2025:doc:catalogue': 'CAT',
    'urn:fdc:libredte.cl:2025:doc:order': '801',
    'urn:fdc:libredte.cl:2025:doc:dispatch_advice': '052',
    'urn:fdc:libredte.cl:2025:doc:delivery_note': 'DEN',
    'urn:fdc:libredte.cl:2025:doc:invoice': 'INV',
    'urn:fdc:libredte.cl:2025:doc:credit_note': 'CNO',
    'urn:fdc:libredte.cl:2025:doc:debit_note': 'DNO',
    'urn:fdc:libredte.cl:2025:doc:application_response': 'RES',
    'urn:fdc:libredte.cl:2025:doc:receipt_advice': 'REC',
    'urn:fdc:libredte.cl:2025:doc:reminder': 'PAY',
    'urn:fdc:libredte.cl:2025:doc:ticket': 'TIC',
}

# Mapa que relaciona un DTE de Chile con uno de los tipos de documentos
_MAP_FROM_DTE: Dict[int, DocumentType] = {
    33: DocumentType.INVOICE,
    34: DocumentType.INVOICE,
    39: DocumentType.INVOICE,
    41: DocumentType.INVOICE,
    46: DocumentType.INVOICE,
    52: DocumentType.DISPATCH_ADVICE,
    56: DocumentType.DEBIT_NOTE,
    61: DocumentType.CREDIT_NOTE,
    110: DocumentType.INVOICE,
    111: DocumentType.DEBIT_NOTE,
    112: DocumentType.CREDIT_NOTE,
}