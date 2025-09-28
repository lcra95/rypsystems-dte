# RypSystems DTE - Sistema de Gestión de Configuración

Sistema comprehensive y flexible de gestión de configuraciones para diferentes ambientes y scenarios de deployment.

## 🚀 Características Principales

### ✅ **Gestión Multi-Ambiente**
- Configuraciones específicas para desarrollo, testing, certificación y producción
- Auto-detección de ambiente desde variables de entorno
- Validación de configuraciones por ambiente

### ✅ **Configuración del SII**
- Endpoints automáticos para certificación y producción
- Gestión de autenticación con certificados digitales
- Rate limiting y configuración de timeouts
- Configuración de reintentos y recuperación

### ✅ **Gestión de Certificados**
- Store centralizado de certificados digitales
- Validación automática de certificados
- Auto-descubrimiento en ubicaciones comunes
- Soporte para múltiples formatos (PEM, P12, PFX)

### ✅ **Feature Flags**
- Control dinámico de características
- Rollout gradual con estrategias configurables
- A/B testing y experimentación
- Evaluación basada en contexto de usuario

### ✅ **Validación de Configuraciones**
- Validación automática de tipos y rangos
- Verificación de archivos y URLs
- Reglas personalizadas de validación
- Mensajes de error descriptivos

### ✅ **Múltiples Fuentes**
- Archivos de configuración (JSON, YAML)
- Variables de entorno
- Configuración programática
- Auto-descubrimiento de archivos

## 📦 Instalación

```bash
# El sistema viene incluido con RypSystems DTE
pip install rypsystems-dte

# Dependencias adicionales para YAML
pip install pyyaml
```

## 🏃 Inicio Rápido

### 1. Configuración Básica

```python
from rypsystems_dte.config import ConfigManager, get_config

# Obtener configuración
manager = ConfigManager()
environment = get_config("environment")  # "development"
debug = get_config("debug", False)

# Configurar desde diccionario
config_data = {
    "environment": "production",
    "sii": {
        "environment": "produccion",
        "timeout": 60
    }
}
manager.load_from_dict(config_data)
```

### 2. Configuración por Ambiente

```python
from rypsystems_dte.config import EnvironmentConfig, Environment

# Configuración de desarrollo
dev_config = EnvironmentConfig.development()
print(f"Debug: {dev_config.debug}")  # True

# Configuración de producción
prod_config = EnvironmentConfig.production()
print(f"Log Level: {prod_config.logging.level}")  # WARNING
```

### 3. Configuración del SII

```python
from rypsystems_dte.config import SiiConfig

# Para certificación
sii_cert = SiiConfig.for_certification()
print(f"Environment: {sii_cert.environment}")  # certificacion
print(f"Token URL: {sii_cert.endpoints.get_token.url}")

# Para producción
sii_prod = SiiConfig.for_production()
print(f"Environment: {sii_prod.environment}")  # produccion
```

### 4. Feature Flags

```python
from rypsystems_dte.config import FeatureFlags, get_feature_flag

# Crear y configurar features
flags = FeatureFlags()
flags.register_feature("new_validation", default_value=False)
flags.enable_feature("new_validation")

# Evaluar features
if get_feature_flag("new_validation"):
    print("Nueva validación habilitada")
```

### 5. Gestión de Certificados

```python
from rypsystems_dte.config import CertificateStore, CertificateType

store = CertificateStore()

# Agregar certificado
store.add_certificate(
    name="firma_empresa",
    certificate_path="/path/to/cert.pem",
    certificate_type=CertificateType.SIGNING,
    private_key_path="/path/to/key.pem"
)

# Obtener certificado
cert = store.get_certificate("firma_empresa")
```

## 📋 Archivo de Configuración

Crea un archivo `config.yaml` en tu proyecto:

```yaml
environment: "development"
debug: true

sii:
  environment: "certificacion"
  authentication:
    certificate_path: "/path/to/cert.pem"
    private_key_path: "/path/to/key.pem"
    rut_contribuyente: "12345678-9"

features:
  strict_validation: true
  enhanced_logging: false

logging:
  level: "INFO"
  format: "json"
```

## 🌍 Variables de Entorno

El sistema soporta configuración via variables de entorno:

```bash
# Ambiente general
export RYPSYSTEMS_DTE_ENVIRONMENT=production
export RYPSYSTEMS_DTE_DEBUG=false

# Configuración SII
export RYPSYSTEMS_DTE_SII_ENVIRONMENT=produccion
export RYPSYSTEMS_DTE_SII_TIMEOUT=60

# Logging
export RYPSYSTEMS_DTE_LOG_LEVEL=WARNING

# Features
export RYPSYSTEMS_DTE_FEATURE_BETA_FEATURES=false
```

## 🔧 Configuración Avanzada

### Validación de Configuraciones

```python
from rypsystems_dte.config import ConfigValidator, validate_config

# Validar configuración
config = {"environment": "development", "sii": {"timeout": 30}}
results = validate_config(config)

# Verificar errores
errors = [r for r in results if not r.is_valid]
if errors:
    for error in errors:
        print(f"Error: {error.message}")
```

### Feature Flags con Rollout

```python
from rypsystems_dte.config import FeatureFlags, RolloutStrategy

flags = FeatureFlags()
flags.register_feature("new_feature", default_value=False)

# Rollout gradual al 25% de usuarios
flags.set_feature_rollout(
    name="new_feature",
    percentage=25.0,
    strategy=RolloutStrategy.PERCENTAGE
)
```

### Configuración de Certificados

```python
from rypsystems_dte.config import CertificateStore, CertificateValidator

store = CertificateStore()
validator = CertificateValidator(store)

# Validar certificado
is_valid = validator.validate_certificate_chain("mi_certificado")
expiry_warning = validator.get_certificate_expiry_warning("mi_certificado", days=30)
```

## 🏭 Configuración de Producción

### Archivo de Configuración de Producción

```yaml
environment: "production"
debug: false

sii:
  environment: "produccion"
  verify_ssl: true
  log_sensitive_data: false
  rate_limit:
    requests_per_minute: 100
    requests_per_hour: 2000

logging:
  level: "WARNING"
  format: "json"
  output: "file"
  file_path: "/var/log/rypsystems_dte/production.log"

security:
  validate_certificates: true
  token_expiry: 1800

features:
  beta_features: false
  production_optimizations: true
```

### Variables de Entorno de Producción

```bash
# Configuración crítica
export RYPSYSTEMS_DTE_ENVIRONMENT=production
export RYPSYSTEMS_DTE_DEBUG=false
export RYPSYSTEMS_DTE_SII_ENVIRONMENT=produccion

# Configuración de certificados
export RYPSYSTEMS_DTE_SII_CERTIFICATE_PATH=/etc/ssl/certs/sii.pem
export RYPSYSTEMS_DTE_SII_PRIVATE_KEY_PATH=/etc/ssl/private/sii.key

# Configuración de base de datos
export DATABASE_URL=postgresql://user:pass@prod-db:5432/dte
export REDIS_URL=redis://prod-redis:6379/0
```

## 🔍 Debug y Troubleshooting

### Verificar Configuración Actual

```python
from rypsystems_dte.config import get_config

# Ver toda la configuración
all_config = get_config()
print(json.dumps(all_config, indent=2))

# Verificar configuración específica
sii_env = get_config("sii.environment")
print(f"SII Environment: {sii_env}")
```

### Verificar Feature Flags

```python
from rypsystems_dte.config import get_feature_flags

flags = get_feature_flags()
all_features = flags.get_all_features_status()
print("Features activos:", all_features)
```

### Validar Certificados

```python
from rypsystems_dte.config import get_certificate_store

store = get_certificate_store()
certs = store.list_certificates()
for cert_name in certs:
    status = store.validate_certificate(cert_name)
    print(f"Certificado {cert_name}: {status}")
```

## 📚 API Reference

### Módulos Principales

- **`ConfigManager`**: Gestión centralizada de configuraciones
- **`EnvironmentConfig`**: Configuraciones específicas por ambiente
- **`SiiConfig`**: Configuración de servicios del SII
- **`CertificateStore`**: Gestión de certificados digitales
- **`FeatureFlags`**: Control de características y features
- **`ConfigValidator`**: Validación de configuraciones

### Funciones de Utilidad

- **`get_config(key, default=None)`**: Obtener configuración
- **`set_config_source(type, **kwargs)`**: Configurar fuente
- **`get_feature_flag(name, context=None)`**: Evaluar feature
- **`validate_config(config, validator=None)`**: Validar configuración

## 🤝 Contribución

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crea un Pull Request

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver el archivo [LICENSE](../../../LICENSE) para detalles.