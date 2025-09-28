"""
Configuración de endpoints del SII.

Define las URLs y configuraciones para los diferentes servicios web del SII
en ambientes de producción y certificación.
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass


class SiiEnvironment(str, Enum):
    """Ambientes disponibles del SII."""
    CERTIFICACION = "certificacion"
    PRODUCCION = "produccion"


@dataclass
class SiiEndpointConfig:
    """Configuración de un endpoint específico del SII."""
    soap_url: str
    rest_url: Optional[str] = None
    wsdl_url: Optional[str] = None
    description: str = ""
    requires_auth: bool = True
    timeout: int = 30
    retry_attempts: int = 3


class SiiEndpoints:
    """
    Gestión centralizada de endpoints del SII.

    Proporciona URLs y configuraciones para todos los servicios web del SII
    en ambientes de certificación y producción.
    """

    # URLs base por ambiente
    BASE_URLS = {
        SiiEnvironment.CERTIFICACION: {
            'soap': 'https://maullin.sii.cl/DTEWS',
            'rest': 'https://apicert.sii.cl/recursos/v1',
            'portal': 'https://maullin.sii.cl'
        },
        SiiEnvironment.PRODUCCION: {
            'soap': 'https://palena.sii.cl/DTEWS',
            'rest': 'https://api.sii.cl/recursos/v1',
            'portal': 'https://www4.sii.cl'
        }
    }

    # Configuraciones de servicios específicos
    SERVICES = {
        # Autenticación y tokens
        'auth_seed': SiiEndpointConfig(
            soap_url='/CrSeed.jws',
            description='Obtención de semilla para autenticación',
            requires_auth=False,
            timeout=10
        ),
        'auth_token': SiiEndpointConfig(
            soap_url='/GetTokenFromSeed.jws',
            description='Obtención de token de autenticación',
            requires_auth=False,
            timeout=15
        ),

        # Envío de documentos
        'upload_dte': SiiEndpointConfig(
            soap_url='/services/wssDTEService',
            rest_url='/boleta.electronica.upload',
            wsdl_url='/services/wssDTEService?wsdl',
            description='Envío de documentos DTE',
            timeout=60
        ),
        'upload_libro': SiiEndpointConfig(
            soap_url='/services/wssLibroService',
            description='Envío de libros de compra/venta',
            timeout=120
        ),

        # Consulta de estados
        'query_estado': SiiEndpointConfig(
            soap_url='/services/QueryEstDte.jws',
            rest_url='/boleta.electronica.estado',
            description='Consulta estado de documentos DTE',
            timeout=30
        ),
        'query_estado_libro': SiiEndpointConfig(
            soap_url='/services/QueryEstLibro.jws',
            description='Consulta estado de libros',
            timeout=30
        ),

        # Recepción de acknowledgments
        'ack_reception': SiiEndpointConfig(
            soap_url='/services/wssRecepcionService',
            description='Recepción de acknowledgments',
            timeout=30
        ),

        # Servicios de consulta avanzada
        'consulta_folios': SiiEndpointConfig(
            soap_url='/services/wssDTEService',
            rest_url='/boleta.electronica.folios',
            description='Consulta de folios disponibles'
        ),
        'consulta_cesion': SiiEndpointConfig(
            soap_url='/services/wssCesionService',
            description='Consulta de cesiones de documentos'
        ),

        # Servicios específicos para boletas
        'boleta_honorarios': SiiEndpointConfig(
            soap_url='/services/wssBHEService',
            rest_url='/boleta.honorarios',
            description='Servicios de boletas de honorarios'
        ),

        # Servicios de reportes
        'reporte_consumo': SiiEndpointConfig(
            soap_url='/services/wssReporteService',
            rest_url='/reporte.consumo.folios',
            description='Reporte de consumo de folios'
        ),

        # Servicios de utilidades
        'utils_ping': SiiEndpointConfig(
            soap_url='/services/wssDTEService',
            description='Verificación de conectividad',
            requires_auth=False,
            timeout=10,
            retry_attempts=1
        )
    }

    def __init__(self, environment: SiiEnvironment = SiiEnvironment.CERTIFICACION):
        """
        Initialize SII endpoints manager.

        Args:
            environment: SII environment to use
        """
        self.environment = environment
        self.base_urls = self.BASE_URLS[environment]

    def get_soap_url(self, service: str) -> str:
        """
        Get full SOAP URL for a service.

        Args:
            service: Service name

        Returns:
            Complete SOAP URL

        Raises:
            ValueError: If service is not found
        """
        if service not in self.SERVICES:
            raise ValueError(f"Servicio '{service}' no encontrado")

        config = self.SERVICES[service]
        base_url = self.base_urls['soap']
        return f"{base_url}{config.soap_url}"

    def get_rest_url(self, service: str) -> Optional[str]:
        """
        Get full REST URL for a service.

        Args:
            service: Service name

        Returns:
            Complete REST URL or None if not available
        """
        if service not in self.SERVICES:
            return None

        config = self.SERVICES[service]
        if not config.rest_url:
            return None

        base_url = self.base_urls['rest']
        return f"{base_url}{config.rest_url}"

    def get_wsdl_url(self, service: str) -> Optional[str]:
        """
        Get WSDL URL for a SOAP service.

        Args:
            service: Service name

        Returns:
            WSDL URL or None if not available
        """
        if service not in self.SERVICES:
            return None

        config = self.SERVICES[service]
        if not config.wsdl_url:
            return None

        base_url = self.base_urls['soap']
        return f"{base_url}{config.wsdl_url}"

    def get_service_config(self, service: str) -> SiiEndpointConfig:
        """
        Get configuration for a service.

        Args:
            service: Service name

        Returns:
            Service configuration

        Raises:
            ValueError: If service is not found
        """
        if service not in self.SERVICES:
            raise ValueError(f"Servicio '{service}' no encontrado")

        return self.SERVICES[service]

    def get_portal_url(self) -> str:
        """Get SII portal URL for the current environment."""
        return self.base_urls['portal']

    def list_services(self) -> Dict[str, str]:
        """
        List all available services.

        Returns:
            Dictionary mapping service names to descriptions
        """
        return {
            service: config.description
            for service, config in self.SERVICES.items()
        }

    def supports_rest(self, service: str) -> bool:
        """
        Check if a service supports REST API.

        Args:
            service: Service name

        Returns:
            True if service supports REST
        """
        if service not in self.SERVICES:
            return False

        return self.SERVICES[service].rest_url is not None

    def get_auth_flow_urls(self) -> Dict[str, str]:
        """
        Get URLs for complete authentication flow.

        Returns:
            Dictionary with authentication URLs
        """
        return {
            'seed': self.get_soap_url('auth_seed'),
            'token': self.get_soap_url('auth_token')
        }

    def get_document_flow_urls(self) -> Dict[str, str]:
        """
        Get URLs for document submission and monitoring flow.

        Returns:
            Dictionary with document flow URLs
        """
        urls = {
            'upload_soap': self.get_soap_url('upload_dte'),
            'query_soap': self.get_soap_url('query_estado'),
            'ack_soap': self.get_soap_url('ack_reception')
        }

        # Add REST URLs if available
        rest_upload = self.get_rest_url('upload_dte')
        if rest_upload:
            urls['upload_rest'] = rest_upload

        rest_query = self.get_rest_url('query_estado')
        if rest_query:
            urls['query_rest'] = rest_query

        return urls

    def is_production(self) -> bool:
        """Check if current environment is production."""
        return self.environment == SiiEnvironment.PRODUCCION

    def is_certification(self) -> bool:
        """Check if current environment is certification."""
        return self.environment == SiiEnvironment.CERTIFICACION

    def switch_environment(self, environment: SiiEnvironment):
        """
        Switch to different environment.

        Args:
            environment: New environment to use
        """
        self.environment = environment
        self.base_urls = self.BASE_URLS[environment]

    def validate_service_availability(self, service: str, protocol: str = 'soap') -> bool:
        """
        Validate if a service is available for the specified protocol.

        Args:
            service: Service name
            protocol: Protocol to check ('soap' or 'rest')

        Returns:
            True if service is available for the protocol
        """
        if service not in self.SERVICES:
            return False

        config = self.SERVICES[service]

        if protocol.lower() == 'soap':
            return bool(config.soap_url)
        elif protocol.lower() == 'rest':
            return bool(config.rest_url)
        else:
            return False

    def get_service_timeout(self, service: str) -> int:
        """
        Get timeout configuration for a service.

        Args:
            service: Service name

        Returns:
            Timeout in seconds
        """
        if service not in self.SERVICES:
            return 30  # Default timeout

        return self.SERVICES[service].timeout

    def get_retry_attempts(self, service: str) -> int:
        """
        Get retry attempts configuration for a service.

        Args:
            service: Service name

        Returns:
            Number of retry attempts
        """
        if service not in self.SERVICES:
            return 3  # Default retry attempts

        return self.SERVICES[service].retry_attempts

    def __str__(self) -> str:
        return f"SiiEndpoints(environment={self.environment.value})"

    def __repr__(self) -> str:
        return f"SiiEndpoints(environment={self.environment!r})"