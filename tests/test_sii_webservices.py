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
            '<RECHAZADOS>0</RECHAZADOS><REPAROS>0</REPAROS></SII:RESP_BODY></SII:RESPUESTA>'
        )
        mock_post.return_value = self._sii_response('getEstUp', 'QueryEstUp', respuesta)

        result = soap_service.query_upload_status('76192083-9', 123)

        assert result['estado'] == 'EPR'
        assert result['descripcion'] == 'Envío Procesado'
        assert result['aceptados'] == '1' and result['rechazados'] == '0'
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