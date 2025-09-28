"""
Exchange Bag - Bolsa de intercambio para múltiples sobres

Traducción de ExchangeBag de LibreDTE PHP.
Representa una bolsa que contiene múltiples sobres para intercambio masivo.
"""

from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from pydantic import BaseModel, Field, validator
from ..enums import DocumentType, ProcessType
from .envelope import Envelope


class ExchangeBag(BaseModel):
    """
    Representa una bolsa que contiene múltiples sobres para intercambio.

    Una bolsa permite agrupar sobres de diferentes tipos de documentos
    y procesos para intercambio masivo entre contribuyentes.
    """

    bag_id: str = Field(
        ...,
        description="ID único de la bolsa",
        max_length=255
    )

    sender_rut: str = Field(
        ...,
        description="RUT del emisor de la bolsa",
        max_length=12
    )

    receiver_rut: str = Field(
        ...,
        description="RUT del receptor de la bolsa",
        max_length=12
    )

    envelopes: List[Envelope] = Field(
        default_factory=list,
        description="Lista de sobres en la bolsa"
    )

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Fecha de creación de la bolsa"
    )

    sent_at: Optional[datetime] = Field(
        None,
        description="Fecha de envío de la bolsa"
    )

    received_at: Optional[datetime] = Field(
        None,
        description="Fecha de recepción de la bolsa"
    )

    status: str = Field(
        "draft",
        description="Estado de la bolsa (draft, sealed, sent, received, processed)",
        max_length=50
    )

    priority: int = Field(
        0,
        description="Prioridad de la bolsa (0=normal, 1=alta, -1=baja)",
        ge=-1,
        le=1
    )

    batch_size: int = Field(
        100,
        description="Tamaño del lote para procesamiento",
        ge=1,
        le=1000
    )

    compression_enabled: bool = Field(
        True,
        description="Si la bolsa está comprimida"
    )

    encryption_enabled: bool = Field(
        False,
        description="Si la bolsa está encriptada"
    )

    digital_signature: Optional[str] = Field(
        None,
        description="Firma digital de la bolsa"
    )

    checksum: Optional[str] = Field(
        None,
        description="Checksum del contenido de la bolsa"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos adicionales de la bolsa"
    )

    @validator('status')
    def validate_status(cls, v):
        """Valida el estado de la bolsa."""
        valid_statuses = ['draft', 'sealed', 'sent', 'received', 'processed', 'error']
        if v.lower() not in valid_statuses:
            raise ValueError(f"status debe ser uno de: {', '.join(valid_statuses)}")
        return v.lower()

    @validator('sender_rut', 'receiver_rut')
    def validate_rut(cls, v):
        """Valida el formato del RUT."""
        from ...sii.utils import RutValidator
        if not RutValidator.validate(v):
            raise ValueError(f"RUT inválido: {v}")
        return RutValidator.format(v)

    @validator('envelopes')
    def validate_envelopes_consistency(cls, v, values):
        """Valida que todos los sobres tengan el mismo emisor y receptor."""
        if not v:
            return v

        sender_rut = values.get('sender_rut')
        receiver_rut = values.get('receiver_rut')

        if sender_rut and receiver_rut:
            for envelope in v:
                if envelope.sender_rut != sender_rut:
                    raise ValueError(
                        f"Todos los sobres deben tener el mismo emisor: {sender_rut}"
                    )
                if envelope.receiver_rut != receiver_rut:
                    raise ValueError(
                        f"Todos los sobres deben tener el mismo receptor: {receiver_rut}"
                    )

        return v

    def get_id(self) -> str:
        """
        Obtiene el ID único de la bolsa.

        Returns:
            ID único de la bolsa
        """
        return self.bag_id

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

    def get_envelope_count(self) -> int:
        """
        Obtiene la cantidad de sobres en la bolsa.

        Returns:
            Número de sobres
        """
        return len(self.envelopes)

    def get_total_document_count(self) -> int:
        """
        Obtiene la cantidad total de documentos en todos los sobres.

        Returns:
            Número total de documentos
        """
        return sum(envelope.get_document_count() for envelope in self.envelopes)

    def is_empty(self) -> bool:
        """
        Verifica si la bolsa está vacía.

        Returns:
            True si está vacía, False en caso contrario
        """
        return len(self.envelopes) == 0

    def is_draft(self) -> bool:
        """
        Verifica si la bolsa está en estado borrador.

        Returns:
            True si está en borrador, False en caso contrario
        """
        return self.status == 'draft'

    def is_sealed(self) -> bool:
        """
        Verifica si la bolsa está sellada.

        Returns:
            True si está sellada, False en caso contrario
        """
        return self.status == 'sealed'

    def is_sent(self) -> bool:
        """
        Verifica si la bolsa ha sido enviada.

        Returns:
            True si ha sido enviada, False en caso contrario
        """
        return self.status == 'sent'

    def is_received(self) -> bool:
        """
        Verifica si la bolsa ha sido recibida.

        Returns:
            True si ha sido recibida, False en caso contrario
        """
        return self.status == 'received'

    def is_processed(self) -> bool:
        """
        Verifica si la bolsa ha sido procesada.

        Returns:
            True si ha sido procesada, False en caso contrario
        """
        return self.status == 'processed'

    def can_add_envelope(self, envelope: Envelope) -> bool:
        """
        Verifica si se puede agregar un sobre a la bolsa.

        Args:
            envelope: Sobre a agregar

        Returns:
            True si se puede agregar, False en caso contrario
        """
        if not self.is_draft():
            return False

        if envelope.sender_rut != self.sender_rut:
            return False

        if envelope.receiver_rut != self.receiver_rut:
            return False

        # Verificar que el sobre no esté ya en la bolsa
        for existing_envelope in self.envelopes:
            if existing_envelope.get_id() == envelope.get_id():
                return False

        return True

    def add_envelope(self, envelope: Envelope) -> bool:
        """
        Agrega un sobre a la bolsa.

        Args:
            envelope: Sobre a agregar

        Returns:
            True si se agregó exitosamente, False en caso contrario
        """
        if not self.can_add_envelope(envelope):
            return False

        self.envelopes.append(envelope)
        return True

    def remove_envelope(self, envelope_id: str) -> bool:
        """
        Remueve un sobre de la bolsa.

        Args:
            envelope_id: ID del sobre a remover

        Returns:
            True si se removió exitosamente, False en caso contrario
        """
        if not self.is_draft():
            return False

        for i, envelope in enumerate(self.envelopes):
            if envelope.get_id() == envelope_id:
                del self.envelopes[i]
                return True

        return False

    def get_envelope(self, envelope_id: str) -> Optional[Envelope]:
        """
        Obtiene un sobre por su ID.

        Args:
            envelope_id: ID del sobre

        Returns:
            Sobre encontrado o None si no existe
        """
        for envelope in self.envelopes:
            if envelope.get_id() == envelope_id:
                return envelope
        return None

    def get_document_types(self) -> Set[DocumentType]:
        """
        Obtiene los tipos de documentos únicos en la bolsa.

        Returns:
            Set con los tipos de documentos
        """
        document_types = set()
        for envelope in self.envelopes:
            document_types.add(envelope.document_type)
        return document_types

    def get_process_types(self) -> Set[ProcessType]:
        """
        Obtiene los tipos de procesos únicos en la bolsa.

        Returns:
            Set con los tipos de procesos
        """
        process_types = set()
        for envelope in self.envelopes:
            process_types.add(envelope.process_type)
        return process_types

    def get_envelopes_by_document_type(self, document_type: DocumentType) -> List[Envelope]:
        """
        Obtiene los sobres de un tipo de documento específico.

        Args:
            document_type: Tipo de documento

        Returns:
            Lista de sobres del tipo especificado
        """
        return [env for env in self.envelopes if env.document_type == document_type]

    def get_envelopes_by_process_type(self, process_type: ProcessType) -> List[Envelope]:
        """
        Obtiene los sobres de un tipo de proceso específico.

        Args:
            process_type: Tipo de proceso

        Returns:
            Lista de sobres del tipo especificado
        """
        return [env for env in self.envelopes if env.process_type == process_type]

    def seal(self) -> bool:
        """
        Sella la bolsa para preparar para envío.

        Returns:
            True si se selló exitosamente, False en caso contrario
        """
        if not self.is_draft() or self.is_empty():
            return False

        # Sellar todos los sobres primero
        for envelope in self.envelopes:
            if not envelope.seal():
                return False

        # Calcular checksum del contenido
        self._calculate_checksum()

        # Cambiar estado a sellado
        self.status = 'sealed'
        return True

    def mark_as_sent(self):
        """Marca la bolsa como enviada."""
        if self.is_sealed():
            self.status = 'sent'
            self.sent_at = datetime.now()

    def mark_as_received(self):
        """Marca la bolsa como recibida."""
        if self.is_sent():
            self.status = 'received'
            self.received_at = datetime.now()

    def mark_as_processed(self):
        """Marca la bolsa como procesada."""
        if self.is_received():
            self.status = 'processed'

    def set_digital_signature(self, signature: str):
        """
        Establece la firma digital de la bolsa.

        Args:
            signature: Firma digital
        """
        self.digital_signature = signature

    def has_digital_signature(self) -> bool:
        """
        Verifica si la bolsa tiene firma digital.

        Returns:
            True si tiene firma digital, False en caso contrario
        """
        return bool(self.digital_signature)

    def _calculate_checksum(self):
        """Calcula el checksum del contenido de la bolsa."""
        import hashlib

        content = ""
        for envelope in self.envelopes:
            if envelope.checksum:
                content += envelope.checksum

        if content:
            self.checksum = hashlib.sha256(content.encode()).hexdigest()

    def verify_checksum(self) -> bool:
        """
        Verifica la integridad de la bolsa mediante checksum.

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
        Obtiene el tamaño total del contenido de la bolsa en bytes.

        Returns:
            Tamaño total en bytes
        """
        return sum(envelope.get_total_size() for envelope in self.envelopes)

    def get_processing_batches(self) -> List[List[Envelope]]:
        """
        Divide los sobres en lotes para procesamiento.

        Returns:
            Lista de lotes, cada uno con una lista de sobres
        """
        batches = []
        for i in range(0, len(self.envelopes), self.batch_size):
            batch = self.envelopes[i:i + self.batch_size]
            batches.append(batch)
        return batches

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte la bolsa a diccionario.

        Returns:
            Diccionario con los datos de la bolsa
        """
        return {
            'bag_id': self.bag_id,
            'sender_rut': self.sender_rut,
            'receiver_rut': self.receiver_rut,
            'envelope_count': self.get_envelope_count(),
            'total_document_count': self.get_total_document_count(),
            'document_types': [dt.name for dt in self.get_document_types()],
            'process_types': [pt.name for pt in self.get_process_types()],
            'status': self.status,
            'priority': self.priority,
            'batch_size': self.batch_size,
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

    class Config:
        """Configuración de Pydantic."""
        arbitrary_types_allowed = True
        validate_assignment = True