"""
Sistema de Monitoreo de Rendimiento y Recolección de Métricas.

Proporciona monitoreo comprensivo de rendimiento incluyendo:
- Métricas de tiempo de ejecución
- Uso de memoria y recursos
- Métricas de negocio (documentos procesados, etc.)
- Alertas basadas en umbrales
- Dashboards de rendimiento
"""

import time
import psutil
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
from statistics import mean, median

from pydantic import BaseModel, Field, field_validator, ConfigDict

from .logger import StructuredLogger, LogLevel, LogContext, get_logger


class MonitoringLevel(str, Enum):
    """Nivel de monitoreo."""
    BASIC = "basic"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"


class AlertThreshold(BaseModel):
    """Umbral de alerta."""

    metric_name: str = Field(..., description="Nombre de la métrica")
    warning_threshold: float = Field(..., description="Umbral de warning")
    critical_threshold: float = Field(..., description="Umbral crítico")
    duration_seconds: int = Field(default=60, description="Duración para activar alerta")
    enabled: bool = Field(default=True, description="Si está habilitada")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class PerformanceMetric(BaseModel):
    """Métrica de rendimiento."""

    name: str = Field(..., description="Nombre de la métrica")
    value: float = Field(..., description="Valor de la métrica")
    unit: str = Field(..., description="Unidad de medida")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    category: str = Field(..., description="Categoría de la métrica")
    tags: Dict[str, str] = Field(default_factory=dict, description="Tags adicionales")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class SystemHealth(BaseModel):
    """Estado de salud del sistema."""

    status: str = Field(..., description="Estado general (healthy, warning, critical)")
    cpu_usage: float = Field(..., description="Uso de CPU (%)")
    memory_usage: float = Field(..., description="Uso de memoria (%)")
    disk_usage: float = Field(..., description="Uso de disco (%)")
    network_active: bool = Field(..., description="Si la red está activa")

    # Métricas de aplicación
    active_operations: int = Field(default=0, description="Operaciones activas")
    error_rate: float = Field(default=0.0, description="Tasa de errores (%)")
    average_response_time: float = Field(default=0.0, description="Tiempo de respuesta promedio (ms)")

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class MetricsCollector:
    """
    Recolector de métricas del sistema.

    Recolecta métricas de sistema y aplicación incluyendo:
    - CPU, memoria, disco
    - Métricas de red
    - Métricas de aplicación personalizadas
    """

    def __init__(self,
                 collection_interval: int = 30,
                 max_history_size: int = 1000):
        """
        Inicializa el recolector de métricas.

        Args:
            collection_interval: Intervalo de recolección en segundos
            max_history_size: Tamaño máximo del historial
        """
        self.collection_interval = collection_interval
        self.max_history_size = max_history_size

        # Almacenamiento de métricas
        self.metrics_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history_size)
        )
        self.current_metrics: Dict[str, PerformanceMetric] = {}

        # Control de recolección
        self._collecting = False
        self._collection_thread: Optional[threading.Thread] = None

        # Métricas personalizadas
        self.custom_metrics: Dict[str, Callable] = {}

    def start_collection(self):
        """Inicia la recolección automática de métricas."""
        if self._collecting:
            return

        self._collecting = True
        self._collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self._collection_thread.start()

    def stop_collection(self):
        """Detiene la recolección automática."""
        self._collecting = False
        if self._collection_thread:
            self._collection_thread.join()

    def _collection_loop(self):
        """Loop principal de recolección."""
        while self._collecting:
            try:
                self.collect_system_metrics()
                self.collect_custom_metrics()
                time.sleep(self.collection_interval)
            except Exception as e:
                # Log error but continue collection
                print(f"Error in metrics collection: {e}")

    def collect_system_metrics(self):
        """Recolecta métricas del sistema."""
        timestamp = datetime.now(timezone.utc)

        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        self._store_metric(PerformanceMetric(
            name="cpu_usage",
            value=cpu_percent,
            unit="percent",
            timestamp=timestamp,
            category="system"
        ))

        # Memoria
        memory = psutil.virtual_memory()
        self._store_metric(PerformanceMetric(
            name="memory_usage",
            value=memory.percent,
            unit="percent",
            timestamp=timestamp,
            category="system"
        ))

        self._store_metric(PerformanceMetric(
            name="memory_available",
            value=memory.available / (1024 * 1024 * 1024),  # GB
            unit="gb",
            timestamp=timestamp,
            category="system"
        ))

        # Disco
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        self._store_metric(PerformanceMetric(
            name="disk_usage",
            value=disk_percent,
            unit="percent",
            timestamp=timestamp,
            category="system"
        ))

        # Red
        net_io = psutil.net_io_counters()
        if hasattr(self, '_last_net_io'):
            bytes_sent_per_sec = (net_io.bytes_sent - self._last_net_io.bytes_sent) / self.collection_interval
            bytes_recv_per_sec = (net_io.bytes_recv - self._last_net_io.bytes_recv) / self.collection_interval

            self._store_metric(PerformanceMetric(
                name="network_sent",
                value=bytes_sent_per_sec / (1024 * 1024),  # MB/s
                unit="mb_per_sec",
                timestamp=timestamp,
                category="network"
            ))

            self._store_metric(PerformanceMetric(
                name="network_received",
                value=bytes_recv_per_sec / (1024 * 1024),  # MB/s
                unit="mb_per_sec",
                timestamp=timestamp,
                category="network"
            ))

        self._last_net_io = net_io

    def collect_custom_metrics(self):
        """Recolecta métricas personalizadas."""
        for name, metric_function in self.custom_metrics.items():
            try:
                metric = metric_function()
                if isinstance(metric, PerformanceMetric):
                    self._store_metric(metric)
                elif isinstance(metric, (int, float)):
                    self._store_metric(PerformanceMetric(
                        name=name,
                        value=float(metric),
                        unit="count",
                        category="custom"
                    ))
            except Exception as e:
                print(f"Error collecting custom metric {name}: {e}")

    def _store_metric(self, metric: PerformanceMetric):
        """Almacena una métrica."""
        self.current_metrics[metric.name] = metric
        self.metrics_history[metric.name].append(metric)

    def add_custom_metric(self, name: str, metric_function: Callable):
        """Agrega una métrica personalizada."""
        self.custom_metrics[name] = metric_function

    def get_metric(self, name: str) -> Optional[PerformanceMetric]:
        """Obtiene la métrica actual."""
        return self.current_metrics.get(name)

    def get_metric_history(self, name: str, hours: int = 1) -> List[PerformanceMetric]:
        """Obtiene historial de una métrica."""
        if name not in self.metrics_history:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            metric for metric in self.metrics_history[name]
            if metric.timestamp >= cutoff_time
        ]

    def get_metric_statistics(self, name: str, hours: int = 1) -> Dict[str, float]:
        """Obtiene estadísticas de una métrica."""
        history = self.get_metric_history(name, hours)
        if not history:
            return {}

        values = [metric.value for metric in history]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": mean(values),
            "median": median(values)
        }


class PerformanceMonitor:
    """
    Monitor de rendimiento de aplicación.

    Proporciona monitoreo comprensivo incluyendo:
    - Timing de operaciones
    - Métricas de throughput
    - Detección de anomalías
    - Alertas automáticas
    """

    def __init__(self,
                 logger: Optional[StructuredLogger] = None,
                 monitoring_level: MonitoringLevel = MonitoringLevel.DETAILED,
                 enable_alerts: bool = True):
        """
        Inicializa el monitor de rendimiento.

        Args:
            logger: Logger para métricas
            monitoring_level: Nivel de monitoreo
            enable_alerts: Si habilitar alertas
        """
        self.logger = logger or get_logger("performance_monitor")
        self.monitoring_level = monitoring_level
        self.enable_alerts = enable_alerts

        # Recolector de métricas
        self.metrics_collector = MetricsCollector()

        # Timing de operaciones
        self.operation_timings: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self.active_operations: Dict[str, float] = {}

        # Contadores
        self.counters: Dict[str, int] = defaultdict(int)

        # Umbrales de alerta
        self.alert_thresholds: Dict[str, AlertThreshold] = {}

        # Estado de alertas
        self.active_alerts: Dict[str, datetime] = {}

        # Configurar umbrales por defecto
        self._setup_default_thresholds()

        # Iniciar recolección si es necesario
        if monitoring_level in [MonitoringLevel.DETAILED, MonitoringLevel.COMPREHENSIVE]:
            self.metrics_collector.start_collection()

    def _setup_default_thresholds(self):
        """Configura umbrales por defecto."""
        self.alert_thresholds.update({
            "cpu_usage": AlertThreshold(
                metric_name="cpu_usage",
                warning_threshold=70.0,
                critical_threshold=90.0
            ),
            "memory_usage": AlertThreshold(
                metric_name="memory_usage",
                warning_threshold=80.0,
                critical_threshold=95.0
            ),
            "disk_usage": AlertThreshold(
                metric_name="disk_usage",
                warning_threshold=85.0,
                critical_threshold=95.0
            ),
            "response_time": AlertThreshold(
                metric_name="avg_response_time",
                warning_threshold=5000.0,  # 5 segundos
                critical_threshold=10000.0  # 10 segundos
            ),
            "error_rate": AlertThreshold(
                metric_name="error_rate",
                warning_threshold=5.0,  # 5%
                critical_threshold=10.0  # 10%
            )
        })

    def start_operation(self, operation_name: str, context: Optional[LogContext] = None) -> str:
        """
        Inicia el timing de una operación.

        Args:
            operation_name: Nombre de la operación
            context: Contexto de logging

        Returns:
            ID único de la operación
        """
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"
        self.active_operations[operation_id] = time.time()

        if self.monitoring_level in [MonitoringLevel.DETAILED, MonitoringLevel.COMPREHENSIVE]:
            self.logger.debug(
                f"Operation started: {operation_name}",
                event_type="operation_start",
                category="performance",
                context=context,
                extra_data={"operation_id": operation_id}
            )

        return operation_id

    def end_operation(self,
                     operation_id: str,
                     operation_name: str = None,
                     success: bool = True,
                     context: Optional[LogContext] = None,
                     **kwargs):
        """
        Termina el timing de una operación.

        Args:
            operation_id: ID de la operación
            operation_name: Nombre de la operación
            success: Si la operación fue exitosa
            context: Contexto de logging
        """
        if operation_id not in self.active_operations:
            return

        start_time = self.active_operations.pop(operation_id)
        duration_ms = (time.time() - start_time) * 1000

        # Extraer nombre de operación del ID si no se proporciona
        if not operation_name:
            operation_name = operation_id.split('_')[0]

        # Almacenar timing
        self.operation_timings[operation_name].append(duration_ms)

        # Actualizar contadores
        self.counters[f"{operation_name}_total"] += 1
        if success:
            self.counters[f"{operation_name}_success"] += 1
        else:
            self.counters[f"{operation_name}_error"] += 1

        # Log de performance
        level = LogLevel.INFO if success else LogLevel.WARNING
        self.logger.log(
            level,
            f"Operation completed: {operation_name} in {duration_ms:.2f}ms",
            event_type="operation_complete",
            category="performance",
            context=context,
            execution_time_ms=duration_ms,
            extra_data={
                "operation_id": operation_id,
                "success": success,
                **kwargs
            }
        )

        # Verificar umbrales
        if self.enable_alerts:
            self._check_performance_thresholds(operation_name, duration_ms)

    def record_metric(self, name: str, value: float, unit: str = "count", **kwargs):
        """Registra una métrica personalizada."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            category="application",
            **kwargs
        )

        self.metrics_collector._store_metric(metric)

        if self.monitoring_level == MonitoringLevel.COMPREHENSIVE:
            self.logger.debug(
                f"Metric recorded: {name} = {value} {unit}",
                event_type="metric_recorded",
                category="metrics",
                extra_data={"metric_name": name, "value": value, "unit": unit}
            )

    def increment_counter(self, name: str, value: int = 1):
        """Incrementa un contador."""
        self.counters[name] += value

        if self.monitoring_level == MonitoringLevel.COMPREHENSIVE:
            self.logger.trace(
                f"Counter incremented: {name} += {value} (total: {self.counters[name]})",
                event_type="counter_increment",
                category="metrics"
            )

    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """Obtiene estadísticas de una operación."""
        timings = list(self.operation_timings.get(operation_name, []))
        if not timings:
            return {}

        total = self.counters.get(f"{operation_name}_total", 0)
        success = self.counters.get(f"{operation_name}_success", 0)
        errors = self.counters.get(f"{operation_name}_error", 0)

        return {
            "operation_name": operation_name,
            "total_calls": total,
            "successful_calls": success,
            "failed_calls": errors,
            "success_rate": (success / total * 100) if total > 0 else 0,
            "avg_duration_ms": mean(timings),
            "min_duration_ms": min(timings),
            "max_duration_ms": max(timings),
            "median_duration_ms": median(timings),
            "recent_calls": len(timings)
        }

    def get_system_health(self) -> SystemHealth:
        """Obtiene el estado de salud del sistema."""
        # Métricas de sistema
        cpu_metric = self.metrics_collector.get_metric("cpu_usage")
        memory_metric = self.metrics_collector.get_metric("memory_usage")
        disk_metric = self.metrics_collector.get_metric("disk_usage")

        cpu_usage = cpu_metric.value if cpu_metric else 0.0
        memory_usage = memory_metric.value if memory_metric else 0.0
        disk_usage = disk_metric.value if disk_metric else 0.0

        # Métricas de aplicación
        active_ops = len(self.active_operations)

        # Calcular tasa de errores
        total_ops = sum(v for k, v in self.counters.items() if k.endswith('_total'))
        error_ops = sum(v for k, v in self.counters.items() if k.endswith('_error'))
        error_rate = (error_ops / total_ops * 100) if total_ops > 0 else 0.0

        # Calcular tiempo de respuesta promedio
        all_timings = []
        for timings in self.operation_timings.values():
            all_timings.extend(list(timings)[-10:])  # Últimas 10 de cada operación
        avg_response_time = mean(all_timings) if all_timings else 0.0

        # Determinar estado general
        status = "healthy"
        if cpu_usage > 90 or memory_usage > 95 or disk_usage > 95 or error_rate > 10:
            status = "critical"
        elif cpu_usage > 70 or memory_usage > 80 or disk_usage > 85 or error_rate > 5:
            status = "warning"

        return SystemHealth(
            status=status,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            network_active=True,  # Simplificado
            active_operations=active_ops,
            error_rate=error_rate,
            average_response_time=avg_response_time
        )

    def _check_performance_thresholds(self, operation_name: str, duration_ms: float):
        """Verifica umbrales de rendimiento."""
        threshold = self.alert_thresholds.get("response_time")
        if not threshold or not threshold.enabled:
            return

        alert_key = f"response_time_{operation_name}"

        if duration_ms >= threshold.critical_threshold:
            if alert_key not in self.active_alerts:
                self.active_alerts[alert_key] = datetime.now(timezone.utc)
                self.logger.critical(
                    f"CRITICAL: Operation {operation_name} took {duration_ms:.2f}ms (threshold: {threshold.critical_threshold}ms)",
                    event_type="performance_alert",
                    category="alert",
                    extra_data={
                        "alert_level": "critical",
                        "metric": "response_time",
                        "value": duration_ms,
                        "threshold": threshold.critical_threshold
                    }
                )
        elif duration_ms >= threshold.warning_threshold:
            if alert_key not in self.active_alerts:
                self.active_alerts[alert_key] = datetime.now(timezone.utc)
                self.logger.warning(
                    f"WARNING: Operation {operation_name} took {duration_ms:.2f}ms (threshold: {threshold.warning_threshold}ms)",
                    event_type="performance_alert",
                    category="alert",
                    extra_data={
                        "alert_level": "warning",
                        "metric": "response_time",
                        "value": duration_ms,
                        "threshold": threshold.warning_threshold
                    }
                )
        else:
            # Limpiar alerta si el valor está por debajo del umbral
            if alert_key in self.active_alerts:
                del self.active_alerts[alert_key]

    def add_alert_threshold(self, threshold: AlertThreshold):
        """Agrega un umbral de alerta."""
        self.alert_thresholds[threshold.metric_name] = threshold

    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de rendimiento."""
        system_health = self.get_system_health()

        # Estadísticas de operaciones
        operation_stats = {}
        for operation_name in self.operation_timings.keys():
            operation_stats[operation_name] = self.get_operation_stats(operation_name)

        return {
            "system_health": system_health.model_dump(),
            "operation_statistics": operation_stats,
            "active_alerts": list(self.active_alerts.keys()),
            "total_counters": dict(self.counters),
            "monitoring_level": self.monitoring_level.value
        }


class SiiPerformanceMonitor(PerformanceMonitor):
    """
    Monitor de rendimiento específico para SII.

    Extiende el monitor base con métricas específicas para comunicación SII.
    """

    def __init__(self, **kwargs):
        """Inicializa monitor de rendimiento SII."""
        super().__init__(**kwargs)

        # Umbrales específicos para SII
        self.add_alert_threshold(AlertThreshold(
            metric_name="sii_response_time",
            warning_threshold=10000.0,  # 10 segundos
            critical_threshold=30000.0  # 30 segundos
        ))

        self.add_alert_threshold(AlertThreshold(
            metric_name="sii_error_rate",
            warning_threshold=2.0,  # 2%
            critical_threshold=5.0  # 5%
        ))

    def monitor_sii_request(self,
                          endpoint: str,
                          operation: str,
                          context: Optional[LogContext] = None) -> str:
        """Inicia monitoreo de request SII."""
        operation_name = f"sii_{operation}"
        operation_id = self.start_operation(operation_name, context)

        # Incrementar contador de requests SII
        self.increment_counter("sii_requests_total")
        self.increment_counter(f"sii_requests_{endpoint}")

        return operation_id

    def complete_sii_request(self,
                           operation_id: str,
                           endpoint: str,
                           status_code: int,
                           success: bool = True,
                           context: Optional[LogContext] = None):
        """Completa monitoreo de request SII."""
        operation_name = f"sii_{endpoint}"

        self.end_operation(
            operation_id,
            operation_name,
            success,
            context,
            endpoint=endpoint,
            status_code=status_code
        )

        # Actualizar contadores específicos de SII
        if success:
            self.increment_counter("sii_requests_success")
        else:
            self.increment_counter("sii_requests_error")

        self.increment_counter(f"sii_status_{status_code}")

    def record_document_processing(self,
                                 document_type: str,
                                 processing_time_ms: float,
                                 success: bool = True):
        """Registra procesamiento de documento."""
        self.record_metric(
            f"document_processing_{document_type}",
            processing_time_ms,
            "milliseconds"
        )

        if success:
            self.increment_counter(f"documents_processed_{document_type}")
        else:
            self.increment_counter(f"documents_failed_{document_type}")

    def get_sii_performance_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de rendimiento específico para SII."""
        base_summary = self.get_performance_summary()

        # Métricas específicas de SII
        sii_metrics = {
            "sii_requests_total": self.counters.get("sii_requests_total", 0),
            "sii_requests_success": self.counters.get("sii_requests_success", 0),
            "sii_requests_error": self.counters.get("sii_requests_error", 0),
            "sii_error_rate": 0.0
        }

        # Calcular tasa de errores SII
        total_sii = sii_metrics["sii_requests_total"]
        if total_sii > 0:
            sii_metrics["sii_error_rate"] = (
                sii_metrics["sii_requests_error"] / total_sii * 100
            )

        # Estadísticas por endpoint
        endpoint_stats = {}
        for operation_name in self.operation_timings.keys():
            if operation_name.startswith("sii_"):
                endpoint_stats[operation_name] = self.get_operation_stats(operation_name)

        base_summary.update({
            "sii_metrics": sii_metrics,
            "sii_endpoint_stats": endpoint_stats
        })

        return base_summary