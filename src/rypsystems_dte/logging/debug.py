"""
Sistema de Recolección de Información de Debug.

Proporciona recolección comprehensiva de información de debug incluyendo:
- Trazas de ejecución detalladas
- Estado de variables y objetos
- Información de contexto de errores
- Dumps de memoria y estado
- Análisis de rendimiento detallado
"""

import inspect
import json
import pickle
import threading
import traceback
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Callable, Type
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, ConfigDict

from .logger import StructuredLogger, LogLevel, LogContext, get_logger


class DebugLevel(str, Enum):
    """Nivel de debug."""
    MINIMAL = "minimal"
    BASIC = "basic"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"


class DebugInfo(BaseModel):
    """Información de debug."""

    # Identificación
    debug_id: str = Field(..., description="ID único de debug")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    level: DebugLevel = Field(..., description="Nivel de debug")

    # Contexto de ejecución
    thread_id: int = Field(..., description="ID del hilo")
    function_name: str = Field(..., description="Nombre de la función")
    file_path: str = Field(..., description="Ruta del archivo")
    line_number: int = Field(..., description="Número de línea")

    # Estado de variables
    local_variables: Dict[str, str] = Field(default_factory=dict, description="Variables locales")
    global_variables: Dict[str, str] = Field(default_factory=dict, description="Variables globales")

    # Información de stack
    stack_trace: List[str] = Field(default_factory=list, description="Stack trace")
    call_stack: List[Dict[str, Any]] = Field(default_factory=list, description="Call stack detallado")

    # Datos específicos del contexto
    operation_context: Dict[str, Any] = Field(default_factory=dict, description="Contexto de operación")
    error_context: Optional[Dict[str, Any]] = Field(None, description="Contexto de error")

    # Métricas
    memory_usage_mb: Optional[float] = Field(None, description="Uso de memoria en MB")
    execution_time_ms: Optional[float] = Field(None, description="Tiempo de ejecución en ms")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class DebugContext(BaseModel):
    """Contexto de debug."""

    # Identificación
    session_id: str = Field(..., description="ID de sesión de debug")
    operation_id: str = Field(..., description="ID de operación")

    # Configuración
    debug_level: DebugLevel = Field(..., description="Nivel de debug")
    capture_variables: bool = Field(default=True, description="Capturar variables")
    capture_stack: bool = Field(default=True, description="Capturar stack")
    max_variable_size: int = Field(default=1000, description="Tamaño máximo de variable")

    # Estado
    active: bool = Field(default=True, description="Si está activo")
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Filtros
    include_modules: List[str] = Field(default_factory=list, description="Módulos a incluir")
    exclude_modules: List[str] = Field(default_factory=list, description="Módulos a excluir")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class TraceCollector:
    """
    Recolector de trazas de ejecución.

    Recolecta información detallada de la ejecución incluyendo:
    - Llamadas a funciones
    - Estado de variables
    - Stack traces
    - Timing de ejecución
    """

    def __init__(self,
                 max_traces: int = 10000,
                 auto_cleanup: bool = True):
        """
        Inicializa el recolector de trazas.

        Args:
            max_traces: Máximo número de trazas a mantener
            auto_cleanup: Si limpiar automáticamente trazas antiguas
        """
        self.max_traces = max_traces
        self.auto_cleanup = auto_cleanup

        # Almacenamiento de trazas
        self.traces: deque = deque(maxlen=max_traces)
        self.traces_by_thread: Dict[int, List[str]] = defaultdict(list)

        # Control de trazado
        self._tracing = False
        self._trace_lock = threading.Lock()

        # Configuración de filtros
        self.include_patterns: List[str] = []
        self.exclude_patterns: List[str] = ['<frozen', '__pycache__']

    def start_tracing(self, context: DebugContext):
        """Inicia el trazado de ejecución."""
        if self._tracing:
            return

        self._tracing = True
        self.current_context = context

        # Configurar el trazador del sistema
        sys.settrace(self._trace_function)

    def stop_tracing(self):
        """Detiene el trazado de ejecución."""
        if not self._tracing:
            return

        self._tracing = False
        sys.settrace(None)

    def _trace_function(self, frame, event, arg):
        """Función de trazado del sistema."""
        if not self._tracing:
            return

        try:
            # Filtrar por módulos si está configurado
            if not self._should_trace_frame(frame):
                return

            trace_info = self._extract_trace_info(frame, event, arg)
            if trace_info:
                with self._trace_lock:
                    self.traces.append(trace_info)
                    thread_id = threading.get_ident()
                    self.traces_by_thread[thread_id].append(trace_info.debug_id)

        except Exception:
            # No queremos que el trazado cause errores
            pass

        return self._trace_function

    def _should_trace_frame(self, frame) -> bool:
        """Determina si se debe trazar un frame."""
        filename = frame.f_code.co_filename

        # Excluir patrones específicos
        for pattern in self.exclude_patterns:
            if pattern in filename:
                return False

        # Incluir solo patrones específicos si están configurados
        if self.include_patterns:
            return any(pattern in filename for pattern in self.include_patterns)

        return True

    def _extract_trace_info(self, frame, event, arg) -> Optional[DebugInfo]:
        """Extrae información de debug de un frame."""
        try:
            debug_id = f"trace_{int(datetime.now().timestamp() * 1000000)}"

            # Información básica del frame
            code = frame.f_code
            filename = code.co_filename
            function_name = code.co_name
            line_number = frame.f_lineno

            # Crear info básica
            debug_info = DebugInfo(
                debug_id=debug_id,
                level=DebugLevel.DETAILED,
                thread_id=threading.get_ident(),
                function_name=function_name,
                file_path=filename,
                line_number=line_number
            )

            # Capturar variables si está habilitado
            if getattr(self, 'current_context', None) and self.current_context.capture_variables:
                debug_info.local_variables = self._capture_variables(
                    frame.f_locals,
                    self.current_context.max_variable_size
                )

            # Capturar stack si está habilitado
            if getattr(self, 'current_context', None) and self.current_context.capture_stack:
                debug_info.stack_trace = traceback.format_stack(frame)
                debug_info.call_stack = self._extract_call_stack(frame)

            return debug_info

        except Exception:
            return None

    def _capture_variables(self, variables: Dict[str, Any], max_size: int) -> Dict[str, str]:
        """Captura variables con límite de tamaño."""
        captured = {}

        for name, value in variables.items():
            try:
                # Convertir a string y limitar tamaño
                str_value = str(value)
                if len(str_value) > max_size:
                    str_value = str_value[:max_size] + "...[truncated]"

                captured[name] = str_value

            except Exception:
                captured[name] = f"<unable to convert {type(value).__name__}>"

        return captured

    def _extract_call_stack(self, frame) -> List[Dict[str, Any]]:
        """Extrae información detallada del call stack."""
        call_stack = []
        current_frame = frame

        try:
            while current_frame:
                stack_entry = {
                    "function": current_frame.f_code.co_name,
                    "filename": current_frame.f_code.co_filename,
                    "line_number": current_frame.f_lineno,
                    "local_vars_count": len(current_frame.f_locals)
                }
                call_stack.append(stack_entry)
                current_frame = current_frame.f_back

                # Limitar profundidad del stack
                if len(call_stack) >= 20:
                    break

        except Exception:
            pass

        return call_stack

    def get_traces_for_thread(self, thread_id: int) -> List[DebugInfo]:
        """Obtiene trazas para un hilo específico."""
        trace_ids = self.traces_by_thread.get(thread_id, [])
        return [trace for trace in self.traces if trace.debug_id in trace_ids]

    def clear_traces(self):
        """Limpia todas las trazas."""
        with self._trace_lock:
            self.traces.clear()
            self.traces_by_thread.clear()


class DebugCollector:
    """
    Recolector principal de información de debug.

    Proporciona recolección comprehensiva de información de debug incluyendo:
    - Gestión de contextos de debug
    - Recolección de trazas
    - Dumps de estado
    - Análisis de errores
    """

    def __init__(self,
                 logger: Optional[StructuredLogger] = None,
                 debug_level: DebugLevel = DebugLevel.BASIC,
                 output_directory: Optional[Path] = None):
        """
        Inicializa el recolector de debug.

        Args:
            logger: Logger para información de debug
            debug_level: Nivel de debug por defecto
            output_directory: Directorio para archivos de debug
        """
        self.logger = logger or get_logger("debug_collector")
        self.debug_level = debug_level
        self.output_directory = output_directory or Path("/tmp/dte_debug")

        # Crear directorio de salida
        self.output_directory.mkdir(parents=True, exist_ok=True)

        # Componentes
        self.trace_collector = TraceCollector()

        # Contextos activos
        self.active_contexts: Dict[str, DebugContext] = {}

        # Información de debug recolectada
        self.debug_sessions: Dict[str, List[DebugInfo]] = defaultdict(list)

        # Lock para thread safety
        self._debug_lock = threading.Lock()

    def start_debug_session(self,
                           operation_id: str,
                           debug_level: Optional[DebugLevel] = None,
                           **kwargs) -> str:
        """
        Inicia una sesión de debug.

        Args:
            operation_id: ID de la operación
            debug_level: Nivel de debug
            **kwargs: Argumentos adicionales para el contexto

        Returns:
            ID de la sesión de debug
        """
        session_id = f"debug_{operation_id}_{int(datetime.now().timestamp())}"

        context = DebugContext(
            session_id=session_id,
            operation_id=operation_id,
            debug_level=debug_level or self.debug_level,
            **kwargs
        )

        with self._debug_lock:
            self.active_contexts[session_id] = context

        # Iniciar trazado si es necesario
        if context.debug_level in [DebugLevel.DETAILED, DebugLevel.COMPREHENSIVE]:
            self.trace_collector.start_tracing(context)

        self.logger.debug(
            f"Debug session started: {session_id}",
            event_type="debug_session_start",
            category="debug",
            extra_data={
                "session_id": session_id,
                "operation_id": operation_id,
                "debug_level": context.debug_level.value
            }
        )

        return session_id

    def end_debug_session(self, session_id: str):
        """Termina una sesión de debug."""
        if session_id not in self.active_contexts:
            return

        context = self.active_contexts[session_id]

        # Detener trazado si estaba activo
        if context.debug_level in [DebugLevel.DETAILED, DebugLevel.COMPREHENSIVE]:
            self.trace_collector.stop_tracing()

        # Generar reporte de debug
        self._generate_debug_report(session_id)

        with self._debug_lock:
            del self.active_contexts[session_id]

        self.logger.debug(
            f"Debug session ended: {session_id}",
            event_type="debug_session_end",
            category="debug",
            extra_data={"session_id": session_id}
        )

    def collect_debug_info(self,
                          session_id: str,
                          function_name: str,
                          variables: Optional[Dict[str, Any]] = None,
                          **kwargs) -> str:
        """
        Recolecta información de debug para una sesión.

        Args:
            session_id: ID de la sesión de debug
            function_name: Nombre de la función
            variables: Variables a capturar
            **kwargs: Información adicional

        Returns:
            ID de la información de debug
        """
        if session_id not in self.active_contexts:
            return ""

        context = self.active_contexts[session_id]
        if not context.active:
            return ""

        # Obtener información del frame actual
        frame = inspect.currentframe().f_back
        debug_id = f"debug_{session_id}_{int(datetime.now().timestamp() * 1000000)}"

        debug_info = DebugInfo(
            debug_id=debug_id,
            level=context.debug_level,
            thread_id=threading.get_ident(),
            function_name=function_name,
            file_path=frame.f_code.co_filename if frame else "unknown",
            line_number=frame.f_lineno if frame else 0
        )

        # Capturar variables si está habilitado
        if context.capture_variables and variables:
            debug_info.local_variables = self._safe_capture_variables(
                variables,
                context.max_variable_size
            )

        # Capturar stack si está habilitado
        if context.capture_stack and frame:
            debug_info.stack_trace = traceback.format_stack(frame)

        # Agregar contexto de operación
        debug_info.operation_context = kwargs

        # Almacenar información
        with self._debug_lock:
            self.debug_sessions[session_id].append(debug_info)

        # Log de debug
        if context.debug_level == DebugLevel.COMPREHENSIVE:
            self.logger.trace(
                f"Debug info collected: {function_name}",
                event_type="debug_info_collected",
                category="debug",
                extra_data={
                    "session_id": session_id,
                    "debug_id": debug_id,
                    "function_name": function_name
                }
            )

        return debug_id

    def collect_error_debug(self,
                          error: Exception,
                          session_id: Optional[str] = None,
                          operation_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Recolecta información de debug específica para errores.

        Args:
            error: Excepción ocurrida
            session_id: ID de sesión opcional
            operation_context: Contexto de operación

        Returns:
            ID de la información de debug
        """
        # Crear sesión temporal si no existe
        if not session_id:
            session_id = self.start_debug_session(
                "error_debug",
                DebugLevel.COMPREHENSIVE
            )
            temporary_session = True
        else:
            temporary_session = False

        # Obtener información del error
        frame = inspect.currentframe().f_back
        debug_id = f"error_{session_id}_{int(datetime.now().timestamp() * 1000000)}"

        debug_info = DebugInfo(
            debug_id=debug_id,
            level=DebugLevel.COMPREHENSIVE,
            thread_id=threading.get_ident(),
            function_name=frame.f_code.co_name if frame else "unknown",
            file_path=frame.f_code.co_filename if frame else "unknown",
            line_number=frame.f_lineno if frame else 0
        )

        # Información específica del error
        debug_info.error_context = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_args": list(error.args) if error.args else [],
            "stack_trace": traceback.format_exc()
        }

        # Capturar variables del frame
        if frame:
            debug_info.local_variables = self._safe_capture_variables(
                frame.f_locals,
                2000  # Más espacio para errores
            )

        # Contexto de operación
        if operation_context:
            debug_info.operation_context = operation_context

        # Almacenar información
        with self._debug_lock:
            self.debug_sessions[session_id].append(debug_info)

        # Generar dump de error
        self._generate_error_dump(debug_info, session_id)

        # Cerrar sesión temporal
        if temporary_session:
            self.end_debug_session(session_id)

        return debug_id

    def _safe_capture_variables(self,
                               variables: Dict[str, Any],
                               max_size: int) -> Dict[str, str]:
        """Captura variables de forma segura."""
        captured = {}

        for name, value in variables.items():
            try:
                # Evitar variables privadas y métodos
                if name.startswith('_'):
                    continue

                # Convertir a string de forma segura
                if isinstance(value, (str, int, float, bool, type(None))):
                    str_value = str(value)
                elif isinstance(value, (list, tuple, dict)):
                    # Limitar tamaño de estructuras de datos
                    str_value = str(value)[:max_size]
                else:
                    # Para otros objetos, solo el tipo y repr básico
                    str_value = f"<{type(value).__name__} object>"

                # Truncar si es muy largo
                if len(str_value) > max_size:
                    str_value = str_value[:max_size] + "...[truncated]"

                captured[name] = str_value

            except Exception as e:
                captured[name] = f"<error capturing: {e}>"

        return captured

    def _generate_debug_report(self, session_id: str):
        """Genera reporte de debug para una sesión."""
        if session_id not in self.debug_sessions:
            return

        debug_infos = self.debug_sessions[session_id]
        if not debug_infos:
            return

        # Crear reporte
        report = {
            "session_id": session_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "debug_info_count": len(debug_infos),
            "debug_infos": [info.model_dump() for info in debug_infos]
        }

        # Guardar reporte
        report_file = self.output_directory / f"debug_report_{session_id}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self.logger.info(
            f"Debug report generated: {report_file}",
            event_type="debug_report_generated",
            category="debug",
            extra_data={
                "session_id": session_id,
                "report_file": str(report_file),
                "debug_info_count": len(debug_infos)
            }
        )

    def _generate_error_dump(self, debug_info: DebugInfo, session_id: str):
        """Genera dump específico para errores."""
        dump_data = {
            "error_debug_id": debug_info.debug_id,
            "session_id": session_id,
            "timestamp": debug_info.timestamp.isoformat(),
            "error_context": debug_info.error_context,
            "function_name": debug_info.function_name,
            "file_path": debug_info.file_path,
            "line_number": debug_info.line_number,
            "local_variables": debug_info.local_variables,
            "operation_context": debug_info.operation_context
        }

        # Guardar dump
        dump_file = self.output_directory / f"error_dump_{debug_info.debug_id}.json"
        with open(dump_file, 'w', encoding='utf-8') as f:
            json.dump(dump_data, f, indent=2, ensure_ascii=False)

        self.logger.error(
            f"Error debug dump generated: {dump_file}",
            event_type="error_dump_generated",
            category="debug",
            extra_data={
                "debug_id": debug_info.debug_id,
                "dump_file": str(dump_file)
            }
        )

    def get_debug_summary(self, session_id: str) -> Dict[str, Any]:
        """Obtiene resumen de debug para una sesión."""
        if session_id not in self.debug_sessions:
            return {}

        debug_infos = self.debug_sessions[session_id]

        # Estadísticas básicas
        total_infos = len(debug_infos)
        error_infos = sum(1 for info in debug_infos if info.error_context)

        # Funciones más frecuentes
        function_counts = defaultdict(int)
        for info in debug_infos:
            function_counts[info.function_name] += 1

        return {
            "session_id": session_id,
            "total_debug_infos": total_infos,
            "error_debug_infos": error_infos,
            "most_frequent_functions": dict(function_counts),
            "session_duration": (
                (debug_infos[-1].timestamp - debug_infos[0].timestamp).total_seconds()
                if debug_infos else 0
            )
        }

    def cleanup_old_sessions(self, hours: int = 24):
        """Limpia sesiones de debug antiguas."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        sessions_to_remove = []
        for session_id, debug_infos in self.debug_sessions.items():
            if debug_infos and debug_infos[0].timestamp < cutoff_time:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del self.debug_sessions[session_id]

        if sessions_to_remove:
            self.logger.info(
                f"Cleaned up {len(sessions_to_remove)} old debug sessions",
                event_type="debug_cleanup",
                category="debug"
            )


class SiiDebugCollector(DebugCollector):
    """
    Recolector de debug específico para SII.

    Extiende el recolector base con funcionalidad específica para SII.
    """

    def __init__(self, **kwargs):
        """Inicializa recolector de debug SII."""
        super().__init__(**kwargs)

        # Configurar filtros específicos para SII
        self.trace_collector.include_patterns.extend([
            'rypsystems_dte',
            'sii'
        ])

    def collect_sii_request_debug(self,
                                session_id: str,
                                endpoint: str,
                                request_data: Dict[str, Any],
                                headers: Dict[str, str]) -> str:
        """Recolecta debug específico para requests SII."""
        return self.collect_debug_info(
            session_id,
            f"sii_request_{endpoint}",
            {
                "endpoint": endpoint,
                "request_data_size": len(str(request_data)),
                "headers_count": len(headers)
            },
            sii_context={
                "endpoint": endpoint,
                "request_type": "sii_request",
                "has_auth": "Authorization" in headers
            }
        )

    def collect_sii_response_debug(self,
                                 session_id: str,
                                 endpoint: str,
                                 status_code: int,
                                 response_data: Optional[Dict[str, Any]] = None) -> str:
        """Recolecta debug específico para respuestas SII."""
        return self.collect_debug_info(
            session_id,
            f"sii_response_{endpoint}",
            {
                "endpoint": endpoint,
                "status_code": status_code,
                "response_data_size": len(str(response_data)) if response_data else 0
            },
            sii_context={
                "endpoint": endpoint,
                "response_type": "sii_response",
                "status_code": status_code,
                "success": 200 <= status_code < 300
            }
        )

    def collect_document_debug(self,
                             session_id: str,
                             document_type: str,
                             folio: int,
                             operation: str,
                             document_data: Optional[Dict[str, Any]] = None) -> str:
        """Recolecta debug específico para documentos."""
        return self.collect_debug_info(
            session_id,
            f"document_{operation}",
            {
                "document_type": document_type,
                "folio": folio,
                "operation": operation,
                "document_size": len(str(document_data)) if document_data else 0
            },
            document_context={
                "document_type": document_type,
                "folio": folio,
                "operation": operation
            }
        )