"""
Pruebas básicas de integración para servicios web del SII.

Verifica que los componentes principales se integren correctamente.
"""

import pytest
from rypsystems_dte.sii.base import SiiAmbiente
from rypsystems_dte.sii.webservices import (
    DocumentSender,
    StatusChecker,
    SiiEndpoints,
    SiiEnvironment,
    SendingProtocol,
    DocumentStatus
)


class TestBasicSiiIntegration:
    """Pruebas básicas de integración para servicios web del SII."""

    def test_document_sender_initialization(self):
        """Prueba inicialización básica del enviador de documentos."""
        sender = DocumentSender(SiiAmbiente.CERTIFICACION)

        assert sender.environment == SiiAmbiente.CERTIFICACION
        assert sender.protocol == SendingProtocol.AUTO
        assert sender.soap_service is not None
        assert sender.rest_service is not None

    def test_status_checker_initialization(self):
        """Prueba inicialización básica del verificador de estado."""
        checker = StatusChecker(SiiAmbiente.CERTIFICACION)

        assert checker.environment == SiiAmbiente.CERTIFICACION
        assert checker.soap_service is not None
        assert checker.rest_service is not None

    def test_sii_endpoints_basic_functionality(self):
        """Prueba funcionalidad básica de endpoints."""
        endpoints = SiiEndpoints(SiiEnvironment.CERTIFICACION)

        # Verificar URLs básicas
        soap_url = endpoints.get_soap_url('auth_seed')
        assert 'maullin.sii.cl' in soap_url
        assert 'CrSeed.jws' in soap_url

        rest_url = endpoints.get_rest_url('upload_dte')
        assert rest_url is not None
        assert 'apicert.sii.cl' in rest_url

    def test_document_sender_service_integration(self):
        """Prueba integración básica entre servicios."""
        sender = DocumentSender(SiiAmbiente.CERTIFICACION)

        # Verificar que los servicios están configurados correctamente
        connectivity = sender.test_connectivity()

        assert 'soap_connectivity' in connectivity
        assert 'rest_connectivity' in connectivity
        assert 'soap_authenticated' in connectivity
        assert 'rest_authenticated' in connectivity

    def test_sending_protocols_enum(self):
        """Prueba enumeración de protocolos de envío."""
        protocols = [
            SendingProtocol.SOAP_ONLY,
            SendingProtocol.REST_ONLY,
            SendingProtocol.AUTO,
            SendingProtocol.SOAP_PREFERRED,
            SendingProtocol.REST_PREFERRED
        ]

        for protocol in protocols:
            sender = DocumentSender(
                SiiAmbiente.CERTIFICACION,
                protocol=protocol
            )
            assert sender.protocol == protocol

    def test_document_status_enum(self):
        """Prueba enumeración de estados de documento."""
        statuses = [
            DocumentStatus.PENDING,
            DocumentStatus.ACCEPTED,
            DocumentStatus.REJECTED,
            DocumentStatus.PROCESSED,
            DocumentStatus.ERROR,
            DocumentStatus.UNKNOWN,
            DocumentStatus.NOT_FOUND
        ]

        for status in statuses:
            assert isinstance(status.value, str)
            assert len(status.value) > 0

    def test_sender_statistics_functionality(self):
        """Prueba funcionalidad de estadísticas."""
        sender = DocumentSender(SiiAmbiente.CERTIFICACION)

        stats = sender.get_sending_stats()

        required_keys = [
            'total_sent',
            'soap_sent',
            'rest_sent',
            'failures',
            'success_rate',
            'last_sent',
            'soap_authenticated',
            'rest_authenticated'
        ]

        for key in required_keys:
            assert key in stats

    def test_environment_switching(self):
        """Prueba cambio de ambientes."""
        # Certificación
        endpoints_cert = SiiEndpoints(SiiEnvironment.CERTIFICACION)
        assert endpoints_cert.is_certification()
        assert not endpoints_cert.is_production()

        # Producción
        endpoints_prod = SiiEndpoints(SiiEnvironment.PRODUCCION)
        assert endpoints_prod.is_production()
        assert not endpoints_prod.is_certification()

    def test_service_availability_checks(self):
        """Prueba verificación de disponibilidad de servicios."""
        endpoints = SiiEndpoints(SiiEnvironment.CERTIFICACION)

        # Servicios que deben estar disponibles
        assert endpoints.validate_service_availability('upload_dte', 'soap')
        assert endpoints.validate_service_availability('upload_dte', 'rest')
        assert endpoints.validate_service_availability('query_estado', 'soap')
        assert endpoints.validate_service_availability('query_estado', 'rest')

        # Servicio que no existe
        assert not endpoints.validate_service_availability('nonexistent', 'soap')

    def test_basic_error_handling(self):
        """Prueba manejo básico de errores."""
        sender = DocumentSender(SiiAmbiente.CERTIFICACION)

        # Verificar que no está listo sin autenticación
        assert not sender.is_ready_to_send()

    def test_module_imports(self):
        """Prueba que todos los módulos se importen correctamente."""
        from rypsystems_dte.sii.webservices import (
            SiiEndpoints,
            SiiEnvironment,
            SoapService,
            RestService,
            DocumentSender,
            SendingProtocol,
            SendingResult,
            StatusChecker,
            DocumentStatus,
            StatusQueryResult,
            SiiWebServiceException,
            SiiAuthenticationError,
            SiiValidationError,
            SiiCommunicationError,
            SiiTimeoutError,
            SiiDocumentRejectedError,
            SiiRateLimitError
        )

        # Verificar que todas las clases existen
        assert SiiEndpoints is not None
        assert SoapService is not None
        assert RestService is not None
        assert DocumentSender is not None
        assert StatusChecker is not None

    def test_service_info_retrieval(self):
        """Prueba obtención de información de servicios."""
        sender = DocumentSender(SiiAmbiente.CERTIFICACION)

        # Información del servicio SOAP
        soap_info = sender.soap_service.get_service_info()
        assert 'environment' in soap_info
        assert 'authenticated' in soap_info
        assert 'connectivity' in soap_info

        # Información del servicio REST
        rest_info = sender.rest_service.get_service_info()
        assert 'environment' in rest_info
        assert 'authenticated' in rest_info
        assert 'connectivity' in rest_info


if __name__ == '__main__':
    pytest.main([__file__, '-v'])