"""
Exchange Document - Documento para intercambio

Traducción de Document de LibreDTE PHP.
Representa un documento que puede ser intercambiado entre contribuyentes.
"""

from typing import Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from ..enums import DocumentType
from ...dte.document import BaseDocument


class ExchangeDocument(BaseModel):
    """
    Representa un documento que puede ser intercambiado.

    Encapsula la información necesaria para el intercambio de un documento
    tributario electrónico entre contribuyentes.
    """

    document: Union[BaseDocument, Dict[str, Any]] = Field(
        ...,
        description="Documento base o datos del documento"
    )

    document_type: DocumentType = Field(
        ...,
        description="Tipo de documento"
    )

    document_id: str = Field(
        ...,
        description="ID único del documento",
        max_length=255
    )

    sender_rut: str = Field(
        ...,
        description="RUT del emisor",
        max_length=12
    )

    receiver_rut: str = Field(
        ...,
        description="RUT del receptor",
        max_length=12
    )

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Fecha de creación del documento"
    )

    expires_at: Optional[datetime] = Field(
        None,
        description="Fecha de expiración del documento"
    )

    status: str = Field(
        "draft",
        description="Estado del documento (draft, sent, received, accepted, rejected)",
        max_length=50
    )

    priority: int = Field(
        0,
        description="Prioridad del documento (0=normal, 1=alta, -1=baja)",
        ge=-1,
        le=1
    )

    retry_count: int = Field(
        0,
        description="Número de reintentos de envío",
        ge=0
    )

    max_retries: int = Field(
        3,
        description="Número máximo de reintentos",
        ge=0,
        le=10
    )

    error_message: Optional[str] = Field(
        None,
        description="Mensaje de error en caso de fallo",
        max_length=1000
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos adicionales del documento"
    )

    xml_content: Optional[str] = Field(
        None,
        description="Contenido XML del documento"
    )

    digital_signature: Optional[str] = Field(
        None,
        description="Firma digital del documento"
    )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """Valida el estado del documento."""
        valid_statuses = ['draft', 'pending', 'sent', 'received', 'accepted', 'rejected', 'error']
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

    def get_id(self) -> str:
        """
        Obtiene el ID único del documento.

        Returns:
            ID único del documento
        """
        return self.document_id

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

    def get_document_type_id(self) -> str:
        """
        Obtiene el ID del tipo de documento.

        Returns:
            ID del tipo de documento
        """
        return self.document_type.get_id()

    def get_xml_content(self) -> Optional[str]:
        """
        Obtiene el contenido XML del documento.

        Returns:
            Contenido XML del documento o None si no está disponible
        """
        if self.xml_content:
            return self.xml_content

        # Si es un BaseDocument, obtener el XML
        if isinstance(self.document, BaseDocument):
            return self.document.save_xml()

        return None

    def set_xml_content(self, xml_content: str):
        """
        Establece el contenido XML del documento.

        Args:
            xml_content: Contenido XML del documento
        """
        self.xml_content = xml_content

    def is_draft(self) -> bool:
        """
        Verifica si el documento está en estado borrador.

        Returns:
            True si está en borrador, False en caso contrario
        """
        return self.status == 'draft'

    def is_sent(self) -> bool:
        """
        Verifica si el documento ha sido enviado.

        Returns:
            True si ha sido enviado, False en caso contrario
        """
        return self.status == 'sent'

    def is_received(self) -> bool:
        """
        Verifica si el documento ha sido recibido.

        Returns:
            True si ha sido recibido, False en caso contrario
        """
        return self.status == 'received'

    def is_accepted(self) -> bool:
        """
        Verifica si el documento ha sido aceptado.

        Returns:
            True si ha sido aceptado, False en caso contrario
        """
        return self.status == 'accepted'

    def is_rejected(self) -> bool:
        """
        Verifica si el documento ha sido rechazado.

        Returns:
            True si ha sido rechazado, False en caso contrario
        """
        return self.status == 'rejected'

    def has_error(self) -> bool:
        """
        Verifica si el documento tiene error.

        Returns:
            True si tiene error, False en caso contrario
        """
        return self.status == 'error' or bool(self.error_message)

    def is_expired(self) -> bool:
        """
        Verifica si el documento ha expirado.

        Returns:
            True si ha expirado, False en caso contrario
        """
        return self.expires_at is not None and datetime.now() > self.expires_at

    def can_retry(self) -> bool:
        """
        Verifica si el documento puede ser reintentado.

        Returns:
            True si puede ser reintentado, False en caso contrario
        """
        return (
            self.retry_count < self.max_retries and
            not self.is_accepted() and
            not self.is_expired()
        )

    def mark_as_sent(self):
        """Marca el documento como enviado."""
        self.status = 'sent'

    def mark_as_received(self):
        """Marca el documento como recibido."""
        self.status = 'received'

    def mark_as_accepted(self):
        """Marca el documento como aceptado."""
        self.status = 'accepted'

    def mark_as_rejected(self, error_message: Optional[str] = None):
        """
        Marca el documento como rechazado.

        Args:
            error_message: Mensaje de error opcional
        """
        self.status = 'rejected'
        if error_message:
            self.error_message = error_message

    def mark_as_error(self, error_message: str):
        """
        Marca el documento con error.

        Args:
            error_message: Mensaje de error
        """
        self.status = 'error'
        self.error_message = error_message

    def increment_retry_count(self):
        """Incrementa el contador de reintentos."""
        self.retry_count += 1

    def set_digital_signature(self, signature: str):
        """
        Establece la firma digital del documento.

        Args:
            signature: Firma digital
        """
        self.digital_signature = signature

    def has_digital_signature(self) -> bool:
        """
        Verifica si el documento tiene firma digital.

        Returns:
            True si tiene firma digital, False en caso contrario
        """
        return bool(self.digital_signature)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el documento a diccionario.

        Returns:
            Diccionario con los datos del documento
        """
        return {
            'document_id': self.document_id,
            'document_type': self.get_document_type_id(),
            'sender_rut': self.sender_rut,
            'receiver_rut': self.receiver_rut,
            'status': self.status,
            'priority': self.priority,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'error_message': self.error_message,
            'has_signature': self.has_digital_signature(),
            'metadata': self.metadata
        }

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )