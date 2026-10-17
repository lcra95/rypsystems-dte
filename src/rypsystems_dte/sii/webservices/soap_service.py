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
import time

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

    # ------------------------------------------------------------------
    # Envío de XML (EnvioDTE) y consultas de estado
    # ------------------------------------------------------------------

    UPLOAD_STATUS_MESSAGES = {
        '1': 'El usuario {sender} no tiene permisos para enviar XML al SII.',
        '2': 'Error en el tamaño del archivo enviado con el XML, muy grande o muy chico.',
        '3': 'El archivo enviado está cortado, el tamaño es diferente al parámetro "size".',
        '5': 'El usuario {sender} no está autenticado (posible token expirado).',
        '6': 'La empresa no está autorizada a enviar archivos XML al SII.',
        '7': 'El esquema del XML es inválido.',
        '8': 'Existe un error en la firma del documento XML.',
        '9': 'Los servidores del SII están con problemas internos.',
        '99': 'El XML enviado ya fue previamente recibido por el SII.',
    }

    UPLOAD_STATES = {
        'RSC': 'Rechazado por Error en Schema',
        'SOK': 'Schema Validado',
        'CRT': 'Carátula OK',
        'RFR': 'Rechazado por Error en Firma',
        'FOK': 'Firma de Envió Validada',
        'PDR': 'Envió en Proceso',
        'RCT': 'Rechazado por Error en Carátula',
        'EPR': 'Envío Procesado',
    }

    @staticmethod
    def _split_rut(rut: str):
        from ..utils import RutValidator
        if not RutValidator.validate(rut):
            raise SiiValidationError(f"El RUT {rut} no es válido.")
        numero, dv = rut.replace('.', '').upper().split('-')
        return numero, dv

    def _portal_url(self, path: str) -> str:
        """URL en el servidor DTE del ambiente (maullin o palena), como getUrl() de PHP."""
        server = self.endpoints.base_urls['soap'].rsplit('/DTEWS', 1)[0]
        return f"{server}{path}"

    def upload_dte(
        self,
        rut_sender: str,
        rut_company: str,
        file_content: Union[str, bytes],
        compress: bool = False,
    ) -> Dict[str, Any]:
        """
        Sube un XML (EnvioDTE firmado) al SII.

        Traducción de SendXmlDocumentJob: POST multipart a
        /cgi_dte/UPL/DTEUpload con el token en la cookie TOKEN.

        Args:
            rut_sender: RUT de quien envía (el del certificado)
            rut_company: RUT de la empresa emisora
            file_content: XML del EnvioDTE en ISO-8859-1
            compress: Enviar el XML comprimido con gzip

        Returns:
            {'success', 'code', 'message', 'track_id', 'response'}

        Raises:
            SiiAuthenticationError: Si no hay token
            SiiValidationError: Si el SII rechaza el envío
        """
        if not self.is_authenticated():
            raise SiiAuthenticationError("No hay token de autenticación. Debe autenticarse primero.")

        if isinstance(file_content, str):
            file_content = file_content.encode('iso-8859-1', errors='xmlcharrefreplace')
        if not file_content.strip() or file_content.strip() == b'<?xml version="1.0" encoding="ISO-8859-1"?>':
            raise SiiValidationError("El XML que se desea enviar al SII no puede ser vacío.")
        if b'<?xml' not in file_content[:100]:
            file_content = b'<?xml version="1.0" encoding="ISO-8859-1"?>\n' + file_content

        rut_s, dv_s = self._split_rut(rut_sender)
        rut_c, dv_c = self._split_rut(rut_company)

        filename = f"{rut_company}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xml"
        mimetype = 'application/xml'
        if compress:
            import gzip
            file_content = gzip.compress(file_content)
            filename += '.gz'
            mimetype = 'application/gzip'

        url = self._portal_url('/cgi_dte/UPL/DTEUpload')
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; PROG 1.0; RypSystems DTE)',
            'Cookie': f'TOKEN={self.auth_token}',
        }
        data = {'rutSender': rut_s, 'dvSender': dv_s, 'rutCompany': rut_c, 'dvCompany': dv_c}

        body = None
        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    url,
                    data=data,
                    files={'archivo': (filename, file_content, mimetype)},
                    headers=headers,
                    timeout=self.timeout,
                )
                body = response.content
                if body and body.strip() != b'Error 500' and response.status_code < 500:
                    break
            except requests.exceptions.RequestException as e:
                body = None
                logger.warning(f"Error subiendo XML al SII (intento {attempt + 1}): {e}")
            if attempt < self.retry_attempts - 1:
                time.sleep(0.2 * self.retry_attempts)

        if not body or body.strip() == b'Error 500':
            raise SiiCommunicationError(
                "Falló el envío del XML al SII. El SII tiene problemas en sus servidores (Error 500)."
                if body else "Falló el envío del XML al SII. No hubo respuesta.",
                endpoint=url,
            )

        return self._parse_upload_response(body, rut_sender)

    def _parse_upload_response(self, response_xml: Union[str, bytes], rut_sender: str = '') -> Dict[str, Any]:
        """Interpreta la respuesta RECEPCIONDTE del upload."""
        if isinstance(response_xml, str):
            response_xml = response_xml.encode('iso-8859-1', errors='replace')
        try:
            root = ET.fromstring(re.sub(rb'^\s*<\?xml[^>]*\?>', b'', response_xml))
        except ET.ParseError as e:
            raise SiiCommunicationError(f"La respuesta del envío del XML al SII no es válida: {e}")

        status = (root.findtext('.//STATUS') or '').strip()
        track_id = (root.findtext('.//TRACKID') or '').strip()
        errors = [(e.text or '').strip() for e in root.iter('ERROR')]

        if not status:
            raise SiiCommunicationError("La respuesta del envío del XML al SII no trae un código de estado válido.")

        if status == '0':
            logger.info(f"XML enviado al SII, Track ID {track_id}")
            return {
                'success': True,
                'code': status,
                'message': 'Envío recibido por el SII',
                'track_id': int(track_id) if track_id.isdigit() else track_id,
                'response': response_xml.decode('iso-8859-1'),
            }

        message = self.UPLOAD_STATUS_MESSAGES.get(
            status, f'Ocurrió un error con código de estado "{status}", que es desconocido.'
        ).format(sender=rut_sender)
        if errors:
            message += ' ' + ' '.join(errors)
        raise SiiValidationError(message)

    def query_upload_status(self, rut_company: str, track_id: Union[int, str]) -> Dict[str, Any]:
        """
        Consulta el estado de un envío por su Track ID (servicio QueryEstUp).

        Traducción de CheckXmlDocumentSentStatusJob.

        Returns:
            {'estado', 'glosa', 'num_atencion', 'aceptados', 'rechazados', 'reparos', 'informados', 'raw'}
        """
        if not self.is_authenticated():
            raise SiiAuthenticationError("No hay token de autenticación. Debe autenticarse primero.")
        rut, dv = self._split_rut(rut_company)
        xml = self._call('QueryEstUp', 'getEstUp', {
            'Rut': rut, 'Dv': dv, 'TrackId': track_id, 'Token': self.auth_token,
        })
        data = self._parse_respuesta(xml)
        estado = data.get('ESTADO')
        # El cuerpo trae un bloque TIPO_DOCTO/INFORMADOS/ACEPTADOS/... por tipo.
        detalle = []
        body = re.search(r'RESP_BODY>(.*?)</[^>]*RESP_BODY>', xml or '', re.S)
        for bloque in re.split(r'(?=<TIPO_DOCTO>)', body.group(1) if body else ''):
            campos = dict(re.findall(r'<([A-Z_]+)>([^<]*)</\1>', bloque))
            if 'TIPO_DOCTO' in campos:
                detalle.append({k.lower(): v.strip() for k, v in campos.items()})

        def total(campo):
            valores = [int(d[campo]) for d in detalle if d.get(campo, '').isdigit()]
            return str(sum(valores)) if valores else data.get(campo.upper())

        return {
            'estado': estado,
            'descripcion': self.UPLOAD_STATES.get(estado or '', data.get('GLOSA')),
            'glosa': data.get('GLOSA'),
            'num_atencion': data.get('NUM_ATENCION'),
            'informados': total('informados'),
            'aceptados': total('aceptados'),
            'rechazados': total('rechazados'),
            'reparos': total('reparos'),
            'detalle': detalle,
            'raw': xml,
        }

    def query_document_status(
        self,
        rut_sender: str,
        rut_company: str,
        document_type: int,
        folio: int,
        fecha_emision: Optional[str] = None,
        monto: Optional[int] = None,
        rut_receptor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Consulta el estado de un DTE en el SII (servicio QueryEstDte).

        Traducción de ValidateDocumentJob.

        Args:
            rut_sender: RUT del consultante (el del certificado)
            rut_company: RUT de la empresa emisora
            document_type: Tipo de DTE
            folio: Folio
            fecha_emision: Fecha de emisión AAAA-MM-DD
            monto: Monto total
            rut_receptor: RUT del receptor

        Returns:
            {'estado', 'glosa', 'err_code', 'glosa_err', 'num_atencion', 'raw'}
        """
        if not self.is_authenticated():
            raise SiiAuthenticationError("No hay token de autenticación. Debe autenticarse primero.")
        if not fecha_emision or monto is None or not rut_receptor:
            raise SiiValidationError(
                "Para consultar el estado de un DTE el SII exige fecha de emisión, monto total y RUT del receptor."
            )
        try:
            fecha_sii = datetime.strptime(fecha_emision, '%Y-%m-%d').strftime('%d%m%Y')
        except ValueError:
            raise SiiValidationError(
                f"La fecha {fecha_emision} del documento no es válida, debe tener formato AAAA-MM-DD."
            )
        rut_u, dv_u = self._split_rut(rut_sender)
        rut_c, dv_c = self._split_rut(rut_company)
        rut_r, dv_r = self._split_rut(rut_receptor)
        xml = self._call('QueryEstDte', 'getEstDte', {
            'RutConsultante': rut_u, 'DvConsultante': dv_u,
            'RutCompania': rut_c, 'DvCompania': dv_c,
            'RutReceptor': rut_r, 'DvReceptor': dv_r,
            'TipoDte': document_type, 'FolioDte': folio,
            'FechaEmisionDte': fecha_sii, 'MontoDte': monto,
            'Token': self.auth_token,
        })
        data = self._parse_respuesta(xml)
        return {
            'estado': data.get('ESTADO'),
            'glosa': data.get('GLOSA_ESTADO') or data.get('GLOSA'),
            'err_code': data.get('ERR_CODE'),
            'glosa_err': data.get('GLOSA_ERR'),
            'num_atencion': data.get('NUM_ATENCION'),
            'raw': xml,
        }

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