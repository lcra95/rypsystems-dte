"""
Sistema de Manejo de Errores con Clasificación y Recuperación.

Proporciona manejo robusto de errores incluyendo:
- Clasificación automática de errores
- Estrategias de recuperación
- Logging contextual de errores
- Métricas de errores
- Escalado automático
"""

import traceback
import time
from typing import Dict, List, Optional, Any, Union, Callable, Type
from enum import Enum
from datetime import datetime, timezone, timedelta

from pydantic import BaseModel, Field, field_validator, ConfigDict

from .logger import StructuredLogger, LogLevel, LogContext, get_logger


class ErrorSeverity(str, Enum):
    """Severidad del error."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Categoría del error."""
    VALIDATION = "validation"
    COMMUNICATION = "communication"
    PROCESSING = "processing"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    NETWORK = "network"
    TIMEOUT = "timeout"


class RecoveryStrategy(str, Enum):
    """Estrategia de recuperación."""
    NONE = "none"
    RETRY = "retry"
    FALLBACK = "fallback"
    ESCALATE = "escalate"
    ABORT = "abort"
    CONTINUE = "continue"


class DTEError(Exception):
    """Base exception para errores de DTE."""

    def __init__(self,
                 message: str,
                 error_code: str = None,
                 category: ErrorCategory = ErrorCategory.SYSTEM,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 context: Dict[str, Any] = None,
                 recoverable: bool = True,
                 recovery_strategy: RecoveryStrategy = RecoveryStrategy.NONE):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.recoverable = recoverable
        self.recovery_strategy = recovery_strategy
        self.timestamp = datetime.now(timezone.utc)


class DTEException(DTEError):
    """Exception general de DTE."""
    pass


class ValidationError(DTEError):
    """Error de validación."""

    def __init__(self, message: str, field: str = None, value: Any = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.field = field
        self.value = value


class CommunicationError(DTEError):
    """Error de comunicación."""

    def __init__(self, message: str, endpoint: str = None, status_code: int = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.COMMUNICATION,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=RecoveryStrategy.RETRY,
            **kwargs
        )
        self.endpoint = endpoint
        self.status_code = status_code


class ProcessingError(DTEError):
    """Error de procesamiento."""

    def __init__(self, message: str, document_type: str = None, folio: int = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.PROCESSING,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.document_type = document_type
        self.folio = folio


class ConfigurationError(DTEError):
    """Error de configuración."""

    def __init__(self, message: str, config_key: str = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.CRITICAL,
            recoverable=False,
            **kwargs
        )
        self.config_key = config_key


class ErrorRecovery(BaseModel):
    """Información de recuperación de error."""

    strategy: RecoveryStrategy = Field(..., description="Estrategia de recuperación")
    max_attempts: int = Field(default=3, description="Máximo número de intentos")
    delay_seconds: float = Field(default=1.0, description="Delay entre intentos")
    exponential_backoff: bool = Field(default=True, description="Usar backoff exponencial")
    recovery_function: Optional[Callable] = Field(None, description="Función de recuperación")
    escalation_threshold: int = Field(default=5, description="Umbral para escalado")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class ErrorHandler:
    """
    Manejador de errores con clasificación y recuperación.

    Proporciona manejo robusto de errores incluyendo:
    - Clasificación automática de errores
    - Estrategias de recuperación configurable
    - Logging contextual
    - Métricas de errores
    """

    def __init__(self,
                 logger: Optional[StructuredLogger] = None,
                 enable_recovery: bool = True,
                 default_recovery: RecoveryStrategy = RecoveryStrategy.RETRY):
        """
        Inicializa el manejador de errores.

        Args:
            logger: Logger para errores
            enable_recovery: Si habilitar recuperación automática
            default_recovery: Estrategia de recuperación por defecto
        """
        self.logger = logger or get_logger("error_handler")
        self.enable_recovery = enable_recovery
        self.default_recovery = default_recovery

        # Configuración de recuperación por categoría
        self.recovery_config: Dict[ErrorCategory, ErrorRecovery] = {
            ErrorCategory.COMMUNICATION: ErrorRecovery(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=3,
                delay_seconds=1.0,
                exponential_backoff=True
            ),
            ErrorCategory.TIMEOUT: ErrorRecovery(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=2,
                delay_seconds=2.0
            ),
            ErrorCategory.VALIDATION: ErrorRecovery(
                strategy=RecoveryStrategy.NONE,
                max_attempts=1
            ),
            ErrorCategory.CONFIGURATION: ErrorRecovery(
                strategy=RecoveryStrategy.ESCALATE,
                max_attempts=1
            ),
            ErrorCategory.AUTHENTICATION: ErrorRecovery(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=2,
                delay_seconds=0.5
            )
        }

        # Estadísticas de errores
        self.error_stats: Dict[str, Any] = {
            "total_errors": 0,
            "errors_by_category": {},
            "errors_by_severity": {},
            "recovery_attempts": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0
        }

        # Histórico de errores
        self.error_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000

    def handle_error(self,
                    error: Exception,
                    context: Optional[LogContext] = None,
                    operation: str = None,
                    **kwargs) -> bool:
        """
        Maneja un error con clasificación y recuperación.

        Args:
            error: Error a manejar
            context: Contexto de logging
            operation: Operación donde ocurrió el error
            **kwargs: Argumentos adicionales

        Returns:
            True si el error se recuperó exitosamente
        """
        # Clasificar error
        classified_error = self._classify_error(error)

        # Actualizar estadísticas
        self._update_stats(classified_error)

        # Agregar al historial
        self._add_to_history(classified_error, context, operation)

        # Log del error
        self._log_error(classified_error, context, operation, **kwargs)

        # Intentar recuperación si está habilitada
        if self.enable_recovery and classified_error.recoverable:
            return self._attempt_recovery(classified_error, context, operation, **kwargs)

        return False

    def _classify_error(self, error: Exception) -> DTEError:
        """Clasifica un error automáticamente."""
        if isinstance(error, DTEError):
            return error

        # Clasificación automática basada en tipo de error
        error_message = str(error)
        error_type = type(error).__name__

        # Errores de red/comunicación
        if any(keyword in error_message.lower() for keyword in [
            'connection', 'timeout', 'network', 'http', 'socket', 'ssl'
        ]):
            return CommunicationError(
                error_message,
                error_code=error_type,
                context={"original_error": error_type}
            )

        # Errores de validación
        if any(keyword in error_message.lower() for keyword in [
            'validation', 'invalid', 'format', 'required', 'missing'
        ]):
            return ValidationError(
                error_message,
                error_code=error_type,
                context={"original_error": error_type}
            )

        # Errores de configuración
        if any(keyword in error_message.lower() for keyword in [
            'config', 'setting', 'parameter', 'environment', 'key'
        ]):
            return ConfigurationError(
                error_message,
                error_code=error_type,
                context={"original_error": error_type}
            )

        # Errores de autenticación
        if any(keyword in error_message.lower() for keyword in [
            'auth', 'login', 'credential', 'token', 'unauthorized', 'forbidden'
        ]):
            return DTEError(
                error_message,
                error_code=error_type,
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.HIGH,
                context={"original_error": error_type}
            )

        # Error genérico del sistema
        return DTEError(
            error_message,
            error_code=error_type,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            context={"original_error": error_type}
        )

    def _update_stats(self, error: DTEError):
        """Actualiza estadísticas de errores."""
        self.error_stats["total_errors"] += 1

        # Por categoría
        category = error.category.value
        if category not in self.error_stats["errors_by_category"]:
            self.error_stats["errors_by_category"][category] = 0
        self.error_stats["errors_by_category"][category] += 1

        # Por severidad
        severity = error.severity.value
        if severity not in self.error_stats["errors_by_severity"]:
            self.error_stats["errors_by_severity"][severity] = 0
        self.error_stats["errors_by_severity"][severity] += 1

    def _add_to_history(self,
                       error: DTEError,
                       context: Optional[LogContext] = None,
                       operation: str = None):
        """Agrega error al historial."""
        error_record = {
            "timestamp": error.timestamp.isoformat(),
            "message": error.message,
            "error_code": error.error_code,
            "category": error.category.value,
            "severity": error.severity.value,
            "operation": operation,
            "context": error.context,
            "recoverable": error.recoverable
        }

        if context:
            error_record["operation_id"] = context.operation_id
            error_record["document_type"] = context.document_type
            error_record["document_folio"] = context.document_folio

        self.error_history.append(error_record)

        # Mantener tamaño del historial
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]

    def _log_error(self,
                  error: DTEError,
                  context: Optional[LogContext] = None,
                  operation: str = None,
                  **kwargs):
        """Log del error con contexto completo."""
        # Determinar nivel de log basado en severidad
        log_level_map = {
            ErrorSeverity.LOW: LogLevel.WARNING,
            ErrorSeverity.MEDIUM: LogLevel.ERROR,
            ErrorSeverity.HIGH: LogLevel.ERROR,
            ErrorSeverity.CRITICAL: LogLevel.CRITICAL
        }

        log_level = log_level_map.get(error.severity, LogLevel.ERROR)

        # Preparar información del error
        error_info = {
            "error_type": type(error).__name__,
            "error_code": error.error_code,
            "category": error.category.value,
            "severity": error.severity.value,
            "recoverable": error.recoverable,
            "recovery_strategy": error.recovery_strategy.value,
            "stack_trace": traceback.format_exc()
        }

        # Agregar contexto específico del error
        if hasattr(error, 'field'):
            error_info["field"] = error.field
        if hasattr(error, 'endpoint'):
            error_info["endpoint"] = error.endpoint
        if hasattr(error, 'status_code'):
            error_info["status_code"] = error.status_code

        self.logger.log(
            log_level,
            f"Error in {operation or 'unknown operation'}: {error.message}",
            event_type="error",
            category="error_handling",
            context=context,
            extra_data=error_info,
            **kwargs
        )

    def _attempt_recovery(self,
                         error: DTEError,
                         context: Optional[LogContext] = None,
                         operation: str = None,
                         **kwargs) -> bool:
        """Intenta recuperación del error."""
        recovery_config = self.recovery_config.get(
            error.category,
            ErrorRecovery(strategy=self.default_recovery)
        )

        self.error_stats["recovery_attempts"] += 1

        if recovery_config.strategy == RecoveryStrategy.NONE:
            return False

        elif recovery_config.strategy == RecoveryStrategy.RETRY:
            return self._retry_operation(error, recovery_config, context, operation, **kwargs)

        elif recovery_config.strategy == RecoveryStrategy.FALLBACK:
            return self._fallback_operation(error, recovery_config, context, operation, **kwargs)

        elif recovery_config.strategy == RecoveryStrategy.ESCALATE:
            self._escalate_error(error, context, operation)
            return False

        elif recovery_config.strategy == RecoveryStrategy.CONTINUE:
            self.logger.warning(
                f"Continuing after error in {operation}: {error.message}",
                event_type="error_recovery",
                category="recovery",
                context=context
            )
            return True

        return False

    def _retry_operation(self,
                        error: DTEError,
                        recovery_config: ErrorRecovery,
                        context: Optional[LogContext] = None,
                        operation: str = None,
                        **kwargs) -> bool:
        """Reintentar operación."""
        if not recovery_config.recovery_function:
            return False

        for attempt in range(recovery_config.max_attempts):
            try:
                # Calcular delay
                delay = recovery_config.delay_seconds
                if recovery_config.exponential_backoff and attempt > 0:
                    delay = recovery_config.delay_seconds * (2 ** attempt)

                # Esperar antes del reintento
                if attempt > 0:
                    time.sleep(delay)

                self.logger.info(
                    f"Retrying operation {operation} (attempt {attempt + 1}/{recovery_config.max_attempts})",
                    event_type="retry_attempt",
                    category="recovery",
                    context=context,
                    extra_data={
                        "attempt": attempt + 1,
                        "max_attempts": recovery_config.max_attempts,
                        "delay_seconds": delay
                    }
                )

                # Ejecutar función de recuperación
                result = recovery_config.recovery_function(**kwargs)

                self.logger.info(
                    f"Recovery successful for {operation} on attempt {attempt + 1}",
                    event_type="recovery_success",
                    category="recovery",
                    context=context
                )

                self.error_stats["successful_recoveries"] += 1
                return True

            except Exception as retry_error:
                if attempt == recovery_config.max_attempts - 1:
                    # Último intento fallido
                    self.logger.error(
                        f"Recovery failed for {operation} after {recovery_config.max_attempts} attempts: {retry_error}",
                        event_type="recovery_failed",
                        category="recovery",
                        context=context,
                        extra_data={
                            "final_error": str(retry_error),
                            "attempts": recovery_config.max_attempts
                        }
                    )
                    self.error_stats["failed_recoveries"] += 1

        return False

    def _fallback_operation(self,
                          error: DTEError,
                          recovery_config: ErrorRecovery,
                          context: Optional[LogContext] = None,
                          operation: str = None,
                          **kwargs) -> bool:
        """Operación de fallback."""
        if not recovery_config.recovery_function:
            return False

        try:
            self.logger.info(
                f"Attempting fallback for {operation}",
                event_type="fallback_attempt",
                category="recovery",
                context=context
            )

            result = recovery_config.recovery_function(**kwargs)

            self.logger.info(
                f"Fallback successful for {operation}",
                event_type="fallback_success",
                category="recovery",
                context=context
            )

            self.error_stats["successful_recoveries"] += 1
            return True

        except Exception as fallback_error:
            self.logger.error(
                f"Fallback failed for {operation}: {fallback_error}",
                event_type="fallback_failed",
                category="recovery",
                context=context,
                extra_data={"fallback_error": str(fallback_error)}
            )
            self.error_stats["failed_recoveries"] += 1

        return False

    def _escalate_error(self,
                       error: DTEError,
                       context: Optional[LogContext] = None,
                       operation: str = None):
        """Escalar error a nivel superior."""
        self.logger.critical(
            f"Escalating error in {operation}: {error.message}",
            event_type="error_escalation",
            category="escalation",
            context=context,
            extra_data={
                "error_code": error.error_code,
                "category": error.category.value,
                "severity": error.severity.value
            }
        )

        # Aquí se podría implementar notificación automática
        # por email, Slack, etc.

    def get_error_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de errores."""
        stats = self.error_stats.copy()

        # Calcular tasa de recuperación
        total_recoveries = stats["successful_recoveries"] + stats["failed_recoveries"]
        if total_recoveries > 0:
            stats["recovery_rate"] = stats["successful_recoveries"] / total_recoveries
        else:
            stats["recovery_rate"] = 0.0

        return stats

    def get_recent_errors(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Obtiene errores recientes."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent_errors = []
        for error_record in reversed(self.error_history):
            error_time = datetime.fromisoformat(error_record["timestamp"].replace('Z', '+00:00'))
            if error_time >= cutoff_time:
                recent_errors.append(error_record)
            else:
                break

        return recent_errors

    def set_recovery_config(self,
                          category: ErrorCategory,
                          recovery: ErrorRecovery):
        """Configura recuperación para una categoría."""
        self.recovery_config[category] = recovery

    def add_recovery_function(self,
                            category: ErrorCategory,
                            recovery_function: Callable):
        """Agrega función de recuperación para una categoría."""
        if category in self.recovery_config:
            self.recovery_config[category].recovery_function = recovery_function


class SiiErrorHandler(ErrorHandler):
    """
    Manejador de errores específico para SII.

    Extiende el manejador base con lógica específica para errores de SII.
    """

    def __init__(self, **kwargs):
        """Inicializa manejador de errores SII."""
        super().__init__(**kwargs)

        # Configuración específica para SII
        self.recovery_config.update({
            ErrorCategory.COMMUNICATION: ErrorRecovery(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=5,  # Más intentos para SII
                delay_seconds=2.0,
                exponential_backoff=True
            ),
            ErrorCategory.AUTHENTICATION: ErrorRecovery(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=3,
                delay_seconds=1.0
            ),
            ErrorCategory.TIMEOUT: ErrorRecovery(
                strategy=RecoveryStrategy.RETRY,
                max_attempts=3,
                delay_seconds=5.0  # Más tiempo para SII
            )
        })

    def handle_sii_error(self,
                        error: Exception,
                        endpoint: str,
                        operation: str,
                        document_type: str = None,
                        folio: int = None,
                        **kwargs) -> bool:
        """Maneja errores específicos de SII."""
        # Crear contexto específico para SII
        context = LogContext(
            endpoint=endpoint,
            function=operation,
            document_type=document_type,
            document_folio=folio
        )

        # Clasificar error específico de SII
        sii_error = self._classify_sii_error(error, endpoint)

        return super().handle_error(sii_error, context, operation, **kwargs)

    def _classify_sii_error(self, error: Exception, endpoint: str) -> DTEError:
        """Clasifica errores específicos de SII."""
        error_message = str(error)

        # Errores de autenticación SII
        if any(keyword in error_message.lower() for keyword in [
            'semilla', 'token', 'certificado', 'authentication'
        ]):
            return DTEError(
                error_message,
                error_code="SII_AUTH_ERROR",
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.HIGH,
                context={"endpoint": endpoint}
            )

        # Errores de validación SII
        if any(keyword in error_message.lower() for keyword in [
            'schema', 'xsd', 'validation', 'rechazado'
        ]):
            return ValidationError(
                error_message,
                error_code="SII_VALIDATION_ERROR",
                context={"endpoint": endpoint}
            )

        # Errores de comunicación SII
        if any(keyword in error_message.lower() for keyword in [
            'soap', 'wsdl', 'connection', 'timeout'
        ]):
            return CommunicationError(
                error_message,
                error_code="SII_COMM_ERROR",
                endpoint=endpoint
            )

        # Error genérico de SII
        return DTEError(
            error_message,
            error_code="SII_ERROR",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            context={"endpoint": endpoint}
        )