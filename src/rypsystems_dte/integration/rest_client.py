"""
REST Client for SII APIs.

Handles REST-based communication with modern SII APIs for document
operations and status queries.
"""

import json
from typing import Optional, Dict, Any, List
import requests
from datetime import datetime
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


class RestClient:
    """
    REST client for modern SII APIs.

    Provides a more modern HTTP-based interface for SII operations
    when available, falling back to SOAP when necessary.
    """

    def __init__(
        self,
        ambiente: SiiAmbiente = SiiAmbiente.CERTIFICACION,
        timeout: int = 30,
        retry_attempts: int = 3
    ):
        """
        Initialize REST client.

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
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'rypsystems-dte/1.0.0'
        })

    def _get_api_base_url(self) -> str:
        """
        Get the base URL for SII REST APIs.

        Returns:
            Base URL for API endpoints
        """
        if self.ambiente == SiiAmbiente.PRODUCCION:
            return "https://api.sii.cl/v1"
        else:
            return "https://apicert.sii.cl/v1"

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make REST request to SII API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request data for POST/PUT requests

        Returns:
            Parsed JSON response

        Raises:
            SiiConnectionException: If connection fails
            SiiTimeoutException: If request times out
            SiiValidationException: If API returns error
        """
        url = f"{self._get_api_base_url()}{endpoint}"
        headers = self.session.headers.copy()

        if self.auth_token:
            headers['Authorization'] = f"Bearer {self.auth_token}"

        for attempt in range(self.retry_attempts):
            try:
                logger.debug(f"Making {method} request to {url} (attempt {attempt + 1})")

                if method.upper() == 'GET':
                    response = self.session.get(url, headers=headers, timeout=self.timeout, params=data)
                elif method.upper() == 'POST':
                    response = self.session.post(url, headers=headers, json=data, timeout=self.timeout)
                elif method.upper() == 'PUT':
                    response = self.session.put(url, headers=headers, json=data, timeout=self.timeout)
                elif method.upper() == 'DELETE':
                    response = self.session.delete(url, headers=headers, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Handle response
                if response.status_code in [200, 201, 202]:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        return {"raw_response": response.text}

                elif response.status_code == 401:
                    raise SiiAuthenticationException("Token de autenticación inválido o expirado")

                elif response.status_code in [400, 422]:
                    try:
                        error_data = response.json()
                        raise SiiValidationException(
                            error_data.get('message', 'Error de validación'),
                            validation_errors=error_data.get('errors', [])
                        )
                    except json.JSONDecodeError:
                        raise SiiValidationException(f"Error de validación: {response.text}")

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

    def authenticate(self, rut_company: str, api_key: str, api_secret: str) -> str:
        """
        Authenticate with SII REST API.

        Args:
            rut_company: Company RUT
            api_key: API key
            api_secret: API secret

        Returns:
            JWT authentication token

        Raises:
            SiiAuthenticationException: If authentication fails
        """
        try:
            auth_data = {
                "rut_company": rut_company,
                "api_key": api_key,
                "api_secret": api_secret,
                "grant_type": "client_credentials"
            }

            response = self._make_request('POST', '/auth/token', auth_data)

            token = response.get('access_token')
            if not token:
                raise SiiAuthenticationException("No se recibió token de acceso")

            self.auth_token = token
            self.token_expiry = datetime.now()

            # Store token expiration if provided
            expires_in = response.get('expires_in')
            if expires_in:
                from datetime import timedelta
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

            logger.info(f"Successfully authenticated with SII REST API for RUT {rut_company}")
            return token

        except Exception as e:
            if isinstance(e, SiiAuthenticationException):
                raise
            raise SiiAuthenticationException(f"Error en autenticación REST: {e}")

    def submit_documents(self, request: SiiSubmissionRequest) -> SiiResponse:
        """
        Submit documents via REST API.

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
            submission_data = {
                "rut_sender": request.rut_sender,
                "rut_company": request.rut_company,
                "documents": request.documents,
                "validate_only": request.validate_only,
                "priority": request.priority
            }

            if request.envelope_xml:
                submission_data["envelope_xml"] = request.envelope_xml

            response_data = self._make_request('POST', '/documents/submit', submission_data)

            # Parse REST response
            success = response_data.get('success', False)
            track_id = response_data.get('track_id', '')

            response = SiiResponse(
                success=success,
                operation="submit_documents",
                request_id=request.request_id,
                message=response_data.get('message', ''),
                raw_response=response_data
            )

            # Process document statuses
            documents_status = response_data.get('documents', [])
            for i, doc_status in enumerate(documents_status):
                doc_data = request.documents[i] if i < len(request.documents) else {}

                status = SiiDocumentStatus(
                    document_id=doc_data.get('document_id', ''),
                    folio=doc_data.get('folio', 0),
                    document_type=doc_data.get('document_type', 0),
                    rut_emisor=doc_data.get('rut_emisor', ''),
                    state=self._map_status_to_state(doc_status.get('status', 'unknown')),
                    sii_track_id=track_id,
                    submission_date=datetime.now(),
                    validation_errors=doc_status.get('validation_errors', []),
                    business_errors=doc_status.get('business_errors', []),
                    warnings=doc_status.get('warnings', []),
                    sii_response_code=doc_status.get('code', ''),
                    sii_response_message=doc_status.get('message', '')
                )
                response.document_statuses.append(status)

            return response

        except Exception as e:
            if isinstance(e, (SiiConnectionException, SiiValidationException, SiiAuthenticationException)):
                raise
            raise SiiValidationException(f"Error en envío REST de documentos: {e}")

    def query_document_status(self, request: SiiQueryRequest) -> SiiResponse:
        """
        Query document status via REST API.

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
            params = {
                "rut_company": request.rut_company,
                "rut_sender": request.rut_sender
            }

            if request.document_ids:
                params["document_ids"] = ",".join(request.document_ids)
            if request.track_ids:
                params["track_ids"] = ",".join(request.track_ids)
            if request.folios:
                params["folios"] = ",".join(map(str, request.folios))
            if request.document_types:
                params["document_types"] = ",".join(map(str, request.document_types))
            if request.date_from:
                params["date_from"] = request.date_from.isoformat()
            if request.date_to:
                params["date_to"] = request.date_to.isoformat()

            response_data = self._make_request('GET', '/documents/status', params)

            response = SiiResponse(
                success=response_data.get('success', False),
                operation="query_status",
                request_id=request.request_id,
                message=response_data.get('message', ''),
                raw_response=response_data
            )

            # Process document statuses
            documents = response_data.get('documents', [])
            for doc_data in documents:
                status = SiiDocumentStatus(
                    document_id=doc_data.get('document_id', ''),
                    folio=doc_data.get('folio', 0),
                    document_type=doc_data.get('document_type', 0),
                    rut_emisor=doc_data.get('rut_emisor', ''),
                    state=self._map_status_to_state(doc_data.get('status', 'unknown')),
                    sii_track_id=doc_data.get('track_id', ''),
                    submission_date=self._parse_datetime(doc_data.get('submission_date')),
                    processing_date=self._parse_datetime(doc_data.get('processing_date')),
                    validation_errors=doc_data.get('validation_errors', []),
                    business_errors=doc_data.get('business_errors', []),
                    warnings=doc_data.get('warnings', []),
                    sii_response_code=doc_data.get('code', ''),
                    sii_response_message=doc_data.get('message', '')
                )
                response.document_statuses.append(status)

            return response

        except Exception as e:
            if isinstance(e, (SiiConnectionException, SiiAuthenticationException)):
                raise
            raise SiiValidationException(f"Error en consulta REST de estado: {e}")

    def get_document_receipt(self, track_id: str, receipt_type: str = 'xml') -> Optional[str]:
        """
        Get document receipt from SII.

        Args:
            track_id: SII tracking ID
            receipt_type: Type of receipt (xml, pdf, json)

        Returns:
            Receipt content or None if not available

        Raises:
            SiiAuthenticationException: If not authenticated
        """
        if not self.auth_token:
            raise SiiAuthenticationException("No hay token de autenticación válido")

        try:
            params = {
                "track_id": track_id,
                "format": receipt_type
            }

            response_data = self._make_request('GET', '/documents/receipt', params)
            return response_data.get('receipt_content')

        except Exception as e:
            logger.warning(f"Error getting receipt for track_id {track_id}: {e}")
            return None

    def _map_status_to_state(self, status: str) -> SiiDocumentState:
        """
        Map SII status string to internal state enum.

        Args:
            status: SII status string

        Returns:
            Corresponding document state
        """
        status_mapping = {
            'pending': SiiDocumentState.PENDING,
            'accepted': SiiDocumentState.ACCEPTED,
            'rejected': SiiDocumentState.REJECTED,
            'processed': SiiDocumentState.PROCESSED,
            'error': SiiDocumentState.ERROR,
            'timeout': SiiDocumentState.TIMEOUT
        }

        return status_mapping.get(status.lower(), SiiDocumentState.UNKNOWN)

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse datetime string from API response.

        Args:
            date_str: ISO format datetime string

        Returns:
            Parsed datetime or None
        """
        if not date_str:
            return None

        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            logger.warning(f"Could not parse datetime: {date_str}")
            return None