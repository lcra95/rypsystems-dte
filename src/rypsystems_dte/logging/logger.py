"""
Sistema de Logging Estructurado con Contexto.

Proporciona logging estructurado y contextual incluyendo:
- Logging con contexto de operación
- Formateo estructurado para análisis
- Niveles de logging configurables
- Integración con sistemas de monitoreo
- Logging específico para SII
"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, ConfigDict


class LogLevel(str, Enum):
    """Niveles de logging."""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogContext(BaseModel):
    """Contexto de logging."""

    # Identificadores
    operation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: Optional[str] = Field(None, description="ID de request")
    session_id: Optional[str] = Field(None, description="ID de sesión")
    user_id: Optional[str] = Field(None, description="ID de usuario")

    # Contexto de documento
    document_type: Optional[str] = Field(None, description="Tipo de documento")
    document_folio: Optional[int] = Field(None, description="Folio del documento")
    document_rut: Optional[str] = Field(None, description="RUT del documento")

    # Contexto de operación
    module: Optional[str] = Field(None, description="Módulo ejecutando")
    function: Optional[str] = Field(None, description="Función ejecutando")
    step: Optional[str] = Field(None, description="Paso actual")

    # Contexto SII
    ambiente: Optional[str] = Field(None, description="Ambiente SII")
    endpoint: Optional[str] = Field(None, description="Endpoint SII")

    # Timing
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: Optional[float] = Field(None, description="Duración en ms")

    # Metadatos adicionales
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class LogEntry(BaseModel):
    """Entrada de log estructurada."""

    # Información básica
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    level: LogLevel = Field(..., description="Nivel de log")
    message: str = Field(..., description="Mensaje de log")

    # Contexto
    context: LogContext = Field(..., description="Contexto de logging")

    # Detalles del evento
    event_type: Optional[str] = Field(None, description="Tipo de evento")
    category: Optional[str] = Field(None, description="Categoría del evento")
    tags: List[str] = Field(default_factory=list, description="Tags del evento")

    # Datos del error (si aplica)
    error_type: Optional[str] = Field(None, description="Tipo de error")
    error_code: Optional[str] = Field(None, description="Código de error")
    stack_trace: Optional[str] = Field(None, description="Stack trace")

    # Performance
    execution_time_ms: Optional[float] = Field(None, description="Tiempo de ejecución")
    memory_usage_mb: Optional[float] = Field(None, description="Uso de memoria")

    # Datos adicionales
    extra_data: Dict[str, Any] = Field(default_factory=dict, description="Datos adicionales")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )

    def to_json(self) -> str:
        """Convierte la entrada a JSON."""
        return self.model_dump_json(exclude_none=True, by_alias=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la entrada a diccionario."""
        return self.model_dump(exclude_none=True, by_alias=True)


class StructuredLogger:
    """
    Logger estructurado con contexto.

    Proporciona logging estructurado con:
    - Contexto automático de operación
    - Formateo JSON para análisis
    - Niveles configurables
    - Integración con sistemas de monitoreo
    """

    def __init__(self,
                 name: str,
                 level: LogLevel = LogLevel.INFO,
                 output_file: Optional[Path] = None,
                 console_output: bool = True,
                 json_format: bool = True,
                 include_context: bool = True):
        """
        Inicializa el logger estructurado.

        Args:
            name: Nombre del logger
            level: Nivel de logging
            output_file: Archivo de salida opcional
            console_output: Si mostrar en consola
            json_format: Si usar formato JSON
            include_context: Si incluir contexto automático
        """
        self.name = name
        self.level = level
        self.output_file = output_file
        self.console_output = console_output
        self.json_format = json_format
        self.include_context = include_context

        # Configurar logger interno
        self._logger = logging.getLogger(name)
        self._logger.setLevel(self._get_logging_level(level))

        # Limpiar handlers existentes
        self._logger.handlers.clear()

        # Configurar handlers
        self._setup_handlers()

        # Contexto actual
        self._current_context: Optional[LogContext] = None

    def _get_logging_level(self, level: LogLevel) -> int:
        """Convierte LogLevel a nivel de logging estándar."""
        mapping = {
            LogLevel.TRACE: logging.DEBUG - 5,
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL
        }
        return mapping.get(level, logging.INFO)

    def _setup_handlers(self):
        """Configura los handlers del logger."""
        # Handler para consola
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            if self.json_format:
                console_handler.setFormatter(self._get_json_formatter())
            else:
                console_handler.setFormatter(self._get_text_formatter())
            self._logger.addHandler(console_handler)

        # Handler para archivo
        if self.output_file:
            file_handler = logging.FileHandler(self.output_file, encoding='utf-8')
            file_handler.setFormatter(self._get_json_formatter())
            self._logger.addHandler(file_handler)

    def _get_json_formatter(self) -> logging.Formatter:
        """Obtiene formatter JSON."""
        return logging.Formatter('%(message)s')

    def _get_text_formatter(self) -> logging.Formatter:
        """Obtiene formatter de texto."""
        return logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def set_context(self, context: LogContext):
        """Establece el contexto actual."""
        self._current_context = context

    def get_context(self) -> Optional[LogContext]:
        """Obtiene el contexto actual."""
        return self._current_context

    def clear_context(self):
        """Limpia el contexto actual."""
        self._current_context = None

    def _create_log_entry(self,
                         level: LogLevel,
                         message: str,
                         **kwargs) -> LogEntry:
        """Crea una entrada de log."""
        # Usar contexto actual o crear uno nuevo
        context = kwargs.pop('context', None) or self._current_context or LogContext()

        # Actualizar duración si hay start_time
        if context.start_time and not context.duration_ms:
            duration = (datetime.now(timezone.utc) - context.start_time).total_seconds() * 1000
            context.duration_ms = duration

        return LogEntry(
            level=level,
            message=message,
            context=context,
            **kwargs
        )

    def log(self,
            level: LogLevel,
            message: str,
            **kwargs):
        """Log genérico."""
        if self._should_log(level):
            entry = self._create_log_entry(level, message, **kwargs)

            if self.json_format:
                log_message = entry.to_json()
            else:
                log_message = f"[{entry.context.operation_id}] {message}"

            self._logger.log(self._get_logging_level(level), log_message)

    def trace(self, message: str, **kwargs):
        """Log nivel trace."""
        self.log(LogLevel.TRACE, message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log nivel debug."""
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log nivel info."""
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log nivel warning."""
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log nivel error."""
        self.log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log nivel critical."""
        self.log(LogLevel.CRITICAL, message, **kwargs)

    def _should_log(self, level: LogLevel) -> bool:
        """Determina si debe loggear el nivel."""
        level_values = {
            LogLevel.TRACE: 0,
            LogLevel.DEBUG: 1,
            LogLevel.INFO: 2,
            LogLevel.WARNING: 3,
            LogLevel.ERROR: 4,
            LogLevel.CRITICAL: 5
        }
        return level_values.get(level, 2) >= level_values.get(self.level, 2)

    def log_operation_start(self,
                          operation: str,
                          context: Optional[LogContext] = None,
                          **kwargs) -> LogContext:
        """Inicia logging de operación."""
        if not context:
            context = LogContext()

        context.function = operation
        context.step = "start"
        context.start_time = datetime.now(timezone.utc)

        self.set_context(context)

        self.info(f"Operation started: {operation}",
                 event_type="operation_start",
                 category="operation",
                 context=context,
                 **kwargs)

        return context

    def log_operation_end(self,
                         operation: str,
                         success: bool = True,
                         **kwargs):
        """Termina logging de operación."""
        if self._current_context:
            self._current_context.step = "end"

            level = LogLevel.INFO if success else LogLevel.ERROR
            status = "completed" if success else "failed"

            self.log(level, f"Operation {status}: {operation}",
                    event_type="operation_end",
                    category="operation",
                    **kwargs)

    def log_performance(self,
                       operation: str,
                       duration_ms: float,
                       **kwargs):
        """Log de performance."""
        self.info(f"Performance: {operation} took {duration_ms:.2f}ms",
                 event_type="performance",
                 category="metrics",
                 execution_time_ms=duration_ms,
                 **kwargs)

    def log_error_with_context(self,
                             error: Exception,
                             operation: str,
                             **kwargs):
        """Log de error con contexto completo."""
        import traceback

        self.error(f"Error in {operation}: {str(error)}",
                  event_type="error",
                  category="error",
                  error_type=type(error).__name__,
                  stack_trace=traceback.format_exc(),
                  **kwargs)


class DTELogger(StructuredLogger):
    """
    Logger específico para DTE.

    Extiende el logger estructurado con funcionalidad específica para DTE.
    """

    def __init__(self, **kwargs):
        """Inicializa logger DTE."""
        super().__init__("rypsystems_dte", **kwargs)

    def log_document_processing(self,
                              document_type: str,
                              folio: int,
                              rut: str,
                              operation: str,
                              success: bool = True,
                              **kwargs):
        """Log específico para procesamiento de documentos."""
        context = LogContext(
            document_type=document_type,
            document_folio=folio,
            document_rut=rut,
            function=operation
        )

        level = LogLevel.INFO if success else LogLevel.ERROR
        status = "processed" if success else "failed"

        self.log(level, f"Document {status}: {document_type} {folio} for {rut}",
                event_type="document_processing",
                category="document",
                context=context,
                **kwargs)

    def log_validation_result(self,
                            document_type: str,
                            folio: int,
                            validation_type: str,
                            is_valid: bool,
                            errors: List[str] = None,
                            **kwargs):
        """Log específico para resultados de validación."""
        context = LogContext(
            document_type=document_type,
            document_folio=folio,
            function="validation"
        )

        level = LogLevel.INFO if is_valid else LogLevel.WARNING
        status = "passed" if is_valid else "failed"

        self.log(level, f"Validation {status}: {validation_type} for {document_type} {folio}",
                event_type="validation",
                category="validation",
                context=context,
                extra_data={
                    "validation_type": validation_type,
                    "is_valid": is_valid,
                    "errors": errors or []
                },
                **kwargs)

    def log_signature_operation(self,
                              operation: str,
                              success: bool,
                              certificate_subject: str = None,
                              **kwargs):
        """Log específico para operaciones de firma."""
        context = LogContext(function="signature")

        level = LogLevel.INFO if success else LogLevel.ERROR
        status = "successful" if success else "failed"

        self.log(level, f"Signature operation {status}: {operation}",
                event_type="signature",
                category="security",
                context=context,
                extra_data={
                    "operation": operation,
                    "certificate_subject": certificate_subject
                },
                **kwargs)


class SiiLogger(DTELogger):
    """
    Logger específico para SII.

    Extiende el logger DTE con funcionalidad específica para comunicación SII.
    """

    def __init__(self, **kwargs):
        """Inicializa logger SII."""
        super().__init__(**kwargs)

    def log_sii_request(self,
                       endpoint: str,
                       method: str,
                       document_type: str = None,
                       folio: int = None,
                       ambiente: str = "produccion",
                       **kwargs):
        """Log de request a SII."""
        context = LogContext(
            endpoint=endpoint,
            ambiente=ambiente,
            document_type=document_type,
            document_folio=folio,
            function="sii_request"
        )

        self.info(f"SII request: {method} {endpoint}",
                 event_type="sii_request",
                 category="communication",
                 context=context,
                 extra_data={
                     "method": method,
                     "endpoint": endpoint
                 },
                 **kwargs)

    def log_sii_response(self,
                        endpoint: str,
                        status_code: int,
                        response_time_ms: float,
                        success: bool = True,
                        **kwargs):
        """Log de respuesta de SII."""
        context = LogContext(
            endpoint=endpoint,
            function="sii_response"
        )

        level = LogLevel.INFO if success else LogLevel.ERROR
        status = "successful" if success else "failed"

        self.log(level, f"SII response {status}: {status_code} from {endpoint} in {response_time_ms:.2f}ms",
                event_type="sii_response",
                category="communication",
                context=context,
                execution_time_ms=response_time_ms,
                extra_data={
                    "status_code": status_code,
                    "response_time_ms": response_time_ms
                },
                **kwargs)

    def log_authentication(self,
                          auth_type: str,
                          success: bool,
                          user_rut: str = None,
                          **kwargs):
        """Log de autenticación SII."""
        context = LogContext(
            function="authentication",
            user_id=user_rut
        )

        level = LogLevel.INFO if success else LogLevel.WARNING
        status = "successful" if success else "failed"

        self.log(level, f"SII authentication {status}: {auth_type}",
                event_type="authentication",
                category="security",
                context=context,
                extra_data={
                    "auth_type": auth_type,
                    "user_rut": user_rut
                },
                **kwargs)


# Instancias globales
_global_loggers: Dict[str, StructuredLogger] = {}


def get_logger(name: str = "rypsystems_dte",
               logger_type: str = "dte",
               **kwargs) -> StructuredLogger:
    """
    Obtiene o crea un logger.

    Args:
        name: Nombre del logger
        logger_type: Tipo de logger (dte, sii, structured)
        **kwargs: Argumentos para el logger

    Returns:
        Instancia del logger
    """
    if name not in _global_loggers:
        if logger_type == "sii":
            _global_loggers[name] = SiiLogger(**kwargs)
        elif logger_type == "dte":
            _global_loggers[name] = DTELogger(**kwargs)
        else:
            _global_loggers[name] = StructuredLogger(name, **kwargs)

    return _global_loggers[name]


def configure_logging(config: Dict[str, Any]):
    """
    Configura el sistema de logging global.

    Args:
        config: Configuración de logging
    """
    # Configuración por defecto
    default_config = {
        "level": "info",
        "json_format": True,
        "console_output": True,
        "file_output": None,
        "include_context": True
    }

    # Actualizar con configuración proporcionada
    default_config.update(config)

    # Aplicar configuración a loggers existentes
    for logger in _global_loggers.values():
        logger.level = LogLevel(default_config["level"])
        logger.json_format = default_config["json_format"]
        logger.console_output = default_config["console_output"]
        logger.include_context = default_config["include_context"]

        if default_config.get("file_output"):
            logger.output_file = Path(default_config["file_output"])

        # Reconfigurar handlers
        logger._setup_handlers()