"""
Servicio de envío de documentos al SII.

Coordina el envío de documentos DTE al SII usando SOAP y REST,
con manejo inteligente de protocolos, reintentos y validaciones.
"""

import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date
import logging
from enum import Enum

from ..base import SiiAmbiente
from ...dte.document import BaseDocument
from .soap_service import SoapService
from .rest_service import RestService
from .sii_endpoints import SiiEnvironment
from .exceptions import (
    SiiWebServiceException,
    SiiAuthenticationError,
    SiiValidationError,
    SiiCommunicationError,
    SiiDocumentRejectedError,
    SiiRateLimitError
)


logger = logging.getLogger(__name__)


class SendingProtocol(str, Enum):
    """Protocolos disponibles para envío."""
    SOAP_ONLY = "soap_only"
    REST_ONLY = "rest_only"
    AUTO = "auto"  # Try REST first, fallback to SOAP
    SOAP_PREFERRED = "soap_preferred"
    REST_PREFERRED = "rest_preferred"


class SendingResult:
    """Resultado del envío de documento."""

    def __init__(
        self,
        success: bool,
        protocol_used: str,
        track_id: Optional[str] = None,
        message: str = "",
        sii_response: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None
    ):
        self.success = success
        self.protocol_used = protocol_used
        self.track_id = track_id
        self.message = message
        self.sii_response = sii_response or {}
        self.errors = errors or []
        self.timestamp = datetime.now()

    def __str__(self) -> str:
        status = "✅ Exitoso" if self.success else "❌ Fallido"
        return f"{status} ({self.protocol_used}): {self.message}"


class DocumentSender:
    """
    Servicio coordinado de envío de documentos al SII.

    Maneja el envío inteligente de documentos usando SOAP y REST,
    con estrategias de fallback, reintentos y validaciones.
    """

    def __init__(
        self,
        environment: SiiAmbiente = SiiAmbiente.CERTIFICACION,
        protocol: SendingProtocol = SendingProtocol.AUTO,
        timeout: int = 60,
        retry_attempts: int = 3,
        rate_limit_delay: int = 1
    ):
        """
        Initialize document sender.

        Args:
            environment: SII environment
            protocol: Sending protocol strategy
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            rate_limit_delay: Delay between requests in seconds
        """
        # Convert SiiAmbiente to SiiEnvironment
        sii_env = SiiEnvironment.PRODUCCION if environment == SiiAmbiente.PRODUCCION else SiiEnvironment.CERTIFICACION

        self.environment = environment
        self.protocol = protocol
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.rate_limit_delay = rate_limit_delay

        # Initialize services
        self.soap_service = SoapService(sii_env, timeout, retry_attempts)
        self.rest_service = RestService(sii_env, timeout, retry_attempts)

        # Sending statistics
        self.stats = {
            'total_sent': 0,
            'soap_sent': 0,
            'rest_sent': 0,
            'failures': 0,
            'last_sent': None
        }

    def authenticate_soap(self, rut_company: str, certificate_content: str, private_key_content: str) -> bool:
        """
        Autenticar servicio SOAP.

        Args:
            rut_company: RUT de la empresa
            certificate_content: Certificado digital
            private_key_content: Clave privada

        Returns:
            True si autenticación exitosa

        Raises:
            SiiAuthenticationError: Si falla autenticación
        """
        try:
            token = self.soap_service.authenticate(rut_company, certificate_content, private_key_content)
            logger.info(f"Autenticación SOAP exitosa para {rut_company}")
            return bool(token)

        except Exception as e:
            logger.error(f"Error en autenticación SOAP: {e}")
            raise SiiAuthenticationError(f"Error autenticando SOAP: {str(e)}")

    def authenticate_rest(self, rut_company: str, api_key: str, api_secret: str) -> bool:
        """
        Autenticar servicio REST.

        Args:
            rut_company: RUT de la empresa
            api_key: API key
            api_secret: API secret

        Returns:
            True si autenticación exitosa

        Raises:
            SiiAuthenticationError: Si falla autenticación
        """
        try:
            token = self.rest_service.authenticate(rut_company, api_key, api_secret)
            logger.info(f"Autenticación REST exitosa para {rut_company}")
            return bool(token)

        except Exception as e:
            logger.error(f"Error en autenticación REST: {e}")
            raise SiiAuthenticationError(f"Error autenticando REST: {str(e)}")

    def send_document(
        self,
        document: BaseDocument,
        rut_sender: Optional[str] = None,
        rut_company: Optional[str] = None,
        validate_only: bool = False
    ) -> SendingResult:
        """
        Envía un documento al SII.

        Args:
            document: Documento a enviar
            rut_sender: RUT del emisor (opcional, se extrae del documento)
            rut_company: RUT de la empresa (opcional, se extrae del documento)
            validate_only: Solo validar, no procesar

        Returns:
            Resultado del envío

        Raises:
            SiiValidationError: Si el documento no es válido
            SiiAuthenticationError: Si no hay autenticación válida
        """
        # Extract RUTs from document if not provided
        if not rut_sender:
            rut_sender = document.get_rut_emisor()
        if not rut_company:
            rut_company = document.get_rut_emisor()  # Typically same for small businesses

        # Validate document data
        self._validate_document_for_sending(document)

        # Apply rate limiting
        self._apply_rate_limiting()

        # Determine protocol to use
        protocols_to_try = self._get_protocols_to_try()

        last_exception = None
        for protocol in protocols_to_try:
            try:
                if protocol == 'soap':
                    result = self._send_via_soap(document, rut_sender, rut_company, validate_only)
                elif protocol == 'rest':
                    result = self._send_via_rest(document, rut_sender, rut_company, validate_only)
                else:
                    continue

                # Update statistics
                self._update_stats(protocol, True)

                logger.info(f"Documento enviado exitosamente via {protocol.upper()}")
                return result

            except SiiRateLimitError as e:
                logger.warning(f"Rate limit excedido en {protocol}, esperando...")
                time.sleep(e.retry_after or 60)
                last_exception = e
                continue

            except SiiAuthenticationError as e:
                logger.error(f"Error de autenticación en {protocol}: {e}")
                last_exception = e
                continue

            except SiiValidationError as e:
                # Validation errors are not retryable
                logger.error(f"Error de validación en {protocol}: {e}")
                self._update_stats(protocol, False)
                return SendingResult(
                    success=False,
                    protocol_used=protocol,
                    message=str(e),
                    errors=[str(e)]
                )

            except Exception as e:
                logger.warning(f"Error enviando via {protocol}: {e}")
                last_exception = e
                continue

        # All protocols failed
        self._update_stats("unknown", False)
        error_msg = f"Falló envío por todos los protocolos: {last_exception}"

        return SendingResult(
            success=False,
            protocol_used="failed",
            message=error_msg,
            errors=[str(last_exception)]
        )

    def send_multiple_documents(
        self,
        documents: List[BaseDocument],
        rut_sender: Optional[str] = None,
        rut_company: Optional[str] = None,
        validate_only: bool = False,
        stop_on_error: bool = False
    ) -> List[SendingResult]:
        """
        Envía múltiples documentos al SII.

        Args:
            documents: Lista de documentos a enviar
            rut_sender: RUT del emisor
            rut_company: RUT de la empresa
            validate_only: Solo validar, no procesar
            stop_on_error: Parar al primer error

        Returns:
            Lista de resultados de envío
        """
        if not documents:
            return []

        results = []

        logger.info(f"Iniciando envío de {len(documents)} documentos")

        for i, document in enumerate(documents):
            try:
                logger.debug(f"Enviando documento {i+1}/{len(documents)}: {document.get_id()}")

                result = self.send_document(document, rut_sender, rut_company, validate_only)
                results.append(result)

                if not result.success and stop_on_error:
                    logger.warning(f"Deteniendo envío masivo por error en documento {i+1}")
                    break

                # Small delay between documents to avoid rate limiting
                if i < len(documents) - 1:  # Not the last document
                    time.sleep(self.rate_limit_delay)

            except Exception as e:
                logger.error(f"Error enviando documento {i+1}: {e}")

                error_result = SendingResult(
                    success=False,
                    protocol_used="error",
                    message=str(e),
                    errors=[str(e)]
                )
                results.append(error_result)

                if stop_on_error:
                    logger.warning(f"Deteniendo envío masivo por excepción en documento {i+1}")
                    break

        successful = sum(1 for r in results if r.success)
        logger.info(f"Envío masivo completado: {successful}/{len(results)} exitosos")

        return results

    def _send_via_soap(
        self,
        document: BaseDocument,
        rut_sender: str,
        rut_company: str,
        validate_only: bool
    ) -> SendingResult:
        """Envía documento via SOAP."""
        if not self.soap_service.is_authenticated():
            raise SiiAuthenticationError("Servicio SOAP no autenticado")

        try:
            # Get document XML
            xml_content = document.save_xml()

            # Send via SOAP
            response = self.soap_service.upload_dte(rut_sender, rut_company, xml_content)

            # Parse response
            success = response.get('success', False)
            message = response.get('message', 'Sin mensaje')
            track_id = response.get('track_id')

            if not success:
                # Check for rejection reasons
                if 'rechazado' in message.lower():
                    raise SiiDocumentRejectedError(
                        f"Documento rechazado: {message}",
                        rejection_reasons=[message]
                    )

            return SendingResult(
                success=success,
                protocol_used='soap',
                track_id=track_id,
                message=message,
                sii_response=response
            )

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiCommunicationError(f"Error en envío SOAP: {str(e)}")

    def _send_via_rest(
        self,
        document: BaseDocument,
        rut_sender: str,
        rut_company: str,
        validate_only: bool
    ) -> SendingResult:
        """Envía documento via REST."""
        if not self.rest_service.is_authenticated():
            raise SiiAuthenticationError("Servicio REST no autenticado")

        try:
            # Check if document type supports REST
            document_type = document.get_tipo_documento()
            if not self._supports_rest_sending(document_type):
                raise SiiValidationError(f"Tipo de documento {document_type} no soporta envío REST")

            # Prepare document data for REST
            document_data = {
                'tipo_documento': document_type,
                'folio': document.get_folio(),
                'fecha_emision': document.get_datos().get('Encabezado', {}).get('IdDoc', {}).get('FchEmis'),
                'datos': document.get_datos(),
                'validate_only': validate_only
            }

            # Send via REST
            response = self.rest_service.upload_boleta(rut_sender, rut_company, document_data)

            # Parse response
            success = response.get('success', False)
            message = response.get('message', 'Sin mensaje')
            track_id = response.get('track_id')

            return SendingResult(
                success=success,
                protocol_used='rest',
                track_id=track_id,
                message=message,
                sii_response=response
            )

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiCommunicationError(f"Error en envío REST: {str(e)}")

    def _validate_document_for_sending(self, document: BaseDocument):
        """Valida documento antes del envío."""
        try:
            # Basic validations
            if not document.get_rut_emisor():
                raise SiiValidationError("Documento sin RUT emisor")

            if not document.get_folio():
                raise SiiValidationError("Documento sin folio")

            # Check document has required data
            datos = document.get_datos()
            if not datos:
                raise SiiValidationError("Documento sin datos")

            # Validate document structure
            encabezado = datos.get('Encabezado')
            if not encabezado:
                raise SiiValidationError("Documento sin encabezado")

            # Check for TED (electronic stamp)
            if not hasattr(document, 'get_ted') or not document.get_ted():
                logger.warning("Documento sin TED - puede ser rechazado por SII")

        except Exception as e:
            if isinstance(e, SiiValidationError):
                raise
            raise SiiValidationError(f"Error validando documento: {str(e)}")

    def _get_protocols_to_try(self) -> List[str]:
        """Determina protocolos a intentar según estrategia."""
        if self.protocol == SendingProtocol.SOAP_ONLY:
            return ['soap']
        elif self.protocol == SendingProtocol.REST_ONLY:
            return ['rest']
        elif self.protocol == SendingProtocol.SOAP_PREFERRED:
            return ['soap', 'rest']
        elif self.protocol == SendingProtocol.REST_PREFERRED:
            return ['rest', 'soap']
        else:  # AUTO
            # Smart selection based on authentication status
            protocols = []
            if self.rest_service.is_authenticated():
                protocols.append('rest')
            if self.soap_service.is_authenticated():
                protocols.append('soap')

            if not protocols:
                # Default order if none authenticated
                protocols = ['rest', 'soap']

            return protocols

    def _supports_rest_sending(self, document_type: int) -> bool:
        """Verifica si tipo de documento soporta envío REST."""
        # Typically, REST is supported for boletas and some facturas
        rest_supported_types = [39, 41, 33, 34]  # Boletas and facturas
        return document_type in rest_supported_types

    def _apply_rate_limiting(self):
        """Aplica limitación de velocidad."""
        if self.stats['last_sent']:
            elapsed = (datetime.now() - self.stats['last_sent']).total_seconds()
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                logger.debug(f"Aplicando rate limiting: esperando {sleep_time:.2f}s")
                time.sleep(sleep_time)

    def _update_stats(self, protocol: str, success: bool):
        """Actualiza estadísticas de envío."""
        self.stats['total_sent'] += 1
        self.stats['last_sent'] = datetime.now()

        if success:
            if protocol == 'soap':
                self.stats['soap_sent'] += 1
            elif protocol == 'rest':
                self.stats['rest_sent'] += 1
        else:
            self.stats['failures'] += 1

    def get_sending_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de envío."""
        total = self.stats['total_sent']
        success_rate = ((total - self.stats['failures']) / total * 100) if total > 0 else 0

        return {
            'total_sent': total,
            'soap_sent': self.stats['soap_sent'],
            'rest_sent': self.stats['rest_sent'],
            'failures': self.stats['failures'],
            'success_rate': round(success_rate, 2),
            'last_sent': self.stats['last_sent'].isoformat() if self.stats['last_sent'] else None,
            'soap_authenticated': self.soap_service.is_authenticated(),
            'rest_authenticated': self.rest_service.is_authenticated()
        }

    def test_connectivity(self) -> Dict[str, bool]:
        """Prueba conectividad con servicios SII."""
        return {
            'soap_connectivity': self.soap_service.ping(),
            'rest_connectivity': self.rest_service.ping(),
            'soap_authenticated': self.soap_service.is_authenticated(),
            'rest_authenticated': self.rest_service.is_authenticated()
        }

    def is_ready_to_send(self) -> bool:
        """Verifica si está listo para enviar documentos."""
        return (
            self.soap_service.is_authenticated() or
            self.rest_service.is_authenticated()
        )

    def logout(self):
        """Cierra sesiones de ambos servicios."""
        self.soap_service.logout()
        self.rest_service.logout()
        logger.info("Sesiones cerradas para todos los servicios")

    def __str__(self) -> str:
        return f"DocumentSender(environment={self.environment.name}, protocol={self.protocol.value})"