"""
RypSystems DTE - Comprehensive Logging and Error Handling Module
Sistema robusto de manejo de errores con logging apropiado y mecanismos de recuperación

Componentes:
- Logger: Sistema de logging estructurado con contexto
- ErrorHandler: Clasificación y recuperación de errores
- Monitor: Monitoreo de rendimiento y métricas
- Debug: Recolección de información de debug
- Context: Gestión de contexto para logging
"""

from .logger import (
    DTELogger,
    SiiLogger,
    LogLevel,
    LogContext,
    LogEntry,
    StructuredLogger,
    get_logger,
    configure_logging
)
from .error_handler import (
    DTEError,
    DTEException,
    ValidationError,
    CommunicationError,
    ProcessingError,
    ConfigurationError,
    ErrorHandler,
    SiiErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    ErrorRecovery,
    RecoveryStrategy
)
from .monitor import (
    PerformanceMonitor,
    SiiPerformanceMonitor,
    MetricsCollector,
    PerformanceMetric,
    MonitoringLevel,
    AlertThreshold,
    SystemHealth
)
from .debug import (
    DebugCollector,
    SiiDebugCollector,
    DebugInfo,
    DebugLevel,
    DebugContext,
    TraceCollector
)
from .context import (
    LoggingContext,
    OperationContext,
    SiiContext,
    ContextManager,
    RequestContext,
    DocumentContext
)

__all__ = [
    # Logger components
    'DTELogger',
    'SiiLogger',
    'LogLevel',
    'LogContext',
    'LogEntry',
    'StructuredLogger',
    'get_logger',
    'configure_logging',

    # Error handling
    'DTEError',
    'DTEException',
    'ValidationError',
    'CommunicationError',
    'ProcessingError',
    'ConfigurationError',
    'ErrorHandler',
    'SiiErrorHandler',
    'ErrorSeverity',
    'ErrorCategory',
    'ErrorRecovery',
    'RecoveryStrategy',

    # Performance monitoring
    'PerformanceMonitor',
    'SiiPerformanceMonitor',
    'MetricsCollector',
    'PerformanceMetric',
    'MonitoringLevel',
    'AlertThreshold',
    'SystemHealth',

    # Debug collection
    'DebugCollector',
    'SiiDebugCollector',
    'DebugInfo',
    'DebugLevel',
    'DebugContext',
    'TraceCollector',

    # Context management
    'LoggingContext',
    'OperationContext',
    'SiiContext',
    'ContextManager',
    'RequestContext',
    'DocumentContext'
]