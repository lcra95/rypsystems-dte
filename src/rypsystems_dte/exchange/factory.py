"""
Exchange Factory - Fábrica para crear elementos del intercambio

Traducción de Factory de LibreDTE PHP.
Proporciona métodos para crear documentos, sobres y bolsas de intercambio.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
import uuid

from .enums import DocumentType, ProcessType
from .entities import Sender, Receiver, PartyEndpoint
from .support import ExchangeDocument, Envelope, ExchangeBag
from .exceptions import ExchangeException
from ..sii.base import Contribuyente
from ..dte.document import BaseDocument


class ExchangeFactory:
    """
    Fábrica para crear elementos del sistema de intercambio.

    Proporciona métodos de conveniencia para crear documentos, sobres
    y bolsas de intercambio con configuraciones predeterminadas.
    """

    def __init__(self):
        """Inicializa la fábrica de intercambio."""
        self._document_counter = 0
        self._envelope_counter = 0
        self._bag_counter = 0

    def create_sender(
        self,
        contribuyente: Contribuyente,
        document_type: DocumentType,
        process_type: ProcessType,
        endpoint_url: Optional[str] = None,
        certificate_path: Optional[str] = None,
        private_key_path: Optional[str] = None,
        **extra_params
    ) -> Sender:
        """
        Crea una entidad emisor.

        Args:
            contribuyente: Contribuyente emisor
            document_type: Tipo de documento
            process_type: Tipo de proceso
            endpoint_url: URL del endpoint (opcional)
            certificate_path: Ruta al certificado (opcional)
            private_key_path: Ruta a la clave privada (opcional)
            **extra_params: Parámetros adicionales

        Returns:
            Entidad emisor configurada

        Raises:
            ExchangeException: Si hay error en la configuración
        """
        try:
            return Sender(
                contribuyente=contribuyente,
                document_type=document_type,
                process_type=process_type,
                endpoint_url=endpoint_url,
                certificate_path=certificate_path,
                private_key_path=private_key_path,
                extra_params=extra_params
            )
        except Exception as e:
            raise ExchangeException(f"Error creando emisor: {str(e)}")

    def create_receiver(
        self,
        contribuyente: Contribuyente,
        document_type: DocumentType,
        process_type: ProcessType,
        endpoint_url: Optional[str] = None,
        notification_email: Optional[str] = None,
        auto_accept: bool = False,
        **extra_params
    ) -> Receiver:
        """
        Crea una entidad receptor.

        Args:
            contribuyente: Contribuyente receptor
            document_type: Tipo de documento
            process_type: Tipo de proceso
            endpoint_url: URL del endpoint (opcional)
            notification_email: Email de notificación (opcional)
            auto_accept: Si acepta automáticamente (opcional)
            **extra_params: Parámetros adicionales

        Returns:
            Entidad receptor configurada

        Raises:
            ExchangeException: Si hay error en la configuración
        """
        try:
            return Receiver(
                contribuyente=contribuyente,
                document_type=document_type,
                process_type=process_type,
                endpoint_url=endpoint_url,
                notification_email=notification_email,
                auto_accept=auto_accept,
                extra_params=extra_params
            )
        except Exception as e:
            raise ExchangeException(f"Error creando receptor: {str(e)}")

    def create_party_endpoint(
        self,
        contribuyente: Contribuyente,
        endpoint_url: str,
        endpoint_type: str = "rest",
        authentication_type: str = "none",
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        certificate_path: Optional[str] = None,
        private_key_path: Optional[str] = None,
        timeout: int = 30,
        retry_attempts: int = 3,
        **extra_params
    ) -> PartyEndpoint:
        """
        Crea un endpoint de participante.

        Args:
            contribuyente: Contribuyente asociado
            endpoint_url: URL del endpoint
            endpoint_type: Tipo de endpoint
            authentication_type: Tipo de autenticación
            username: Usuario (opcional)
            password: Contraseña (opcional)
            api_key: API key (opcional)
            certificate_path: Ruta al certificado (opcional)
            private_key_path: Ruta a la clave privada (opcional)
            timeout: Timeout en segundos
            retry_attempts: Intentos de reintento
            **extra_params: Parámetros adicionales

        Returns:
            Endpoint configurado

        Raises:
            ExchangeException: Si hay error en la configuración
        """
        try:
            return PartyEndpoint(
                contribuyente=contribuyente,
                endpoint_url=endpoint_url,
                endpoint_type=endpoint_type,
                authentication_type=authentication_type,
                username=username,
                password=password,
                api_key=api_key,
                certificate_path=certificate_path,
                private_key_path=private_key_path,
                timeout=timeout,
                retry_attempts=retry_attempts,
                extra_params=extra_params
            )
        except Exception as e:
            raise ExchangeException(f"Error creando endpoint: {str(e)}")

    def create_exchange_document(
        self,
        document: Union[BaseDocument, Dict[str, Any]],
        document_type: DocumentType,
        sender_rut: str,
        receiver_rut: str,
        document_id: Optional[str] = None,
        expires_hours: int = 72,
        priority: int = 0,
        max_retries: int = 3,
        **metadata
    ) -> ExchangeDocument:
        """
        Crea un documento de intercambio.

        Args:
            document: Documento base o datos del documento
            document_type: Tipo de documento
            sender_rut: RUT del emisor
            receiver_rut: RUT del receptor
            document_id: ID del documento (opcional, se genera automáticamente)
            expires_hours: Horas hasta expiración
            priority: Prioridad del documento
            max_retries: Máximo número de reintentos
            **metadata: Metadatos adicionales

        Returns:
            Documento de intercambio configurado

        Raises:
            ExchangeException: Si hay error en la configuración
        """
        try:
            if document_id is None:
                self._document_counter += 1
                document_id = f"DOC_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._document_counter:06d}"

            expires_at = datetime.now() + timedelta(hours=expires_hours) if expires_hours > 0 else None

            exchange_doc = ExchangeDocument(
                document=document,
                document_type=document_type,
                document_id=document_id,
                sender_rut=sender_rut,
                receiver_rut=receiver_rut,
                expires_at=expires_at,
                priority=priority,
                max_retries=max_retries,
                metadata=metadata
            )

            # Si es un BaseDocument, extraer el XML automáticamente
            if isinstance(document, BaseDocument):
                xml_content = document.save_xml()
                exchange_doc.set_xml_content(xml_content)

            return exchange_doc

        except Exception as e:
            raise ExchangeException(f"Error creando documento de intercambio: {str(e)}")

    def create_envelope(
        self,
        document_type: DocumentType,
        process_type: ProcessType,
        sender_rut: str,
        receiver_rut: str,
        envelope_id: Optional[str] = None,
        priority: int = 0,
        compression_enabled: bool = True,
        encryption_enabled: bool = False,
        **metadata
    ) -> Envelope:
        """
        Crea un sobre de intercambio.

        Args:
            document_type: Tipo de documentos en el sobre
            process_type: Tipo de proceso
            sender_rut: RUT del emisor
            receiver_rut: RUT del receptor
            envelope_id: ID del sobre (opcional, se genera automáticamente)
            priority: Prioridad del sobre
            compression_enabled: Si está comprimido
            encryption_enabled: Si está encriptado
            **metadata: Metadatos adicionales

        Returns:
            Sobre de intercambio configurado

        Raises:
            ExchangeException: Si hay error en la configuración
        """
        try:
            if envelope_id is None:
                self._envelope_counter += 1
                envelope_id = f"ENV_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._envelope_counter:06d}"

            return Envelope(
                envelope_id=envelope_id,
                document_type=document_type,
                process_type=process_type,
                sender_rut=sender_rut,
                receiver_rut=receiver_rut,
                priority=priority,
                compression_enabled=compression_enabled,
                encryption_enabled=encryption_enabled,
                metadata=metadata
            )

        except Exception as e:
            raise ExchangeException(f"Error creando sobre: {str(e)}")

    def create_exchange_bag(
        self,
        sender_rut: str,
        receiver_rut: str,
        bag_id: Optional[str] = None,
        priority: int = 0,
        batch_size: int = 100,
        compression_enabled: bool = True,
        encryption_enabled: bool = False,
        **metadata
    ) -> ExchangeBag:
        """
        Crea una bolsa de intercambio.

        Args:
            sender_rut: RUT del emisor
            receiver_rut: RUT del receptor
            bag_id: ID de la bolsa (opcional, se genera automáticamente)
            priority: Prioridad de la bolsa
            batch_size: Tamaño del lote
            compression_enabled: Si está comprimida
            encryption_enabled: Si está encriptada
            **metadata: Metadatos adicionales

        Returns:
            Bolsa de intercambio configurada

        Raises:
            ExchangeException: Si hay error en la configuración
        """
        try:
            if bag_id is None:
                self._bag_counter += 1
                bag_id = f"BAG_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._bag_counter:06d}"

            return ExchangeBag(
                bag_id=bag_id,
                sender_rut=sender_rut,
                receiver_rut=receiver_rut,
                priority=priority,
                batch_size=batch_size,
                compression_enabled=compression_enabled,
                encryption_enabled=encryption_enabled,
                metadata=metadata
            )

        except Exception as e:
            raise ExchangeException(f"Error creando bolsa: {str(e)}")

    def create_envelope_with_documents(
        self,
        documents: List[Union[BaseDocument, Dict[str, Any]]],
        document_type: DocumentType,
        process_type: ProcessType,
        sender_rut: str,
        receiver_rut: str,
        envelope_id: Optional[str] = None,
        expires_hours: int = 72,
        **options
    ) -> Envelope:
        """
        Crea un sobre con documentos incluidos.

        Args:
            documents: Lista de documentos a incluir
            document_type: Tipo de documentos
            process_type: Tipo de proceso
            sender_rut: RUT del emisor
            receiver_rut: RUT del receptor
            envelope_id: ID del sobre (opcional)
            expires_hours: Horas hasta expiración de documentos
            **options: Opciones adicionales

        Returns:
            Sobre con documentos incluidos

        Raises:
            ExchangeException: Si hay error en la creación
        """
        try:
            # Crear el sobre
            envelope = self.create_envelope(
                document_type=document_type,
                process_type=process_type,
                sender_rut=sender_rut,
                receiver_rut=receiver_rut,
                envelope_id=envelope_id,
                **options
            )

            # Agregar documentos al sobre
            for document in documents:
                exchange_doc = self.create_exchange_document(
                    document=document,
                    document_type=document_type,
                    sender_rut=sender_rut,
                    receiver_rut=receiver_rut,
                    expires_hours=expires_hours
                )

                if not envelope.add_document(exchange_doc):
                    raise ExchangeException(f"No se pudo agregar documento al sobre")

            return envelope

        except Exception as e:
            raise ExchangeException(f"Error creando sobre con documentos: {str(e)}")

    def create_bag_with_envelopes(
        self,
        envelopes: List[Envelope],
        sender_rut: str,
        receiver_rut: str,
        bag_id: Optional[str] = None,
        **options
    ) -> ExchangeBag:
        """
        Crea una bolsa con sobres incluidos.

        Args:
            envelopes: Lista de sobres a incluir
            sender_rut: RUT del emisor
            receiver_rut: RUT del receptor
            bag_id: ID de la bolsa (opcional)
            **options: Opciones adicionales

        Returns:
            Bolsa con sobres incluidos

        Raises:
            ExchangeException: Si hay error en la creación
        """
        try:
            # Crear la bolsa
            bag = self.create_exchange_bag(
                sender_rut=sender_rut,
                receiver_rut=receiver_rut,
                bag_id=bag_id,
                **options
            )

            # Agregar sobres a la bolsa
            for envelope in envelopes:
                if not bag.add_envelope(envelope):
                    raise ExchangeException(f"No se pudo agregar sobre {envelope.get_id()} a la bolsa")

            return bag

        except Exception as e:
            raise ExchangeException(f"Error creando bolsa con sobres: {str(e)}")

    def reset_counters(self):
        """Reinicia los contadores de la fábrica."""
        self._document_counter = 0
        self._envelope_counter = 0
        self._bag_counter = 0