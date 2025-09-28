"""
Exchange Service - Servicio principal del módulo Exchange

Traducción de ExchangeService de LibreDTE PHP.
Proporciona la funcionalidad principal para el intercambio de documentos.
"""

from typing import List, Optional, Dict, Any, Tuple
import requests
import json
import time
from datetime import datetime

from .enums import DocumentType, ProcessType
from .entities import Sender, Receiver, PartyEndpoint
from .support import ExchangeDocument, Envelope, ExchangeBag
from .factory import ExchangeFactory
from .exceptions import ExchangeException


class ExchangeService:
    """
    Servicio principal para el intercambio de documentos tributarios electrónicos.

    Maneja el envío, recepción y procesamiento de documentos entre contribuyentes
    utilizando diferentes protocolos y métodos de comunicación.
    """

    def __init__(self, factory: Optional[ExchangeFactory] = None):
        """
        Inicializa el servicio de intercambio.

        Args:
            factory: Fábrica de intercambio (opcional, se crea una por defecto)
        """
        self.factory = factory or ExchangeFactory()
        self._session = requests.Session()
        self._default_timeout = 30
        self._default_retries = 3

    def send_document(
        self,
        document: ExchangeDocument,
        sender: Sender,
        receiver: Receiver,
        endpoint: Optional[PartyEndpoint] = None
    ) -> Dict[str, Any]:
        """
        Envía un documento individual.

        Args:
            document: Documento a enviar
            sender: Entidad emisor
            receiver: Entidad receptor
            endpoint: Endpoint del receptor (opcional)

        Returns:
            Resultado del envío

        Raises:
            ExchangeException: Si hay error en el envío
        """
        try:
            # Validar compatibilidad
            self._validate_document_compatibility(document, sender, receiver)

            # Preparar documento para envío
            if document.is_draft():
                self._prepare_document_for_sending(document, sender)

            # Obtener endpoint
            target_endpoint = endpoint or self._get_default_endpoint(receiver)
            if not target_endpoint:
                raise ExchangeException("No se encontró endpoint para el receptor")

            # Enviar documento
            result = self._send_single_document(document, target_endpoint)

            # Actualizar estado del documento
            if result.get('success', False):
                document.mark_as_sent()
            else:
                document.mark_as_error(result.get('error', 'Error desconocido'))

            return result

        except Exception as e:
            document.mark_as_error(str(e))
            raise ExchangeException(f"Error enviando documento: {str(e)}")

    def send_envelope(
        self,
        envelope: Envelope,
        sender: Sender,
        receiver: Receiver,
        endpoint: Optional[PartyEndpoint] = None
    ) -> Dict[str, Any]:
        """
        Envía un sobre con múltiples documentos.

        Args:
            envelope: Sobre a enviar
            sender: Entidad emisor
            receiver: Entidad receptor
            endpoint: Endpoint del receptor (opcional)

        Returns:
            Resultado del envío

        Raises:
            ExchangeException: Si hay error en el envío
        """
        try:
            # Validar compatibilidad
            self._validate_envelope_compatibility(envelope, sender, receiver)

            # Sellar sobre si está en borrador
            if envelope.is_draft():
                if not envelope.seal():
                    raise ExchangeException("No se pudo sellar el sobre")

            # Obtener endpoint
            target_endpoint = endpoint or self._get_default_endpoint(receiver)
            if not target_endpoint:
                raise ExchangeException("No se encontró endpoint para el receptor")

            # Enviar sobre
            result = self._send_envelope_data(envelope, target_endpoint)

            # Actualizar estado del sobre
            if result.get('success', False):
                envelope.mark_as_sent()
            else:
                envelope.status = 'error'

            return result

        except Exception as e:
            envelope.status = 'error'
            raise ExchangeException(f"Error enviando sobre: {str(e)}")

    def send_bag(
        self,
        bag: ExchangeBag,
        sender: Sender,
        receiver: Receiver,
        endpoint: Optional[PartyEndpoint] = None
    ) -> Dict[str, Any]:
        """
        Envía una bolsa con múltiples sobres.

        Args:
            bag: Bolsa a enviar
            sender: Entidad emisor
            receiver: Entidad receptor
            endpoint: Endpoint del receptor (opcional)

        Returns:
            Resultado del envío

        Raises:
            ExchangeException: Si hay error en el envío
        """
        try:
            # Validar compatibilidad
            self._validate_bag_compatibility(bag, sender, receiver)

            # Sellar bolsa si está en borrador
            if bag.is_draft():
                if not bag.seal():
                    raise ExchangeException("No se pudo sellar la bolsa")

            # Obtener endpoint
            target_endpoint = endpoint or self._get_default_endpoint(receiver)
            if not target_endpoint:
                raise ExchangeException("No se encontró endpoint para el receptor")

            # Enviar bolsa en lotes
            results = []
            batches = bag.get_processing_batches()

            for i, batch in enumerate(batches):
                batch_result = self._send_envelope_batch(batch, target_endpoint, i + 1, len(batches))
                results.append(batch_result)

            # Compilar resultado final
            success_count = sum(1 for r in results if r.get('success', False))
            total_count = len(results)

            result = {
                'success': success_count == total_count,
                'batches_sent': success_count,
                'total_batches': total_count,
                'results': results
            }

            # Actualizar estado de la bolsa
            if result['success']:
                bag.mark_as_sent()
            else:
                bag.status = 'error'

            return result

        except Exception as e:
            bag.status = 'error'
            raise ExchangeException(f"Error enviando bolsa: {str(e)}")

    def receive_document(
        self,
        document_data: Dict[str, Any],
        receiver: Receiver
    ) -> ExchangeDocument:
        """
        Recibe y procesa un documento.

        Args:
            document_data: Datos del documento recibido
            receiver: Entidad receptor

        Returns:
            Documento procesado

        Raises:
            ExchangeException: Si hay error en la recepción
        """
        try:
            # Crear documento de intercambio
            document = self._create_document_from_data(document_data, receiver)

            # Validar documento
            if not self._validate_received_document(document, receiver):
                document.mark_as_rejected("Documento no válido")
                return document

            # Marcar como recibido
            document.mark_as_received()

            # Auto-aceptar si está configurado
            if receiver.should_auto_accept():
                document.mark_as_accepted()

            return document

        except Exception as e:
            raise ExchangeException(f"Error recibiendo documento: {str(e)}")

    def _validate_document_compatibility(
        self,
        document: ExchangeDocument,
        sender: Sender,
        receiver: Receiver
    ):
        """Valida la compatibilidad entre documento, emisor y receptor."""
        if document.document_type != sender.document_type:
            raise ExchangeException("Tipo de documento no coincide con el emisor")

        if document.document_type != receiver.document_type:
            raise ExchangeException("Tipo de documento no coincide con el receptor")

        if document.sender_rut != sender.get_rut():
            raise ExchangeException("RUT emisor no coincide")

        if document.receiver_rut != receiver.get_rut():
            raise ExchangeException("RUT receptor no coincide")

    def _validate_envelope_compatibility(
        self,
        envelope: Envelope,
        sender: Sender,
        receiver: Receiver
    ):
        """Valida la compatibilidad entre sobre, emisor y receptor."""
        if envelope.document_type != sender.document_type:
            raise ExchangeException("Tipo de documento del sobre no coincide con el emisor")

        if envelope.sender_rut != sender.get_rut():
            raise ExchangeException("RUT emisor del sobre no coincide")

        if envelope.receiver_rut != receiver.get_rut():
            raise ExchangeException("RUT receptor del sobre no coincide")

    def _validate_bag_compatibility(
        self,
        bag: ExchangeBag,
        sender: Sender,
        receiver: Receiver
    ):
        """Valida la compatibilidad entre bolsa, emisor y receptor."""
        if bag.sender_rut != sender.get_rut():
            raise ExchangeException("RUT emisor de la bolsa no coincide")

        if bag.receiver_rut != receiver.get_rut():
            raise ExchangeException("RUT receptor de la bolsa no coincide")

    def _prepare_document_for_sending(self, document: ExchangeDocument, sender: Sender):
        """Prepara un documento para envío."""
        # Obtener contenido XML si no está disponible
        if not document.get_xml_content():
            if hasattr(document.document, 'save_xml'):
                xml_content = document.document.save_xml()
                document.set_xml_content(xml_content)

        # Firmar documento si el emisor puede firmar
        if sender.can_sign() and not document.has_digital_signature():
            signature = self._sign_document(document, sender)
            document.set_digital_signature(signature)

    def _get_default_endpoint(self, receiver: Receiver) -> Optional[PartyEndpoint]:
        """Obtiene el endpoint por defecto para un receptor."""
        if receiver.endpoint_url:
            return PartyEndpoint(
                contribuyente=receiver.contribuyente,
                endpoint_url=receiver.endpoint_url,
                timeout=self._default_timeout,
                retry_attempts=self._default_retries
            )
        return None

    def _send_single_document(
        self,
        document: ExchangeDocument,
        endpoint: PartyEndpoint
    ) -> Dict[str, Any]:
        """Envía un documento individual a un endpoint."""
        try:
            # Preparar datos para envío
            payload = {
                'document_id': document.get_id(),
                'document_type': document.get_document_type_id(),
                'sender_rut': document.get_sender_rut(),
                'receiver_rut': document.get_receiver_rut(),
                'xml_content': document.get_xml_content(),
                'digital_signature': document.digital_signature,
                'metadata': document.metadata
            }

            # Configurar headers
            headers = endpoint.get_auth_headers()
            headers.update({
                'Content-Type': 'application/json',
                'User-Agent': 'rypsystems-dte/1.0'
            })

            # Realizar request
            response = self._session.post(
                endpoint.endpoint_url,
                json=payload,
                headers=headers,
                timeout=endpoint.timeout
            )

            # Actualizar última conexión
            endpoint.update_last_connection()

            # Procesar respuesta
            if response.status_code == 200:
                return {
                    'success': True,
                    'response': response.json() if response.content else {},
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}",
                    'status_code': response.status_code
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Timeout de conexión',
                'status_code': 0
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Error de conexión',
                'status_code': 0
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Error inesperado: {str(e)}",
                'status_code': 0
            }

    def _send_envelope_data(
        self,
        envelope: Envelope,
        endpoint: PartyEndpoint
    ) -> Dict[str, Any]:
        """Envía los datos de un sobre a un endpoint."""
        try:
            # Preparar datos del sobre
            payload = {
                'envelope_id': envelope.get_id(),
                'document_type': envelope.document_type.get_id(),
                'process_type': envelope.process_type.get_id(),
                'sender_rut': envelope.get_sender_rut(),
                'receiver_rut': envelope.get_receiver_rut(),
                'document_count': envelope.get_document_count(),
                'documents': [doc.to_dict() for doc in envelope.documents],
                'checksum': envelope.checksum,
                'metadata': envelope.metadata
            }

            # Configurar headers
            headers = endpoint.get_auth_headers()
            headers.update({
                'Content-Type': 'application/json',
                'User-Agent': 'rypsystems-dte/1.0'
            })

            # Realizar request
            response = self._session.post(
                f"{endpoint.endpoint_url}/envelope",
                json=payload,
                headers=headers,
                timeout=endpoint.timeout
            )

            # Actualizar última conexión
            endpoint.update_last_connection()

            # Procesar respuesta
            if response.status_code == 200:
                return {
                    'success': True,
                    'response': response.json() if response.content else {},
                    'envelope_id': envelope.get_id()
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}",
                    'envelope_id': envelope.get_id()
                }

        except Exception as e:
            return {
                'success': False,
                'error': f"Error enviando sobre: {str(e)}",
                'envelope_id': envelope.get_id()
            }

    def _send_envelope_batch(
        self,
        envelopes: List[Envelope],
        endpoint: PartyEndpoint,
        batch_number: int,
        total_batches: int
    ) -> Dict[str, Any]:
        """Envía un lote de sobres."""
        try:
            results = []
            for envelope in envelopes:
                result = self._send_envelope_data(envelope, endpoint)
                results.append(result)

                # Pequeña pausa entre envíos
                time.sleep(0.1)

            success_count = sum(1 for r in results if r.get('success', False))

            return {
                'success': success_count == len(envelopes),
                'batch_number': batch_number,
                'total_batches': total_batches,
                'envelopes_sent': success_count,
                'total_envelopes': len(envelopes),
                'results': results
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"Error enviando lote {batch_number}: {str(e)}",
                'batch_number': batch_number,
                'total_batches': total_batches
            }

    def _create_document_from_data(
        self,
        document_data: Dict[str, Any],
        receiver: Receiver
    ) -> ExchangeDocument:
        """Crea un documento de intercambio a partir de datos recibidos."""
        return self.factory.create_exchange_document(
            document=document_data.get('document', {}),
            document_type=receiver.document_type,
            sender_rut=document_data.get('sender_rut', ''),
            receiver_rut=receiver.get_rut(),
            document_id=document_data.get('document_id', ''),
            **document_data.get('metadata', {})
        )

    def _validate_received_document(
        self,
        document: ExchangeDocument,
        receiver: Receiver
    ) -> bool:
        """Valida un documento recibido."""
        # Validar tipo de documento
        if not receiver.accepts_document_type(document.document_type):
            return False

        # Validar RUT receptor
        if document.receiver_rut != receiver.get_rut():
            return False

        # Validar que no esté expirado
        if document.is_expired():
            return False

        return True

    def _sign_document(self, document: ExchangeDocument, sender: Sender) -> str:
        """
        Firma un documento (implementación placeholder).

        Args:
            document: Documento a firmar
            sender: Emisor con certificado

        Returns:
            Firma digital
        """
        # TODO: Implementar firma digital real
        import hashlib
        content = document.get_xml_content() or document.get_id()
        return hashlib.sha256(content.encode()).hexdigest()

    def close(self):
        """Cierra el servicio y libera recursos."""
        if self._session:
            self._session.close()