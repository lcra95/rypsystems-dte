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
from .rest_service import RestService
from .document_sender import DocumentSender, SendingProtocol, SendingResult
from .status_checker import StatusChecker, DocumentStatus, StatusQueryResult
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
    'RestService',
    'DocumentSender',
    'SendingProtocol',
    'SendingResult',
    'StatusChecker',
    'DocumentStatus',
    'StatusQueryResult',
    'SiiWebServiceException',
    'SiiAuthenticationError',
    'SiiValidationError',
    'SiiCommunicationError',
    'SiiTimeoutError',
    'SiiDocumentRejectedError',
    'SiiRateLimitError'
]