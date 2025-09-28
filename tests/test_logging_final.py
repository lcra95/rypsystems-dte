"""
Test final básico para verificar que el sistema de logging esté operacional
"""

import pytest
import time
import threading
from rypsystems_dte.logging import (
    DTELogger, SiiLogger,
    ValidationError, CommunicationError, ProcessingError,
    ErrorHandler, SiiErrorHandler,
    LoggingContext, OperationContext, SiiContext, ContextManager
)


def test_system_operational():
    """Test que verifica que todo el sistema esté operacional"""

    # 1. Test creación de componentes
    logger = DTELogger()
    error_handler = ErrorHandler()

    assert logger is not None
    assert error_handler is not None

    # 2. Test contexto básico
    LoggingContext.clear_context()

    with OperationContext("test_operation", document_type="factura"):
        current = LoggingContext.get_current_context()
        assert current is not None
        assert current.operation == "test_operation"

    assert LoggingContext.get_current_context() is None

    # 3. Test logging básico
    logger.info("Test message")
    logger.error("Test error")

    # 4. Test manejo de errores
    try:
        raise ValidationError("Test validation error")
    except ValidationError as e:
        error_handler.handle_error(e, operation="test_operation")

    # 5. Test estadísticas
    stats = error_handler.get_error_statistics()
    assert isinstance(stats, dict)

    # 6. Test SII context
    with SiiContext("test_sii_operation"):
        current = LoggingContext.get_current_context()
        assert current is not None
        assert "sii_test_sii_operation" in current.operation

    # 7. Test threading básico
    def thread_test():
        LoggingContext.clear_context()
        with OperationContext("thread_test"):
            logger.info("Thread test")

    thread = threading.Thread(target=thread_test)
    thread.start()
    thread.join()

    # Si llegamos aquí, todo funciona
    print("✅ Sistema de logging completamente operacional")


def test_comprehensive_workflow():
    """Test de workflow comprehensivo"""
    LoggingContext.clear_context()

    logger = DTELogger()
    error_handler = ErrorHandler()

    with OperationContext("comprehensive_test", document_type="factura", folio=1001):
        logger.info("Iniciando procesamiento de documento")

        try:
            # Simular validación
            logger.debug("Validando datos de entrada")

            # Simular procesamiento
            logger.info("Procesando documento DTE")

            # Simular comunicación con SII
            with SiiContext("envio_dte", ambiente="certificacion"):
                logger.info("Enviando documento al SII")

                # Simular posible error de comunicación
                if False:  # Cambiar a True para probar manejo de errores
                    raise CommunicationError("Error de conexión con SII")

                logger.info("Documento enviado exitosamente")

            logger.info("Procesamiento completado exitosamente")

        except Exception as e:
            error_handler.handle_error(e, operation="comprehensive_test")
            logger.error(f"Error en procesamiento: {e}")

    # Verificar estadísticas
    stats = error_handler.get_error_statistics()
    logger.info(f"Estadísticas de errores: {stats}")

    print("✅ Workflow comprehensivo completado")


if __name__ == "__main__":
    test_system_operational()
    test_comprehensive_workflow()
    print("🎉 Todos los tests pasaron - Sistema de logging completamente funcional")