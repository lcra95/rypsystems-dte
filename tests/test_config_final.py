"""
Test final para verificar que el sistema de configuración está operacional
"""

import pytest
import os
import tempfile
import json
from pathlib import Path

def test_config_system_operational():
    """Test que verifica que todo el sistema de configuración esté operacional"""

    # 1. Test ConfigManager básico
    from rypsystems_dte.config import ConfigManager, get_config, set_config_source

    manager = ConfigManager()
    assert manager is not None

    # Test configuración básica
    assert manager.get("environment") == "development"
    assert manager.set("test.key", "test_value")
    assert manager.get("test.key") == "test_value"

    # 2. Test Environment Config
    from rypsystems_dte.config import EnvironmentConfig, Environment, get_environment, set_environment

    # Test configuraciones por ambiente
    dev_config = EnvironmentConfig.development()
    assert dev_config.name == Environment.DEVELOPMENT
    assert dev_config.debug is True

    prod_config = EnvironmentConfig.production()
    assert prod_config.name == Environment.PRODUCTION
    assert prod_config.debug is False

    cert_config = EnvironmentConfig.certification()
    assert cert_config.name == Environment.CERTIFICATION

    # 3. Test SII Config
    from rypsystems_dte.config import SiiConfig, SiiEnvironment, SiiEndpoints

    sii_cert = SiiConfig.for_certification()
    assert sii_cert.environment == SiiEnvironment.CERTIFICACION
    assert sii_cert.is_certification()

    sii_prod = SiiConfig.for_production()
    assert sii_prod.environment == SiiEnvironment.PRODUCCION
    assert sii_prod.is_production()

    # Test endpoints
    cert_endpoints = SiiEndpoints.certification()
    assert "maullin.sii.cl" in cert_endpoints.get_token.url

    prod_endpoints = SiiEndpoints.production()
    assert "palena.sii.cl" in prod_endpoints.get_token.url

    # 4. Test Certificate Store
    from rypsystems_dte.config import CertificateStore, CertificateConfig, CertificateType

    store = CertificateStore()
    assert store is not None
    assert isinstance(store.certificates, dict)

    # 5. Test Feature Flags
    from rypsystems_dte.config import FeatureFlags, get_feature_flag, enable_feature, disable_feature

    flags = FeatureFlags()
    assert flags is not None

    # Test registro y evaluación de features
    success = flags.register_feature(
        name="test_feature",
        description="Test feature",
        default_value=False
    )
    assert success

    # Test habilitar/deshabilitar
    assert flags.enable_feature("test_feature")
    assert flags.is_enabled("test_feature") is True

    assert flags.disable_feature("test_feature")
    assert flags.is_enabled("test_feature") is False

    # 6. Test Validation
    from rypsystems_dte.config import ConfigValidator, ValidationRule, ValidationType

    validator = ConfigValidator()
    assert validator is not None

    # Crear regla simple
    rule = ValidationRule(
        name="test_rule",
        field_path="test.field",
        validation_type=ValidationType.REQUIRED
    )

    validator.add_rule(rule)

    # Test validación
    valid_config = {"test": {"field": "value"}}
    assert validator.is_valid(valid_config)

    invalid_config = {}
    assert not validator.is_valid(invalid_config)

    print("✅ Sistema de configuración completamente operacional")


def test_config_file_operations():
    """Test operaciones con archivos de configuración"""
    from rypsystems_dte.config import ConfigManager

    manager = ConfigManager()

    # Test carga desde diccionario
    test_config = {
        "app": {
            "name": "RypSystems DTE",
            "version": "1.0.0"
        },
        "database": {
            "host": "localhost",
            "port": 5432
        }
    }

    success = manager.load_from_dict(test_config)
    assert success

    assert manager.get("app.name") == "RypSystems DTE"
    assert manager.get("app.version") == "1.0.0"
    assert manager.get("database.host") == "localhost"
    assert manager.get("database.port") == 5432

    # Test carga desde archivo JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        temp_path = f.name

    try:
        success = manager.load_from_file(temp_path)
        assert success
        assert manager.get("app.name") == "RypSystems DTE"
    finally:
        os.unlink(temp_path)

    print("✅ Operaciones con archivos de configuración funcionando")


def test_environment_integration():
    """Test integración con variables de entorno"""
    from rypsystems_dte.config import ConfigManager

    manager = ConfigManager()

    # Simular variables de entorno
    test_env = {
        'RYPSYSTEMS_DTE_APP_NAME': 'Test App',
        'RYPSYSTEMS_DTE_DEBUG': 'true',
        'RYPSYSTEMS_DTE_PORT': '8080'
    }

    # Patch del entorno
    import os
    original_env = os.environ.copy()
    os.environ.update(test_env)

    try:
        success = manager.load_from_environment()
        assert success

        # Las variables se convierten a configuración anidada
        assert manager.get("app.name") == "Test App"
        assert manager.get("debug") is True
        assert manager.get("port") == 8080

    finally:
        # Restaurar entorno original
        os.environ.clear()
        os.environ.update(original_env)

    print("✅ Integración con variables de entorno funcionando")


def test_complete_integration():
    """Test integración completa del sistema"""
    from rypsystems_dte.config import (
        ConfigManager, EnvironmentConfig, Environment,
        SiiConfig, FeatureFlags, get_config, set_config_source
    )

    # 1. Configurar ambiente de desarrollo
    config = EnvironmentConfig.development()
    assert config.debug is True

    # 2. Configurar SII para certificación
    sii_config = SiiConfig.for_certification()
    assert sii_config.environment.value == "certificacion"

    # 3. Configurar feature flags
    flags = FeatureFlags()
    flags.register_feature("enhanced_validation", default_value=True)
    flags.enable_feature("enhanced_validation")
    assert flags.is_enabled("enhanced_validation")

    # 4. Crear configuración integrada
    integrated_config = {
        "environment": config.name.value,
        "debug": config.debug,
        "sii": {
            "environment": sii_config.environment.value,
            "timeout": sii_config.connection_timeout
        },
        "features": {
            "enhanced_validation": True
        }
    }

    # 5. Cargar en ConfigManager
    manager = ConfigManager()
    success = manager.load_from_dict(integrated_config, merge=True)
    assert success

    # 6. Verificar integración
    assert manager.get("environment") == "development"
    assert manager.get("debug") is True
    assert manager.get("sii.environment") == "certificacion"
    assert manager.get("sii.timeout") == 30
    assert manager.get("features.enhanced_validation") is True

    print("✅ Integración completa del sistema funcionando")


def test_production_readiness():
    """Test que el sistema está listo para producción"""
    from rypsystems_dte.config import (
        EnvironmentConfig, Environment, SiiConfig, SiiEnvironment,
        FeatureFlags, CertificateStore
    )

    # 1. Configuración de producción
    prod_config = EnvironmentConfig.production()
    assert prod_config.name == Environment.PRODUCTION
    assert prod_config.debug is False
    assert prod_config.logging.level == "WARNING"
    assert prod_config.security.validate_certificates is True

    # 2. SII en producción
    sii_prod = SiiConfig.for_production()
    assert sii_prod.environment == SiiEnvironment.PRODUCCION
    assert sii_prod.verify_ssl is True
    assert sii_prod.log_sensitive_data is False

    # 3. Feature flags para producción
    flags = FeatureFlags()
    flags.register_feature("beta_features", default_value=False)
    flags.register_feature("production_optimizations", default_value=True)

    # En producción, beta features deben estar deshabilitadas
    assert flags.is_enabled("beta_features") is False
    assert flags.is_enabled("production_optimizations") is True

    # 4. Certificate store
    store = CertificateStore()
    assert store.global_validation is True

    print("✅ Sistema listo para producción")


if __name__ == "__main__":
    test_config_system_operational()
    test_config_file_operations()
    test_environment_integration()
    test_complete_integration()
    test_production_readiness()
    print("🎉 Todos los tests pasaron - Sistema de configuración completamente funcional")