"""
SOAP Client for SII web services.

Handles SOAP-based communication with Chilean SII services for document
submission and status queries.
"""

import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
import requests
from datetime import datetime
import hashlib
import base64
import logging

from ..sii.base import SiiAmbiente
from .exceptions import (
    SiiConnectionException,
    SiiAuthenticationException,
    SiiValidationException,
    SiiTimeoutException
)
from .models.sii_response import SiiResponse, SiiDocumentStatus, SiiDocumentState
from .models.sii_request import SiiSubmissionRequest, SiiQueryRequest


logger = logging.getLogger(__name__)


class SoapClient:
    """
    SOAP client for Chilean SII web services.

    Handles authentication, document submission, and status queries
    using SOAP protocol as required by SII.
    """

    def __init__(
        self,
        ambiente: SiiAmbiente = SiiAmbiente.CERTIFICACION,
        timeout: int = 30,
        retry_attempts: int = 3
    ):
        """
        Initialize SOAP client.

        Args:
            ambiente: SII environment (production or certification)
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
        """
        self.ambiente = ambiente
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.session = requests.Session()
        self.auth_token = None
        self.token_expiry = None

        # Configure session headers
        self.session.headers.update({
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '',
            'User-Agent': 'rypsystems-dte/1.0.0'
        })

    def _get_service_url(self, service_name: str) -> str:
        """
        Get the URL for a specific SII service.

        Args:
            service_name: Name of the SII service

        Returns:
            Complete URL for the service
        """
        base_urls = {
            SiiAmbiente.PRODUCCION: "https://palena.sii.cl",
            SiiAmbiente.CERTIFICACION: "https://maullin.sii.cl"
        }

        service_paths = {
            'authentication': '/DTEWS/CrSeed.jws',
            'document_submission': '/DTEWS/services/wsdte',
            'document_query': '/DTEWS/services/QueryEstDte',
            'receipt': '/DTEWS/services/wsdte'
        }

        base_url = base_urls[self.ambiente]
        service_path = service_paths.get(service_name, '')

        return f"{base_url}{service_path}"

    def _create_soap_envelope(self, body_content: str, soap_action: str = "") -> str:
        """
        Create SOAP envelope with the given body content.

        Args:
            body_content: XML content for SOAP body
            soap_action: SOAP action header

        Returns:
            Complete SOAP envelope as string
        """
        envelope = f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns="http://service.ws.dte.sii.cl/">
    <soap:Header/>
    <soap:Body>
        {body_content}
    </soap:Body>
</soap:Envelope>'''

        return envelope

    def _parse_soap_response(self, response_xml: str) -> Dict[str, Any]:
        """
        Parse SOAP response XML.

        Args:
            response_xml: Raw SOAP response

        Returns:
            Parsed response data

        Raises:
            SiiValidationException: If response contains errors
        """
        try:
            root = ET.fromstring(response_xml)

            # Find SOAP body
            body = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Body')
            if body is None:
                raise SiiValidationException("Respuesta SOAP inválida: sin Body")

            # Check for SOAP faults
            fault = body.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
            if fault is not None:
                fault_code = fault.findtext('.//faultcode', 'UNKNOWN')
                fault_string = fault.findtext('.//faultstring', 'Error desconocido')
                raise SiiValidationException(f"SOAP Fault [{fault_code}]: {fault_string}")

            # Extract response data
            response_data = {}
            for elem in body.iter():
                if elem.text and elem.tag.split('}')[-1] not in ['Body']:
                    key = elem.tag.split('}')[-1]
                    response_data[key] = elem.text

            return response_data

        except ET.ParseError as e:
            raise SiiValidationException(f"Error parsing SOAP response: {e}")

    def _make_soap_request(self, service_name: str, soap_body: str, soap_action: str = "") -> Dict[str, Any]:
        """
        Make SOAP request to SII service.

        Args:
            service_name: Name of the SII service
            soap_body: SOAP body content
            soap_action: SOAP action header

        Returns:
            Parsed response data

        Raises:
            SiiConnectionException: If connection fails
            SiiTimeoutException: If request times out
        """
        url = self._get_service_url(service_name)
        envelope = self._create_soap_envelope(soap_body, soap_action)

        headers = self.session.headers.copy()
        if soap_action:
            headers['SOAPAction'] = f'"{soap_action}"'

        for attempt in range(self.retry_attempts):
            try:
                logger.debug(f"Making SOAP request to {url} (attempt {attempt + 1})")

                response = self.session.post(
                    url,
                    data=envelope,
                    headers=headers,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    return self._parse_soap_response(response.text)
                else:
                    raise SiiConnectionException(
                        f"HTTP {response.status_code}: {response.text}",
                        endpoint=url,
                        status_code=response.status_code
                    )

            except requests.exceptions.Timeout:
                if attempt == self.retry_attempts - 1:
                    raise SiiTimeoutException(
                        f"Timeout after {self.timeout} seconds",
                        timeout_seconds=self.timeout
                    )
                logger.warning(f"Request timeout, retrying... (attempt {attempt + 1})")

            except requests.exceptions.ConnectionError as e:
                if attempt == self.retry_attempts - 1:
                    raise SiiConnectionException(f"Connection error: {e}", endpoint=url)
                logger.warning(f"Connection error, retrying... (attempt {attempt + 1})")

    def authenticate(self, rut_company: str, certificate_content: str, private_key_content: str) -> str:
        """
        Authenticate with SII and get access token.

        Args:
            rut_company: Company RUT
            certificate_content: X.509 certificate content
            private_key_content: Private key content

        Returns:
            Authentication token

        Raises:
            SiiAuthenticationException: If authentication fails
        """
        try:
            # Step 1: Get seed from SII
            seed_body = f'''
                <tns:getSeed/>
            '''

            seed_response = self._make_soap_request('authentication', seed_body)
            seed_value = seed_response.get('seed', '')

            if not seed_value:
                raise SiiAuthenticationException("No se pudo obtener seed del SII")

            # Step 2: Sign seed with certificate (simplified implementation)
            # In production, use proper cryptographic signing
            signed_seed = self._sign_seed(seed_value, certificate_content, private_key_content)

            # Step 3: Get authentication token
            auth_body = f'''
                <tns:getToken>
                    <tns:semilla>{signed_seed}</tns:semilla>
                </tns:getToken>
            '''

            auth_response = self._make_soap_request('authentication', auth_body)
            token = auth_response.get('token', '')

            if not token:
                raise SiiAuthenticationException("No se pudo obtener token de autenticación")

            self.auth_token = token
            self.token_expiry = datetime.now()

            logger.info(f"Successfully authenticated with SII for RUT {rut_company}")
            return token

        except Exception as e:
            if isinstance(e, SiiAuthenticationException):
                raise
            raise SiiAuthenticationException(f"Error en autenticación: {e}")

    def _sign_seed(self, seed: str, certificate: str, private_key: str) -> str:
        """
        Sign seed with certificate (simplified implementation).

        In production, this should use proper PKCS#7 signing with the certificate.
        This is a simplified version for demonstration.

        Args:
            seed: Seed value from SII
            certificate: X.509 certificate
            private_key: Private key

        Returns:
            Base64 encoded signed seed
        """
        # TODO: Implement proper PKCS#7 signing
        # For now, return a base64 encoded hash (NOT cryptographically secure)
        combined = f"{seed}{certificate[:100]}"
        hash_value = hashlib.sha256(combined.encode()).digest()
        return base64.b64encode(hash_value).decode()

    def submit_documents(self, request: SiiSubmissionRequest) -> SiiResponse:
        """
        Submit documents to SII.

        Args:
            request: Document submission request

        Returns:
            SII response with submission results

        Raises:
            SiiAuthenticationException: If not authenticated
            SiiValidationException: If submission fails
        """
        if not self.auth_token:
            raise SiiAuthenticationException("No hay token de autenticación válido")

        try:
            # Prepare submission data
            envelope_xml = request.envelope_xml or self._create_envelope_xml(request.documents)

            submission_body = f'''
                <tns:uploadFile>
                    <tns:rutSender>{request.rut_sender}</tns:rutSender>
                    <tns:rutCompany>{request.rut_company}</tns:rutCompany>
                    <tns:archivo>{base64.b64encode(envelope_xml.encode()).decode()}</tns:archivo>
                    <tns:token>{self.auth_token}</tns:token>
                </tns:uploadFile>
            '''

            response_data = self._make_soap_request('document_submission', submission_body)

            # Parse submission response
            track_id = response_data.get('trackid', '')
            estado = response_data.get('estado', '')

            # Create response object
            response = SiiResponse(
                success=bool(track_id and estado != 'ERROR'),
                operation="submit_documents",
                request_id=request.request_id,
                message=response_data.get('mensaje', '')
            )

            # Add document statuses
            for doc in request.documents:
                doc_status = SiiDocumentStatus(
                    document_id=doc.get('document_id', ''),
                    folio=doc.get('folio', 0),
                    document_type=doc.get('document_type', 0),
                    rut_emisor=doc.get('rut_emisor', ''),
                    state=SiiDocumentState.PENDING if track_id else SiiDocumentState.ERROR,
                    sii_track_id=track_id,
                    submission_date=datetime.now(),
                    sii_response_code=estado,
                    sii_response_message=response_data.get('mensaje', '')
                )
                response.document_statuses.append(doc_status)

            return response

        except Exception as e:
            if isinstance(e, (SiiConnectionException, SiiValidationException)):
                raise
            raise SiiValidationException(f"Error en envío de documentos: {e}")

    def query_document_status(self, request: SiiQueryRequest) -> SiiResponse:
        """
        Query document status in SII.

        Args:
            request: Status query request

        Returns:
            SII response with document statuses

        Raises:
            SiiAuthenticationException: If not authenticated
        """
        if not self.auth_token:
            raise SiiAuthenticationException("No hay token de autenticación válido")

        try:
            # Build query parameters
            query_params = []
            if request.track_ids:
                for track_id in request.track_ids:
                    query_params.append(f"<tns:trackId>{track_id}</tns:trackId>")

            query_body = f'''
                <tns:consultarEstDte>
                    <tns:rutConsultante>{request.rut_sender}</tns:rutConsultante>
                    <tns:rutCompania>{request.rut_company}</tns:rutCompania>
                    <tns:token>{self.auth_token}</tns:token>
                    {''.join(query_params)}
                </tns:consultarEstDte>
            '''

            response_data = self._make_soap_request('document_query', query_body)

            # Parse query response
            response = SiiResponse(
                success=True,
                operation="query_status",
                request_id=request.request_id,
                raw_response=response_data
            )

            # Parse document statuses from response
            # This would need to be implemented based on actual SII response format
            # For now, return a basic response
            return response

        except Exception as e:
            if isinstance(e, (SiiConnectionException, SiiAuthenticationException)):
                raise
            raise SiiValidationException(f"Error en consulta de estado: {e}")

    def _create_envelope_xml(self, documents: List[Dict[str, Any]]) -> str:
        """
        Create envelope XML for document submission.

        Args:
            documents: List of documents to include

        Returns:
            XML envelope content
        """
        # This would create the proper SII envelope format
        # For now, return a basic structure
        envelope = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
        envelope += '<EnvioDTE>\n'
        envelope += '  <SetDTE>\n'

        for doc in documents:
            envelope += f'    <DTE version="1.0">\n'
            envelope += f'      <!-- Document {doc.get("document_id", "")} -->\n'
            envelope += f'    </DTE>\n'

        envelope += '  </SetDTE>\n'
        envelope += '</EnvioDTE>\n'

        return envelope