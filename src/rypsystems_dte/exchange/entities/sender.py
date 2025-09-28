"""
Sender Entity - Entidad emisor del intercambio

Traducción de Sender de LibreDTE PHP.
Representa al emisor en un intercambio de documentos tributarios electrónicos.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from ..enums import DocumentType, ProcessType
from ...sii.base import Contribuyente


class Sender(BaseModel):
    """
    Entidad que representa al emisor en un intercambio de documentos.

    Permite configurar la información del contribuyente que envía documentos
    y los parámetros del intercambio.
    """

    contribuyente: Contribuyente = Field(
        ...,
        description="Contribuyente emisor del intercambio"
    )

    document_type: DocumentType = Field(
        ...,
        description="Tipo de documento a intercambiar"
    )

    process_type: ProcessType = Field(
        ...,
        description="Tipo de proceso comercial"
    )

    endpoint_url: Optional[str] = Field(
        None,
        description="URL del endpoint para el intercambio",
        max_length=255
    )

    certificate_path: Optional[str] = Field(
        None,
        description="Ruta al certificado digital",
        max_length=255
    )

    private_key_path: Optional[str] = Field(
        None,
        description="Ruta a la clave privada",
        max_length=255
    )

    extra_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parámetros adicionales del intercambio"
    )

    @field_validator('document_type')
    @classmethod
    def validate_document_type(cls, v):
        """Valida que el tipo de documento sea una instancia correcta del enum."""
        if not isinstance(v, DocumentType):
            raise ValueError("document_type debe ser una instancia de DocumentType")
        return v

    @field_validator('process_type')
    @classmethod
    def validate_process_type(cls, v):
        """Valida que el tipo de proceso sea una instancia correcta del enum."""
        if not isinstance(v, ProcessType):
            raise ValueError("process_type debe ser una instancia de ProcessType")
        return v

    @model_validator(mode='after')
    def validate_document_process_compatibility(self):
        """Valida que el tipo de documento sea válido para el proceso."""
        if not self.document_type.is_valid_for_process(self.process_type):
            raise ValueError(
                f"El tipo de documento {self.document_type.name} no es válido "
                f"para el proceso {self.process_type.name}"
            )
        return self

    def get_id(self) -> str:
        """
        Obtiene el ID único del emisor.

        Returns:
            ID único del emisor basado en RUT y tipo de documento
        """
        return f"{self.contribuyente.get_rut()}_{self.document_type.get_id()}"

    def get_rut(self) -> str:
        """
        Obtiene el RUT del contribuyente emisor.

        Returns:
            RUT del contribuyente emisor
        """
        return self.contribuyente.get_rut()

    def get_name(self) -> str:
        """
        Obtiene el nombre del contribuyente emisor.

        Returns:
            Nombre del contribuyente emisor
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

    def has_certificate(self) -> bool:
        """
        Verifica si el emisor tiene certificado configurado.

        Returns:
            True si tiene certificado configurado, False en caso contrario
        """
        return bool(self.certificate_path)

    def has_private_key(self) -> bool:
        """
        Verifica si el emisor tiene clave privada configurada.

        Returns:
            True si tiene clave privada configurada, False en caso contrario
        """
        return bool(self.private_key_path)

    def can_sign(self) -> bool:
        """
        Verifica si el emisor puede firmar documentos.

        Returns:
            True si puede firmar, False en caso contrario
        """
        return self.has_certificate() and self.has_private_key()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte la entidad a diccionario.

        Returns:
            Diccionario con los datos del emisor
        """
        return {
            'rut': self.get_rut(),
            'name': self.get_name(),
            'document_type': self.get_document_type_id(),
            'process_type': self.get_process_type_id(),
            'endpoint_url': self.endpoint_url,
            'can_sign': self.can_sign(),
            'extra_params': self.extra_params
        }

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )