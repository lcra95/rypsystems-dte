"""
SII Configuration - Configuración de endpoints y servicios del SII

Maneja configuraciones específicas para la comunicación con los servicios
web del Servicio de Impuestos Internos de Chile.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from pydantic import BaseModel, Field, ConfigDict, field_validator


class SiiEnvironment(str, Enum):
    """Ambientes del SII"""
    CERTIFICACION = "certificacion"
    PRODUCCION = "produccion"


class AuthenticationMethod(str, Enum):
    """Métodos de autenticación soportados"""
    CERTIFICATE = "certificate"
    TOKEN = "token"
    HYBRID = "hybrid"


@dataclass
class SiiEndpoint:
    """Definición de un endpoint del SII"""
    name: str
    url: str
    soap_action: Optional[str] = None
    method: str = "POST"
    timeout: int = 30
    retry_attempts: int = 3
    requires_auth: bool = True


class SiiEndpoints(BaseModel):
    """Endpoints específicos del SII para cada ambiente"""
    model_config = ConfigDict(extra='allow')

    # Autenticación
    get_token: SiiEndpoint = Field(description="Endpoint para obtener token")
    get_seed: SiiEndpoint = Field(description="Endpoint para obtener semilla")

    # Envío de documentos
    send_dte: SiiEndpoint = Field(description="Envío de DTE")
    send_book: SiiEndpoint = Field(description="Envío de libro")
    send_boleta: SiiEndpoint = Field(description="Envío de boletas")

    # Consultas de estado
    query_dte_status: SiiEndpoint = Field(description="Consulta estado DTE")
    query_company_status: SiiEndpoint = Field(description="Consulta estado empresa")
    query_document_details: SiiEndpoint = Field(description="Consulta detalles documento")

    # Otros servicios
    get_caf: SiiEndpoint = Field(description="Obtener CAF")
    validate_dte: SiiEndpoint = Field(description="Validar DTE")

    @classmethod
    def certification(cls) -> 'SiiEndpoints':
        """Endpoints para ambiente de certificación"""
        base_url = "https://maullin.sii.cl"
        ws_base = f"{base_url}/DTEWS"

        return cls(
            get_token=SiiEndpoint(
                name="GetToken",
                url=f"{ws_base}/GetTokenFromSeed.jws",
                soap_action="",
                timeout=30
            ),
            get_seed=SiiEndpoint(
                name="GetSeed",
                url=f"{ws_base}/CrSeed.jws",
                soap_action="",
                timeout=30,
                requires_auth=False
            ),
            send_dte=SiiEndpoint(
                name="SendDTE",
                url=f"{ws_base}/QueryEstDte.jws",
                soap_action="",
                timeout=60,
                retry_attempts=5
            ),
            send_book=SiiEndpoint(
                name="SendBook",
                url=f"{ws_base}/UploadEnvio.jws",
                soap_action="",
                timeout=120
            ),
            send_boleta=SiiEndpoint(
                name="SendBoleta",
                url=f"{ws_base}/BolHonorarios.jws",
                soap_action="",
                timeout=60
            ),
            query_dte_status=SiiEndpoint(
                name="QueryDTEStatus",
                url=f"{ws_base}/QueryEstDte.jws",
                soap_action="",
                timeout=30
            ),
            query_company_status=SiiEndpoint(
                name="QueryCompanyStatus",
                url=f"{ws_base}/QueryEstUp.jws",
                soap_action="",
                timeout=30
            ),
            query_document_details=SiiEndpoint(
                name="QueryDocumentDetails",
                url=f"{ws_base}/QueryEstDteAv.jws",
                soap_action="",
                timeout=30
            ),
            get_caf=SiiEndpoint(
                name="GetCAF",
                url=f"{base_url}/cvc_cgi/dte/of_solicita_folios",
                method="GET",
                timeout=60,
                requires_auth=True
            ),
            validate_dte=SiiEndpoint(
                name="ValidateDTE",
                url=f"{ws_base}/ValidarDte.jws",
                soap_action="",
                timeout=45
            )
        )

    @classmethod
    def production(cls) -> 'SiiEndpoints':
        """Endpoints para ambiente de producción"""
        base_url = "https://palena.sii.cl"
        ws_base = f"{base_url}/DTEWS"

        return cls(
            get_token=SiiEndpoint(
                name="GetToken",
                url=f"{ws_base}/GetTokenFromSeed.jws",
                soap_action="",
                timeout=30
            ),
            get_seed=SiiEndpoint(
                name="GetSeed",
                url=f"{ws_base}/CrSeed.jws",
                soap_action="",
                timeout=30,
                requires_auth=False
            ),
            send_dte=SiiEndpoint(
                name="SendDTE",
                url=f"{ws_base}/QueryEstDte.jws",
                soap_action="",
                timeout=60,
                retry_attempts=3  # Menos reintentos en producción
            ),
            send_book=SiiEndpoint(
                name="SendBook",
                url=f"{ws_base}/UploadEnvio.jws",
                soap_action="",
                timeout=120
            ),
            send_boleta=SiiEndpoint(
                name="SendBoleta",
                url=f"{ws_base}/BolHonorarios.jws",
                soap_action="",
                timeout=60
            ),
            query_dte_status=SiiEndpoint(
                name="QueryDTEStatus",
                url=f"{ws_base}/QueryEstDte.jws",
                soap_action="",
                timeout=30
            ),
            query_company_status=SiiEndpoint(
                name="QueryCompanyStatus",
                url=f"{ws_base}/QueryEstUp.jws",
                soap_action="",
                timeout=30
            ),
            query_document_details=SiiEndpoint(
                name="QueryDocumentDetails",
                url=f"{ws_base}/QueryEstDteAv.jws",
                soap_action="",
                timeout=30
            ),
            get_caf=SiiEndpoint(
                name="GetCAF",
                url=f"{base_url}/cvc_cgi/dte/of_solicita_folios",
                method="GET",
                timeout=60,
                requires_auth=True
            ),
            validate_dte=SiiEndpoint(
                name="ValidateDTE",
                url=f"{ws_base}/ValidarDte.jws",
                soap_action="",
                timeout=45
            )
        )


class AuthenticationConfig(BaseModel):
    """Configuración de autenticación con SII"""
    model_config = ConfigDict(extra='allow')

    method: AuthenticationMethod = Field(
        default=AuthenticationMethod.CERTIFICATE,
        description="Método de autenticación"
    )

    # Configuración de certificados
    certificate_path: Optional[str] = Field(None, description="Ruta del certificado")
    private_key_path: Optional[str] = Field(None, description="Ruta de la llave privada")
    certificate_password: Optional[str] = Field(None, description="Contraseña del certificado")

    # Configuración de tokens
    token_lifetime: int = Field(default=21600, description="Vida útil del token (segundos)")
    auto_refresh_token: bool = Field(default=True, description="Auto-renovar token")
    token_refresh_threshold: int = Field(default=300, description="Umbral para renovar token (segundos)")

    # RUT del contribuyente
    rut_contribuyente: Optional[str] = Field(None, description="RUT del contribuyente")
    rut_empresa: Optional[str] = Field(None, description="RUT de la empresa certificadora")

    # Configuración de resolución
    resolucion_numero: Optional[int] = Field(None, description="Número de resolución SII")
    resolucion_fecha: Optional[str] = Field(None, description="Fecha de resolución")

    @field_validator('rut_contribuyente', 'rut_empresa')
    @classmethod
    def validate_rut(cls, v):
        """Valida formato de RUT"""
        if v is not None:
            # Validación básica de formato RUT
            if not v or '-' not in v:
                raise ValueError("RUT debe tener formato XXXXXXXX-X")
        return v


class RateLimitConfig(BaseModel):
    """Configuración de rate limiting"""
    model_config = ConfigDict(extra='allow')

    enabled: bool = Field(default=True, description="Habilitar rate limiting")
    requests_per_minute: int = Field(default=60, description="Requests por minuto")
    requests_per_hour: int = Field(default=1000, description="Requests por hora")
    burst_limit: int = Field(default=10, description="Límite de burst")
    backoff_factor: float = Field(default=1.5, description="Factor de backoff")
    max_backoff: int = Field(default=60, description="Máximo backoff (segundos)")


class SiiConfig(BaseModel):
    """
    Configuración completa para servicios SII

    Agrupa toda la configuración necesaria para comunicarse con el SII
    incluyendo endpoints, autenticación y parámetros de comunicación.
    """
    model_config = ConfigDict(extra='allow')

    # Ambiente del SII
    environment: SiiEnvironment = Field(
        default=SiiEnvironment.CERTIFICACION,
        description="Ambiente del SII"
    )

    # Endpoints
    endpoints: SiiEndpoints = Field(description="Endpoints del SII")

    # Autenticación
    authentication: AuthenticationConfig = Field(
        default_factory=AuthenticationConfig,
        description="Configuración de autenticación"
    )

    # Rate limiting
    rate_limit: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="Configuración de rate limiting"
    )

    # Configuración de comunicación
    connection_timeout: int = Field(default=30, description="Timeout de conexión (segundos)")
    read_timeout: int = Field(default=60, description="Timeout de lectura (segundos)")
    max_retries: int = Field(default=3, description="Máximo número de reintentos")
    retry_delay: float = Field(default=1.0, description="Delay entre reintentos (segundos)")

    # Configuración SSL
    verify_ssl: bool = Field(default=True, description="Verificar certificados SSL")
    ssl_cert_path: Optional[str] = Field(None, description="Ruta certificado SSL cliente")
    ssl_key_path: Optional[str] = Field(None, description="Ruta llave SSL cliente")
    ca_bundle_path: Optional[str] = Field(None, description="Ruta bundle CA")

    # Configuración de cache
    cache_enabled: bool = Field(default=True, description="Habilitar cache")
    cache_ttl: int = Field(default=3600, description="TTL del cache (segundos)")
    cache_max_size: int = Field(default=1000, description="Tamaño máximo del cache")

    # Headers adicionales
    user_agent: str = Field(
        default="RypSystems-DTE/1.0",
        description="User-Agent para requests"
    )
    additional_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Headers adicionales"
    )

    # Configuración de logging específica para SII
    log_requests: bool = Field(default=True, description="Loggear requests al SII")
    log_responses: bool = Field(default=True, description="Loggear responses del SII")
    log_sensitive_data: bool = Field(default=False, description="Loggear datos sensibles")

    @classmethod
    def for_certification(cls, **overrides) -> 'SiiConfig':
        """
        Configuración para ambiente de certificación

        Args:
            **overrides: Configuraciones a sobrescribir

        Returns:
            Configuración para certificación
        """
        config = cls(
            environment=SiiEnvironment.CERTIFICACION,
            endpoints=SiiEndpoints.certification(),
            verify_ssl=False,  # Certificación puede tener certificados self-signed
            rate_limit=RateLimitConfig(
                requests_per_minute=30,  # Más conservador en certificación
                requests_per_hour=500
            ),
            log_sensitive_data=True  # Más logging en certificación
        )

        # Aplicar overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config

    @classmethod
    def for_production(cls, **overrides) -> 'SiiConfig':
        """
        Configuración para ambiente de producción

        Args:
            **overrides: Configuraciones a sobrescribir

        Returns:
            Configuración para producción
        """
        config = cls(
            environment=SiiEnvironment.PRODUCCION,
            endpoints=SiiEndpoints.production(),
            verify_ssl=True,
            rate_limit=RateLimitConfig(
                requests_per_minute=60,
                requests_per_hour=2000
            ),
            max_retries=3,
            log_sensitive_data=False,  # No loggear datos sensibles en producción
            cache_ttl=7200  # Cache más largo en producción
        )

        # Aplicar overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config

    def get_endpoint(self, endpoint_name: str) -> Optional[SiiEndpoint]:
        """
        Obtiene un endpoint específico

        Args:
            endpoint_name: Nombre del endpoint

        Returns:
            Endpoint o None si no existe
        """
        return getattr(self.endpoints, endpoint_name, None)

    def is_production(self) -> bool:
        """Verifica si está configurado para producción"""
        return self.environment == SiiEnvironment.PRODUCCION

    def is_certification(self) -> bool:
        """Verifica si está configurado para certificación"""
        return self.environment == SiiEnvironment.CERTIFICACION

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la configuración a diccionario"""
        return self.model_dump()

    def update_from_dict(self, config_dict: Dict[str, Any]) -> 'SiiConfig':
        """
        Actualiza configuración desde diccionario

        Args:
            config_dict: Diccionario con configuración

        Returns:
            Nueva instancia con configuración actualizada
        """
        current_dict = self.to_dict()
        self._deep_merge(current_dict, config_dict)
        return SiiConfig.model_validate(current_dict)

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Hace merge profundo de diccionarios"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


# Configuración global de SII
_sii_config: Optional[SiiConfig] = None


def get_sii_config() -> SiiConfig:
    """
    Obtiene la configuración SII global

    Returns:
        Configuración SII actual
    """
    global _sii_config

    if _sii_config is None:
        # Detectar ambiente desde configuración general
        from .environment import get_environment, Environment

        env = get_environment()

        if env == Environment.PRODUCTION:
            _sii_config = SiiConfig.for_production()
        else:
            _sii_config = SiiConfig.for_certification()

    return _sii_config


def set_sii_config(config: SiiConfig) -> None:
    """
    Establece la configuración SII global

    Args:
        config: Nueva configuración SII
    """
    global _sii_config
    _sii_config = config


def load_sii_config_from_dict(config_dict: Dict[str, Any]) -> SiiConfig:
    """
    Carga configuración SII desde diccionario

    Args:
        config_dict: Diccionario con configuración

    Returns:
        Configuración SII
    """
    return SiiConfig.model_validate(config_dict)