"""
SII Web Services Integration.

Implementación completa de servicios web del SII chileno incluyendo:
- Envío de documentos al SII
- Verificación de estado de documentos
- Recepción de acknowledgments
- Manejo de errores y reintentos
- Integración SOAP y REST
"""

from .sii_endpoints import SiiEndpoints, SiiEnvironment
from .soap_service import SoapService
from .boleta_service import BoletaService
from .registro_reclamo_service import RegistroReclamoService
from .exceptions import (
    SiiWebServiceException,
    SiiAuthenticationError,
    SiiValidationError,
    SiiCommunicationError,
    SiiTimeoutError,
    SiiDocumentRejectedError,
    SiiRateLimitError
)

__all__ = [
    'SiiEndpoints',
    'SiiEnvironment',
    'SoapService',
    'BoletaService',
    'RegistroReclamoService',
    'SiiWebServiceException',
    'SiiAuthenticationError',
    'SiiValidationError',
    'SiiCommunicationError',
    'SiiTimeoutError',
    'SiiDocumentRejectedError',
    'SiiRateLimitError'
]