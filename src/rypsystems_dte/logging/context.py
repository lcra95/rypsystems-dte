"""
RypSystems DTE - Logging Context Management

Sistema de gestión de contexto para logging estructurado y seguimiento de operaciones.
Proporciona contexto thread-safe para operaciones DTE y comunicación con SII.
"""

import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field


class ContextType(str, Enum):
    """Tipos de contexto de operación"""
    OPERATION = "operation"
    REQUEST = "request"
    DOCUMENT = "document"
    VALIDATION = "validation"
    COMMUNICATION = "communication"
    BATCH = "batch"
    ERROR = "error"
    DEBUG = "debug"


class ContextScope(str, Enum):
    """Alcance del contexto"""
    GLOBAL = "global"
    SESSION = "session"
    OPERATION = "operation"
    REQUEST = "request"
    DOCUMENT = "document"


@dataclass
class ContextData:
    """Datos de contexto para logging"""
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context_type: ContextType = ContextType.OPERATION
    scope: ContextScope = ContextScope.OPERATION
    operation: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    document_id: Optional[str] = None
    correlation_id: Optional[str] = None
    parent_context_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el contexto a diccionario para logging"""
        return {
            'context_id': self.context_id,
            'context_type': self.context_type.value,
            'scope': self.scope.value,
            'operation': self.operation,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'request_id': self.request_id,
            'document_id': self.document_id,
            'correlation_id': self.correlation_id,
            'parent_context_id': self.parent_context_id,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata,
            'tags': self.tags
        }


class LoggingContext:
    """
    Gestor de contexto thread-safe para logging estructurado

    Mantiene contexto de operación para todas las operaciones de logging
    en el thread actual, proporcionando trazabilidad completa.
    """

    _local = threading.local()
    _global_context: Dict[str, Any] = {}
    _context_stack: Dict[str, List[ContextData]] = {}
    _lock = threading.RLock()

    @classmethod
    def get_current_context(cls) -> Optional[ContextData]:
        """Obtiene el contexto actual del thread"""
        if not hasattr(cls._local, 'context_stack') or not cls._local.context_stack:
            return None
        return cls._local.context_stack[-1]

    @classmethod
    def get_context_stack(cls) -> List[ContextData]:
        """Obtiene la pila completa de contextos"""
        if not hasattr(cls._local, 'context_stack'):
            cls._local.context_stack = []
        return cls._local.context_stack.copy()

    @classmethod
    def push_context(cls, context: ContextData) -> str:
        """Agrega un nuevo contexto a la pila"""
        if not hasattr(cls._local, 'context_stack'):
            cls._local.context_stack = []

        # Establecer parent_context_id si hay contexto previo
        if cls._local.context_stack:
            context.parent_context_id = cls._local.context_stack[-1].context_id

        cls._local.context_stack.append(context)

        with cls._lock:
            thread_id = threading.get_ident()
            if thread_id not in cls._context_stack:
                cls._context_stack[thread_id] = []
            cls._context_stack[thread_id].append(context)

        return context.context_id

    @classmethod
    def pop_context(cls) -> Optional[ContextData]:
        """Remueve el contexto actual de la pila"""
        if not hasattr(cls._local, 'context_stack') or not cls._local.context_stack:
            return None

        context = cls._local.context_stack.pop()

        with cls._lock:
            thread_id = threading.get_ident()
            if thread_id in cls._context_stack and cls._context_stack[thread_id]:
                cls._context_stack[thread_id].pop()

        return context

    @classmethod
    def clear_context(cls):
        """Limpia todo el contexto del thread actual"""
        if hasattr(cls._local, 'context_stack'):
            cls._local.context_stack.clear()

        with cls._lock:
            thread_id = threading.get_ident()
            if thread_id in cls._context_stack:
                cls._context_stack[thread_id].clear()

    @classmethod
    def get_context_dict(cls) -> Dict[str, Any]:
        """Obtiene el contexto actual como diccionario"""
        context = cls.get_current_context()
        if context:
            result = context.to_dict()
            result.update(cls._global_context)
            return result
        return cls._global_context.copy()

    @classmethod
    def set_global_context(cls, **kwargs):
        """Establece contexto global para todos los threads"""
        with cls._lock:
            cls._global_context.update(kwargs)

    @classmethod
    def clear_global_context(cls):
        """Limpia el contexto global"""
        with cls._lock:
            cls._global_context.clear()


class OperationContext:
    """
    Contexto específico para operaciones DTE

    Extiende LoggingContext con información específica de operaciones DTE.
    """

    def __init__(self,
                 operation: str,
                 document_type: Optional[str] = None,
                 folio: Optional[int] = None,
                 rut_emisor: Optional[str] = None,
                 rut_receptor: Optional[str] = None,
                 **metadata):
        """
        Inicializa contexto de operación

        Args:
            operation: Nombre de la operación
            document_type: Tipo de documento DTE
            folio: Folio del documento
            rut_emisor: RUT del emisor
            rut_receptor: RUT del receptor
            **metadata: Metadatos adicionales
        """
        self.context = ContextData(
            context_type=ContextType.OPERATION,
            scope=ContextScope.OPERATION,
            operation=operation,
            metadata={
                'document_type': document_type,
                'folio': folio,
                'rut_emisor': rut_emisor,
                'rut_receptor': rut_receptor,
                **metadata
            }
        )
        self.context_id = None

    def __enter__(self):
        """Entrada del context manager"""
        self.context_id = LoggingContext.push_context(self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Salida del context manager"""
        LoggingContext.pop_context()

        # Log de finalización de operación
        if exc_type:
            self.context.metadata['error'] = {
                'type': exc_type.__name__,
                'message': str(exc_val),
                'traceback': str(exc_tb) if exc_tb else None
            }

    def add_metadata(self, **kwargs):
        """Agrega metadatos al contexto"""
        self.context.metadata.update(kwargs)

    def add_tags(self, *tags):
        """Agrega tags al contexto"""
        self.context.tags.extend(tags)


class SiiContext:
    """
    Contexto específico para comunicación con SII

    Maneja contexto específico para operaciones con el SII.
    """

    def __init__(self,
                 operation: str,
                 ambiente: str = "certificacion",
                 empresa_rut: Optional[str] = None,
                 **metadata):
        """
        Inicializa contexto SII

        Args:
            operation: Operación SII (envio, consulta, etc.)
            ambiente: Ambiente (certificacion/produccion)
            empresa_rut: RUT de la empresa
            **metadata: Metadatos adicionales
        """
        self.context = ContextData(
            context_type=ContextType.COMMUNICATION,
            scope=ContextScope.REQUEST,
            operation=f"sii_{operation}",
            metadata={
                'ambiente': ambiente,
                'empresa_rut': empresa_rut,
                'sii_operation': operation,
                **metadata
            },
            tags=['sii', ambiente]
        )
        self.context_id = None

    def __enter__(self):
        """Entrada del context manager"""
        self.context_id = LoggingContext.push_context(self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Salida del context manager"""
        LoggingContext.pop_context()

        if exc_type:
            self.context.metadata['sii_error'] = {
                'type': exc_type.__name__,
                'message': str(exc_val)
            }

    def set_request_info(self, endpoint: str, headers: Dict[str, str] = None):
        """Establece información de la request"""
        self.context.metadata.update({
            'sii_endpoint': endpoint,
            'sii_headers': headers or {}
        })

    def set_response_info(self, status_code: int, response_time: float):
        """Establece información de la response"""
        self.context.metadata.update({
            'sii_status_code': status_code,
            'sii_response_time_ms': response_time * 1000
        })


class RequestContext:
    """Contexto para requests HTTP específicos"""

    def __init__(self, method: str, url: str, **metadata):
        self.context = ContextData(
            context_type=ContextType.REQUEST,
            scope=ContextScope.REQUEST,
            operation=f"{method.upper()} {url}",
            metadata={
                'http_method': method,
                'http_url': url,
                **metadata
            },
            tags=['http', method.lower()]
        )
        self.context_id = None

    def __enter__(self):
        self.context_id = LoggingContext.push_context(self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        LoggingContext.pop_context()


class DocumentContext:
    """Contexto para procesamiento de documentos específicos"""

    def __init__(self, document_id: str, document_type: str, **metadata):
        self.context = ContextData(
            context_type=ContextType.DOCUMENT,
            scope=ContextScope.DOCUMENT,
            operation=f"process_{document_type}",
            document_id=document_id,
            metadata={
                'document_type': document_type,
                **metadata
            },
            tags=['document', document_type]
        )
        self.context_id = None

    def __enter__(self):
        self.context_id = LoggingContext.push_context(self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        LoggingContext.pop_context()


class ContextManager:
    """
    Gestor centralizado de contextos para logging

    Proporciona una interfaz unificada para manejar diferentes tipos de contexto.
    """

    @staticmethod
    @contextmanager
    def operation(operation: str, **kwargs):
        """Context manager para operaciones"""
        with OperationContext(operation, **kwargs) as ctx:
            yield ctx

    @staticmethod
    @contextmanager
    def sii_operation(operation: str, **kwargs):
        """Context manager para operaciones SII"""
        with SiiContext(operation, **kwargs) as ctx:
            yield ctx

    @staticmethod
    @contextmanager
    def request(method: str, url: str, **kwargs):
        """Context manager para requests HTTP"""
        with RequestContext(method, url, **kwargs) as ctx:
            yield ctx

    @staticmethod
    @contextmanager
    def document(document_id: str, document_type: str, **kwargs):
        """Context manager para documentos"""
        with DocumentContext(document_id, document_type, **kwargs) as ctx:
            yield ctx

    @staticmethod
    def get_current_context() -> Dict[str, Any]:
        """Obtiene el contexto actual completo"""
        return LoggingContext.get_context_dict()

    @staticmethod
    def clear_all_context():
        """Limpia todo el contexto"""
        LoggingContext.clear_context()
        LoggingContext.clear_global_context()