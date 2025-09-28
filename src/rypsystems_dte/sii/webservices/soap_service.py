"""
Servicio SOAP para comunicación con SII.

Implementa la comunicación SOAP con los servicios web del SII chileno,
incluyendo autenticación, envío de documentos y consulta de estados.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Union
import requests
import hashlib
import base64
from datetime import datetime
import logging
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography import x509

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
        retry_attempts: int = 3
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

        # Configure session
        self.session.headers.update({
            'Content-Type': 'text/xml; charset=utf-8',
            'User-Agent': 'rypsystems-dte/1.0.0'
        })

    def get_seed(self) -> str:
        """
        Obtiene semilla del SII para autenticación.

        Returns:
            Semilla como string

        Raises:
            SiiCommunicationError: Si hay error en comunicación
        """
        soap_body = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
    <soapenv:Header/>
    <soapenv:Body>
        <getSeed xmlns="https://palena.sii.cl/DTEWS/CrSeed.jws"/>
    </soapenv:Body>
</soapenv:Envelope>"""

        try:
            url = self.endpoints.get_soap_url('auth_seed')
            response = self._make_soap_request(url, soap_body, 'getSeed')

            # Parse response
            root = ET.fromstring(response)
            seed_element = root.find('.//{https://palena.sii.cl/DTEWS/CrSeed.jws}getSeedReturn')

            if seed_element is None:
                raise SiiCommunicationError("No se pudo obtener semilla del SII")

            seed = seed_element.text
            if not seed or seed == '0':
                raise SiiCommunicationError("Semilla inválida recibida del SII")

            logger.info("Semilla obtenida exitosamente del SII")
            return seed

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiCommunicationError(f"Error obteniendo semilla: {str(e)}")

    def sign_seed(self, seed: str, certificate_content: str, private_key_content: str) -> str:
        """
        Firma la semilla con el certificado digital.

        Args:
            seed: Semilla obtenida del SII
            certificate_content: Contenido del certificado en formato PEM
            private_key_content: Contenido de la clave privada en formato PEM

        Returns:
            Semilla firmada en base64

        Raises:
            SiiAuthenticationError: Si hay error en la firma
        """
        try:
            # Load private key
            if isinstance(private_key_content, str):
                private_key_content = private_key_content.encode('utf-8')

            private_key = serialization.load_pem_private_key(
                private_key_content,
                password=None
            )

            # Sign the seed
            signature = private_key.sign(
                seed.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA1()
            )

            # Encode signature in base64
            signed_seed = base64.b64encode(signature).decode('utf-8')

            logger.debug("Semilla firmada exitosamente")
            return signed_seed

        except Exception as e:
            raise SiiAuthenticationError(f"Error firmando semilla: {str(e)}")

    def get_token(self, signed_seed: str) -> str:
        """
        Obtiene token de autenticación usando semilla firmada.

        Args:
            signed_seed: Semilla firmada en base64

        Returns:
            Token de autenticación

        Raises:
            SiiAuthenticationError: Si hay error obteniendo token
        """
        soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
    <soapenv:Header/>
    <soapenv:Body>
        <getToken xmlns="https://palena.sii.cl/DTEWS/GetTokenFromSeed.jws">
            <pszXml><![CDATA[{signed_seed}]]></pszXml>
        </getToken>
    </soapenv:Body>
</soapenv:Envelope>"""

        try:
            url = self.endpoints.get_soap_url('auth_token')
            response = self._make_soap_request(url, soap_body, 'getToken')

            # Parse response
            root = ET.fromstring(response)
            token_element = root.find('.//{https://palena.sii.cl/DTEWS/GetTokenFromSeed.jws}getTokenReturn')

            if token_element is None:
                raise SiiAuthenticationError("No se pudo obtener token del SII")

            token = token_element.text
            if not token:
                raise SiiAuthenticationError("Token vacío recibido del SII")

            # Store token
            self.auth_token = token
            self.token_expiry = datetime.now()

            logger.info("Token de autenticación obtenido exitosamente")
            return token

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiAuthenticationError(f"Error obteniendo token: {str(e)}")

    def authenticate(self, rut_company: str, certificate_content: str, private_key_content: str) -> str:
        """
        Proceso completo de autenticación con SII.

        Args:
            rut_company: RUT de la empresa
            certificate_content: Certificado digital en PEM
            private_key_content: Clave privada en PEM

        Returns:
            Token de autenticación

        Raises:
            SiiAuthenticationError: Si falla la autenticación
        """
        try:
            # Step 1: Get seed
            seed = self.get_seed()

            # Step 2: Sign seed
            signed_seed = self.sign_seed(seed, certificate_content, private_key_content)

            # Step 3: Get token
            token = self.get_token(signed_seed)

            logger.info(f"Autenticación completa exitosa para RUT {rut_company}")
            return token

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiAuthenticationError(f"Error en autenticación: {str(e)}")

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
                    data=soap_body,
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
            seed = self.get_seed()
            return bool(seed and seed != '0')
        except Exception:
            return False

    def is_authenticated(self) -> bool:
        """Verifica si hay una sesión autenticada válida."""
        return bool(self.auth_token)

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