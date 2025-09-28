"""
Servicio de consulta de estados de documentos en SII.

Maneja la consulta y monitoreo de estados de documentos DTE en SII,
con soporte para consultas individuales, masivas y monitoreo continuo.
"""

import time
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, date, timedelta
from enum import Enum
import logging

from ..base import SiiAmbiente
from ...dte.document import BaseDocument
from .soap_service import SoapService
from .rest_service import RestService
from .sii_endpoints import SiiEnvironment
from .exceptions import (
    SiiWebServiceException,
    SiiAuthenticationError,
    SiiCommunicationError,
    SiiTimeoutError
)


logger = logging.getLogger(__name__)


class DocumentStatus(str, Enum):
    """Estados posibles de documentos en SII."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PROCESSED = "processed"
    ERROR = "error"
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"


class StatusQueryResult:
    """Resultado de consulta de estado."""

    def __init__(
        self,
        document_id: str,
        status: DocumentStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
        last_updated: Optional[datetime] = None,
        protocol_used: str = "unknown"
    ):
        self.document_id = document_id
        self.status = status
        self.message = message
        self.details = details or {}
        self.last_updated = last_updated or datetime.now()
        self.protocol_used = protocol_used

    @property
    def is_final_status(self) -> bool:
        """Verifica si el estado es final (no cambiará)."""
        return self.status in [
            DocumentStatus.ACCEPTED,
            DocumentStatus.REJECTED,
            DocumentStatus.ERROR
        ]

    @property
    def is_successful(self) -> bool:
        """Verifica si el estado indica éxito."""
        return self.status in [
            DocumentStatus.ACCEPTED,
            DocumentStatus.PROCESSED
        ]

    def __str__(self) -> str:
        return f"{self.document_id}: {self.status.value} - {self.message}"


class StatusChecker:
    """
    Servicio de consulta de estados de documentos.

    Proporciona funcionalidades para consultar estados de documentos
    individuales y masivos, con monitoreo continuo y notificaciones.
    """

    def __init__(
        self,
        environment: SiiAmbiente = SiiAmbiente.CERTIFICACION,
        timeout: int = 30,
        retry_attempts: int = 3,
        polling_interval: int = 30
    ):
        """
        Initialize status checker.

        Args:
            environment: SII environment
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            polling_interval: Polling interval for monitoring in seconds
        """
        # Convert SiiAmbiente to SiiEnvironment
        sii_env = SiiEnvironment.PRODUCCION if environment == SiiAmbiente.PRODUCCION else SiiEnvironment.CERTIFICACION

        self.environment = environment
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.polling_interval = polling_interval

        # Initialize services
        self.soap_service = SoapService(sii_env, timeout, retry_attempts)
        self.rest_service = RestService(sii_env, timeout, retry_attempts)

        # Monitoring state
        self.monitored_documents = {}
        self.monitoring_active = False
        self.last_check_time = None

        # Statistics
        self.stats = {
            'total_queries': 0,
            'soap_queries': 0,
            'rest_queries': 0,
            'cache_hits': 0,
            'errors': 0
        }

        # Simple status cache
        self.status_cache = {}
        self.cache_ttl = timedelta(minutes=5)

    def check_document_status(
        self,
        document: Union[BaseDocument, str],
        rut_sender: Optional[str] = None,
        use_cache: bool = True,
        prefer_rest: bool = True
    ) -> StatusQueryResult:
        """
        Consulta el estado de un documento específico.

        Args:
            document: Documento o ID del documento
            rut_sender: RUT del emisor (requerido si se pasa ID como string)
            use_cache: Usar cache de resultados
            prefer_rest: Preferir REST sobre SOAP

        Returns:
            Resultado de la consulta

        Raises:
            SiiAuthenticationError: Si no hay autenticación válida
            SiiCommunicationError: Si hay error de comunicación
        """
        # Extract document information
        if isinstance(document, str):
            document_id = document
            if not rut_sender:
                raise ValueError("rut_sender es requerido cuando document es string")
            # Parse document ID to extract type and folio
            doc_type, folio = self._parse_document_id(document_id)
        else:
            document_id = document.get_id()
            rut_sender = rut_sender or document.get_rut_emisor()
            doc_type = document.get_tipo_documento()
            folio = document.get_folio()

        # Check cache first
        if use_cache:
            cached_result = self._get_cached_status(document_id)
            if cached_result:
                self.stats['cache_hits'] += 1
                return cached_result

        # Determine protocols to try
        protocols = ['rest', 'soap'] if prefer_rest else ['soap', 'rest']

        last_exception = None
        for protocol in protocols:
            try:
                if protocol == 'rest' and self.rest_service.is_authenticated():
                    result = self._check_status_rest(document_id, rut_sender, doc_type, folio)
                elif protocol == 'soap' and self.soap_service.is_authenticated():
                    result = self._check_status_soap(document_id, rut_sender, doc_type, folio)
                else:
                    continue

                # Update statistics
                self.stats['total_queries'] += 1
                if protocol == 'rest':
                    self.stats['rest_queries'] += 1
                else:
                    self.stats['soap_queries'] += 1

                # Cache result
                if use_cache:
                    self._cache_status(document_id, result)

                logger.debug(f"Estado consultado via {protocol.upper()}: {result}")
                return result

            except Exception as e:
                logger.warning(f"Error consultando estado via {protocol}: {e}")
                last_exception = e
                continue

        # All protocols failed
        self.stats['errors'] += 1
        error_msg = f"Error consultando estado: {last_exception}"

        return StatusQueryResult(
            document_id=document_id,
            status=DocumentStatus.ERROR,
            message=error_msg,
            protocol_used="error"
        )

    def check_multiple_documents(
        self,
        documents: List[Union[BaseDocument, str]],
        rut_sender: Optional[str] = None,
        batch_size: int = 10,
        delay_between_batches: float = 1.0
    ) -> List[StatusQueryResult]:
        """
        Consulta estados de múltiples documentos.

        Args:
            documents: Lista de documentos o IDs
            rut_sender: RUT del emisor (para IDs como string)
            batch_size: Tamaño de lote para consultas
            delay_between_batches: Delay entre lotes en segundos

        Returns:
            Lista de resultados de consulta
        """
        if not documents:
            return []

        results = []
        total_docs = len(documents)

        logger.info(f"Consultando estado de {total_docs} documentos")

        # Process in batches
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]
            batch_results = []

            logger.debug(f"Procesando lote {i//batch_size + 1}: {len(batch)} documentos")

            for document in batch:
                try:
                    result = self.check_document_status(document, rut_sender)
                    batch_results.append(result)

                except Exception as e:
                    logger.error(f"Error consultando documento {document}: {e}")
                    error_result = StatusQueryResult(
                        document_id=str(document),
                        status=DocumentStatus.ERROR,
                        message=str(e),
                        protocol_used="error"
                    )
                    batch_results.append(error_result)

            results.extend(batch_results)

            # Delay between batches (except for last batch)
            if i + batch_size < total_docs:
                time.sleep(delay_between_batches)

        successful = sum(1 for r in results if r.status != DocumentStatus.ERROR)
        logger.info(f"Consulta masiva completada: {successful}/{total_docs} exitosos")

        return results

    def start_monitoring(
        self,
        documents: List[Union[BaseDocument, str]],
        callback: Optional[Callable[[StatusQueryResult], None]] = None,
        rut_sender: Optional[str] = None,
        max_monitoring_time: int = 3600  # 1 hour default
    ):
        """
        Inicia monitoreo continuo de documentos.

        Args:
            documents: Documentos a monitorear
            callback: Función callback para notificaciones de cambio
            rut_sender: RUT del emisor
            max_monitoring_time: Tiempo máximo de monitoreo en segundos
        """
        if self.monitoring_active:
            logger.warning("Monitoreo ya está activo")
            return

        logger.info(f"Iniciando monitoreo de {len(documents)} documentos")

        # Initialize monitoring data
        for document in documents:
            doc_id = document.get_id() if hasattr(document, 'get_id') else str(document)
            self.monitored_documents[doc_id] = {
                'document': document,
                'last_status': None,
                'status_changes': [],
                'start_time': datetime.now()
            }

        self.monitoring_active = True
        self.last_check_time = datetime.now()

        try:
            start_time = datetime.now()

            while self.monitoring_active:
                # Check if max monitoring time exceeded
                if (datetime.now() - start_time).total_seconds() > max_monitoring_time:
                    logger.info("Tiempo máximo de monitoreo alcanzado")
                    break

                # Check all monitored documents
                self._check_monitored_documents(callback, rut_sender)

                # Remove documents with final status
                self._cleanup_final_documents()

                # Break if no more documents to monitor
                if not self.monitored_documents:
                    logger.info("Todos los documentos alcanzaron estado final")
                    break

                # Wait for next check
                time.sleep(self.polling_interval)

        except Exception as e:
            logger.error(f"Error durante monitoreo: {e}")

        finally:
            self.monitoring_active = False
            logger.info("Monitoreo finalizado")

    def stop_monitoring(self):
        """Detiene el monitoreo continuo."""
        self.monitoring_active = False
        self.monitored_documents.clear()
        logger.info("Monitoreo detenido")

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Obtiene estado del monitoreo."""
        return {
            'active': self.monitoring_active,
            'documents_monitored': len(self.monitored_documents),
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'polling_interval': self.polling_interval
        }

    def _check_status_soap(
        self,
        document_id: str,
        rut_sender: str,
        document_type: int,
        folio: int
    ) -> StatusQueryResult:
        """Consulta estado via SOAP."""
        try:
            # Get company RUT (typically same as sender for small businesses)
            rut_company = rut_sender

            response = self.soap_service.query_document_status(
                rut_sender, rut_company, document_type, folio
            )

            # Parse SOAP response
            status = self._parse_soap_status(response)
            message = response.get('message', 'Estado consultado via SOAP')

            return StatusQueryResult(
                document_id=document_id,
                status=status,
                message=message,
                details=response,
                protocol_used='soap'
            )

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiCommunicationError(f"Error en consulta SOAP: {str(e)}")

    def _check_status_rest(
        self,
        document_id: str,
        rut_sender: str,
        document_type: int,
        folio: int
    ) -> StatusQueryResult:
        """Consulta estado via REST."""
        try:
            rut_company = rut_sender

            response = self.rest_service.query_document_status_rest(
                rut_sender, rut_company, document_type, folio
            )

            # Parse REST response
            status = self._parse_rest_status(response)
            message = response.get('message', 'Estado consultado via REST')

            return StatusQueryResult(
                document_id=document_id,
                status=status,
                message=message,
                details=response,
                protocol_used='rest'
            )

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiCommunicationError(f"Error en consulta REST: {str(e)}")

    def _parse_soap_status(self, response: Dict[str, Any]) -> DocumentStatus:
        """Parsea estado desde respuesta SOAP."""
        status_text = response.get('status', '').lower()

        if 'accepted' in status_text or 'aceptado' in status_text:
            return DocumentStatus.ACCEPTED
        elif 'rejected' in status_text or 'rechazado' in status_text:
            return DocumentStatus.REJECTED
        elif 'pending' in status_text or 'pendiente' in status_text:
            return DocumentStatus.PENDING
        elif 'processed' in status_text or 'procesado' in status_text:
            return DocumentStatus.PROCESSED
        elif 'not found' in status_text or 'no encontrado' in status_text:
            return DocumentStatus.NOT_FOUND
        else:
            return DocumentStatus.UNKNOWN

    def _parse_rest_status(self, response: Dict[str, Any]) -> DocumentStatus:
        """Parsea estado desde respuesta REST."""
        status_text = response.get('status', '').lower()

        status_mapping = {
            'accepted': DocumentStatus.ACCEPTED,
            'rejected': DocumentStatus.REJECTED,
            'pending': DocumentStatus.PENDING,
            'processed': DocumentStatus.PROCESSED,
            'not_found': DocumentStatus.NOT_FOUND,
            'error': DocumentStatus.ERROR
        }

        return status_mapping.get(status_text, DocumentStatus.UNKNOWN)

    def _parse_document_id(self, document_id: str) -> tuple[int, int]:
        """Parsea ID de documento para extraer tipo y folio."""
        try:
            # Format: RUT_TTFFOLIO (e.g., 76354771-K_T033F000001001)
            parts = document_id.split('_T')
            if len(parts) != 2:
                raise ValueError("Formato de ID inválido")

            type_folio = parts[1]
            if not type_folio.startswith('T') or 'F' not in type_folio:
                raise ValueError("Formato de tipo/folio inválido")

            # Extract type
            type_part = type_folio[1:type_folio.index('F')]
            doc_type = int(type_part)

            # Extract folio
            folio_part = type_folio[type_folio.index('F')+1:]
            folio = int(folio_part)

            return doc_type, folio

        except Exception as e:
            raise ValueError(f"Error parseando ID de documento '{document_id}': {e}")

    def _get_cached_status(self, document_id: str) -> Optional[StatusQueryResult]:
        """Obtiene estado desde cache."""
        if document_id not in self.status_cache:
            return None

        cached_data = self.status_cache[document_id]
        if datetime.now() - cached_data['timestamp'] > self.cache_ttl:
            # Cache expired
            del self.status_cache[document_id]
            return None

        return cached_data['result']

    def _cache_status(self, document_id: str, result: StatusQueryResult):
        """Guarda estado en cache."""
        self.status_cache[document_id] = {
            'result': result,
            'timestamp': datetime.now()
        }

        # Simple cache cleanup - remove old entries
        if len(self.status_cache) > 1000:
            # Remove oldest 100 entries
            sorted_items = sorted(
                self.status_cache.items(),
                key=lambda x: x[1]['timestamp']
            )
            for doc_id, _ in sorted_items[:100]:
                del self.status_cache[doc_id]

    def _check_monitored_documents(
        self,
        callback: Optional[Callable[[StatusQueryResult], None]],
        rut_sender: Optional[str]
    ):
        """Verifica documentos monitoreados."""
        for doc_id, monitor_data in list(self.monitored_documents.items()):
            try:
                result = self.check_document_status(
                    monitor_data['document'],
                    rut_sender,
                    use_cache=False  # Fresh check for monitoring
                )

                # Check for status change
                last_status = monitor_data['last_status']
                if last_status is None or last_status.status != result.status:
                    # Status changed
                    monitor_data['status_changes'].append({
                        'from': last_status.status.value if last_status else None,
                        'to': result.status.value,
                        'timestamp': datetime.now(),
                        'message': result.message
                    })

                    # Call callback if provided
                    if callback:
                        try:
                            callback(result)
                        except Exception as e:
                            logger.error(f"Error en callback: {e}")

                monitor_data['last_status'] = result

            except Exception as e:
                logger.error(f"Error monitoreando documento {doc_id}: {e}")

        self.last_check_time = datetime.now()

    def _cleanup_final_documents(self):
        """Remueve documentos con estado final del monitoreo."""
        to_remove = []

        for doc_id, monitor_data in self.monitored_documents.items():
            last_status = monitor_data['last_status']
            if last_status and last_status.is_final_status:
                to_remove.append(doc_id)
                logger.info(f"Documento {doc_id} alcanzó estado final: {last_status.status.value}")

        for doc_id in to_remove:
            del self.monitored_documents[doc_id]

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del servicio."""
        total_queries = self.stats['total_queries']
        cache_hit_rate = (self.stats['cache_hits'] / total_queries * 100) if total_queries > 0 else 0

        return {
            'total_queries': total_queries,
            'soap_queries': self.stats['soap_queries'],
            'rest_queries': self.stats['rest_queries'],
            'cache_hits': self.stats['cache_hits'],
            'cache_hit_rate': round(cache_hit_rate, 2),
            'errors': self.stats['errors'],
            'cache_size': len(self.status_cache),
            'monitoring_active': self.monitoring_active,
            'monitored_documents': len(self.monitored_documents)
        }

    def clear_cache(self):
        """Limpia cache de estados."""
        self.status_cache.clear()
        logger.info("Cache de estados limpiado")

    def is_authenticated(self) -> bool:
        """Verifica si hay autenticación válida."""
        return (
            self.soap_service.is_authenticated() or
            self.rest_service.is_authenticated()
        )

    def __str__(self) -> str:
        return f"StatusChecker(environment={self.environment.name})"