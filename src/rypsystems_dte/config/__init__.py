"""
RypSystems DTE - Sistema de Gestión de Configuración

Sistema comprehensive de configuración para diferentes ambientes y deployment scenarios.
Proporciona manejo flexible de configuraciones con soporte para:

- Configuración por ambientes (desarrollo, certificación, producción)
- Endpoints y credenciales del SII
- Gestión de certificados digitales
- Feature flags y toggles
- Configuración de logging y monitoring
- Validación y caching de configuraciones

Componentes:
- ConfigManager: Gestión centralizada de configuraciones
- EnvironmentConfig: Configuraciones específicas por ambiente
- SiiConfig: Configuración de endpoints y servicios SII
- CertificateConfig: Gestión de certificados digitales
- FeatureFlags: Control de características y funcionalidades
"""

from .manager import (
    ConfigManager,
    get_config,
    set_config_source,
    reload_config
)
from .environment import (
    EnvironmentConfig,
    Environment,
    get_environment,
    set_environment
)
from .sii import (
    SiiConfig,
    SiiEnvironment,
    SiiEndpoints,
    AuthenticationConfig
)
from .certificates import (
    CertificateConfig,
    CertificateStore,
    CertificateValidator
)
from .features import (
    FeatureFlags,
    FeatureConfig,
    get_feature_flag,
    enable_feature,
    disable_feature
)
from .validation import (
    ConfigValidator,
    ValidationError as ConfigValidationError,
    validate_config
)

__all__ = [
    # Core configuration management
    'ConfigManager',
    'get_config',
    'set_config_source',
    'reload_config',

    # Environment configuration
    'EnvironmentConfig',
    'Environment',
    'get_environment',
    'set_environment',

    # SII configuration
    'SiiConfig',
    'SiiEnvironment',
    'SiiEndpoints',
    'AuthenticationConfig',

    # Certificate management
    'CertificateConfig',
    'CertificateStore',
    'CertificateValidator',

    # Feature flags
    'FeatureFlags',
    'FeatureConfig',
    'get_feature_flag',
    'enable_feature',
    'disable_feature',

    # Validation
    'ConfigValidator',
    'ConfigValidationError',
    'validate_config'
]