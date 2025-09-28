"""
SII Request models.

Pydantic models for creating requests to Chilean SII web services.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict


class SiiOperation(str, Enum):
    """Types of operations supported by SII."""

    SUBMIT_DOCUMENT = "submit_document"
    QUERY_STATUS = "query_status"
    GET_RECEIPT = "get_receipt"
    AUTHENTICATE = "authenticate"
    VALIDATE_DOCUMENT = "validate_document"


class SiiRequest(BaseModel):
    """Base request to SII web services."""

    operation: SiiOperation = Field(..., description="Tipo de operación")
    request_id: str = Field(..., description="ID único de la petición")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp de la petición")

    # Authentication information
    rut_company: str = Field(..., description="RUT de la empresa")
    rut_sender: str = Field(..., description="RUT del emisor")

    # Optional tracking information
    session_id: Optional[str] = Field(None, description="ID de sesión")
    correlation_id: Optional[str] = Field(None, description="ID de correlación")

    model_config = ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )

    @field_validator('rut_company', 'rut_sender')
    @classmethod
    def validate_rut(cls, v):
        """Valida el formato del RUT."""
        from ...sii.utils import RutValidator
        if not RutValidator.validate(v):
            raise ValueError(f"RUT inválido: {v}")
        return RutValidator.format(v)


class SiiSubmissionRequest(SiiRequest):
    """Request for submitting documents to SII."""

    operation: SiiOperation = Field(default=SiiOperation.SUBMIT_DOCUMENT)

    # Document information
    documents: List[Dict[str, Any]] = Field(..., description="Documentos a enviar")
    envelope_xml: Optional[str] = Field(None, description="XML del sobre de documentos")

    # Submission options
    validate_only: bool = Field(False, description="Solo validar, no procesar")
    priority: int = Field(0, description="Prioridad de procesamiento (0=normal, 1=alta)")

    # File information
    file_name: Optional[str] = Field(None, description="Nombre del archivo enviado")
    file_size: Optional[int] = Field(None, description="Tamaño del archivo en bytes")

    def get_document_ids(self) -> List[str]:
        """Obtiene los IDs de los documentos en la petición."""
        return [doc.get('document_id', '') for doc in self.documents if 'document_id' in doc]

    def get_document_count(self) -> int:
        """Obtiene la cantidad de documentos en la petición."""
        return len(self.documents)


class SiiQueryRequest(SiiRequest):
    """Request for querying document status in SII."""

    operation: SiiOperation = Field(default=SiiOperation.QUERY_STATUS)

    # Query parameters
    document_ids: Optional[List[str]] = Field(None, description="IDs de documentos específicos")
    folios: Optional[List[int]] = Field(None, description="Folios de documentos")
    document_types: Optional[List[int]] = Field(None, description="Tipos de documento")

    # Date range for queries
    date_from: Optional[date] = Field(None, description="Fecha desde")
    date_to: Optional[date] = Field(None, description="Fecha hasta")

    # Tracking information
    track_ids: Optional[List[str]] = Field(None, description="IDs de seguimiento SII")
    submission_ids: Optional[List[str]] = Field(None, description="IDs de envío")

    @field_validator('date_from', 'date_to')
    @classmethod
    def validate_dates(cls, v):
        """Valida que las fechas no sean futuras."""
        if v and v > date.today():
            raise ValueError("La fecha no puede ser futura")
        return v

    def has_specific_documents(self) -> bool:
        """Verifica si la consulta es para documentos específicos."""
        return bool(self.document_ids or self.folios or self.track_ids)

    def is_date_range_query(self) -> bool:
        """Verifica si es una consulta por rango de fechas."""
        return bool(self.date_from or self.date_to)


class SiiAuthenticationRequest(SiiRequest):
    """Request for SII authentication."""

    operation: SiiOperation = Field(default=SiiOperation.AUTHENTICATE)

    # Certificate information
    certificate_content: str = Field(..., description="Contenido del certificado")
    private_key_content: str = Field(..., description="Contenido de la clave privada")

    # Optional authentication parameters
    token_duration: int = Field(3600, description="Duración del token en segundos")
    refresh_token: Optional[str] = Field(None, description="Token de renovación")

    @field_validator('token_duration')
    @classmethod
    def validate_token_duration(cls, v):
        """Valida la duración del token."""
        if v < 300 or v > 28800:  # Entre 5 minutos y 8 horas
            raise ValueError("Duración del token debe estar entre 300 y 28800 segundos")
        return v


class SiiReceiptRequest(SiiRequest):
    """Request for getting document receipt from SII."""

    operation: SiiOperation = Field(default=SiiOperation.GET_RECEIPT)

    # Receipt parameters
    track_id: str = Field(..., description="ID de seguimiento SII")
    receipt_type: str = Field("xml", description="Tipo de acuse (xml, pdf)")

    @field_validator('receipt_type')
    @classmethod
    def validate_receipt_type(cls, v):
        """Valida el tipo de acuse."""
        valid_types = ['xml', 'pdf', 'json']
        if v.lower() not in valid_types:
            raise ValueError(f"Tipo de acuse debe ser uno de: {', '.join(valid_types)}")
        return v.lower()