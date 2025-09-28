"""
Process Type Enum - Tipos de procesos comerciales

Traducción del enum ProcessType de LibreDTE PHP.
Define la lista de procesos comerciales para los que se pueden intercambiar documentos.
"""

from enum import Enum


class ProcessType(Enum):
    """
    Define la lista de procesos comerciales para los que se pueden intercambiar documentos.

    Para la definición de las URN se utilizó RFC 4198.
    @link https://www.rfc-editor.org/rfc/rfc4198.html
    """

    # Proceso de cotización
    QUOTING = 'urn:fdc:libredte.cl:2025:prac:quoting'

    # Proceso de licitación
    TENDERING = 'urn:fdc:libredte.cl:2025:prac:tendering'

    # Proceso de contratación
    CONTRACTING = 'urn:fdc:libredte.cl:2025:prac:contracting'

    # Proceso de abastecimiento
    SOURCING = 'urn:fdc:libredte.cl:2025:poacc:sourcing'

    # Proceso de orden de compra
    ORDERING = 'urn:fdc:libredte.cl:2025:poacc:ordering'

    # Proceso de cumplimiento de órdenes
    FULFILLMENT = 'urn:fdc:libredte.cl:2025:poacc:fulfillment'

    # Proceso de facturación
    BILLING = 'urn:fdc:libredte.cl:2025:poacc:billing'

    # Proceso de pago
    PAYMENT = 'urn:fdc:libredte.cl:2025:poacc:payment'

    # Proceso de soporte al cliente
    SUPPORT = 'urn:fdc:libredte.cl:2025:poacc:support'

    # Proceso de reportes para control continuo
    REPORTING = 'urn:fdc:libredte.cl:2025:ctc:reporting'

    def get_id(self) -> str:
        """
        Obtiene el ID del tipo de proceso.

        El ID tiene la estructura de una URN según RFC 4198.
        Ejemplo: `urn:fdc:libredte.cl:2025:poacc:billing`

        Returns:
            ID del tipo de proceso
        """
        return self.value