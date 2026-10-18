"""
Pruebas integrales para servicios web del SII.

Incluye pruebas de endpoints, del servicio SOAP y de las excepciones.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from rypsystems_dte.sii.base import SiiAmbiente
from rypsystems_dte.sii.webservices import (
    SoapService,
    SiiEndpoints,
    SiiEnvironment,
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

    # Respuestas con el formato real del SII (capturado desde maullin.sii.cl):
    # el resultado viene como un XML SII:RESPUESTA escapado dentro de {función}Return.
    @staticmethod
    def _sii_response(function: str, service: str, respuesta: str) -> Mock:
        from xml.sax.saxutils import escape
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<soapenv:Body>'
            f'<ns1:{function}Response xmlns:ns1="https://maullin.sii.cl/DTEWS/{service}.jws">'
            f'<ns1:{function}Return xsi:type="xsd:string">{escape(respuesta)}</ns1:{function}Return>'
            f'</ns1:{function}Response>'
            '</soapenv:Body></soapenv:Envelope>'
        )
        return mock_response

    @staticmethod
    def _respuesta(body: str, estado: str = '00', glosa: str = '') -> str:
        glosa_xml = f'<GLOSA>{glosa}</GLOSA>' if glosa else ''
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema">'
            f'<SII:RESP_BODY>{body}</SII:RESP_BODY>'
            f'<SII:RESP_HDR><ESTADO>{estado}</ESTADO>{glosa_xml}</SII:RESP_HDR>'
            '</SII:RESPUESTA>'
        )

    @patch('requests.Session.post')
    def test_get_seed_success(self, mock_post, soap_service):
        """Prueba obtención exitosa de semilla."""
        mock_post.return_value = self._sii_response(
            'getSeed', 'CrSeed', self._respuesta('<SEMILLA>012345678901</SEMILLA>')
        )

        seed = soap_service.get_seed()

        # Igual que LibreDTE PHP, la semilla se trata como entero.
        assert seed == '12345678901'
        mock_post.assert_called_once()
        assert mock_post.call_args.args[0] == 'https://maullin.sii.cl/DTEWS/CrSeed.jws'

    @patch('requests.Session.post')
    def test_get_seed_invalid(self, mock_post, soap_service):
        """Prueba manejo de semilla inválida."""
        mock_post.return_value = self._sii_response(
            'getSeed', 'CrSeed', self._respuesta('<SEMILLA>0</SEMILLA>', estado='-1')
        )

        with pytest.raises(SiiCommunicationError, match="Semilla inválida"):
            soap_service.get_seed()

    def test_sign_seed_success(self, soap_service):
        """La solicitud getToken se firma con XML-DSig sobre el documento completo."""
        from rypsystems_dte.firma import SelfSignedCertificate, XmlSigner

        certificate = SelfSignedCertificate().create()
        signed_seed = soap_service.sign_seed('123456789', certificate)

        assert signed_seed.startswith('<?xml version="1.0" encoding="ISO-8859-1"?>')
        assert '<getToken>' in signed_seed and '<Semilla>123456789</Semilla>' in signed_seed
        assert '<Reference URI="">' in signed_seed
        assert XmlSigner().is_valid_xml(signed_seed.encode('iso-8859-1'))

    def test_sign_seed_pem(self, soap_service):
        """Compatibilidad: certificado y clave en PEM."""
        from rypsystems_dte.firma import SelfSignedCertificate

        certificate = SelfSignedCertificate().create()
        signed_seed = soap_service.sign_seed(
            '123456789', certificate.get_certificate_pem(), certificate.get_private_key_pem()
        )
        assert '<Semilla>123456789</Semilla>' in signed_seed

    def test_sign_seed_certificado_falso(self, soap_service):
        """Un certificado inválido ya no produce una "firma" (antes se aceptaba)."""
        with pytest.raises(SiiAuthenticationError):
            soap_service.sign_seed('123456789', 'no es un certificado', 'ni una clave')

    @patch('requests.Session.post')
    def test_get_token_success(self, mock_post, soap_service):
        """Prueba obtención exitosa de token."""
        mock_post.return_value = self._sii_response(
            'getToken', 'GetTokenFromSeed', self._respuesta('<TOKEN>ABC123TOKEN</TOKEN>')
        )

        token = soap_service.get_token('<getToken>...</getToken>')

        assert token == 'ABC123TOKEN'
        assert soap_service.auth_token == 'ABC123TOKEN'
        assert soap_service.is_authenticated()
        # pszXml se envía escapado dentro del sobre SOAP.
        sent = mock_post.call_args.kwargs['data'].decode('utf-8')
        assert '<pszXml>&lt;getToken&gt;...&lt;/getToken&gt;</pszXml>' in sent

    @patch('requests.Session.post')
    def test_get_token_rechazado(self, mock_post, soap_service):
        """El SII rechaza la firma de la semilla."""
        mock_post.return_value = self._sii_response(
            'getToken', 'GetTokenFromSeed',
            self._respuesta('', estado='-07', glosa='Error : (Firma no valida)'),
        )

        with pytest.raises(SiiAuthenticationError, match='Firma no valida'):
            soap_service.get_token('<getToken/>')
        assert not soap_service.is_authenticated()

    @patch.object(SoapService, 'get_seed')
    @patch.object(SoapService, 'sign_seed')
    @patch.object(SoapService, 'get_token')
    def test_authenticate_success(self, mock_get_token, mock_sign_seed, mock_get_seed, soap_service):
        """Prueba autenticación completa exitosa."""
        from rypsystems_dte.firma import SelfSignedCertificate

        certificate = SelfSignedCertificate().create()
        mock_get_seed.return_value = '123456789'
        mock_sign_seed.return_value = 'signed_seed'
        mock_get_token.return_value = 'ABC123TOKEN'

        token = soap_service.authenticate(certificate)

        assert token == 'ABC123TOKEN'
        mock_get_seed.assert_called_once()
        mock_sign_seed.assert_called_once_with('123456789', certificate)
        mock_get_token.assert_called_once_with('signed_seed')

    def test_upload_dte_not_authenticated(self, soap_service):
        """Prueba envío sin autenticación."""
        with pytest.raises(SiiAuthenticationError, match="No hay token"):
            soap_service.upload_dte('76354771-K', '76354771-K', '<xml>test</xml>')

    @staticmethod
    def _upload_response(status: str, track_id: str = '', detail: str = '') -> Mock:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = (
            '<?xml version="1.0" encoding="ISO-8859-1"?>\n<RECEPCIONDTE>'
            '<RUTSENDER>11222333-9</RUTSENDER><RUTCOMPANY>76192083-9</RUTCOMPANY>'
            '<FILE>76192083-9_x.xml</FILE><TIMESTAMP>2026-10-17 17:00:00</TIMESTAMP>'
            f'<STATUS>{status}</STATUS>'
            + (f'<TRACKID>{track_id}</TRACKID>' if track_id else '')
            + (f'<DETAIL><ERROR>{detail}</ERROR></DETAIL>' if detail else '')
            + '</RECEPCIONDTE>'
        ).encode('iso-8859-1')
        return mock_response

    @patch('requests.post')
    def test_upload_dte_success(self, mock_post, soap_service):
        """Envío exitoso: POST multipart a DTEUpload con la cookie TOKEN."""
        soap_service.auth_token = 'ABC123TOKEN'
        mock_post.return_value = self._upload_response('0', '0123456789')

        result = soap_service.upload_dte('11222333-9', '76192083-9', '<EnvioDTE/>')

        assert result['success'] is True
        assert result['code'] == '0'
        assert result['track_id'] == 123456789
        args, kwargs = mock_post.call_args
        assert args[0] == 'https://maullin.sii.cl/cgi_dte/UPL/DTEUpload'
        assert kwargs['headers']['Cookie'] == 'TOKEN=ABC123TOKEN'
        assert kwargs['data'] == {'rutSender': '11222333', 'dvSender': '9', 'rutCompany': '76192083', 'dvCompany': '9'}
        filename, content, mimetype = kwargs['files']['archivo']
        assert content.startswith(b'<?xml version="1.0" encoding="ISO-8859-1"?>')
        assert mimetype == 'application/xml'

    @patch('requests.post')
    def test_upload_dte_rechazado(self, mock_post, soap_service):
        """El SII rechaza el envío por esquema inválido."""
        soap_service.auth_token = 'ABC123TOKEN'
        mock_post.return_value = self._upload_response('7', detail='Error en linea 3')

        with pytest.raises(SiiValidationError, match='esquema del XML es inválido. Error en linea 3'):
            soap_service.upload_dte('11222333-9', '76192083-9', '<EnvioDTE/>')

    @patch('requests.post')
    def test_upload_dte_error_500(self, mock_post, soap_service):
        soap_service.auth_token = 'ABC123TOKEN'
        soap_service.retry_attempts = 1
        mock_response = Mock(status_code=500, content=b'Error 500')
        mock_post.return_value = mock_response

        with pytest.raises(SiiCommunicationError, match='Error 500'):
            soap_service.upload_dte('11222333-9', '76192083-9', '<EnvioDTE/>')

    def test_upload_dte_rut_invalido(self, soap_service):
        soap_service.auth_token = 'ABC123TOKEN'
        with pytest.raises(SiiValidationError, match='no es válido'):
            soap_service.upload_dte('11222333-1', '76192083-9', '<EnvioDTE/>')

    @patch('requests.Session.post')
    def test_query_upload_status(self, mock_post, soap_service):
        """Estado de un envío por Track ID (QueryEstUp)."""
        soap_service.auth_token = 'ABC123TOKEN'
        respuesta = (
            '<SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema">'
            '<SII:RESP_HDR><TRACKID>123</TRACKID><ESTADO>EPR</ESTADO><GLOSA>Envio Procesado</GLOSA>'
            '<NUM_ATENCION>1 ( 2026/10/17 17:00:00)</NUM_ATENCION></SII:RESP_HDR>'
            '<SII:RESP_BODY><TIPO_DOCTO>33</TIPO_DOCTO><INFORMADOS>1</INFORMADOS><ACEPTADOS>1</ACEPTADOS>'
            '<RECHAZADOS>0</RECHAZADOS><REPAROS>0</REPAROS>'
            '<TIPO_DOCTO>61</TIPO_DOCTO><INFORMADOS>3</INFORMADOS><ACEPTADOS>2</ACEPTADOS>'
            '<RECHAZADOS>1</RECHAZADOS><REPAROS>0</REPAROS></SII:RESP_BODY></SII:RESPUESTA>'
        )
        mock_post.return_value = self._sii_response('getEstUp', 'QueryEstUp', respuesta)

        result = soap_service.query_upload_status('76192083-9', 123)

        assert result['estado'] == 'EPR'
        assert result['descripcion'] == 'Envío Procesado'
        # Totales de todos los tipos y detalle por tipo (formato real del SII).
        assert result['aceptados'] == '3' and result['rechazados'] == '1'
        assert [d['tipo_docto'] for d in result['detalle']] == ['33', '61']
        assert result['detalle'][1] == {'tipo_docto': '61', 'informados': '3', 'aceptados': '2',
                                        'rechazados': '1', 'reparos': '0'}
        sent = mock_post.call_args.kwargs['data'].decode('utf-8')
        assert '<Rut>76192083</Rut><Dv>9</Dv><TrackId>123</TrackId><Token>ABC123TOKEN</Token>' in sent

    @patch('requests.Session.post')
    def test_query_document_status(self, mock_post, soap_service):
        """Estado de un DTE (QueryEstDte)."""
        soap_service.auth_token = 'ABC123TOKEN'
        respuesta = (
            '<SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema"><SII:RESP_HDR>'
            '<ESTADO>DOK</ESTADO><GLOSA_ESTADO>Documento Recibido por el SII</GLOSA_ESTADO>'
            '<ERR_CODE>0</ERR_CODE><GLOSA_ERR>Datos coinciden</GLOSA_ERR><NUM_ATENCION>1</NUM_ATENCION>'
            '</SII:RESP_HDR></SII:RESPUESTA>'
        )
        mock_post.return_value = self._sii_response('getEstDte', 'QueryEstDte', respuesta)

        result = soap_service.query_document_status(
            '11222333-9', '76192083-9', 33, 1, fecha_emision='2026-10-17', monto=1190, rut_receptor='60803000-K'
        )

        assert result['estado'] == 'DOK'
        assert result['glosa'] == 'Documento Recibido por el SII'
        sent = mock_post.call_args.kwargs['data'].decode('utf-8')
        assert '<FechaEmisionDte>17102026</FechaEmisionDte>' in sent
        assert '<RutReceptor>60803000</RutReceptor><DvReceptor>K</DvReceptor>' in sent

    def test_query_document_status_faltan_datos(self, soap_service):
        soap_service.auth_token = 'ABC123TOKEN'
        with pytest.raises(SiiValidationError, match='fecha de emisión, monto total y RUT del receptor'):
            soap_service.query_document_status('11222333-9', '76192083-9', 33, 1)

    def test_ping_connectivity(self, soap_service):
        """Prueba verificación de conectividad."""
        with patch.object(soap_service, 'get_seed', return_value='123456789'):
            assert soap_service.ping() is True

        with patch.object(soap_service, 'get_seed', side_effect=Exception('Network error')):
            assert soap_service.ping() is False


class TestSiiExceptions:
    """Pruebas para excepciones del SII."""

    def test_base_exception(self):
        """Prueba excepción base."""
        exc = SiiWebServiceException("Test error")
        assert str(exc) == "Test error"
        assert exc.error_code is None and exc.endpoint is None
        assert str(SiiWebServiceException("Test error", error_code="5")) == "Test error (Código SII: 5)"

    def test_authentication_error(self):
        """Prueba error de autenticación."""
        exc = SiiAuthenticationError("Auth failed", endpoint="GetTokenFromSeed")
        assert "Auth failed" in str(exc)
        assert exc.endpoint == "GetTokenFromSeed"

    def test_validation_error_with_details(self):
        """Prueba error de validación con detalles."""
        validation_errors = ["Campo requerido", "Formato inválido"]
        exc = SiiValidationError("Validation failed", validation_errors=validation_errors)

        assert exc.validation_errors == validation_errors
        assert "1. Campo requerido" in exc.get_validation_details()

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
