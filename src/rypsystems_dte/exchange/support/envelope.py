"""
Exchange Envelope - Sobre para intercambio de documentos

Traducción de Envelope de LibreDTE PHP.
Representa un sobre que contiene uno o más documentos para intercambio.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from ..enums import DocumentType, ProcessType
from .document import ExchangeDocument


class Envelope(BaseModel):
    """
    Representa un sobre que contiene documentos para intercambio.

    Un sobre agrupa documentos del mismo tipo y proceso para ser
    intercambiados entre contribuyentes de manera eficiente.
    """

    envelope_id: str = Field(
        ...,
        description="ID único del sobre",
        max_length=255
    )

    document_type: DocumentType = Field(
        ...,
        description="Tipo de documentos en el sobre"
    )

    process_type: ProcessType = Field(
        ...,
        description="Tipo de proceso comercial"
    )

    sender_rut: str = Field(
        ...,
        description="RUT del emisor del sobre",
        max_length=12
    )

    receiver_rut: str = Field(
        ...,
        description="RUT del receptor del sobre",
        max_length=12
    )

    documents: List[ExchangeDocument] = Field(
        default_factory=list,
        description="Lista de documentos en el sobre"
    )

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Fecha de creación del sobre"
    )

    sent_at: Optional[datetime] = Field(
        None,
        description="Fecha de envío del sobre"
    )

    received_at: Optional[datetime] = Field(
        None,
        description="Fecha de recepción del sobre"
    )

    status: str = Field(
        "draft",
        description="Estado del sobre (draft, sealed, sent, received, processed)",
        max_length=50
    )

    priority: int = Field(
        0,
        description="Prioridad del sobre (0=normal, 1=alta, -1=baja)",
        ge=-1,
        le=1
    )

    compression_enabled: bool = Field(
        True,
        description="Si el sobre está comprimido"
    )

    encryption_enabled: bool = Field(
        False,
        description="Si el sobre está encriptado"
    )

    digital_signature: Optional[str] = Field(
        None,
        description="Firma digital del sobre"
    )

    checksum: Optional[str] = Field(
        None,
        description="Checksum del contenido del sobre"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos adicionales del sobre"
    )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Valida el estado del sobre."""
        valid_statuses = ['draft', 'sealed', 'sent', 'received', 'processed', 'error']
        if v.lower() not in valid_statuses:
            raise ValueError(f"status debe ser uno de: {', '.join(valid_statuses)}")
        return v.lower()

    @field_validator('sender_rut', 'receiver_rut')
    @classmethod
    def validate_rut(cls, v):
        """Valida el formato del RUT."""
        from ...sii.utils import RutValidator
        if not RutValidator.validate(v):
            raise ValueError(f"RUT inválido: {v}")
        return RutValidator.format(v)

    @model_validator(mode='after')
    def validate_documents_consistency(self):
        """Valida que todos los documentos sean del mismo tipo."""
        if not self.documents:
            return self

        for doc in self.documents:
            if doc.document_type != self.document_type:
                raise ValueError(
                    f"Todos los documentos deben ser del tipo {self.document_type.name}"
                )

        return self

    def get_id(self) -> str:
        """
        Obtiene el ID único del sobre.

        Returns:
            ID único del sobre
        """
        return self.envelope_id

    def get_sender_rut(self) -> str:
        """
        Obtiene el RUT del emisor.

        Returns:
            RUT del emisor
        """
        return self.sender_rut

    def get_receiver_rut(self) -> str:
        """
        Obtiene el RUT del receptor.

        Returns:
            RUT del receptor
        """
        return self.receiver_rut

    def get_document_count(self) -> int:
        """
        Obtiene la cantidad de documentos en el sobre.

        Returns:
            Número de documentos
        """
        return len(self.documents)

    def is_empty(self) -> bool:
        """
        Verifica si el sobre está vacío.

        Returns:
            True si está vacío, False en caso contrario
        """
        return len(self.documents) == 0

    def is_draft(self) -> bool:
        """
        Verifica si el sobre está en estado borrador.

        Returns:
            True si está en borrador, False en caso contrario
        """
        return self.status == 'draft'

    def is_sealed(self) -> bool:
        """
        Verifica si el sobre está sellado.

        Returns:
            True si está sellado, False en caso contrario
        """
        return self.status == 'sealed'

    def is_sent(self) -> bool:
        """
        Verifica si el sobre ha sido enviado.

        Returns:
            True si ha sido enviado, False en caso contrario
        """
        return self.status == 'sent'

    def is_received(self) -> bool:
        """
        Verifica si el sobre ha sido recibido.

        Returns:
            True si ha sido recibido, False en caso contrario
        """
        return self.status == 'received'

    def is_processed(self) -> bool:
        """
        Verifica si el sobre ha sido procesado.

        Returns:
            True si ha sido procesado, False en caso contrario
        """
        return self.status == 'processed'

    def can_add_document(self, document: ExchangeDocument) -> bool:
        """
        Verifica si se puede agregar un documento al sobre.

        Args:
            document: Documento a agregar

        Returns:
            True si se puede agregar, False en caso contrario
        """
        if not self.is_draft():
            return False

        if document.document_type != self.document_type:
            return False

        if document.sender_rut != self.sender_rut:
            return False

        if document.receiver_rut != self.receiver_rut:
            return False

        return True

    def add_document(self, document: ExchangeDocument) -> bool:
        """
        Agrega un documento al sobre.

        Args:
            document: Documento a agregar

        Returns:
            True si se agregó exitosamente, False en caso contrario
        """
        if not self.can_add_document(document):
            return False

        self.documents.append(document)
        return True

    def remove_document(self, document_id: str) -> bool:
        """
        Remueve un documento del sobre.

        Args:
            document_id: ID del documento a remover

        Returns:
            True si se removió exitosamente, False en caso contrario
        """
        if not self.is_draft():
            return False

        for i, doc in enumerate(self.documents):
            if doc.get_id() == document_id:
                del self.documents[i]
                return True

        return False

    def get_document(self, document_id: str) -> Optional[ExchangeDocument]:
        """
        Obtiene un documento por su ID.

        Args:
            document_id: ID del documento

        Returns:
            Documento encontrado o None si no existe
        """
        for doc in self.documents:
            if doc.get_id() == document_id:
                return doc
        return None

    def seal(self) -> bool:
        """
        Sella el sobre para prepararlo para envío.

        Returns:
            True si se selló exitosamente, False en caso contrario
        """
        if not self.is_draft() or self.is_empty():
            return False

        # Calcular checksum del contenido
        self._calculate_checksum()

        # Cambiar estado a sellado
        self.status = 'sealed'
        return True

    def mark_as_sent(self):
        """Marca el sobre como enviado."""
        if self.is_sealed():
            self.status = 'sent'
            self.sent_at = datetime.now()

    def mark_as_received(self):
        """Marca el sobre como recibido."""
        if self.is_sent():
            self.status = 'received'
            self.received_at = datetime.now()

    def mark_as_processed(self):
        """Marca el sobre como procesado."""
        if self.is_received():
            self.status = 'processed'

    def set_digital_signature(self, signature: str):
        """
        Establece la firma digital del sobre.

        Args:
            signature: Firma digital
        """
        self.digital_signature = signature

    def has_digital_signature(self) -> bool:
        """
        Verifica si el sobre tiene firma digital.

        Returns:
            True si tiene firma digital, False en caso contrario
        """
        return bool(self.digital_signature)

    def _calculate_checksum(self):
        """Calcula el checksum del contenido del sobre."""
        import hashlib

        content = ""
        for doc in self.documents:
            xml_content = doc.get_xml_content()
            if xml_content:
                content += xml_content

        if content:
            self.checksum = hashlib.sha256(content.encode()).hexdigest()

    def verify_checksum(self) -> bool:
        """
        Verifica la integridad del sobre mediante checksum.

        Returns:
            True si la verificación es exitosa, False en caso contrario
        """
        if not self.checksum:
            return False

        old_checksum = self.checksum
        self._calculate_checksum()
        return old_checksum == self.checksum

    def get_total_size(self) -> int:
        """
        Obtiene el tamaño total del contenido del sobre en bytes.

        Returns:
            Tamaño total en bytes
        """
        total_size = 0
        for doc in self.documents:
            xml_content = doc.get_xml_content()
            if xml_content:
                total_size += len(xml_content.encode('utf-8'))
        return total_size

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el sobre a diccionario.

        Returns:
            Diccionario con los datos del sobre
        """
        return {
            'envelope_id': self.envelope_id,
            'document_type': self.document_type.get_id(),
            'process_type': self.process_type.get_id(),
            'sender_rut': self.sender_rut,
            'receiver_rut': self.receiver_rut,
            'document_count': self.get_document_count(),
            'status': self.status,
            'priority': self.priority,
            'compression_enabled': self.compression_enabled,
            'encryption_enabled': self.encryption_enabled,
            'has_signature': self.has_digital_signature(),
            'total_size': self.get_total_size(),
            'created_at': self.created_at.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'received_at': self.received_at.isoformat() if self.received_at else None,
            'checksum': self.checksum,
            'metadata': self.metadata
        }

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )