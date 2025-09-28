"""
Integration module for SII communication.

This module provides integration with Chilean SII (Servicio de Impuestos Internos)
web services for electronic document submission, status queries, and receipt handling.
"""

from .sii_client import SiiClient
from .soap_client import SoapClient
from .rest_client import RestClient
from .exceptions import (
    IntegrationException,
    SiiConnectionException,
    SiiAuthenticationException,
    SiiValidationException,
    SiiTimeoutException
)
from .models.sii_response import SiiResponse, SiiDocumentStatus
from .models.sii_request import SiiRequest

__all__ = [
    'SiiClient',
    'SoapClient',
    'RestClient',
    'IntegrationException',
    'SiiConnectionException',
    'SiiAuthenticationException',
    'SiiValidationException',
    'SiiTimeoutException',
    'SiiResponse',
    'SiiDocumentStatus',
    'SiiRequest'
]