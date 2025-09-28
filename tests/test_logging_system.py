"""
Tests para el sistema comprehensivo de error handling y logging
"""

import pytest
import json
import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from rypsystems_dte.logging import (
    DTELogger, SiiLogger, LogLevel, LogContext, LogEntry, StructuredLogger,
    DTEError, ValidationError, CommunicationError, ProcessingError,
    ErrorHandler, SiiErrorHandler, ErrorSeverity, ErrorCategory,
    PerformanceMonitor, MetricsCollector, PerformanceMetric,
    DebugCollector, SiiDebugCollector, DebugInfo, DebugLevel,
    LoggingContext, OperationContext, SiiContext, ContextManager,
    RequestContext, DocumentContext
)


class TestStructuredLogger:
    """Tests para el logger estructurado"""

    def test_logger_initialization(self):
        """Test inicialización del logger"""
        logger = StructuredLogger("test_logger")
        assert logger.name == "test_logger"
        assert logger.level == LogLevel.INFO

    def test_basic_logging(self):
        """Test logging básico"""
        logger = StructuredLogger("test", output_file=None)

        with patch('builtins.print') as mock_print:
            logger.info("Test message", extra_data={"key": "value"})
            mock_print.assert_called_once()

            # Verificar que se imprimió JSON válido
            args = mock_print.call_args[0][0]
            log_data = json.loads(args)
            assert log_data['message'] == "Test message"
            assert log_data['level'] == "INFO"
            assert log_data['extra_data']['key'] == "value"

    def test_context_logging(self):
        """Test logging con contexto"""
        logger = StructuredLogger("test", output_file=None)

        with OperationContext("test_operation", document_type="factura"):
            with patch('builtins.print') as mock_print:
                logger.info("Test with context")

                args = mock_print.call_args[0][0]
                log_data = json.loads(args)
                assert 'context' in log_data
                assert log_data['context']['operation'] == "test_operation"
                assert log_data['context']['metadata']['document_type'] == "factura"


class TestDTELogger:
    """Tests para DTELogger"""

    def test_dte_logger_initialization(self):
        """Test inicialización de DTELogger"""
        logger = DTELogger("dte_test")
        assert isinstance(logger, DTELogger)
        assert logger.name == "dte_test"

    def test_document_logging(self):
        """Test logging de documentos"""
        logger = DTELogger("dte_test", output_file=None)

        with patch('builtins.print') as mock_print:
            logger.log_document_created("factura", 1001, "76354771-K", "66666666-6")

            args = mock_print.call_args[0][0]
            log_data = json.loads(args)
            assert "Document created" in log_data['message']
            assert log_data['document_type'] == "factura"
            assert log_data['folio'] == 1001

    def test_operation_timing(self):
        """Test medición de tiempo de operaciones"""
        logger = DTELogger("dte_test", output_file=None)

        with patch('builtins.print'):
            with logger.operation_timer("test_operation"):
                time.sleep(0.01)  # Simular trabajo

        # Verificar que se registró el tiempo
        assert logger._operation_times
        assert "test_operation" in logger._operation_times


class TestSiiLogger:
    """Tests para SiiLogger"""

    def test_sii_logger_initialization(self):
        """Test inicialización de SiiLogger"""
        logger = SiiLogger("sii_test")
        assert isinstance(logger, SiiLogger)

    def test_request_response_logging(self):
        """Test logging de requests/responses SII"""
        logger = SiiLogger("sii_test", output_file=None)

        with patch('builtins.print') as mock_print:
            logger.log_sii_request("POST", "/api/endpoint", {"data": "test"})

            args = mock_print.call_args[0][0]
            log_data = json.loads(args)
            assert "SII Request" in log_data['message']
            assert log_data['sii_method'] == "POST"
            assert log_data['sii_endpoint'] == "/api/endpoint"

    def test_token_logging(self):
        """Test logging de tokens SII"""
        logger = SiiLogger("sii_test", output_file=None)

        with patch('builtins.print') as mock_print:
            logger.log_token_obtained("test_token", 3600)

            args = mock_print.call_args[0][0]
            log_data = json.loads(args)
            assert "SII Token obtained" in log_data['message']
            assert log_data['token_expires_in'] == 3600


class TestErrorHandler:
    """Tests para el sistema de manejo de errores"""

    def test_error_handler_initialization(self):
        """Test inicialización del error handler"""
        handler = ErrorHandler()
        assert handler.max_retries == 3
        assert handler.retry_delay == 1.0

    def test_error_classification(self):
        """Test clasificación de errores"""
        handler = ErrorHandler()

        # Test ValidationError
        error = ValidationError("Invalid data")
        severity, category = handler.classify_error(error)
        assert severity == ErrorSeverity.MEDIUM
        assert category == ErrorCategory.VALIDATION

        # Test CommunicationError
        error = CommunicationError("Network timeout")
        severity, category = handler.classify_error(error)
        assert severity == ErrorSeverity.HIGH
        assert category == ErrorCategory.COMMUNICATION

    def test_error_recovery(self):
        """Test recuperación de errores"""
        handler = ErrorHandler()

        # Mock de función que falla
        mock_func = Mock(side_effect=[CommunicationError("Network error"), "Success"])

        # Test recuperación exitosa
        result = handler.handle_with_recovery(mock_func)
        assert result == "Success"
        assert mock_func.call_count == 2

    def test_error_statistics(self):
        """Test estadísticas de errores"""
        handler = ErrorHandler()

        # Simular errores
        error1 = ValidationError("Error 1")
        error2 = CommunicationError("Error 2")

        handler.classify_error(error1)
        handler.classify_error(error2)

        stats = handler.get_error_statistics()
        assert stats['total_errors'] == 2
        assert stats['by_category']['validation'] == 1
        assert stats['by_category']['communication'] == 1


class TestSiiErrorHandler:
    """Tests para SiiErrorHandler"""

    def test_sii_error_handler_initialization(self):
        """Test inicialización de SiiErrorHandler"""
        handler = SiiErrorHandler()
        assert isinstance(handler, SiiErrorHandler)

    def test_sii_specific_errors(self):
        """Test manejo de errores específicos del SII"""
        handler = SiiErrorHandler()

        # Test error de autenticación
        error = CommunicationError("Authentication failed")
        error.sii_code = "AUTH_ERROR"

        severity, category = handler.classify_error(error)
        assert severity == ErrorSeverity.HIGH
        assert category == ErrorCategory.AUTHENTICATION


class TestPerformanceMonitor:
    """Tests para el monitor de performance"""

    def test_performance_monitor_initialization(self):
        """Test inicialización del monitor"""
        monitor = PerformanceMonitor()
        assert monitor.monitoring_level.value == "standard"

    def test_operation_timing(self):
        """Test medición de tiempo de operaciones"""
        monitor = PerformanceMonitor()

        with monitor.measure_operation("test_op"):
            time.sleep(0.01)

        metrics = monitor.get_metrics()
        assert "test_op" in metrics
        assert metrics["test_op"]["count"] == 1
        assert metrics["test_op"]["avg_time"] > 0

    def test_alert_thresholds(self):
        """Test umbrales de alerta"""
        monitor = PerformanceMonitor()
        monitor.set_alert_threshold("slow_op", max_time=0.001)  # Umbral muy bajo

        alerts = []
        def alert_handler(metric, threshold, value):
            alerts.append((metric, threshold, value))

        monitor.set_alert_handler(alert_handler)

        with monitor.measure_operation("slow_op"):
            time.sleep(0.01)  # Operación lenta

        assert len(alerts) > 0
        assert alerts[0][0] == "slow_op"


class TestMetricsCollector:
    """Tests para el colector de métricas"""

    def test_metrics_collector_initialization(self):
        """Test inicialización del colector"""
        collector = MetricsCollector()
        assert collector.collection_interval == 60

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_system_metrics_collection(self, mock_memory, mock_cpu):
        """Test recolección de métricas del sistema"""
        # Mock system metrics
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0, available=1000000)

        collector = MetricsCollector()
        metrics = collector.collect_system_metrics()

        assert 'cpu_percent' in metrics
        assert 'memory_percent' in metrics
        assert metrics['cpu_percent'] == 50.0
        assert metrics['memory_percent'] == 60.0


class TestDebugCollector:
    """Tests para el colector de debug"""

    def test_debug_collector_initialization(self):
        """Test inicialización del debug collector"""
        collector = DebugCollector()
        assert collector.debug_level == DebugLevel.INFO

    def test_debug_session_management(self):
        """Test manejo de sesiones de debug"""
        collector = DebugCollector()

        session_id = collector.start_debug_session("test_operation")
        assert session_id is not None

        sessions = collector.get_active_sessions()
        assert session_id in [s.session_id for s in sessions]

        collector.end_debug_session(session_id)
        sessions = collector.get_active_sessions()
        assert session_id not in [s.session_id for s in sessions]

    def test_debug_info_collection(self):
        """Test recolección de información de debug"""
        collector = DebugCollector()

        session_id = collector.start_debug_session("test_operation")
        collector.collect_debug_info(session_id, "Test debug info", {"key": "value"})

        session = next((s for s in collector.get_active_sessions() if s.session_id == session_id), None)
        assert session is not None
        assert len(session.debug_entries) == 1
        assert session.debug_entries[0].message == "Test debug info"


class TestLoggingContext:
    """Tests para el contexto de logging"""

    def test_context_stack_management(self):
        """Test manejo de la pila de contextos"""
        # Limpiar contexto previo
        LoggingContext.clear_context()

        # Verificar contexto vacío
        assert LoggingContext.get_current_context() is None

        # Crear y pushear contexto
        from rypsystems_dte.logging.context import ContextData, ContextType
        context = ContextData(operation="test", context_type=ContextType.OPERATION)

        context_id = LoggingContext.push_context(context)
        assert context_id == context.context_id

        # Verificar contexto actual
        current = LoggingContext.get_current_context()
        assert current is not None
        assert current.operation == "test"

        # Pop contexto
        popped = LoggingContext.pop_context()
        assert popped.context_id == context_id
        assert LoggingContext.get_current_context() is None

    def test_nested_contexts(self):
        """Test contextos anidados"""
        LoggingContext.clear_context()

        from rypsystems_dte.logging.context import ContextData, ContextType

        # Contexto padre
        parent_context = ContextData(operation="parent", context_type=ContextType.OPERATION)
        LoggingContext.push_context(parent_context)

        # Contexto hijo
        child_context = ContextData(operation="child", context_type=ContextType.REQUEST)
        LoggingContext.push_context(child_context)

        # Verificar parent_context_id
        current = LoggingContext.get_current_context()
        assert current.operation == "child"
        assert current.parent_context_id == parent_context.context_id

        # Limpiar
        LoggingContext.clear_context()


class TestOperationContext:
    """Tests para OperationContext"""

    def test_operation_context_manager(self):
        """Test context manager de operaciones"""
        LoggingContext.clear_context()

        with OperationContext("test_operation", document_type="factura", folio=1001) as ctx:
            current = LoggingContext.get_current_context()
            assert current is not None
            assert current.operation == "test_operation"
            assert current.metadata['document_type'] == "factura"
            assert current.metadata['folio'] == 1001

        # Verificar que el contexto se limpió
        assert LoggingContext.get_current_context() is None

    def test_operation_context_with_error(self):
        """Test context manager con error"""
        LoggingContext.clear_context()

        try:
            with OperationContext("failing_operation") as ctx:
                raise ValueError("Test error")
        except ValueError:
            pass

        # El contexto debe limpiarse incluso con errores
        assert LoggingContext.get_current_context() is None


class TestSiiContext:
    """Tests para SiiContext"""

    def test_sii_context_manager(self):
        """Test context manager SII"""
        LoggingContext.clear_context()

        with SiiContext("envio_dte", ambiente="certificacion", empresa_rut="76354771-K") as ctx:
            current = LoggingContext.get_current_context()
            assert current is not None
            assert current.operation == "sii_envio_dte"
            assert current.metadata['ambiente'] == "certificacion"
            assert current.metadata['empresa_rut'] == "76354771-K"
            assert 'sii' in current.tags
            assert 'certificacion' in current.tags

        assert LoggingContext.get_current_context() is None

    def test_sii_context_request_response(self):
        """Test información de request/response en SiiContext"""
        LoggingContext.clear_context()

        with SiiContext("consulta_estado") as ctx:
            ctx.set_request_info("/api/consulta", {"Authorization": "Bearer token"})
            ctx.set_response_info(200, 0.5)

            current = LoggingContext.get_current_context()
            assert current.metadata['sii_endpoint'] == "/api/consulta"
            assert current.metadata['sii_status_code'] == 200
            assert current.metadata['sii_response_time_ms'] == 500


class TestContextManager:
    """Tests para ContextManager"""

    def test_context_manager_operation(self):
        """Test ContextManager.operation"""
        LoggingContext.clear_context()

        with ContextManager.operation("test_op", document_type="boleta") as ctx:
            current_ctx = ContextManager.get_current_context()
            assert current_ctx['operation'] == "test_op"
            assert current_ctx['metadata']['document_type'] == "boleta"

        assert LoggingContext.get_current_context() is None

    def test_context_manager_sii_operation(self):
        """Test ContextManager.sii_operation"""
        LoggingContext.clear_context()

        with ContextManager.sii_operation("envio", ambiente="produccion") as ctx:
            current_ctx = ContextManager.get_current_context()
            assert current_ctx['operation'] == "sii_envio"
            assert current_ctx['metadata']['ambiente'] == "produccion"

        assert LoggingContext.get_current_context() is None


class TestIntegration:
    """Tests de integración del sistema completo"""

    def test_complete_logging_flow(self):
        """Test flujo completo de logging con contexto y errores"""
        LoggingContext.clear_context()

        # Configurar logger y error handler
        logger = DTELogger("integration_test", output_file=None)
        error_handler = ErrorHandler()

        with patch('builtins.print') as mock_print:
            with OperationContext("generate_invoice", document_type="factura", folio=1001):
                try:
                    # Simular operación que falla
                    raise ValidationError("Invalid RUT format")
                except ValidationError as e:
                    # Manejar error
                    severity, category = error_handler.classify_error(e)
                    logger.error(f"Operation failed: {e}",
                               error_type=type(e).__name__,
                               error_severity=severity.value,
                               error_category=category.value)

        # Verificar que se loggeó correctamente
        assert mock_print.called
        args = mock_print.call_args[0][0]
        log_data = json.loads(args)

        assert log_data['level'] == "ERROR"
        assert "Operation failed" in log_data['message']
        assert log_data['error_type'] == "ValidationError"
        assert log_data['context']['operation'] == "generate_invoice"
        assert log_data['context']['metadata']['document_type'] == "factura"

    def test_performance_monitoring_with_context(self):
        """Test monitoreo de performance con contexto"""
        LoggingContext.clear_context()

        monitor = PerformanceMonitor()

        with OperationContext("performance_test"):
            with monitor.measure_operation("test_operation"):
                time.sleep(0.01)

        metrics = monitor.get_metrics()
        assert "test_operation" in metrics
        assert metrics["test_operation"]["count"] == 1

    def test_threading_context_isolation(self):
        """Test aislamiento de contexto entre threads"""
        results = {}

        def thread_function(thread_id):
            LoggingContext.clear_context()

            with OperationContext(f"thread_operation_{thread_id}"):
                time.sleep(0.01)  # Simular trabajo
                current = LoggingContext.get_current_context()
                results[thread_id] = current.operation if current else None

        # Crear y ejecutar threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_function, args=(i,))
            threads.append(thread)
            thread.start()

        # Esperar threads
        for thread in threads:
            thread.join()

        # Verificar aislamiento
        assert len(results) == 3
        assert results[0] == "thread_operation_0"
        assert results[1] == "thread_operation_1"
        assert results[2] == "thread_operation_2"


if __name__ == "__main__":
    pytest.main([__file__])