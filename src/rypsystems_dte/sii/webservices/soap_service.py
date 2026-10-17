"""
Servicio SOAP para comunicación con SII.

Implementa la comunicación SOAP con los servicios web del SII chileno,
incluyendo autenticación, envío de documentos y consulta de estados.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
from xml.sax.saxutils import escape
import logging

import requests

from ...firma.digital_certificate import DigitalCertificate
from ...firma.xml_signer import XmlSigner
from ...xml.encoder import XmlEncoder, save_xml

from .sii_endpoints import SiiEndpoints, SiiEnvironment
from .exceptions import (
    SiiWebServiceException,
    SiiAuthenticationError,
    SiiCommunicationError,
    SiiTimeoutError,
    SiiValidationError
)


logger = logging.getLogger(__name__)


class SoapService:
    """
    Servicio SOAP para comunicación con SII.

    Maneja toda la comunicación SOAP con los servicios web del SII,
    incluyendo autenticación con certificados y envío de documentos.
    """

    def __init__(
        self,
        environment: SiiEnvironment = SiiEnvironment.CERTIFICACION,
        timeout: int = 30,
        retry_attempts: int = 3,
        token_ttl: int = 3600,
    ):
        """
        Initialize SOAP service.

        Args:
            environment: SII environment
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
        """
        self.endpoints = SiiEndpoints(environment)
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.session = requests.Session()

        # Authentication state
        self.auth_token = None
        self.token_expiry = None
        self.token_ttl = token_ttl

        # Configure session
        self.session.headers.update({
            'Content-Type': 'text/xml; charset=utf-8',
            'User-Agent': 'rypsystems-dte/1.0.0'
        })

    # ------------------------------------------------------------------
    # Llamadas SOAP (RPC/literal) a los servicios DTEWS del SII
    # ------------------------------------------------------------------

    def _service_url(self, service: str) -> str:
        """URL del servicio .jws en el servidor del ambiente (maullin o palena)."""
        return f"{self.endpoints.base_urls['soap']}/{service}.jws"

    def _rpc_envelope(self, service: str, function: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Arma el sobre SOAP de una llamada RPC/literal."""
        args = ''.join(
            f'<{name}>{escape(str(value))}</{name}>' for name, value in (params or {}).items()
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
            '<soapenv:Body>'
            f'<ns1:{function} xmlns:ns1="{self._service_url(service)}">{args}</ns1:{function}>'
            '</soapenv:Body>'
            '</soapenv:Envelope>'
        )

    def _call(self, service: str, function: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Llama una función de un servicio DTEWS y entrega el contenido de
        {function}Return (un XML como texto en el caso de los servicios DTE).

        Raises:
            SiiCommunicationError: Si la respuesta no tiene el formato esperado
        """
        url = self._service_url(service)
        response = self._make_soap_request(url, self._rpc_envelope(service, function, params), '')
        # El SII declara UTF-8 pero puede enviar ISO-8859-1; se reemplazan los
        # caracteres inválidos como hace LibreDTE PHP.
        response = response.replace('\ufffd', '?').replace('ï¿½', '?')
        try:
            root = ET.fromstring(response.encode('utf-8'))
        except ET.ParseError as e:
            raise SiiCommunicationError(f"Respuesta inválida del SII en {function}: {e}", endpoint=url)

        fault = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
        if fault is not None:
            raise SiiCommunicationError(
                f"El SII respondió con error en {function}: {fault.findtext('faultstring')}", endpoint=url
            )

        for node in root.iter():
            if isinstance(node.tag, str) and node.tag.split('}')[-1] == f'{function}Return':
                return (node.text or '').strip()
        raise SiiCommunicationError(f"La respuesta del SII no contiene {function}Return.", endpoint=url)

    @staticmethod
    def _parse_respuesta(xml: str) -> Dict[str, Optional[str]]:
        """
        Extrae los campos de una respuesta SII:RESPUESTA (ESTADO, GLOSA y los
        nodos de RESP_BODY), ignorando namespaces.
        """
        xml = re.sub(r'^\s*<\?xml[^>]*\?>', '', xml or '')
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as e:
            raise SiiCommunicationError(f"La respuesta del SII no es un XML válido: {e}")
        data: Dict[str, Optional[str]] = {}
        for node in root.iter():
            if isinstance(node.tag, str) and len(node) == 0:
                data[node.tag.split('}')[-1]] = (node.text or '').strip()
        return data

    # ------------------------------------------------------------------
    # Autenticación: semilla -> getToken firmado -> token
    # ------------------------------------------------------------------

    def get_seed(self) -> str:
        """
        Obtiene una semilla del servicio CrSeed.

        Returns:
            Semilla (número como string)

        Raises:
            SiiCommunicationError: Si el SII no entrega una semilla válida
        """
        respuesta = self._parse_respuesta(self._call('CrSeed', 'getSeed'))
        semilla = respuesta.get('SEMILLA')
        if respuesta.get('ESTADO') != '00' or not semilla or not semilla.isdigit() or int(semilla) == 0:
            raise SiiCommunicationError("Semilla inválida recibida del SII")
        logger.info("Semilla obtenida exitosamente del SII")
        # LibreDTE PHP la convierte a entero antes de firmarla.
        return str(int(semilla))

    def sign_seed(
        self,
        seed: str,
        certificate: Union[DigitalCertificate, str],
        private_key_content: Optional[str] = None,
    ) -> str:
        """
        Arma y firma (XML-DSig, documento completo) la solicitud getToken.

        Args:
            seed: Semilla obtenida con get_seed()
            certificate: Certificado con clave privada. Por compatibilidad
                también se acepta el certificado en PEM más private_key_content.

        Returns:
            XML getToken firmado (ISO-8859-1) como texto

        Raises:
            SiiAuthenticationError: Si no es posible firmar
        """
        try:
            if not isinstance(certificate, DigitalCertificate):
                certificate = DigitalCertificate.from_pem(certificate, private_key_content)
            xml = save_xml(XmlEncoder().encode({'getToken': {'item': {'Semilla': int(seed)}}}))
            signed = XmlSigner().sign_xml(xml, certificate)
        except Exception as e:
            raise SiiAuthenticationError(f"No fue posible firmar getToken. {e}")
        logger.debug("Solicitud getToken firmada exitosamente")
        return signed.decode('iso-8859-1')

    def get_token(self, signed_seed: str) -> str:
        """
        Obtiene un token del servicio GetTokenFromSeed.

        Args:
            signed_seed: XML getToken firmado (ver sign_seed())

        Returns:
            Token de autenticación

        Raises:
            SiiAuthenticationError: Si el SII rechaza la solicitud
        """
        try:
            respuesta = self._parse_respuesta(self._call('GetTokenFromSeed', 'getToken', {'pszXml': signed_seed}))
        except SiiCommunicationError as e:
            raise SiiAuthenticationError(f"Error obteniendo token: {e}")

        token = respuesta.get('TOKEN')
        if respuesta.get('ESTADO') != '00' or not token:
            raise SiiAuthenticationError(
                f"No fue posible obtener el token del SII (estado {respuesta.get('ESTADO')}). "
                f"{respuesta.get('GLOSA') or ''}".strip()
            )

        self.auth_token = token
        self.token_expiry = datetime.now() + timedelta(seconds=self.token_ttl)
        logger.info("Token de autenticación obtenido exitosamente")
        return token

    def authenticate(
        self,
        certificate: Union[DigitalCertificate, str],
        certificate_content: Optional[str] = None,
        private_key_content: Optional[str] = None,
    ) -> str:
        """
        Proceso completo de autenticación con el SII.

        Args:
            certificate: Certificado con clave privada. Por compatibilidad se
                acepta authenticate(rut, certificado_pem, clave_pem).

        Returns:
            Token de autenticación (se reutiliza mientras esté vigente)

        Raises:
            SiiAuthenticationError: Si falla la autenticación
        """
        if self.is_authenticated():
            return self.auth_token
        if not isinstance(certificate, DigitalCertificate):
            # Firma antigua: authenticate(rut_company, certificate_pem, private_key_pem)
            certificate = certificate_content
        try:
            seed = self.get_seed()
            if isinstance(certificate, DigitalCertificate):
                signed_seed = self.sign_seed(seed, certificate)
            else:
                signed_seed = self.sign_seed(seed, certificate, private_key_content)
            return self.get_token(signed_seed)
        except SiiWebServiceException:
            raise
        except Exception as e:
            raise SiiAuthenticationError(f"Error en autenticación: {e}")

    def upload_dte(self, rut_sender: str, rut_company: str, file_content: str) -> Dict[str, Any]:
        """
        Envía un DTE al SII.

        Args:
            rut_sender: RUT del emisor
            rut_company: RUT de la empresa
            file_content: Contenido XML del DTE

        Returns:
            Respuesta del SII

        Raises:
            SiiAuthenticationError: Si no hay token válido
            SiiValidationError: Si el documento es rechazado
        """
        if not self.auth_token:
            raise SiiAuthenticationError("No hay token de autenticación. Debe autenticarse primero.")

        soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
    <soapenv:Header>
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <wsse:UsernameToken>
                <wsse:Username>{rut_sender}</wsse:Username>
                <wsse:Password>{self.auth_token}</wsse:Password>
            </wsse:UsernameToken>
        </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
        <uploadDTE xmlns="http://DefaultNamespace">
            <rutSender>{rut_sender}</rutSender>
            <rutCompany>{rut_company}</rutCompany>
            <file><![CDATA[{file_content}]]></file>
        </uploadDTE>
    </soapenv:Body>
</soapenv:Envelope>"""

        try:
            url = self.endpoints.get_soap_url('upload_dte')
            response = self._make_soap_request(url, soap_body, 'uploadDTE')

            # Parse response
            response_data = self._parse_upload_response(response)

            logger.info(f"Documento enviado exitosamente para RUT {rut_sender}")
            return response_data

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiValidationError(f"Error enviando documento: {str(e)}")

    def query_document_status(
        self,
        rut_sender: str,
        rut_company: str,
        document_type: int,
        folio: int
    ) -> Dict[str, Any]:
        """
        Consulta el estado de un documento en SII.

        Args:
            rut_sender: RUT del emisor
            rut_company: RUT de la empresa
            document_type: Tipo de documento
            folio: Folio del documento

        Returns:
            Estado del documento

        Raises:
            SiiAuthenticationError: Si no hay token válido
        """
        if not self.auth_token:
            raise SiiAuthenticationError("No hay token de autenticación. Debe autenticarse primero.")

        soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
    <soapenv:Header>
        <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
            <wsse:UsernameToken>
                <wsse:Username>{rut_sender}</wsse:Username>
                <wsse:Password>{self.auth_token}</wsse:Password>
            </wsse:UsernameToken>
        </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
        <queryEstDte xmlns="http://DefaultNamespace">
            <rutConsultante>{rut_sender}</rutConsultante>
            <rutCompany>{rut_company}</rutCompany>
            <rutEmisor>{rut_sender}</rutEmisor>
            <tipoDte>{document_type}</tipoDte>
            <folioDte>{folio}</folioDte>
        </queryEstDte>
    </soapenv:Body>
</soapenv:Envelope>"""

        try:
            url = self.endpoints.get_soap_url('query_estado')
            response = self._make_soap_request(url, soap_body, 'queryEstDte')

            # Parse response
            status_data = self._parse_status_response(response)

            logger.info(f"Estado consultado para documento {document_type}-{folio}")
            return status_data

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiCommunicationError(f"Error consultando estado: {str(e)}")

    def _make_soap_request(self, url: str, soap_body: str, action: str) -> str:
        """
        Realiza una petición SOAP al SII.

        Args:
            url: URL del servicio
            soap_body: Cuerpo SOAP
            action: Acción SOAP

        Returns:
            Respuesta XML del servidor

        Raises:
            SiiCommunicationError: Si hay error de comunicación
            SiiTimeoutError: Si hay timeout
        """
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': f'"{action}"',
            'User-Agent': 'rypsystems-dte/1.0.0'
        }

        for attempt in range(self.retry_attempts):
            try:
                logger.debug(f"Haciendo petición SOAP a {url} (intento {attempt + 1})")

                response = self.session.post(
                    url,
                    data=soap_body.encode('utf-8') if isinstance(soap_body, str) else soap_body,
                    headers=headers,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    return response.text

                elif response.status_code in [500, 502, 503, 504]:
                    # Server errors, retry
                    if attempt == self.retry_attempts - 1:
                        raise SiiCommunicationError(
                            f"Error del servidor SII: HTTP {response.status_code}",
                            status_code=response.status_code,
                            endpoint=url
                        )
                    continue

                else:
                    raise SiiCommunicationError(
                        f"Error HTTP {response.status_code}: {response.text}",
                        status_code=response.status_code,
                        endpoint=url
                    )

            except requests.exceptions.Timeout:
                if attempt == self.retry_attempts - 1:
                    raise SiiTimeoutError(
                        f"Timeout después de {self.timeout} segundos",
                        timeout_seconds=self.timeout,
                        endpoint=url
                    )

            except requests.exceptions.ConnectionError as e:
                if attempt == self.retry_attempts - 1:
                    raise SiiCommunicationError(
                        f"Error de conexión: {str(e)}",
                        endpoint=url
                    )

        # Should not reach here
        raise SiiCommunicationError("Error inesperado en petición SOAP")

    def _parse_upload_response(self, response_xml: str) -> Dict[str, Any]:
        """Parsea respuesta de envío de documento."""
        try:
            root = ET.fromstring(response_xml)

            # Look for different possible response formats
            result_element = (
                root.find('.//uploadDTEReturn') or
                root.find('.//return') or
                root.find('.//result')
            )

            if result_element is None:
                return {'success': False, 'message': 'Respuesta no válida del SII'}

            result_text = result_element.text or ''

            # Parse result (formato típico: "0 - Proceso OK")
            if ' - ' in result_text:
                code, message = result_text.split(' - ', 1)
                success = code.strip() == '0'
            else:
                success = 'ok' in result_text.lower()
                code = '0' if success else '1'
                message = result_text

            return {
                'success': success,
                'code': code,
                'message': message,
                'raw_response': response_xml
            }

        except ET.ParseError:
            return {
                'success': False,
                'message': 'Error parseando respuesta XML del SII',
                'raw_response': response_xml
            }

    def _parse_status_response(self, response_xml: str) -> Dict[str, Any]:
        """Parsea respuesta de consulta de estado."""
        try:
            root = ET.fromstring(response_xml)

            # Look for status response
            status_element = (
                root.find('.//queryEstDteReturn') or
                root.find('.//return') or
                root.find('.//status')
            )

            if status_element is None:
                return {'status': 'unknown', 'message': 'No se pudo obtener estado'}

            status_text = status_element.text or ''

            # Parse status
            status_info = {
                'status': 'unknown',
                'message': status_text,
                'raw_response': response_xml
            }

            # Try to extract more detailed status information
            if 'aceptado' in status_text.lower():
                status_info['status'] = 'accepted'
            elif 'rechazado' in status_text.lower():
                status_info['status'] = 'rejected'
            elif 'pendiente' in status_text.lower():
                status_info['status'] = 'pending'
            elif 'procesado' in status_text.lower():
                status_info['status'] = 'processed'

            return status_info

        except ET.ParseError:
            return {
                'status': 'error',
                'message': 'Error parseando respuesta XML del SII',
                'raw_response': response_xml
            }

    def ping(self) -> bool:
        """
        Verifica conectividad con servicios SII.

        Returns:
            True si hay conectividad
        """
        try:
            return bool(self.get_seed())
        except Exception:
            return False

    def is_authenticated(self) -> bool:
        """Verifica si hay una sesión autenticada válida."""
        if not self.auth_token:
            return False
        return self.token_expiry is None or datetime.now() < self.token_expiry

    def logout(self):
        """Limpia token de autenticación."""
        self.auth_token = None
        self.token_expiry = None

    def get_service_info(self) -> Dict[str, Any]:
        """
        Obtiene información del servicio.

        Returns:
            Información del servicio y conectividad
        """
        return {
            'environment': self.endpoints.environment.value,
            'authenticated': self.is_authenticated(),
            'connectivity': self.ping(),
            'base_url': self.endpoints.base_urls['soap'],
            'timeout': self.timeout,
            'retry_attempts': self.retry_attempts
        }