"""
Receiver Entity - Entidad receptor del intercambio

Traducción de Receiver de LibreDTE PHP.
Representa al receptor en un intercambio de documentos tributarios electrónicos.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from ..enums import DocumentType, ProcessType
from ...sii.base import Contribuyente


class Receiver(BaseModel):
    """
    Entidad que representa al receptor en un intercambio de documentos.

    Permite configurar la información del contribuyente que recibe documentos
    y los parámetros del intercambio.
    """

    contribuyente: Contribuyente = Field(
        ...,
        description="Contribuyente receptor del intercambio"
    )

    document_type: DocumentType = Field(
        ...,
        description="Tipo de documento a recibir"
    )

    process_type: ProcessType = Field(
        ...,
        description="Tipo de proceso comercial"
    )

    endpoint_url: Optional[str] = Field(
        None,
        description="URL del endpoint para recibir el intercambio",
        max_length=255
    )

    notification_email: Optional[str] = Field(
        None,
        description="Email para notificaciones",
        max_length=255
    )

    auto_accept: bool = Field(
        False,
        description="Aceptar documentos automáticamente"
    )

    extra_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parámetros adicionales del intercambio"
    )

    @validator('document_type', 'process_type')
    def validate_types(cls, v, values, field):
        """Valida que los tipos sean instancias correctas de los enums."""
        if field.name == 'document_type' and not isinstance(v, DocumentType):
            raise ValueError("document_type debe ser una instancia de DocumentType")
        if field.name == 'process_type' and not isinstance(v, ProcessType):
            raise ValueError("process_type debe ser una instancia de ProcessType")
        return v

    @validator('process_type')
    def validate_document_process_compatibility(cls, v, values):
        """Valida que el tipo de documento sea válido para el proceso."""
        if 'document_type' in values:
            document_type = values['document_type']
            if not document_type.is_valid_for_process(v):
                raise ValueError(
                    f"El tipo de documento {document_type.name} no es válido "
                    f"para el proceso {v.name}"
                )
        return v

    @validator('notification_email')
    def validate_email(cls, v):
        """Valida el formato del email de notificación."""
        if v is not None:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError("notification_email debe tener un formato válido")
        return v

    def get_id(self) -> str:
        """
        Obtiene el ID único del receptor.

        Returns:
            ID único del receptor basado en RUT y tipo de documento
        """
        return f"{self.contribuyente.get_rut()}_{self.document_type.get_id()}"

    def get_rut(self) -> str:
        """
        Obtiene el RUT del contribuyente receptor.

        Returns:
            RUT del contribuyente receptor
        """
        return self.contribuyente.get_rut()

    def get_name(self) -> str:
        """
        Obtiene el nombre del contribuyente receptor.

        Returns:
            Nombre del contribuyente receptor
        """
        return self.contribuyente.razon_social

    def get_document_type_id(self) -> str:
        """
        Obtiene el ID del tipo de documento.

        Returns:
            ID del tipo de documento
        """
        return self.document_type.get_id()

    def get_process_type_id(self) -> str:
        """
        Obtiene el ID del tipo de proceso.

        Returns:
            ID del tipo de proceso
        """
        return self.process_type.get_id()

    def accepts_document_type(self, document_type: DocumentType) -> bool:
        """
        Verifica si el receptor acepta un tipo de documento específico.

        Args:
            document_type: Tipo de documento a verificar

        Returns:
            True si acepta el tipo de documento, False en caso contrario
        """
        return document_type == self.document_type

    def accepts_process_type(self, process_type: ProcessType) -> bool:
        """
        Verifica si el receptor acepta un tipo de proceso específico.

        Args:
            process_type: Tipo de proceso a verificar

        Returns:
            True si acepta el tipo de proceso, False en caso contrario
        """
        return process_type == self.process_type

    def should_auto_accept(self) -> bool:
        """
        Verifica si el receptor acepta documentos automáticamente.

        Returns:
            True si acepta automáticamente, False en caso contrario
        """
        return self.auto_accept

    def has_notification_email(self) -> bool:
        """
        Verifica si el receptor tiene email de notificación configurado.

        Returns:
            True si tiene email configurado, False en caso contrario
        """
        return bool(self.notification_email)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte la entidad a diccionario.

        Returns:
            Diccionario con los datos del receptor
        """
        return {
            'rut': self.get_rut(),
            'name': self.get_name(),
            'document_type': self.get_document_type_id(),
            'process_type': self.get_process_type_id(),
            'endpoint_url': self.endpoint_url,
            'notification_email': self.notification_email,
            'auto_accept': self.auto_accept,
            'extra_params': self.extra_params
        }

    class Config:
        """Configuración de Pydantic."""
        arbitrary_types_allowed = True
        validate_assignment = True