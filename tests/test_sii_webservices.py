"""
Pruebas integrales para servicios web del SII.

Incluye pruebas para SOAP, REST, envío coordinado y monitoreo de estado.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from rypsystems_dte.sii.base import SiiAmbiente
from rypsystems_dte.sii.webservices import (
    SoapService,
    RestService,
    DocumentSender,
    StatusChecker,
    SiiEndpoints,
    SiiEnvironment,
    SendingProtocol,
    SendingResult,
    DocumentStatus,
    StatusQueryResult
)
from rypsystems_dte.sii.webservices.exceptions import (
    SiiWebServiceException,
    SiiAuthenticationError,
    SiiValidationError,
    SiiCommunicationError,
    SiiTimeoutError,
    SiiDocumentRejectedError,
    SiiRateLimitError
)


class TestSiiEndpoints:
    """Pruebas para configuración de endpoints del SII."""

    def test_initialization_certification(self):
        """Prueba inicialización en ambiente de certificación."""
        endpoints = SiiEndpoints(SiiEnvironment.CERTIFICACION)

        assert endpoints.environment == SiiEnvironment.CERTIFICACION
        assert 'maullin.sii.cl' in endpoints.base_urls['soap']
        assert 'apicert.sii.cl' in endpoints.base_urls['rest']

    def test_initialization_production(self):
        """Prueba inicialización en ambiente de producción."""
        endpoints = SiiEndpoints(SiiEnvironment.PRODUCCION)

        assert endpoints.environment == SiiEnvironment.PRODUCCION
        assert 'palena.sii.cl' in endpoints.base_urls['soap']
        assert 'api.sii.cl' in endpoints.base_urls['rest']

    def test_get_soap_url(self):
        """Prueba generación de URLs SOAP."""
        endpoints = SiiEndpoints(SiiEnvironment.CERTIFICACION)

        url = endpoints.get_soap_url('auth_seed')
        assert url == 'https://maullin.sii.cl/DTEWS/CrSeed.jws'

        url = endpoints.get_soap_url('upload_dte')
        assert url == 'https://maullin.sii.cl/DTEWS/services/wssDTEService'

    def test_get_rest_url(self):
        """Prueba generación de URLs REST."""
        endpoints = SiiEndpoints(SiiEnvironment.CERTIFICACION)

        url = endpoints.get_rest_url('upload_dte')
        assert url == 'https://apicert.sii.cl/recursos/v1/boleta.electronica.upload'

        # Servicio sin REST
        url = endpoints.get_rest_url('auth_seed')
        assert url is None

    def test_supports_rest(self):
        """Prueba verificación de soporte REST."""
        endpoints = SiiEndpoints()

        assert endpoints.supports_rest('upload_dte') is True
        assert endpoints.supports_rest('query_estado') is True
        assert endpoints.supports_rest('auth_seed') is False

    def test_service_not_found(self):
        """Prueba error para servicio inexistente."""
        endpoints = SiiEndpoints()

        with pytest.raises(ValueError, match="no encontrado"):
            endpoints.get_soap_url('nonexistent_service')


class TestSoapService:
    """Pruebas para servicio SOAP del SII."""

    @pytest.fixture
    def soap_service(self):
        """Fixture para servicio SOAP."""
        return SoapService(SiiEnvironment.CERTIFICACION, timeout=30)

    @patch('requests.Session.post')
    def test_get_seed_success(self, mock_post, soap_service):
        """Prueba obtención exitosa de semilla."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
            <soapenv:Body>
                <getSeedReturn xmlns="https://palena.sii.cl/DTEWS/CrSeed.jws">123456789</getSeedReturn>
            </soapenv:Body>
        </soapenv:Envelope>'''
        mock_post.return_value = mock_response

        seed = soap_service.get_seed()

        assert seed == '123456789'
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_get_seed_invalid(self, mock_post, soap_service):
        """Prueba manejo de semilla inválida."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
            <soapenv:Body>
                <getSeedReturn xmlns="https://palena.sii.cl/DTEWS/CrSeed.jws">0</getSeedReturn>
            </soapenv:Body>
        </soapenv:Envelope>'''
        mock_post.return_value = mock_response

        with pytest.raises(SiiCommunicationError, match="Semilla inválida"):
            soap_service.get_seed()

    def test_sign_seed_success(self, soap_service):
        """Prueba firma exitosa de semilla."""
        # Certificado y clave de prueba (auto-firmados)
        test_cert = """-----BEGIN CERTIFICATE-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAuE7w+FAKE_CERT_DATA
-----END CERTIFICATE-----"""

        test_key = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC4FAKE_KEY_DATA
-----END PRIVATE KEY-----"""

        with patch('cryptography.hazmat.primitives.serialization.load_pem_private_key') as mock_load_key:
            mock_private_key = Mock()
            mock_signature = b'fake_signature_bytes'
            mock_private_key.sign.return_value = mock_signature
            mock_load_key.return_value = mock_private_key

            signed_seed = soap_service.sign_seed('123456789', test_cert, test_key)

            assert signed_seed is not None
            assert isinstance(signed_seed, str)

    @patch('requests.Session.post')
    def test_get_token_success(self, mock_post, soap_service):
        """Prueba obtención exitosa de token."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
            <soapenv:Body>
                <getTokenReturn xmlns="https://palena.sii.cl/DTEWS/GetTokenFromSeed.jws">ABC123TOKEN</getTokenReturn>
            </soapenv:Body>
        </soapenv:Envelope>'''
        mock_post.return_value = mock_response

        token = soap_service.get_token('signed_seed')

        assert token == 'ABC123TOKEN'
        assert soap_service.auth_token == 'ABC123TOKEN'

    @patch.object(SoapService, 'get_seed')
    @patch.object(SoapService, 'sign_seed')
    @patch.object(SoapService, 'get_token')
    def test_authenticate_success(self, mock_get_token, mock_sign_seed, mock_get_seed, soap_service):
        """Prueba autenticación completa exitosa."""
        mock_get_seed.return_value = '123456789'
        mock_sign_seed.return_value = 'signed_seed'
        mock_get_token.return_value = 'ABC123TOKEN'

        token = soap_service.authenticate('76354771-K', 'cert_content', 'key_content')

        assert token == 'ABC123TOKEN'
        mock_get_seed.assert_called_once()
        mock_sign_seed.assert_called_once_with('123456789', 'cert_content', 'key_content')
        mock_get_token.assert_called_once_with('signed_seed')

    def test_upload_dte_not_authenticated(self, soap_service):
        """Prueba envío sin autenticación."""
        with pytest.raises(SiiAuthenticationError, match="No hay token"):
            soap_service.upload_dte('76354771-K', '76354771-K', '<xml>test</xml>')

    @patch('requests.Session.post')
    def test_upload_dte_success(self, mock_post, soap_service):
        """Prueba envío exitoso de DTE."""
        soap_service.auth_token = 'ABC123TOKEN'

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope>
            <soapenv:Body>
                <uploadDTEReturn>0 - Proceso OK</uploadDTEReturn>
            </soapenv:Body>
        </soapenv:Envelope>'''
        mock_post.return_value = mock_response

        result = soap_service.upload_dte('76354771-K', '76354771-K', '<xml>test</xml>')

        assert result['success'] is True
        assert result['code'] == '0'
        assert 'Proceso OK' in result['message']

    def test_ping_connectivity(self, soap_service):
        """Prueba verificación de conectividad."""
        with patch.object(soap_service, 'get_seed', return_value='123456789'):
            assert soap_service.ping() is True

        with patch.object(soap_service, 'get_seed', side_effect=Exception('Network error')):
            assert soap_service.ping() is False


class TestRestService:
    """Pruebas para servicio REST del SII."""

    @pytest.fixture
    def rest_service(self):
        """Fixture para servicio REST."""
        return RestService(SiiEnvironment.CERTIFICACION, timeout=30)

    @patch('requests.Session.post')
    def test_authenticate_success(self, mock_post, rest_service):
        """Prueba autenticación REST exitosa."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'jwt_token_123',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response

        token = rest_service.authenticate('76354771-K', 'api_key', 'api_secret')

        assert token == 'jwt_token_123'
        assert rest_service.access_token == 'jwt_token_123'
        assert rest_service.session.headers['Authorization'] == 'Bearer jwt_token_123'

    @patch('requests.Session.post')
    def test_authenticate_no_token(self, mock_post, rest_service):
        """Prueba manejo de respuesta sin token."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'message': 'Error'}
        mock_post.return_value = mock_response

        with pytest.raises(SiiAuthenticationError, match="No se recibió token"):
            rest_service.authenticate('76354771-K', 'api_key', 'api_secret')

    def test_upload_boleta_not_authenticated(self, rest_service):
        """Prueba envío sin autenticación."""
        with pytest.raises(SiiAuthenticationError, match="No hay token"):
            rest_service.upload_boleta('76354771-K', '76354771-K', {'test': 'data'})

    @patch('requests.Session.post')
    def test_upload_boleta_success(self, mock_post, rest_service):
        """Prueba envío exitoso de boleta."""
        rest_service.access_token = 'jwt_token_123'
        rest_service.token_expiry = datetime.now() + timedelta(hours=1)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'message': 'Boleta enviada exitosamente',
            'track_id': 'TRK123'
        }
        mock_post.return_value = mock_response

        result = rest_service.upload_boleta('76354771-K', '76354771-K', {'tipo': 39})

        assert result['success'] is True
        assert result['track_id'] == 'TRK123'

    def test_is_authenticated_valid(self, rest_service):
        """Prueba verificación de autenticación válida."""
        rest_service.access_token = 'jwt_token_123'
        rest_service.token_expiry = datetime.now() + timedelta(hours=1)

        assert rest_service.is_authenticated() is True

    def test_is_authenticated_expired(self, rest_service):
        """Prueba verificación de autenticación expirada."""
        rest_service.access_token = 'jwt_token_123'
        rest_service.token_expiry = datetime.now() - timedelta(hours=1)

        assert rest_service.is_authenticated() is False

    @patch('requests.Session.post')
    def test_bulk_upload_success(self, mock_post, rest_service):
        """Prueba envío masivo exitoso."""
        rest_service.access_token = 'jwt_token_123'
        rest_service.token_expiry = datetime.now() + timedelta(hours=1)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'processed': 5,
            'errors': []
        }
        mock_post.return_value = mock_response

        documents = [{'tipo': 39, 'folio': i} for i in range(1, 6)]
        result = rest_service.upload_bulk_documents('76354771-K', '76354771-K', documents)

        assert result['success'] is True
        assert result['processed'] == 5

    def test_bulk_upload_too_many(self, rest_service):
        """Prueba error por demasiados documentos."""
        rest_service.access_token = 'jwt_token_123'
        rest_service.token_expiry = datetime.now() + timedelta(hours=1)

        documents = [{'tipo': 39} for _ in range(101)]

        with pytest.raises(SiiValidationError, match="Demasiados documentos"):
            rest_service.upload_bulk_documents('76354771-K', '76354771-K', documents)


class TestDocumentSender:
    """Pruebas para servicio coordinado de envío."""

    @pytest.fixture
    def document_sender(self):
        """Fixture para enviador de documentos."""
        return DocumentSender(
            environment=SiiAmbiente.CERTIFICACION,
            protocol=SendingProtocol.AUTO
        )

    @pytest.fixture
    def mock_document(self):
        """Fixture para documento mock."""
        doc = Mock()
        doc.get_rut_emisor.return_value = '76354771-K'
        doc.get_folio.return_value = 1001
        doc.get_tipo_documento.return_value = 33
        doc.get_datos.return_value = {
            'Encabezado': {
                'IdDoc': {'FchEmis': '2023-12-01'}
            }
        }
        doc.save_xml.return_value = '<xml>test</xml>'
        doc.get_ted.return_value = 'ted_data'
        return doc

    def test_initialization(self, document_sender):
        """Prueba inicialización del servicio."""
        assert document_sender.environment == SiiAmbiente.CERTIFICACION
        assert document_sender.protocol == SendingProtocol.AUTO
        assert document_sender.soap_service is not None
        assert document_sender.rest_service is not None

    def test_authenticate_soap_success(self, document_sender):
        """Prueba autenticación SOAP exitosa."""
        with patch.object(document_sender.soap_service, 'authenticate', return_value='token'):
            result = document_sender.authenticate_soap('76354771-K', 'cert', 'key')
            assert result is True

    def test_authenticate_rest_success(self, document_sender):
        """Prueba autenticación REST exitosa."""
        with patch.object(document_sender.rest_service, 'authenticate', return_value='token'):
            result = document_sender.authenticate_rest('76354771-K', 'api_key', 'secret')
            assert result is True

    def test_send_document_validation_error(self, document_sender, mock_document):
        """Prueba error de validación en envío."""
        mock_document.get_rut_emisor.return_value = None

        with pytest.raises(SiiValidationError, match="sin RUT emisor"):
            document_sender.send_document(mock_document)

    def test_send_document_no_authentication(self, document_sender, mock_document):
        """Prueba envío sin autenticación."""
        # Mock ambos servicios como no autenticados
        document_sender.soap_service.is_authenticated = Mock(return_value=False)
        document_sender.rest_service.is_authenticated = Mock(return_value=False)

        result = document_sender.send_document(mock_document)

        assert result.success is False
        assert 'autenticación' in result.message.lower()

    def test_send_document_rest_success(self, document_sender, mock_document):
        """Prueba envío exitoso vía REST."""
        # Mock REST autenticado y SOAP no
        document_sender.rest_service.is_authenticated = Mock(return_value=True)
        document_sender.soap_service.is_authenticated = Mock(return_value=False)

        mock_response = {
            'success': True,
            'message': 'Enviado exitosamente',
            'track_id': 'TRK123'
        }
        document_sender.rest_service.upload_boleta = Mock(return_value=mock_response)

        result = document_sender.send_document(mock_document)

        assert result.success is True
        assert result.protocol_used == 'rest'
        assert result.track_id == 'TRK123'

    def test_send_document_soap_fallback(self, document_sender, mock_document):
        """Prueba fallback a SOAP tras fallo REST."""
        # Mock REST falla, SOAP exitoso
        document_sender.rest_service.is_authenticated = Mock(return_value=True)
        document_sender.soap_service.is_authenticated = Mock(return_value=True)

        # REST falla
        document_sender.rest_service.upload_boleta = Mock(
            side_effect=SiiCommunicationError("REST failed")
        )

        # SOAP exitoso
        mock_soap_response = {
            'success': True,
            'message': 'SOAP enviado',
            'track_id': 'SOAP123'
        }
        document_sender.soap_service.upload_dte = Mock(return_value=mock_soap_response)

        result = document_sender.send_document(mock_document)

        assert result.success is True
        assert result.protocol_used == 'soap'

    def test_send_multiple_documents(self, document_sender, mock_document):
        """Prueba envío múltiple."""
        document_sender.rest_service.is_authenticated = Mock(return_value=True)
        document_sender.soap_service.is_authenticated = Mock(return_value=False)

        mock_response = {
            'success': True,
            'message': 'OK',
            'track_id': 'TRK123'
        }
        document_sender.rest_service.upload_boleta = Mock(return_value=mock_response)

        documents = [mock_document, mock_document, mock_document]
        results = document_sender.send_multiple_documents(documents)

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_get_sending_stats(self, document_sender):
        """Prueba obtención de estadísticas."""
        # Simular algunos envíos
        document_sender.stats['total_sent'] = 10
        document_sender.stats['soap_sent'] = 3
        document_sender.stats['rest_sent'] = 6
        document_sender.stats['failures'] = 1

        stats = document_sender.get_sending_stats()

        assert stats['total_sent'] == 10
        assert stats['soap_sent'] == 3
        assert stats['rest_sent'] == 6
        assert stats['failures'] == 1
        assert stats['success_rate'] == 90.0

    def test_connectivity_test(self, document_sender):
        """Prueba verificación de conectividad."""
        document_sender.soap_service.ping = Mock(return_value=True)
        document_sender.rest_service.ping = Mock(return_value=True)
        document_sender.soap_service.is_authenticated = Mock(return_value=True)
        document_sender.rest_service.is_authenticated = Mock(return_value=False)

        connectivity = document_sender.test_connectivity()

        assert connectivity['soap_connectivity'] is True
        assert connectivity['rest_connectivity'] is True
        assert connectivity['soap_authenticated'] is True
        assert connectivity['rest_authenticated'] is False


class TestStatusChecker:
    """Pruebas para verificador de estado."""

    @pytest.fixture
    def status_checker(self):
        """Fixture para verificador de estado."""
        return StatusChecker(SiiAmbiente.CERTIFICACION)

    @pytest.fixture
    def mock_soap_service(self):
        """Fixture para servicio SOAP mock."""
        mock = Mock()
        mock.is_authenticated.return_value = True
        return mock

    @pytest.fixture
    def mock_rest_service(self):
        """Fixture para servicio REST mock."""
        mock = Mock()
        mock.is_authenticated.return_value = True
        return mock

    def test_check_document_status_soap(self, status_checker, mock_soap_service):
        """Prueba consulta de estado vía SOAP."""
        status_checker.soap_service = mock_soap_service

        mock_response = {
            'status': 'accepted',
            'message': 'Documento aceptado'
        }
        mock_soap_service.query_document_status.return_value = mock_response

        result = status_checker.check_document_status(
            '76354771-K', '76354771-K', 33, 1001
        )

        assert result.status == DocumentStatus.ACCEPTED
        assert result.message == 'Documento aceptado'
        assert result.protocol_used == 'soap'

    def test_check_document_status_rest(self, status_checker, mock_rest_service):
        """Prueba consulta de estado vía REST."""
        status_checker.rest_service = mock_rest_service
        status_checker.soap_service.is_authenticated = Mock(return_value=False)

        mock_response = {
            'status': 'processed',
            'message': 'Documento procesado'
        }
        mock_rest_service.query_document_status_rest.return_value = mock_response

        result = status_checker.check_document_status(
            '76354771-K', '76354771-K', 39, 2001
        )

        assert result.status == DocumentStatus.PROCESSED
        assert result.protocol_used == 'rest'

    def test_check_multiple_documents(self, status_checker, mock_soap_service):
        """Prueba consulta múltiple."""
        status_checker.soap_service = mock_soap_service

        mock_soap_service.query_document_status.side_effect = [
            {'status': 'accepted', 'message': 'OK'},
            {'status': 'rejected', 'message': 'Error'},
            {'status': 'pending', 'message': 'Procesando'}
        ]

        queries = [
            ('76354771-K', '76354771-K', 33, 1001),
            ('76354771-K', '76354771-K', 33, 1002),
            ('76354771-K', '76354771-K', 33, 1003)
        ]

        results = status_checker.check_multiple_documents(queries)

        assert len(results) == 3
        assert results[0].status == DocumentStatus.ACCEPTED
        assert results[1].status == DocumentStatus.REJECTED
        assert results[2].status == DocumentStatus.PENDING

    def test_start_monitoring(self, status_checker):
        """Prueba inicio de monitoreo."""
        result = status_checker.start_monitoring(
            '76354771-K', '76354771-K', 33, 1001,
            check_interval=1, max_duration=5
        )

        assert result == "MONITOR_1001"
        assert "MONITOR_1001" in status_checker.monitoring_tasks

    def test_stop_monitoring(self, status_checker):
        """Prueba detener monitoreo."""
        # Iniciar monitoreo
        monitor_id = status_checker.start_monitoring(
            '76354771-K', '76354771-K', 33, 1001
        )

        # Detener monitoreo
        stopped = status_checker.stop_monitoring(monitor_id)

        assert stopped is True
        assert monitor_id not in status_checker.monitoring_tasks

    def test_caching_behavior(self, status_checker, mock_soap_service):
        """Prueba comportamiento de cache."""
        status_checker.soap_service = mock_soap_service
        status_checker.enable_caching = True

        mock_response = {
            'status': 'accepted',
            'message': 'Documento aceptado'
        }
        mock_soap_service.query_document_status.return_value = mock_response

        # Primera consulta
        result1 = status_checker.check_document_status(
            '76354771-K', '76354771-K', 33, 1001
        )

        # Segunda consulta (debería usar cache)
        result2 = status_checker.check_document_status(
            '76354771-K', '76354771-K', 33, 1001
        )

        assert result1.status == result2.status
        # SOAP solo debería haberse llamado una vez
        mock_soap_service.query_document_status.assert_called_once()


class TestSiiExceptions:
    """Pruebas para excepciones del SII."""

    def test_base_exception(self):
        """Prueba excepción base."""
        exc = SiiWebServiceException("Test error")
        assert str(exc) == "Test error"
        assert exc.operation is None

    def test_authentication_error(self):
        """Prueba error de autenticación."""
        exc = SiiAuthenticationError("Auth failed", operation="authenticate")
        assert "Auth failed" in str(exc)
        assert exc.operation == "authenticate"

    def test_validation_error_with_details(self):
        """Prueba error de validación con detalles."""
        validation_errors = ["Campo requerido", "Formato inválido"]
        exc = SiiValidationError("Validation failed", validation_errors=validation_errors)

        assert exc.validation_errors == validation_errors
        assert "Campo requerido" in str(exc)

    def test_communication_error_with_status(self):
        """Prueba error de comunicación con status."""
        exc = SiiCommunicationError(
            "Connection failed",
            status_code=500,
            endpoint="https://test.sii.cl"
        )

        assert exc.status_code == 500
        assert exc.endpoint == "https://test.sii.cl"

    def test_timeout_error(self):
        """Prueba error de timeout."""
        exc = SiiTimeoutError("Timeout", timeout_seconds=30)
        assert exc.timeout_seconds == 30

    def test_document_rejected_error(self):
        """Prueba error de documento rechazado."""
        rejection_reasons = ["RUT inválido", "Folio duplicado"]
        exc = SiiDocumentRejectedError(
            "Document rejected",
            rejection_reasons=rejection_reasons
        )

        assert exc.rejection_reasons == rejection_reasons

    def test_rate_limit_error(self):
        """Prueba error de límite de velocidad."""
        exc = SiiRateLimitError("Rate limit exceeded", retry_after=60)
        assert exc.retry_after == 60


class TestIntegrationSiiWebServices:
    """Pruebas de integración para servicios web del SII."""

    @pytest.fixture
    def integration_setup(self):
        """Setup para pruebas de integración."""
        return {
            'sender': DocumentSender(SiiAmbiente.CERTIFICACION),
            'checker': StatusChecker(SiiAmbiente.CERTIFICACION),
            'endpoints': SiiEndpoints(SiiEnvironment.CERTIFICACION)
        }

    def test_full_document_flow_simulation(self, integration_setup):
        """Prueba flujo completo simulado de documento."""
        sender = integration_setup['sender']
        checker = integration_setup['checker']

        # Mock de documento
        mock_doc = Mock()
        mock_doc.get_rut_emisor.return_value = '76354771-K'
        mock_doc.get_folio.return_value = 1001
        mock_doc.get_tipo_documento.return_value = 33
        mock_doc.get_datos.return_value = {
            'Encabezado': {'IdDoc': {'FchEmis': '2023-12-01'}}
        }
        mock_doc.save_xml.return_value = '<xml>test</xml>'
        mock_doc.get_ted.return_value = 'ted_data'

        # Mock servicios
        sender.rest_service.is_authenticated = Mock(return_value=True)
        sender.soap_service.is_authenticated = Mock(return_value=False)

        # Mock envío exitoso
        mock_send_response = {
            'success': True,
            'message': 'Enviado',
            'track_id': 'TRK123'
        }
        sender.rest_service.upload_boleta = Mock(return_value=mock_send_response)

        # Mock consulta de estado
        checker.rest_service.is_authenticated = Mock(return_value=True)
        mock_status_response = {
            'status': 'accepted',
            'message': 'Documento aceptado'
        }
        checker.rest_service.query_document_status_rest = Mock(return_value=mock_status_response)

        # Ejecutar flujo
        send_result = sender.send_document(mock_doc)
        assert send_result.success is True

        status_result = checker.check_document_status(
            '76354771-K', '76354771-K', 33, 1001
        )
        assert status_result.status == DocumentStatus.ACCEPTED

        # Verificar estadísticas
        stats = sender.get_sending_stats()
        assert stats['total_sent'] == 1
        assert stats['rest_sent'] == 1

    def test_protocol_fallback_scenario(self, integration_setup):
        """Prueba escenario de fallback entre protocolos."""
        sender = integration_setup['sender']

        # Mock documento
        mock_doc = Mock()
        mock_doc.get_rut_emisor.return_value = '76354771-K'
        mock_doc.get_folio.return_value = 1001
        mock_doc.get_tipo_documento.return_value = 33
        mock_doc.get_datos.return_value = {
            'Encabezado': {'IdDoc': {'FchEmis': '2023-12-01'}}
        }
        mock_doc.save_xml.return_value = '<xml>test</xml>'
        mock_doc.get_ted.return_value = 'ted_data'

        # Mock ambos servicios autenticados
        sender.rest_service.is_authenticated = Mock(return_value=True)
        sender.soap_service.is_authenticated = Mock(return_value=True)

        # REST falla, SOAP exitoso
        sender.rest_service.upload_boleta = Mock(
            side_effect=SiiCommunicationError("REST failed")
        )

        soap_response = {
            'success': True,
            'message': 'SOAP OK',
            'track_id': 'SOAP123'
        }
        sender.soap_service.upload_dte = Mock(return_value=soap_response)

        # Ejecutar y verificar fallback
        result = sender.send_document(mock_doc)

        assert result.success is True
        assert result.protocol_used == 'soap'
        assert result.track_id == 'SOAP123'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])