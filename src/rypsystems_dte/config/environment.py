"""
Environment Configuration - Gestión de configuraciones por ambiente

Maneja configuraciones específicas para diferentes ambientes de deployment
(desarrollo, certificación, producción).
"""

import os
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ConfigDict


class Environment(str, Enum):
    """Ambientes soportados"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    CERTIFICATION = "certification"
    PRODUCTION = "production"


class LoggingConfig(BaseModel):
    """Configuración de logging por ambiente"""
    model_config = ConfigDict(extra='allow')

    level: str = Field(default="INFO", description="Nivel de logging")
    format: str = Field(default="json", description="Formato de logs")
    output: str = Field(default="console", description="Destino de logs")
    file_path: Optional[str] = Field(None, description="Ruta de archivo de logs")
    max_file_size: int = Field(default=10485760, description="Tamaño máximo de archivo (bytes)")
    backup_count: int = Field(default=5, description="Número de archivos de backup")
    console_output: bool = Field(default=True, description="Habilitar salida a consola")


class DatabaseConfig(BaseModel):
    """Configuración de base de datos"""
    model_config = ConfigDict(extra='allow')

    host: str = Field(default="localhost", description="Host de la base de datos")
    port: int = Field(default=5432, description="Puerto de la base de datos")
    database: str = Field(default="rypsystems_dte", description="Nombre de la base de datos")
    username: Optional[str] = Field(None, description="Usuario de la base de datos")
    password: Optional[str] = Field(None, description="Contraseña de la base de datos")
    ssl_mode: str = Field(default="prefer", description="Modo SSL")
    pool_size: int = Field(default=10, description="Tamaño del pool de conexiones")
    pool_timeout: int = Field(default=30, description="Timeout del pool (segundos)")


class CacheConfig(BaseModel):
    """Configuración de cache"""
    model_config = ConfigDict(extra='allow')

    enabled: bool = Field(default=True, description="Habilitar cache")
    backend: str = Field(default="memory", description="Backend de cache (memory, redis)")
    ttl: int = Field(default=3600, description="TTL por defecto (segundos)")
    max_size: int = Field(default=1000, description="Tamaño máximo de cache")
    redis_url: Optional[str] = Field(None, description="URL de Redis")


class SecurityConfig(BaseModel):
    """Configuración de seguridad"""
    model_config = ConfigDict(extra='allow')

    validate_certificates: bool = Field(default=True, description="Validar certificados SSL")
    certificate_path: Optional[str] = Field(None, description="Ruta de certificados")
    private_key_path: Optional[str] = Field(None, description="Ruta de llaves privadas")
    ca_bundle_path: Optional[str] = Field(None, description="Ruta del bundle de CA")
    encryption_key: Optional[str] = Field(None, description="Llave de encriptación")
    token_expiry: int = Field(default=3600, description="Expiración de tokens (segundos)")


class PerformanceConfig(BaseModel):
    """Configuración de performance"""
    model_config = ConfigDict(extra='allow')

    max_concurrent_requests: int = Field(default=10, description="Máximo requests concurrentes")
    request_timeout: int = Field(default=30, description="Timeout de requests (segundos)")
    retry_attempts: int = Field(default=3, description="Intentos de reintento")
    retry_delay: float = Field(default=1.0, description="Delay entre reintentos (segundos)")
    enable_gzip: bool = Field(default=True, description="Habilitar compresión GZIP")
    connection_pool_size: int = Field(default=20, description="Tamaño del pool de conexiones")


class EnvironmentConfig(BaseModel):
    """
    Configuración completa para un ambiente específico

    Agrupa todas las configuraciones necesarias para un ambiente de deployment.
    """
    model_config = ConfigDict(extra='allow')

    # Información del ambiente
    name: Environment = Field(description="Nombre del ambiente")
    debug: bool = Field(default=False, description="Modo debug")
    testing: bool = Field(default=False, description="Modo testing")

    # Configuraciones por componente
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: Optional[DatabaseConfig] = Field(None, description="Configuración de DB")
    cache: CacheConfig = Field(default_factory=CacheConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)

    # Configuraciones adicionales
    extra_config: Dict[str, Any] = Field(default_factory=dict, description="Configuraciones adicionales")

    @classmethod
    def development(cls) -> 'EnvironmentConfig':
        """Configuración para ambiente de desarrollo"""
        return cls(
            name=Environment.DEVELOPMENT,
            debug=True,
            testing=False,
            logging=LoggingConfig(
                level="DEBUG",
                format="text",
                output="console",
                console_output=True
            ),
            cache=CacheConfig(
                enabled=False,
                backend="memory"
            ),
            security=SecurityConfig(
                validate_certificates=False
            ),
            performance=PerformanceConfig(
                max_concurrent_requests=5,
                request_timeout=60
            )
        )

    @classmethod
    def testing(cls) -> 'EnvironmentConfig':
        """Configuración para ambiente de testing"""
        return cls(
            name=Environment.TESTING,
            debug=True,
            testing=True,
            logging=LoggingConfig(
                level="DEBUG",
                format="json",
                output="console"
            ),
            cache=CacheConfig(
                enabled=False
            ),
            security=SecurityConfig(
                validate_certificates=False
            ),
            performance=PerformanceConfig(
                max_concurrent_requests=3,
                request_timeout=30
            )
        )

    @classmethod
    def staging(cls) -> 'EnvironmentConfig':
        """Configuración para ambiente de staging"""
        return cls(
            name=Environment.STAGING,
            debug=False,
            testing=False,
            logging=LoggingConfig(
                level="INFO",
                format="json",
                output="file",
                file_path="/var/log/rypsystems_dte/app.log"
            ),
            cache=CacheConfig(
                enabled=True,
                backend="redis"
            ),
            security=SecurityConfig(
                validate_certificates=True
            ),
            performance=PerformanceConfig(
                max_concurrent_requests=15,
                request_timeout=30
            )
        )

    @classmethod
    def certification(cls) -> 'EnvironmentConfig':
        """Configuración para ambiente de certificación SII"""
        return cls(
            name=Environment.CERTIFICATION,
            debug=False,
            testing=False,
            logging=LoggingConfig(
                level="INFO",
                format="json",
                output="file",
                file_path="/var/log/rypsystems_dte/certification.log"
            ),
            cache=CacheConfig(
                enabled=True,
                backend="memory",
                ttl=1800  # 30 minutos para certificación
            ),
            security=SecurityConfig(
                validate_certificates=True
            ),
            performance=PerformanceConfig(
                max_concurrent_requests=10,
                request_timeout=45,  # SII puede ser lento
                retry_attempts=5
            )
        )

    @classmethod
    def production(cls) -> 'EnvironmentConfig':
        """Configuración para ambiente de producción"""
        return cls(
            name=Environment.PRODUCTION,
            debug=False,
            testing=False,
            logging=LoggingConfig(
                level="WARNING",
                format="json",
                output="file",
                file_path="/var/log/rypsystems_dte/production.log",
                max_file_size=52428800,  # 50MB
                backup_count=10
            ),
            cache=CacheConfig(
                enabled=True,
                backend="redis",
                ttl=7200,  # 2 horas
                max_size=10000
            ),
            security=SecurityConfig(
                validate_certificates=True,
                token_expiry=1800  # 30 minutos en producción
            ),
            performance=PerformanceConfig(
                max_concurrent_requests=50,
                request_timeout=30,
                retry_attempts=3,
                connection_pool_size=100
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la configuración a diccionario"""
        return self.model_dump()

    def merge_with(self, other_config: Dict[str, Any]) -> 'EnvironmentConfig':
        """
        Hace merge con otra configuración

        Args:
            other_config: Configuración a mergear

        Returns:
            Nueva instancia con configuración mergeada
        """
        current_dict = self.to_dict()
        self._deep_merge(current_dict, other_config)
        return EnvironmentConfig.model_validate(current_dict)

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Hace merge profundo de diccionarios"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


# Estado global del ambiente
_current_environment: Optional[Environment] = None
_current_config: Optional[EnvironmentConfig] = None


def get_environment() -> Environment:
    """
    Obtiene el ambiente actual

    Returns:
        Ambiente actual o DEVELOPMENT por defecto
    """
    global _current_environment

    if _current_environment is None:
        # Detectar desde variable de entorno
        env_name = os.environ.get("RYPSYSTEMS_DTE_ENVIRONMENT", "development").lower()

        try:
            _current_environment = Environment(env_name)
        except ValueError:
            _current_environment = Environment.DEVELOPMENT

    return _current_environment


def set_environment(environment: Environment) -> None:
    """
    Establece el ambiente actual

    Args:
        environment: Nuevo ambiente
    """
    global _current_environment, _current_config
    _current_environment = environment
    _current_config = None  # Forzar recarga de configuración


def get_environment_config() -> EnvironmentConfig:
    """
    Obtiene la configuración del ambiente actual

    Returns:
        Configuración del ambiente actual
    """
    global _current_config

    if _current_config is None:
        environment = get_environment()

        # Crear configuración base según ambiente
        if environment == Environment.DEVELOPMENT:
            _current_config = EnvironmentConfig.development()
        elif environment == Environment.TESTING:
            _current_config = EnvironmentConfig.testing()
        elif environment == Environment.STAGING:
            _current_config = EnvironmentConfig.staging()
        elif environment == Environment.CERTIFICATION:
            _current_config = EnvironmentConfig.certification()
        elif environment == Environment.PRODUCTION:
            _current_config = EnvironmentConfig.production()
        else:
            _current_config = EnvironmentConfig.development()

        # Aplicar overrides desde variables de entorno
        _apply_environment_overrides(_current_config)

    return _current_config


def _apply_environment_overrides(config: EnvironmentConfig) -> None:
    """
    Aplica overrides desde variables de entorno

    Args:
        config: Configuración a modificar
    """
    # Override de debug
    if "RYPSYSTEMS_DTE_DEBUG" in os.environ:
        config.debug = os.environ["RYPSYSTEMS_DTE_DEBUG"].lower() == "true"

    # Override de logging level
    if "RYPSYSTEMS_DTE_LOG_LEVEL" in os.environ:
        config.logging.level = os.environ["RYPSYSTEMS_DTE_LOG_LEVEL"]

    # Override de database URL
    if "DATABASE_URL" in os.environ:
        db_url = os.environ["DATABASE_URL"]
        # Parsear URL básica (postgresql://user:pass@host:port/db)
        if db_url.startswith("postgresql://"):
            # Configuración básica - en producción usar parser completo
            config.database = DatabaseConfig()

    # Override de Redis URL
    if "REDIS_URL" in os.environ:
        config.cache.redis_url = os.environ["REDIS_URL"]
        config.cache.backend = "redis"


def load_environment_config(config_dict: Dict[str, Any]) -> EnvironmentConfig:
    """
    Carga configuración de ambiente desde diccionario

    Args:
        config_dict: Diccionario con configuración

    Returns:
        Configuración de ambiente
    """
    return EnvironmentConfig.model_validate(config_dict)


def is_development() -> bool:
    """Verifica si está en ambiente de desarrollo"""
    return get_environment() == Environment.DEVELOPMENT


def is_testing() -> bool:
    """Verifica si está en ambiente de testing"""
    return get_environment() == Environment.TESTING


def is_production() -> bool:
    """Verifica si está en ambiente de producción"""
    return get_environment() == Environment.PRODUCTION


def is_certification() -> bool:
    """Verifica si está en ambiente de certificación"""
    return get_environment() == Environment.CERTIFICATION