"""
Test simple para verificar funcionalidad básica del sistema de configuración
"""

def test_basic_config_functionality():
    """Test básico de funcionalidad del sistema de configuración"""

    # 1. Test ConfigManager
    from rypsystems_dte.config.manager import ConfigManager

    manager = ConfigManager()
    assert manager is not None

    # Test configuración básica
    assert manager.get("environment") == "development"
    assert manager.set("test.key", "test_value")
    assert manager.get("test.key") == "test_value"

    print("✅ ConfigManager funcionando")

    # 2. Test Environment Config
    from rypsystems_dte.config.environment import EnvironmentConfig, Environment

    dev_config = EnvironmentConfig.development()
    assert dev_config.name == Environment.DEVELOPMENT
    assert dev_config.debug is True

    prod_config = EnvironmentConfig.production()
    assert prod_config.name == Environment.PRODUCTION
    assert prod_config.debug is False

    print("✅ EnvironmentConfig funcionando")

    # 3. Test SII Config
    from rypsystems_dte.config.sii import SiiConfig, SiiEnvironment

    sii_cert = SiiConfig.for_certification()
    assert sii_cert.environment == SiiEnvironment.CERTIFICACION

    sii_prod = SiiConfig.for_production()
    assert sii_prod.environment == SiiEnvironment.PRODUCCION

    print("✅ SiiConfig funcionando")

    # 4. Test Feature Flags
    from rypsystems_dte.config.features import FeatureFlags

    flags = FeatureFlags()
    assert flags is not None

    # Test registro de feature
    success = flags.register_feature("test_feature", default_value=False)
    assert success

    # Test habilitar feature
    assert flags.enable_feature("test_feature")
    assert flags.is_enabled("test_feature") is True

    print("✅ FeatureFlags funcionando")

    # 5. Test Certificate Store
    from rypsystems_dte.config.certificates import CertificateStore

    store = CertificateStore()
    assert store is not None
    assert isinstance(store.certificates, dict)

    print("✅ CertificateStore funcionando")

    # 6. Test Validation
    from rypsystems_dte.config.validation import ConfigValidator

    validator = ConfigValidator()
    assert validator is not None

    print("✅ ConfigValidator funcionando")


def test_integration_workflow():
    """Test workflow de integración básico"""

    from rypsystems_dte.config.manager import ConfigManager
    from rypsystems_dte.config.environment import EnvironmentConfig
    from rypsystems_dte.config.sii import SiiConfig

    # 1. Crear configuración integrada
    manager = ConfigManager()

    config_data = {
        "environment": "development",
        "debug": True,
        "sii": {
            "environment": "certificacion",
            "timeout": 30
        },
        "logging": {
            "level": "INFO"
        }
    }

    # 2. Cargar configuración
    success = manager.load_from_dict(config_data)
    assert success

    # 3. Verificar valores
    assert manager.get("environment") == "development"
    assert manager.get("debug") is True
    assert manager.get("sii.environment") == "certificacion"
    assert manager.get("sii.timeout") == 30
    assert manager.get("logging.level") == "INFO"

    print("✅ Workflow de integración funcionando")


def test_production_config():
    """Test configuración específica para producción"""

    from rypsystems_dte.config.environment import EnvironmentConfig, Environment
    from rypsystems_dte.config.sii import SiiConfig, SiiEnvironment

    # 1. Configuración de ambiente de producción
    prod_config = EnvironmentConfig.production()
    assert prod_config.name == Environment.PRODUCTION
    assert prod_config.debug is False
    assert prod_config.logging.level == "WARNING"
    assert prod_config.security.validate_certificates is True

    # 2. Configuración SII para producción
    sii_prod = SiiConfig.for_production()
    assert sii_prod.environment == SiiEnvironment.PRODUCCION
    assert sii_prod.verify_ssl is True
    assert sii_prod.log_sensitive_data is False

    print("✅ Configuración de producción lista")


def test_file_operations():
    """Test operaciones con archivos"""

    import json
    import tempfile
    import os
    from rypsystems_dte.config.manager import ConfigManager

    manager = ConfigManager()

    # Test datos
    test_config = {
        "app": {
            "name": "RypSystems DTE",
            "version": "1.0.0"
        }
    }

    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        temp_path = f.name

    try:
        # Cargar desde archivo
        success = manager.load_from_file(temp_path)
        assert success
        assert manager.get("app.name") == "RypSystems DTE"

    finally:
        os.unlink(temp_path)

    print("✅ Operaciones con archivos funcionando")


if __name__ == "__main__":
    test_basic_config_functionality()
    test_integration_workflow()
    test_production_config()
    test_file_operations()
    print("🎉 Sistema de configuración completamente funcional")