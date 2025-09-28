"""
Main SII Client for document integration.

Provides a unified interface for SII communication, automatically choosing
between SOAP and REST protocols based on availability and operation type.
"""

import uuid
from typing import Optional, List, Union
from datetime import datetime, date
import logging

from ..sii.base import SiiAmbiente
from ..dte.document import BaseDocument
from .soap_client import SoapClient
from .rest_client import RestClient
from .exceptions import (
    IntegrationException,
    SiiConnectionException,
    SiiAuthenticationException
)
from .models.sii_response import SiiResponse
from .models.sii_request import (
    SiiSubmissionRequest,
    SiiQueryRequest,
    SiiAuthenticationRequest
)


logger = logging.getLogger(__name__)


class SiiClient:
    """
    Unified SII client for document operations.

    Provides a high-level interface for SII integration, automatically
    selecting the appropriate protocol (SOAP/REST) and handling
    authentication, retries, and error recovery.
    """

    def __init__(
        self,
        ambiente: SiiAmbiente = SiiAmbiente.CERTIFICACION,
        prefer_rest: bool = True,
        timeout: int = 30,
        retry_attempts: int = 3
    ):
        """
        Initialize SII client.

        Args:
            ambiente: SII environment (production or certification)
            prefer_rest: Prefer REST over SOAP when available
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
        """
        self.ambiente = ambiente
        self.prefer_rest = prefer_rest
        self.timeout = timeout
        self.retry_attempts = retry_attempts

        # Initialize protocol clients
        self.soap_client = SoapClient(ambiente, timeout, retry_attempts)
        self.rest_client = RestClient(ambiente, timeout, retry_attempts)

        # Authentication state
        self.is_authenticated = False
        self.current_rut_company = None
        self.auth_method = None  # 'soap' or 'rest'

        logger.info(f"SII Client initialized for {ambiente.name} environment")

    def authenticate_with_certificate(
        self,
        rut_company: str,
        certificate_content: str,
        private_key_content: str
    ) -> bool:
        """
        Authenticate using X.509 certificate (SOAP method).

        Args:
            rut_company: Company RUT
            certificate_content: X.509 certificate content
            private_key_content: Private key content

        Returns:
            True if authentication successful

        Raises:
            SiiAuthenticationException: If authentication fails
        """
        try:
            token = self.soap_client.authenticate(
                rut_company,
                certificate_content,
                private_key_content
            )

            self.is_authenticated = bool(token)
            self.current_rut_company = rut_company
            self.auth_method = 'soap'

            logger.info(f"Successfully authenticated via SOAP for RUT {rut_company}")
            return True

        except Exception as e:
            logger.error(f"SOAP authentication failed: {e}")
            raise SiiAuthenticationException(f"Error en autenticación con certificado: {e}")

    def authenticate_with_api_key(
        self,
        rut_company: str,
        api_key: str,
        api_secret: str
    ) -> bool:
        """
        Authenticate using API key (REST method).

        Args:
            rut_company: Company RUT
            api_key: API key
            api_secret: API secret

        Returns:
            True if authentication successful

        Raises:
            SiiAuthenticationException: If authentication fails
        """
        try:
            token = self.rest_client.authenticate(rut_company, api_key, api_secret)

            self.is_authenticated = bool(token)
            self.current_rut_company = rut_company
            self.auth_method = 'rest'

            logger.info(f"Successfully authenticated via REST for RUT {rut_company}")
            return True

        except Exception as e:
            logger.error(f"REST authentication failed: {e}")
            # Try to fallback to SOAP if available
            logger.info("Attempting fallback to SOAP authentication...")
            raise SiiAuthenticationException(f"Error en autenticación con API key: {e}")

    def submit_document(
        self,
        document: BaseDocument,
        rut_sender: Optional[str] = None,
        validate_only: bool = False
    ) -> SiiResponse:
        """
        Submit a single document to SII.

        Args:
            document: DTE document to submit
            rut_sender: RUT of sender (defaults to document's emisor)
            validate_only: Only validate, don't process

        Returns:
            SII response with submission results

        Raises:
            SiiAuthenticationException: If not authenticated
            IntegrationException: If submission fails
        """
        return self.submit_documents([document], rut_sender, validate_only)

    def submit_documents(
        self,
        documents: List[BaseDocument],
        rut_sender: Optional[str] = None,
        validate_only: bool = False
    ) -> SiiResponse:
        """
        Submit multiple documents to SII.

        Args:
            documents: List of DTE documents to submit
            rut_sender: RUT of sender (defaults to first document's emisor)
            validate_only: Only validate, don't process

        Returns:
            SII response with submission results

        Raises:
            SiiAuthenticationException: If not authenticated
            IntegrationException: If submission fails
        """
        if not self.is_authenticated:
            raise SiiAuthenticationException("Cliente no autenticado con SII")

        if not documents:
            raise IntegrationException("No se proporcionaron documentos para enviar")

        try:
            # Prepare document data
            document_data = []
            for doc in documents:
                doc_info = {
                    'document_id': doc.get_id(),
                    'folio': doc.get_folio(),
                    'document_type': doc.get_tipo_documento(),
                    'rut_emisor': doc.get_rut_emisor(),
                    'xml_content': doc.save_xml()
                }
                document_data.append(doc_info)

            # Use sender RUT from parameter or first document
            if not rut_sender:
                rut_sender = documents[0].get_rut_emisor()

            # Create submission request
            request = SiiSubmissionRequest(
                request_id=str(uuid.uuid4()),
                rut_company=self.current_rut_company,
                rut_sender=rut_sender,
                documents=document_data,
                validate_only=validate_only
            )

            # Choose protocol and submit
            if self.auth_method == 'rest' and self.prefer_rest:
                logger.debug("Submitting documents via REST API")
                response = self.rest_client.submit_documents(request)
            else:
                logger.debug("Submitting documents via SOAP")
                response = self.soap_client.submit_documents(request)

            logger.info(f"Successfully submitted {len(documents)} documents to SII")
            return response

        except Exception as e:
            if isinstance(e, (SiiAuthenticationException, IntegrationException)):
                raise
            raise IntegrationException(f"Error en envío de documentos: {e}")

    def query_document_status(
        self,
        document_ids: Optional[List[str]] = None,
        track_ids: Optional[List[str]] = None,
        folios: Optional[List[int]] = None,
        document_types: Optional[List[int]] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        rut_sender: Optional[str] = None
    ) -> SiiResponse:
        """
        Query document status in SII.

        Args:
            document_ids: Specific document IDs to query
            track_ids: SII tracking IDs to query
            folios: Document folios to query
            document_types: Document types to filter
            date_from: Start date for range query
            date_to: End date for range query
            rut_sender: RUT of sender (defaults to authenticated company)

        Returns:
            SII response with document statuses

        Raises:
            SiiAuthenticationException: If not authenticated
            IntegrationException: If query fails
        """
        if not self.is_authenticated:
            raise SiiAuthenticationException("Cliente no autenticado con SII")

        try:
            # Create query request
            request = SiiQueryRequest(
                request_id=str(uuid.uuid4()),
                rut_company=self.current_rut_company,
                rut_sender=rut_sender or self.current_rut_company,
                document_ids=document_ids,
                track_ids=track_ids,
                folios=folios,
                document_types=document_types,
                date_from=date_from,
                date_to=date_to
            )

            # Choose protocol and query
            if self.auth_method == 'rest' and self.prefer_rest:
                logger.debug("Querying document status via REST API")
                response = self.rest_client.query_document_status(request)
            else:
                logger.debug("Querying document status via SOAP")
                response = self.soap_client.query_document_status(request)

            logger.info(f"Successfully queried document status")
            return response

        except Exception as e:
            if isinstance(e, (SiiAuthenticationException, IntegrationException)):
                raise
            raise IntegrationException(f"Error en consulta de estado: {e}")

    def get_document_receipt(self, track_id: str, receipt_type: str = 'xml') -> Optional[str]:
        """
        Get document receipt from SII.

        Args:
            track_id: SII tracking ID
            receipt_type: Type of receipt (xml, pdf)

        Returns:
            Receipt content or None if not available

        Raises:
            SiiAuthenticationException: If not authenticated
        """
        if not self.is_authenticated:
            raise SiiAuthenticationException("Cliente no autenticado con SII")

        try:
            if self.auth_method == 'rest':
                return self.rest_client.get_document_receipt(track_id, receipt_type)
            else:
                # SOAP receipt retrieval would be implemented here
                logger.warning("Receipt retrieval via SOAP not yet implemented")
                return None

        except Exception as e:
            logger.warning(f"Error getting receipt for track_id {track_id}: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test connection to SII services.

        Returns:
            True if connection is working

        Raises:
            SiiConnectionException: If connection fails
        """
        try:
            # Try a simple query to test connectivity
            if self.is_authenticated:
                # Test with a status query
                response = self.query_document_status(date_from=date.today())
                return response.success
            else:
                # Test basic connectivity without authentication
                # This would need to be implemented based on available SII endpoints
                logger.warning("Cannot test connection without authentication")
                return False

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise SiiConnectionException(f"Error testing connection: {e}")

    def get_authentication_status(self) -> dict:
        """
        Get current authentication status.

        Returns:
            Dictionary with authentication information
        """
        return {
            'is_authenticated': self.is_authenticated,
            'auth_method': self.auth_method,
            'rut_company': self.current_rut_company,
            'ambiente': self.ambiente.name,
            'soap_token': bool(self.soap_client.auth_token),
            'rest_token': bool(self.rest_client.auth_token)
        }

    def logout(self):
        """Clear authentication tokens and reset client state."""
        self.is_authenticated = False
        self.current_rut_company = None
        self.auth_method = None
        self.soap_client.auth_token = None
        self.rest_client.auth_token = None

        logger.info("Successfully logged out from SII")


# Convenience functions for common operations
def create_sii_client(
    ambiente: SiiAmbiente = SiiAmbiente.CERTIFICACION,
    **kwargs
) -> SiiClient:
    """
    Create a configured SII client.

    Args:
        ambiente: SII environment
        **kwargs: Additional client configuration

    Returns:
        Configured SII client
    """
    return SiiClient(ambiente=ambiente, **kwargs)