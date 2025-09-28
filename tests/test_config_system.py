"""
Tests comprehensivos para el sistema de gestión de configuración
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

from rypsystems_dte.config import (
    ConfigManager, get_config, set_config_source, reload_config,
    EnvironmentConfig, Environment, get_environment, set_environment,
    SiiConfig, SiiEnvironment, SiiEndpoints, AuthenticationConfig,
    CertificateConfig, CertificateStore, CertificateValidator,
    FeatureFlags, FeatureConfig, get_feature_flag, enable_feature, disable_feature,
    ConfigValidator, ConfigValidationError, validate_config
)


class TestConfigManager:
    """Tests para ConfigManager"""

    def test_singleton_pattern(self):
        """Test que ConfigManager es singleton"""
        manager1 = ConfigManager()
        manager2 = ConfigManager()
        assert manager1 is manager2

    def test_default_config_loading(self):
        """Test carga de configuración por defecto"""
        manager = ConfigManager()
        assert manager.get("environment") == "development"
        assert manager.get("debug") is True
        assert manager.get("logging.level") == "INFO"

    def test_get_set_config(self):
        """Test obtener y establecer configuración"""
        manager = ConfigManager()

        # Test get con valor por defecto
        assert manager.get("nonexistent.key", "default") == "default"

        # Test set y get
        assert manager.set("test.key", "test_value")
        assert manager.get("test.key") == "test_value"

        # Test has
        assert manager.has("test.key")
        assert not manager.has("nonexistent.key")

    def test_load_from_dict(self):
        """Test carga desde diccionario"""
        manager = ConfigManager()

        test_config = {
            "test_section": {
                "nested_key": "nested_value",
                "number": 42
            },
            "simple_key": "simple_value"
        }

        assert manager.load_from_dict(test_config)
        assert manager.get("test_section.nested_key") == "nested_value"
        assert manager.get("test_section.number") == 42
        assert manager.get("simple_key") == "simple_value"

    def test_load_from_environment(self):
        """Test carga desde variables de entorno"""
        manager = ConfigManager()

        with patch.dict(os.environ, {
            'RYPSYSTEMS_DTE_TEST_VALUE': 'env_test_value',
            'RYPSYSTEMS_DTE_TEST_NUMBER': '123',
            'RYPSYSTEMS_DTE_TEST_BOOL': 'true',
            'RYPSYSTEMS_DTE_NESTED_KEY': 'nested_env_value'
        }):
            assert manager.load_from_environment()
            assert manager.get("test.value") == "env_test_value"
            assert manager.get("test.number") == 123
            assert manager.get("test.bool") is True
            assert manager.get("nested.key") == "nested_env_value"

    def test_load_from_file_json(self):
        """Test carga desde archivo JSON"""
        manager = ConfigManager()

        test_config = {
            "file_test": {
                "json_key": "json_value"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            temp_path = f.name

        try:
            assert manager.load_from_file(temp_path)
            assert manager.get("file_test.json_key") == "json_value"
        finally:
            os.unlink(temp_path)

    def test_get_section(self):
        """Test obtener sección completa"""
        manager = ConfigManager()
        manager.set("section.key1", "value1")
        manager.set("section.key2", "value2")

        section = manager.get_section("section")
        assert section == {"key1": "value1", "key2": "value2"}

    def test_auto_discover_config(self):
        """Test auto-descubrimiento de configuración"""
        manager = ConfigManager()
        # El método debería ejecutarse sin errores
        # En un ambiente real buscaría archivos de configuración
        result = manager.auto_discover_config()
        assert isinstance(result, bool)


class TestEnvironmentConfig:
    """Tests para EnvironmentConfig"""

    def test_environment_detection(self):
        """Test detección de ambiente"""
        # Test ambiente por defecto
        env = get_environment()
        assert env == Environment.DEVELOPMENT

        # Test cambio de ambiente
        set_environment(Environment.PRODUCTION)
        assert get_environment() == Environment.PRODUCTION

        # Resetear
        set_environment(Environment.DEVELOPMENT)

    def test_development_config(self):
        """Test configuración de desarrollo"""
        config = EnvironmentConfig.development()
        assert config.name == Environment.DEVELOPMENT
        assert config.debug is True
        assert config.logging.level == "DEBUG"
        assert config.cache.enabled is False

    def test_production_config(self):
        """Test configuración de producción"""
        config = EnvironmentConfig.production()
        assert config.name == Environment.PRODUCTION
        assert config.debug is False
        assert config.logging.level == "WARNING"
        assert config.cache.enabled is True
        assert config.security.validate_certificates is True

    def test_certification_config(self):
        """Test configuración de certificación"""
        config = EnvironmentConfig.certification()
        assert config.name == Environment.CERTIFICATION
        assert config.debug is False
        assert config.performance.retry_attempts == 5  # Más reintentos en certificación

    def test_config_merge(self):
        """Test merge de configuraciones"""
        config = EnvironmentConfig.development()

        override_config = {
            "logging": {
                "level": "ERROR"
            },
            "new_section": {
                "new_key": "new_value"
            }
        }

        merged_config = config.merge_with(override_config)
        assert merged_config.logging.level == "ERROR"  # Override
        assert merged_config.debug is True  # Mantenido
        assert merged_config.extra_config.get("new_section", {}).get("new_key") == "new_value"


class TestSiiConfig:
    """Tests para SiiConfig"""

    def test_certification_endpoints(self):
        """Test endpoints de certificación"""
        endpoints = SiiEndpoints.certification()
        assert "maullin.sii.cl" in endpoints.get_token.url
        assert endpoints.get_seed.requires_auth is False
        assert endpoints.send_dte.retry_attempts == 5

    def test_production_endpoints(self):
        """Test endpoints de producción"""
        endpoints = SiiEndpoints.production()
        assert "palena.sii.cl" in endpoints.get_token.url
        assert endpoints.send_dte.retry_attempts == 3  # Menos reintentos en producción

    def test_sii_config_creation(self):
        """Test creación de configuración SII"""
        config = SiiConfig.for_certification()
        assert config.environment == SiiEnvironment.CERTIFICACION
        assert config.verify_ssl is False
        assert config.log_sensitive_data is True

        config = SiiConfig.for_production()
        assert config.environment == SiiEnvironment.PRODUCCION
        assert config.verify_ssl is True
        assert config.log_sensitive_data is False

    def test_authentication_config(self):
        """Test configuración de autenticación"""
        auth_config = AuthenticationConfig(
            certificate_path="/path/to/cert.pem",
            private_key_path="/path/to/key.pem",
            rut_contribuyente="12345678-9"
        )

        assert auth_config.certificate_path == "/path/to/cert.pem"
        assert auth_config.rut_contribuyente == "12345678-9"

    def test_get_endpoint(self):
        """Test obtener endpoint específico"""
        config = SiiConfig.for_certification()
        token_endpoint = config.get_endpoint("get_token")
        assert token_endpoint is not None
        assert token_endpoint.name == "GetToken"

        # Endpoint no existente
        assert config.get_endpoint("nonexistent") is None


class TestCertificateStore:
    """Tests para CertificateStore"""

    def test_certificate_store_creation(self):
        """Test creación de store"""
        store = CertificateStore()
        assert isinstance(store.certificates, dict)
        assert len(store.certificates) == 0

    def test_add_certificate(self):
        """Test agregar certificado"""
        store = CertificateStore()

        # Crear archivo temporal para simular certificado
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write("-----BEGIN CERTIFICATE-----\nMOCK CERTIFICATE\n-----END CERTIFICATE-----")
            cert_path = f.name

        try:
            from rypsystems_dte.config.certificates import CertificateType

            success = store.add_certificate(
                name="test_cert",
                certificate_path=cert_path,
                certificate_type=CertificateType.SIGNING,
                auto_load=False  # No auto-cargar para evitar errores
            )

            assert success
            assert "test_cert" in store.certificates
            assert store.certificates["test_cert"].certificate_type == CertificateType.SIGNING

        finally:
            os.unlink(cert_path)

    def test_certificate_listing(self):
        """Test listado de certificados"""
        store = CertificateStore()

        # Agregar certificados mock sin archivos reales
        from rypsystems_dte.config.certificates import CertificateType, CertificateConfig

        store.certificates["signing_cert"] = CertificateConfig(
            name="signing_cert",
            certificate_path="/mock/path1.pem",
            certificate_type=CertificateType.SIGNING,
            auto_load=False
        )

        store.certificates["auth_cert"] = CertificateConfig(
            name="auth_cert",
            certificate_path="/mock/path2.pem",
            certificate_type=CertificateType.AUTHENTICATION,
            auto_load=False
        )

        # Test listado completo
        all_certs = store.list_certificates()
        assert len(all_certs) == 2
        assert "signing_cert" in all_certs
        assert "auth_cert" in all_certs

        # Test listado por tipo
        signing_certs = store.list_certificates(CertificateType.SIGNING)
        assert len(signing_certs) == 1
        assert "signing_cert" in signing_certs

        # Test obtener certificado específico
        signing_cert = store.get_signing_certificate()
        assert signing_cert == "signing_cert"

        auth_cert = store.get_authentication_certificate()
        assert auth_cert == "auth_cert"


class TestFeatureFlags:
    """Tests para FeatureFlags"""

    def test_feature_registration(self):
        """Test registro de características"""
        flags = FeatureFlags()

        success = flags.register_feature(
            name="test_feature",
            description="Test feature",
            default_value=False
        )

        assert success
        assert "test_feature" in flags.features
        assert flags.features["test_feature"].default_value is False

    def test_enable_disable_feature(self):
        """Test habilitar/deshabilitar características"""
        flags = FeatureFlags()
        flags.register_feature("test_feature", default_value=False)

        # Test habilitar
        assert flags.enable_feature("test_feature")
        from rypsystems_dte.config.features import FeatureStatus
        assert flags.features["test_feature"].status == FeatureStatus.ENABLED

        # Test deshabilitar
        assert flags.disable_feature("test_feature")
        assert flags.features["test_feature"].status == FeatureStatus.DISABLED

    def test_feature_evaluation(self):
        """Test evaluación de características"""
        flags = FeatureFlags()
        flags.register_feature("enabled_feature", default_value=True)
        flags.register_feature("disabled_feature", default_value=False)

        flags.enable_feature("enabled_feature")
        flags.disable_feature("disabled_feature")

        # Test evaluación básica
        assert flags.is_enabled("enabled_feature") is True
        assert flags.is_enabled("disabled_feature") is False

        # Test feature no existente
        assert flags.is_enabled("nonexistent_feature") is False

    def test_rollout_configuration(self):
        """Test configuración de rollout"""
        flags = FeatureFlags()
        flags.register_feature("rollout_feature", default_value=False)

        from rypsystems_dte.config.features import RolloutStrategy

        success = flags.set_feature_rollout(
            name="rollout_feature",
            percentage=50.0,
            strategy=RolloutStrategy.PERCENTAGE
        )

        assert success
        feature = flags.features["rollout_feature"]
        from rypsystems_dte.config.features import FeatureStatus
        assert feature.status == FeatureStatus.ROLLOUT
        assert len(feature.rollout_rules) == 1
        assert feature.rollout_rules[0].percentage == 50.0

    def test_load_from_dict(self):
        """Test carga desde diccionario"""
        flags = FeatureFlags()

        config_dict = {
            "simple_feature": True,
            "complex_feature": {
                "status": "enabled",
                "description": "Complex feature"
            }
        }

        success = flags.load_from_dict(config_dict)
        assert success

        assert "simple_feature" in flags.features
        assert "complex_feature" in flags.features
        assert flags.features["complex_feature"].description == "Complex feature"

    def test_get_all_features_status(self):
        """Test obtener estado de todas las características"""
        flags = FeatureFlags()
        flags.register_feature("feature1", default_value=True)
        flags.register_feature("feature2", default_value=False)

        flags.enable_feature("feature1")
        flags.disable_feature("feature2")

        all_status = flags.get_all_features_status()
        assert all_status["feature1"] is True
        assert all_status["feature2"] is False


class TestConfigValidation:
    """Tests para validación de configuración"""

    def test_validation_rule_creation(self):
        """Test creación de reglas de validación"""
        from rypsystems_dte.config.validation import ValidationRule, ValidationType

        rule = ValidationRule(
            name="test_rule",
            field_path="test.field",
            validation_type=ValidationType.REQUIRED
        )

        assert rule.name == "test_rule"
        assert rule.field_path == "test.field"
        assert rule.validation_type == ValidationType.REQUIRED

    def test_required_field_validation(self):
        """Test validación de campo requerido"""
        from rypsystems_dte.config.validation import ValidationRule, ValidationType

        rule = ValidationRule(
            name="required_test",
            field_path="required.field",
            validation_type=ValidationType.REQUIRED,
            required=True
        )

        # Test campo faltante
        config = {}
        result = rule.validate(config)
        assert result.is_valid is False

        # Test campo presente
        config = {"required": {"field": "value"}}
        result = rule.validate(config)
        assert result.is_valid is True

    def test_type_validation(self):
        """Test validación de tipo"""
        from rypsystems_dte.config.validation import ValidationRule, ValidationType

        rule = ValidationRule(
            name="type_test",
            field_path="test.field",
            validation_type=ValidationType.TYPE_CHECK,
            expected_type="str"
        )

        # Test tipo correcto
        config = {"test": {"field": "string_value"}}
        result = rule.validate(config)
        assert result.is_valid is True

        # Test tipo incorrecto
        config = {"test": {"field": 123}}
        result = rule.validate(config)
        assert result.is_valid is False

    def test_range_validation(self):
        """Test validación de rango"""
        from rypsystems_dte.config.validation import ValidationRule, ValidationType

        rule = ValidationRule(
            name="range_test",
            field_path="test.number",
            validation_type=ValidationType.RANGE,
            min_value=1,
            max_value=100
        )

        # Test valor en rango
        config = {"test": {"number": 50}}
        result = rule.validate(config)
        assert result.is_valid is True

        # Test valor fuera de rango
        config = {"test": {"number": 150}}
        result = rule.validate(config)
        assert result.is_valid is False

    def test_config_validator(self):
        """Test validador completo"""
        validator = ConfigValidator()

        # Agregar reglas
        validator.add_required_field("environment", "str")
        validator.add_required_field("logging.level", "str")

        # Test configuración válida
        valid_config = {
            "environment": "development",
            "logging": {"level": "INFO"}
        }

        assert validator.is_valid(valid_config)
        results = validator.validate(valid_config)
        assert len([r for r in results if not r.is_valid]) == 0

        # Test configuración inválida
        invalid_config = {
            "environment": "development"
            # logging.level faltante
        }

        assert not validator.is_valid(invalid_config)
        errors = validator.get_errors(invalid_config)
        assert len(errors) > 0

    def test_default_validator(self):
        """Test validador por defecto"""
        from rypsystems_dte.config.validation import create_default_validator

        validator = create_default_validator()
        assert len(validator.rules) > 0

        # Test con configuración mínima válida
        config = {
            "environment": "development",
            "logging": {"level": "INFO"}
        }

        assert validator.is_valid(config)


class TestIntegration:
    """Tests de integración del sistema completo"""

    def test_complete_config_workflow(self):
        """Test workflow completo de configuración"""
        # 1. Configurar ambiente
        set_environment(Environment.DEVELOPMENT)

        # 2. Configurar source de configuración
        test_config = {
            "environment": "development",
            "debug": True,
            "sii": {
                "environment": "certificacion",
                "authentication": {
                    "rut_contribuyente": "12345678-9"
                }
            },
            "features": {
                "test_feature": True
            }
        }

        success = set_config_source("dict", config=test_config)
        assert success

        # 3. Verificar configuración cargada
        assert get_config("environment") == "development"
        assert get_config("sii.environment") == "certificacion"

        # 4. Verificar feature flags
        assert get_feature_flag("test_feature") is True

        # 5. Validar configuración
        results = validate_config(test_config, raise_on_error=False)
        errors = [r for r in results if not r.is_valid]
        assert len(errors) == 0

    def test_environment_specific_config(self):
        """Test configuración específica por ambiente"""
        # Test desarrollo
        set_environment(Environment.DEVELOPMENT)
        dev_config = EnvironmentConfig.development()
        assert dev_config.debug is True
        assert dev_config.security.validate_certificates is False

        # Test producción
        set_environment(Environment.PRODUCTION)
        prod_config = EnvironmentConfig.production()
        assert prod_config.debug is False
        assert prod_config.security.validate_certificates is True

    def test_sii_config_integration(self):
        """Test integración de configuración SII"""
        # Configuración para certificación
        sii_config = SiiConfig.for_certification(
            authentication__rut_contribuyente="12345678-9"
        )

        assert sii_config.environment == SiiEnvironment.CERTIFICACION
        assert sii_config.is_certification()
        assert not sii_config.is_production()

        # Test obtener endpoint
        token_endpoint = sii_config.get_endpoint("get_token")
        assert token_endpoint is not None
        assert "maullin.sii.cl" in token_endpoint.url

    def test_feature_flags_with_environment(self):
        """Test feature flags con diferentes ambientes"""
        flags = FeatureFlags()

        # Registrar feature con configuración diferente por ambiente
        flags.register_feature(
            name="debug_mode",
            description="Debug mode feature",
            default_value=False
        )

        # En desarrollo, habilitar debug
        set_environment(Environment.DEVELOPMENT)
        flags.enable_feature("debug_mode")
        assert flags.is_enabled("debug_mode") is True

        # En producción, deshabilitar debug
        set_environment(Environment.PRODUCTION)
        flags.disable_feature("debug_mode")
        assert flags.is_enabled("debug_mode") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])