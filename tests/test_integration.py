"""
Test Integration Component.

Pruebas comprehensivas para el módulo de integración SII incluyendo
SOAP, REST, y funcionalidad end-to-end.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date

# Add src to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from rypsystems_dte.sii.base import SiiAmbiente, Contribuyente
from rypsystems_dte.integration.sii_client import SiiClient, create_sii_client
from rypsystems_dte.integration.soap_client import SoapClient
from rypsystems_dte.integration.rest_client import RestClient
from rypsystems_dte.integration.exceptions import (
    IntegrationException,
    SiiConnectionException,
    SiiAuthenticationException,
    SiiValidationException,
    SiiTimeoutException
)
from rypsystems_dte.integration.models.sii_response import (
    SiiResponse,
    SiiDocumentStatus,
    SiiDocumentState
)
from rypsystems_dte.integration.models.sii_request import (
    SiiSubmissionRequest,
    SiiQueryRequest,
    SiiAuthenticationRequest
)
from rypsystems_dte.dte.factory import DTEFactory


class TestIntegrationExceptions:
    """Pruebas para excepciones de integración."""

    def test_integration_exception_basic(self):
        """Prueba excepción básica de integración."""
        exc = IntegrationException("Test error")
        assert str(exc) == "Test error"
        assert exc.error_code is None

    def test_integration_exception_with_code(self):
        """Prueba excepción con código de error."""
        exc = IntegrationException("Test error", "TEST_001")
        assert str(exc) == "[TEST_001] Test error"
        assert exc.error_code == "TEST_001"

    def test_sii_connection_exception(self):
        """Prueba excepción de conexión SII."""
        exc = SiiConnectionException("Connection failed", "https://test.sii.cl", 500)
        assert exc.endpoint == "https://test.sii.cl"
        assert exc.status_code == 500
        assert exc.error_code == "SII_CONNECTION_ERROR"

    def test_sii_authentication_exception(self):
        """Prueba excepción de autenticación SII."""
        exc = SiiAuthenticationException("Auth failed", "token123")
        assert exc.token == "token123"
        assert exc.error_code == "SII_AUTH_ERROR"

    def test_sii_validation_exception(self):
        """Prueba excepción de validación SII."""
        errors = ["Error 1", "Error 2"]
        exc = SiiValidationException("Validation failed", errors, "DOC123")
        assert exc.validation_errors == errors
        assert exc.document_id == "DOC123"
        assert exc.error_code == "SII_VALIDATION_ERROR"

    def test_sii_timeout_exception(self):
        """Prueba excepción de timeout SII."""
        exc = SiiTimeoutException("Request timeout", 30)
        assert exc.timeout_seconds == 30
        assert exc.error_code == "SII_TIMEOUT_ERROR"


class TestSiiModels:
    """Pruebas para modelos de datos SII."""

    def test_sii_document_status_creation(self):
        """Prueba creación de estado de documento."""
        status = SiiDocumentStatus(
            document_id="DOC123",
            folio=1001,
            document_type=33,
            rut_emisor="76354771-K",
            state=SiiDocumentState.ACCEPTED,
            sii_track_id="TRACK123"
        )

        assert status.document_id == "DOC123"
        assert status.folio == 1001
        assert status.document_type == 33
        assert status.rut_emisor == "76354771-K"
        assert status.state == SiiDocumentState.ACCEPTED
        assert status.is_accepted()
        assert not status.is_rejected()
        assert not status.has_errors()

    def test_sii_document_status_with_errors(self):
        """Prueba estado de documento con errores."""
        status = SiiDocumentStatus(
            document_id="DOC123",
            folio=1001,
            document_type=33,
            rut_emisor="76354771-K",
            state=SiiDocumentState.REJECTED,
            validation_errors=["Error de validación"],
            business_errors=["Error de negocio"]
        )

        assert status.is_rejected()
        assert status.has_errors()
        assert len(status.get_all_errors()) == 2
        assert "Error de validación" in status.get_all_errors()
        assert "Error de negocio" in status.get_all_errors()

    def test_sii_response_creation(self):
        """Prueba creación de respuesta SII."""
        response = SiiResponse(
            success=True,
            operation="submit_documents",
            message="Documentos enviados exitosamente"
        )

        assert response.success
        assert response.operation == "submit_documents"
        assert response.message == "Documentos enviados exitosamente"
        assert len(response.document_statuses) == 0

    def test_sii_response_with_documents(self):
        """Prueba respuesta con estados de documentos."""
        status1 = SiiDocumentStatus(
            document_id="DOC1",
            folio=1001,
            document_type=33,
            rut_emisor="76354771-K",
            state=SiiDocumentState.ACCEPTED
        )

        status2 = SiiDocumentStatus(
            document_id="DOC2",
            folio=1002,
            document_type=33,
            rut_emisor="76354771-K",
            state=SiiDocumentState.REJECTED,
            validation_errors=["Error de validación"]
        )

        response = SiiResponse(
            success=True,
            operation="submit_documents",
            document_statuses=[status1, status2]
        )

        assert len(response.document_statuses) == 2
        assert len(response.get_accepted_documents()) == 1
        assert len(response.get_rejected_documents()) == 1
        assert len(response.get_documents_with_errors()) == 1

        summary = response.get_summary()
        assert summary["total"] == 2
        assert summary["accepted"] == 1
        assert summary["rejected"] == 1
        assert summary["with_errors"] == 1

    def test_sii_submission_request(self):
        """Prueba request de envío de documentos."""
        documents = [
            {
                'document_id': 'DOC1',
                'folio': 1001,
                'document_type': 33,
                'xml_content': '<DTE>...</DTE>'
            }
        ]

        request = SiiSubmissionRequest(
            request_id="REQ123",
            rut_company="76354771-K",
            rut_sender="76354771-K",
            documents=documents,
            validate_only=True
        )

        assert request.rut_company == "76354771-K"
        assert request.rut_sender == "76354771-K"
        assert len(request.documents) == 1
        assert request.validate_only
        assert request.get_document_count() == 1
        assert "DOC1" in request.get_document_ids()

    def test_sii_query_request(self):
        """Prueba request de consulta de estado."""
        request = SiiQueryRequest(
            request_id="REQ123",
            rut_company="76354771-K",
            rut_sender="76354771-K",
            document_ids=["DOC1", "DOC2"],
            folios=[1001, 1002],
            date_from=date(2023, 12, 1),
            date_to=date(2023, 12, 31)
        )

        assert request.rut_company == "76354771-K"
        assert request.document_ids == ["DOC1", "DOC2"]
        assert request.folios == [1001, 1002]
        assert request.has_specific_documents()
        assert request.is_date_range_query()

    def test_sii_query_request_validation(self):
        """Prueba validación de request de consulta."""
        with pytest.raises(ValueError, match="La fecha no puede ser futura"):
            SiiQueryRequest(
                request_id="REQ123",
                rut_company="76354771-K",
                rut_sender="76354771-K",
                date_from=date(2030, 1, 1)  # Fecha futura
            )


class TestSoapClient:
    """Pruebas para cliente SOAP."""

    @pytest.fixture
    def soap_client(self):
        """Fixture para cliente SOAP."""
        return SoapClient(ambiente=SiiAmbiente.CERTIFICACION, timeout=10)

    def test_soap_client_initialization(self, soap_client):
        """Prueba inicialización de cliente SOAP."""
        assert soap_client.ambiente == SiiAmbiente.CERTIFICACION
        assert soap_client.timeout == 10
        assert soap_client.retry_attempts == 3
        assert soap_client.auth_token is None

    def test_get_service_url(self, soap_client):
        """Prueba generación de URLs de servicio."""
        auth_url = soap_client._get_service_url('authentication')
        assert 'maullin.sii.cl' in auth_url  # Certificación
        assert '/DTEWS/CrSeed.jws' in auth_url

        doc_url = soap_client._get_service_url('document_submission')
        assert 'maullin.sii.cl' in doc_url
        assert '/DTEWS/services/wsdte' in doc_url

    def test_create_soap_envelope(self, soap_client):
        """Prueba creación de sobre SOAP."""
        body = '<test>content</test>'
        envelope = soap_client._create_soap_envelope(body)

        assert '<?xml version="1.0" encoding="UTF-8"?>' in envelope
        assert 'soap:Envelope' in envelope
        assert 'soap:Body' in envelope
        assert '<test>content</test>' in envelope

    @patch('requests.Session.post')
    def test_soap_request_success(self, mock_post, soap_client):
        """Prueba request SOAP exitoso."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <response>
                    <seed>12345</seed>
                </response>
            </soap:Body>
        </soap:Envelope>'''
        mock_post.return_value = mock_response

        result = soap_client._make_soap_request('authentication', '<test/>')
        assert 'seed' in result
        assert result['seed'] == '12345'

    @patch('requests.Session.post')
    def test_soap_request_connection_error(self, mock_post, soap_client):
        """Prueba error de conexión en request SOAP."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(SiiConnectionException):
            soap_client._make_soap_request('authentication', '<test/>')

    @patch('requests.Session.post')
    def test_soap_request_timeout(self, mock_post, soap_client):
        """Prueba timeout en request SOAP."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        with pytest.raises(SiiTimeoutException):
            soap_client._make_soap_request('authentication', '<test/>')

    def test_sign_seed_basic(self, soap_client):
        """La solicitud getToken se firma con XML-DSig (documento completo)."""
        from rypsystems_dte.firma import SelfSignedCertificate, XmlSigner

        certificate = SelfSignedCertificate().create()
        signed = soap_client._sign_seed("123456789", certificate)
        assert '<Semilla>123456789</Semilla>' in signed
        assert XmlSigner().is_valid_xml(signed.encode('iso-8859-1'))

    def test_sign_seed_certificado_invalido(self, soap_client):
        """Ya no se aceptan certificados falsos (antes se devolvía un hash)."""
        with pytest.raises(SiiAuthenticationException):
            soap_client._sign_seed("123456789", "test_certificate", "test_private_key")


class TestRestClient:
    """Pruebas para cliente REST."""

    @pytest.fixture
    def rest_client(self):
        """Fixture para cliente REST."""
        return RestClient(ambiente=SiiAmbiente.CERTIFICACION, timeout=10)

    def test_rest_client_initialization(self, rest_client):
        """Prueba inicialización de cliente REST."""
        assert rest_client.ambiente == SiiAmbiente.CERTIFICACION
        assert rest_client.timeout == 10
        assert rest_client.retry_attempts == 3
        assert rest_client.auth_token is None

    def test_get_api_base_url(self, rest_client):
        """Prueba generación de URL base de API."""
        url = rest_client._get_api_base_url()
        assert url == "https://apicert.sii.cl/v1"  # Certificación

        # Test producción
        rest_client.ambiente = SiiAmbiente.PRODUCCION
        url = rest_client._get_api_base_url()
        assert url == "https://api.sii.cl/v1"

    @patch('requests.Session.get')
    def test_rest_request_success(self, mock_get, rest_client):
        """Prueba request REST exitoso."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'success', 'data': 'test'}
        mock_get.return_value = mock_response

        result = rest_client._make_request('GET', '/test')
        assert result['status'] == 'success'
        assert result['data'] == 'test'

    @patch('requests.Session.post')
    def test_rest_request_authentication_error(self, mock_post, rest_client):
        """Prueba error de autenticación en request REST."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_post.return_value = mock_response

        with pytest.raises(SiiAuthenticationException):
            rest_client._make_request('POST', '/test', {'data': 'test'})

    @patch('requests.Session.post')
    def test_rest_request_validation_error(self, mock_post, rest_client):
        """Prueba error de validación en request REST."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'message': 'Validation failed',
            'errors': ['Field required']
        }
        mock_post.return_value = mock_response

        with pytest.raises(SiiValidationException) as exc_info:
            rest_client._make_request('POST', '/test', {'data': 'test'})

        assert exc_info.value.validation_errors == ['Field required']

    def test_map_status_to_state(self, rest_client):
        """Prueba mapeo de estados."""
        assert rest_client._map_status_to_state('accepted') == SiiDocumentState.ACCEPTED
        assert rest_client._map_status_to_state('rejected') == SiiDocumentState.REJECTED
        assert rest_client._map_status_to_state('pending') == SiiDocumentState.PENDING
        assert rest_client._map_status_to_state('unknown_status') == SiiDocumentState.UNKNOWN


class TestSiiClient:
    """Pruebas para cliente principal SII."""

    @pytest.fixture
    def sii_client(self):
        """Fixture para cliente SII."""
        return SiiClient(ambiente=SiiAmbiente.CERTIFICACION)

    def test_sii_client_initialization(self, sii_client):
        """Prueba inicialización de cliente SII."""
        assert sii_client.ambiente == SiiAmbiente.CERTIFICACION
        assert sii_client.prefer_rest is True
        assert not sii_client.is_authenticated
        assert sii_client.current_rut_company is None
        assert sii_client.auth_method is None

    def test_create_sii_client_function(self):
        """Prueba función de conveniencia para crear cliente."""
        client = create_sii_client(SiiAmbiente.PRODUCCION, timeout=60)
        assert client.ambiente == SiiAmbiente.PRODUCCION
        assert client.timeout == 60

    @patch.object(SoapClient, 'authenticate')
    def test_authenticate_with_certificate(self, mock_auth, sii_client):
        """Prueba autenticación con certificado."""
        mock_auth.return_value = "test_token"

        success = sii_client.authenticate_with_certificate(
            "76354771-K",
            "certificate_content",
            "private_key_content"
        )

        assert success
        assert sii_client.is_authenticated
        assert sii_client.current_rut_company == "76354771-K"
        assert sii_client.auth_method == 'soap'

    @patch.object(RestClient, 'authenticate')
    def test_authenticate_with_api_key(self, mock_auth, sii_client):
        """Prueba autenticación con API key."""
        mock_auth.return_value = "test_token"

        success = sii_client.authenticate_with_api_key(
            "76354771-K",
            "api_key",
            "api_secret"
        )

        assert success
        assert sii_client.is_authenticated
        assert sii_client.current_rut_company == "76354771-K"
        assert sii_client.auth_method == 'rest'

    def test_submit_document_not_authenticated(self, sii_client):
        """Prueba envío sin autenticación."""
        from rypsystems_dte.dte.factory import DTEFactory
        from rypsystems_dte.sii.base import Contribuyente

        factory = DTEFactory()
        emisor = Contribuyente("76354771-K", "Test Company")
        receptor = Contribuyente("66666666-6", "Test Client")

        document = factory.create_factura_afecta(
            emisor, receptor, 1001, "2023-12-01",
            [{'NmbItem': 'Test Product', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        with pytest.raises(SiiAuthenticationException):
            sii_client.submit_document(document)

    def test_get_authentication_status(self, sii_client):
        """Prueba obtención de estado de autenticación."""
        status = sii_client.get_authentication_status()

        assert 'is_authenticated' in status
        assert 'auth_method' in status
        assert 'rut_company' in status
        assert 'ambiente' in status
        assert status['is_authenticated'] is False
        assert status['ambiente'] == 'CERTIFICACION'

    def test_logout(self, sii_client):
        """Prueba cierre de sesión."""
        # Simular autenticación
        sii_client.is_authenticated = True
        sii_client.current_rut_company = "76354771-K"
        sii_client.auth_method = 'soap'

        sii_client.logout()

        assert not sii_client.is_authenticated
        assert sii_client.current_rut_company is None
        assert sii_client.auth_method is None


class TestIntegrationWithDTE:
    """Pruebas de integración con módulo DTE."""

    @pytest.fixture
    def dte_factory(self):
        """Fixture para fábrica DTE."""
        return DTEFactory()

    @pytest.fixture
    def emisor(self):
        """Fixture para contribuyente emisor."""
        return Contribuyente("76354771-K", "Mi Empresa S.A.")

    @pytest.fixture
    def receptor(self):
        """Fixture para contribuyente receptor."""
        return Contribuyente("66666666-6", "Cliente S.A.")

    @pytest.fixture
    def mock_sii_client(self):
        """Fixture para cliente SII mock."""
        client = Mock(spec=SiiClient)
        client.is_authenticated = True
        return client

    def test_document_submit_to_sii(self, dte_factory, emisor, receptor, mock_sii_client):
        """Prueba envío de documento al SII."""
        # Crear documento
        document = dte_factory.create_factura_afecta(
            emisor, receptor, 1001, "2023-12-01",
            [{'NmbItem': 'Test Product', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        # Configurar mock response
        mock_response = SiiResponse(
            success=True,
            operation="submit_documents",
            message="Documento enviado exitosamente"
        )
        mock_sii_client.submit_document.return_value = mock_response

        # Enviar documento
        response = document.submit_to_sii(mock_sii_client)

        assert response.success
        assert response.operation == "submit_documents"
        mock_sii_client.submit_document.assert_called_once_with(
            document=document,
            rut_sender=None,
            validate_only=False
        )

    def test_document_query_sii_status(self, dte_factory, emisor, receptor, mock_sii_client):
        """Prueba consulta de estado en SII."""
        # Crear documento
        document = dte_factory.create_factura_afecta(
            emisor, receptor, 1001, "2023-12-01",
            [{'NmbItem': 'Test Product', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        # Configurar mock response
        mock_response = SiiResponse(
            success=True,
            operation="query_status",
            message="Consulta exitosa"
        )
        mock_sii_client.query_document_status.return_value = mock_response

        # Consultar estado
        response = document.query_sii_status(mock_sii_client)

        assert response.success
        assert response.operation == "query_status"
        mock_sii_client.query_document_status.assert_called_once()

    def test_document_get_sii_receipt(self, dte_factory, emisor, receptor, mock_sii_client):
        """Prueba obtención de acuse de recibo del SII."""
        # Crear documento
        document = dte_factory.create_factura_afecta(
            emisor, receptor, 1001, "2023-12-01",
            [{'NmbItem': 'Test Product', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        # Configurar mock response
        mock_sii_client.get_document_receipt.return_value = "<receipt>XML content</receipt>"

        # Obtener acuse
        receipt = document.get_sii_receipt(mock_sii_client, "TRACK123")

        assert receipt == "<receipt>XML content</receipt>"
        mock_sii_client.get_document_receipt.assert_called_once_with("TRACK123", "xml")

    def test_invalid_sii_client_type(self, dte_factory, emisor, receptor):
        """Prueba error con tipo de cliente inválido."""
        # Crear documento
        document = dte_factory.create_factura_afecta(
            emisor, receptor, 1001, "2023-12-01",
            [{'NmbItem': 'Test Product', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        # Intentar usar cliente inválido
        invalid_client = "not_a_sii_client"

        with pytest.raises(ValueError, match="sii_client debe ser una instancia de SiiClient"):
            document.submit_to_sii(invalid_client)