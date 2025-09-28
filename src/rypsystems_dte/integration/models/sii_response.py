"""
SII Response models.

Pydantic models for handling responses from Chilean SII web services.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class SiiDocumentState(str, Enum):
    """Possible states of a document in SII."""

    PENDING = "pending"           # Enviado, esperando procesamiento
    ACCEPTED = "accepted"         # Aceptado por SII
    REJECTED = "rejected"         # Rechazado por SII
    PROCESSED = "processed"       # Procesado exitosamente
    ERROR = "error"              # Error en procesamiento
    TIMEOUT = "timeout"          # Timeout en procesamiento
    UNKNOWN = "unknown"          # Estado desconocido


class SiiDocumentStatus(BaseModel):
    """Status information for a single document in SII."""

    document_id: str = Field(..., description="ID del documento")
    folio: int = Field(..., description="Folio del documento")
    document_type: int = Field(..., description="Tipo de documento (código SII)")
    rut_emisor: str = Field(..., description="RUT del emisor")
    state: SiiDocumentState = Field(..., description="Estado actual del documento")

    # SII tracking information
    sii_track_id: Optional[str] = Field(None, description="ID de seguimiento SII")
    submission_date: Optional[datetime] = Field(None, description="Fecha de envío")
    processing_date: Optional[datetime] = Field(None, description="Fecha de procesamiento")

    # Validation and error information
    validation_errors: List[str] = Field(default_factory=list, description="Errores de validación")
    warnings: List[str] = Field(default_factory=list, description="Advertencias")
    business_errors: List[str] = Field(default_factory=list, description="Errores de negocio")

    # Additional SII response data
    sii_response_code: Optional[str] = Field(None, description="Código de respuesta SII")
    sii_response_message: Optional[str] = Field(None, description="Mensaje de respuesta SII")

    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )

    def is_accepted(self) -> bool:
        """Verifica si el documento fue aceptado por SII."""
        return self.state == SiiDocumentState.ACCEPTED

    def is_rejected(self) -> bool:
        """Verifica si el documento fue rechazado por SII."""
        return self.state == SiiDocumentState.REJECTED

    def has_errors(self) -> bool:
        """Verifica si el documento tiene errores."""
        return bool(self.validation_errors or self.business_errors) or self.state == SiiDocumentState.ERROR

    def has_warnings(self) -> bool:
        """Verifica si el documento tiene advertencias."""
        return bool(self.warnings)

    def get_all_errors(self) -> List[str]:
        """Obtiene todos los errores (validación + negocio)."""
        return self.validation_errors + self.business_errors


class SiiResponse(BaseModel):
    """Response from SII web service operations."""

    success: bool = Field(..., description="Si la operación fue exitosa")
    operation: str = Field(..., description="Tipo de operación realizada")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp de la respuesta")

    # Response metadata
    request_id: Optional[str] = Field(None, description="ID de la petición")
    session_id: Optional[str] = Field(None, description="ID de sesión SII")

    # Document statuses (for batch operations)
    document_statuses: List[SiiDocumentStatus] = Field(
        default_factory=list,
        description="Estados de documentos procesados"
    )

    # General response information
    message: Optional[str] = Field(None, description="Mensaje de respuesta")
    error_code: Optional[str] = Field(None, description="Código de error (si aplica)")
    warnings: List[str] = Field(default_factory=list, description="Advertencias generales")

    # Raw SII response for debugging
    raw_response: Optional[Dict[str, Any]] = Field(None, description="Respuesta raw del SII")

    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )

    def get_document_status(self, document_id: str) -> Optional[SiiDocumentStatus]:
        """Obtiene el estado de un documento específico."""
        for status in self.document_statuses:
            if status.document_id == document_id:
                return status
        return None

    def get_accepted_documents(self) -> List[SiiDocumentStatus]:
        """Obtiene todos los documentos aceptados."""
        return [status for status in self.document_statuses if status.is_accepted()]

    def get_rejected_documents(self) -> List[SiiDocumentStatus]:
        """Obtiene todos los documentos rechazados."""
        return [status for status in self.document_statuses if status.is_rejected()]

    def get_documents_with_errors(self) -> List[SiiDocumentStatus]:
        """Obtiene todos los documentos con errores."""
        return [status for status in self.document_statuses if status.has_errors()]

    def has_any_errors(self) -> bool:
        """Verifica si hay algún error en la respuesta."""
        return not self.success or bool(self.error_code) or any(status.has_errors() for status in self.document_statuses)

    def get_summary(self) -> Dict[str, int]:
        """Obtiene un resumen de estados de documentos."""
        summary = {
            "total": len(self.document_statuses),
            "accepted": len(self.get_accepted_documents()),
            "rejected": len(self.get_rejected_documents()),
            "with_errors": len(self.get_documents_with_errors()),
            "with_warnings": len([s for s in self.document_statuses if s.has_warnings()])
        }
        summary["pending"] = summary["total"] - summary["accepted"] - summary["rejected"]
        return summary