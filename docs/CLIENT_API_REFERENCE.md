# RypSystems DTE - Client API Reference

**Complete API documentation for multi-language backend integration**

## Overview

RypSystems DTE is a comprehensive Python library for Chilean electronic tax document (DTE) management that provides production-ready SII integration. This documentation covers how external systems in any programming language can integrate with this library through various client patterns.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Installation & Setup](#installation--setup)
3. [Core API Reference](#core-api-reference)
4. [Configuration Management](#configuration-management)
5. [Document Creation Workflows](#document-creation-workflows)
6. [SII Integration](#sii-integration)
7. [Error Handling](#error-handling)
8. [Multi-Language Integration Patterns](#multi-language-integration-patterns)
9. [Production Deployment](#production-deployment)
10. [Examples & Use Cases](#examples--use-cases)

---

## System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    External Backend                         │
│                  (Any Language)                            │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP/REST API
                      │ Command Line Interface
                      │ Python Import
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                RypSystems DTE Library                      │
├─────────────────────────────────────────────────────────────┤
│  Configuration Management │  Document Factory               │
│  • Environment Config     │  • Factura (Invoice)           │
│  • SII Endpoints          │  • Boleta (Receipt)            │
│  • Feature Flags          │  • Nota Crédito (Credit Note)  │
│  • Certificates           │  • Nota Débito (Debit Note)    │
├─────────────────────────────────────────────────────────────┤
│  SII Integration          │  Document Processing            │
│  • Authentication         │  • Validation                   │
│  • Document Submission    │  • XML Generation               │
│  • Status Queries         │  • PDF417 (TED)                │
│  • Rate Limiting          │  • Digital Signatures          │
├─────────────────────────────────────────────────────────────┤
│  Error Handling & Logging │  Exchange System                │
│  • Structured Logging     │  • Document Bags               │
│  • Error Classification   │  • Envelopes                   │
│  • Recovery Mechanisms    │  • Batch Processing             │
│  • Performance Monitoring │  • Status Tracking             │
└─────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                     SII (Chilean Tax Authority)            │
│               • Certification Environment                   │
│               • Production Environment                      │
└─────────────────────────────────────────────────────────────┘
```

### Integration Patterns

1. **Direct Python Import**: For Python backends
2. **HTTP REST API**: For any language via HTTP service wrapper
3. **Command Line Interface**: For shell scripting and system integration
4. **Message Queue Integration**: For high-volume async processing

---

## Installation & Setup

### Python Library Installation

```bash
# Standard installation
pip install rypsystems-dte

# Development installation
git clone https://github.com/rypsystems/rypsystems-dte
cd rypsystems-dte
pip install -e .

# With optional dependencies
pip install "rypsystems-dte[full]"  # Includes YAML, Redis, etc.
```

### Configuration Files

Create a `config.yaml` file in your project root:

```yaml
# Basic configuration
environment: "development"  # development, testing, certification, production
debug: true

# SII Configuration
sii:
  environment: "certificacion"  # certificacion, produccion
  authentication:
    certificate_path: "/path/to/certificate.pem"
    private_key_path: "/path/to/private_key.pem"
    rut_contribuyente: "12345678-9"

# Logging
logging:
  level: "INFO"
  format: "json"
  output: "console"

# Features
features:
  strict_validation: true
  enhanced_logging: false
```

### Environment Variables

```bash
# Override configuration via environment variables
export RYPSYSTEMS_DTE_ENVIRONMENT=production
export RYPSYSTEMS_DTE_SII_ENVIRONMENT=produccion
export RYPSYSTEMS_DTE_SII_CERTIFICATE_PATH=/etc/ssl/certs/sii.pem
export RYPSYSTEMS_DTE_SII_PRIVATE_KEY_PATH=/etc/ssl/private/sii.key
export RYPSYSTEMS_DTE_LOG_LEVEL=WARNING
```

---

## Core API Reference

### Document Factory API

The primary interface for document creation.

#### Create Factura (Invoice)

```python
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente

# Initialize factory
factory = DTEFactory()

# Create parties
emisor = Contribuyente("76354771-K", "Mi Empresa SpA")
receptor = Contribuyente("12345678-9", "Cliente SPA")

# Create invoice
factura = factory.create_factura_afecta(
    emisor=emisor,
    receptor=receptor,
    folio=1001,
    fecha_emision="2023-12-01",
    detalle=[
        {
            "NmbItem": "Producto 1",
            "QtyItem": 100,
            "PrcItem": 1000
        }
    ],
    referencias=None,  # Optional references to other documents
    descuentos_recargos=None  # Optional discounts/charges
)

# Get document data
datos = factura.get_datos()
xml_content = factura.save_xml()
document_id = factura.get_id()  # Format: RUT_EMISOR_TTTTFNNNNNNNN
```

#### Create Boleta (Receipt)

```python
boleta = factory.create_boleta_afecta(
    emisor=emisor,
    receptor=receptor,
    folio=2001,
    fecha_emision="2023-12-01",
    detalle=[
        {
            "NmbItem": "Servicio 1",
            "QtyItem": 1,
            "PrcItem": 5000
        }
    ]
)
```

#### Create Nota de Crédito (Credit Note)

```python
nota_credito = factory.create_nota_credito(
    emisor=emisor,
    receptor=receptor,
    folio=3001,
    fecha_emision="2023-12-01",
    detalle=[
        {
            "NmbItem": "Descuento",
            "QtyItem": 1,
            "PrcItem": -1000  # Negative amount for credit
        }
    ],
    documento_referencia={
        "TpoDocRef": 33,  # Type of referenced document
        "FolioRef": 1001,  # Folio of referenced document
        "FchRef": "2023-11-01",  # Date of referenced document
        "CodRef": 1,  # Reference code (1=Cancellation, 2=Correction, 3=Other)
        "RazonRef": "Error en facturación"
    }
)
```

### Configuration API

#### ConfigManager

```python
from rypsystems_dte.config import ConfigManager, get_config

# Get global configuration instance
manager = ConfigManager()

# Load configuration from various sources
manager.load_from_file("config.yaml")
manager.load_from_dict({"debug": True})
manager.load_from_environment()

# Get configuration values
environment = get_config("environment")  # "development"
sii_timeout = get_config("sii.timeout", 30)  # 30 (default)
```

#### Environment Configuration

```python
from rypsystems_dte.config import EnvironmentConfig, Environment

# Predefined configurations
dev_config = EnvironmentConfig.development()
prod_config = EnvironmentConfig.production()
cert_config = EnvironmentConfig.certification()

# Access configuration properties
print(dev_config.debug)  # True
print(prod_config.logging.level)  # "WARNING"
```

#### SII Configuration

```python
from rypsystems_dte.config import SiiConfig

# Environment-specific SII configuration
sii_cert = SiiConfig.for_certification()
sii_prod = SiiConfig.for_production()

# Get endpoints
token_url = sii_cert.endpoints.get_token.url
upload_url = sii_cert.endpoints.upload_dte.url
```

### Logging API

#### Structured Logging

```python
from rypsystems_dte.logging import get_logger

# Get domain-specific loggers
dte_logger = get_logger("dte")
sii_logger = get_logger("sii")
app_logger = get_logger("app")

# Log with context
dte_logger.info(
    "Document created successfully",
    extra={
        "document_type": "factura",
        "folio": 1001,
        "rut_emisor": "76354771-K",
        "amount": 100000
    }
)

# Log errors with context
try:
    # Some operation
    pass
except Exception as e:
    dte_logger.error(
        "Document creation failed",
        extra={
            "error_type": type(e).__name__,
            "folio": 1001,
            "operation": "create_factura"
        },
        exc_info=True
    )
```

#### Error Handling

```python
from rypsystems_dte.logging import ErrorHandler, ErrorClassification

# Get error handler
error_handler = ErrorHandler()

# Register error with automatic classification
try:
    # Some operation
    pass
except Exception as e:
    classification = error_handler.handle_error(
        error=e,
        context={
            "operation": "create_document",
            "document_type": "factura",
            "folio": 1001
        }
    )

    print(f"Error severity: {classification.severity}")
    print(f"Recovery suggested: {classification.recoverable}")
```

### Certificate Management API

```python
from rypsystems_dte.config import CertificateStore, CertificateType

# Initialize certificate store
store = CertificateStore()

# Add certificate
store.add_certificate(
    name="firma_empresa",
    certificate_path="/path/to/cert.pem",
    certificate_type=CertificateType.SIGNING,
    private_key_path="/path/to/key.pem",
    rut_titular="76354771-K"
)

# Get certificate
cert = store.get_certificate("firma_empresa")
is_valid = store.validate_certificate("firma_empresa")
```

### Feature Flags API

```python
from rypsystems_dte.config import FeatureFlags, get_feature_flag

# Initialize feature flags
flags = FeatureFlags()

# Register and configure features
flags.register_feature(
    name="enhanced_validation",
    description="Enhanced document validation",
    default_value=True
)

# Check feature status
if get_feature_flag("enhanced_validation"):
    # Use enhanced validation
    pass
```

---

## Configuration Management

### Configuration Hierarchy

Configuration values are resolved in the following order (last wins):

1. **Default Values**: Built-in defaults
2. **Configuration Files**: `config.yaml`, `config.json`
3. **Environment Variables**: `RYPSYSTEMS_DTE_*` prefixed
4. **Runtime Configuration**: Programmatically set values

### Configuration File Structure

```yaml
# Complete configuration example
environment: "production"
debug: false

sii:
  environment: "produccion"
  authentication:
    certificate_path: "/etc/ssl/certs/sii.pem"
    private_key_path: "/etc/ssl/private/sii.key"
    rut_contribuyente: "12345678-9"
    resolucion_numero: 123
    resolucion_fecha: "2023-01-01"

  connection_timeout: 30
  read_timeout: 60
  max_retries: 3
  verify_ssl: true

  rate_limit:
    enabled: true
    requests_per_minute: 60
    requests_per_hour: 1000

logging:
  level: "WARNING"
  format: "json"
  output: "file"
  file_path: "/var/log/rypsystems_dte/production.log"

features:
  strict_validation: true
  enhanced_logging: false
  beta_features: false

certificates:
  store_path: "/etc/ssl/certificates/"
  global_validation: true

security:
  validate_certificates: true
  token_expiry: 3600

cache:
  enabled: true
  backend: "redis"
  redis_url: "redis://localhost:6379/0"
  ttl: 3600
```

### Environment-Specific Configurations

#### Development Configuration

```python
dev_config = EnvironmentConfig.development()
# debug: True
# logging.level: "DEBUG"
# sii.verify_ssl: False (for testing)
# features.beta_features: True
```

#### Production Configuration

```python
prod_config = EnvironmentConfig.production()
# debug: False
# logging.level: "WARNING"
# sii.verify_ssl: True
# security.validate_certificates: True
# features.beta_features: False
```

---

## Document Creation Workflows

### Complete Document Lifecycle

```python
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.logging import get_logger

# Initialize components
factory = DTEFactory()
logger = get_logger("dte")

# 1. Create parties
emisor = Contribuyente("76354771-K", "Mi Empresa SpA")
receptor = Contribuyente("12345678-9", "Cliente SPA")

logger.info("Creating new document", extra={
    "rut_emisor": emisor.rut,
    "rut_receptor": receptor.rut
})

# 2. Create document
try:
    factura = factory.create_factura_afecta(
        emisor=emisor,
        receptor=receptor,
        folio=1001,
        fecha_emision="2023-12-01",
        detalle=[
            {
                "NmbItem": "Producto Premium",
                "QtyItem": 100,
                "PrcItem": 1000,
                "UnmdItem": "UN"
            }
        ]
    )

    logger.info("Document created successfully", extra={
        "document_id": factura.get_id(),
        "total_amount": 100000
    })

except Exception as e:
    logger.error("Document creation failed", exc_info=True)
    raise

# 3. Get document data and XML
document_data = factura.get_datos()
xml_content = factura.save_xml()

# 4. Validate document (automatic in creation)
logger.info("Document validation completed", extra={
    "document_id": factura.get_id(),
    "xml_length": len(xml_content)
})
```

### Document Types and Requirements

#### Factura Afecta (Taxable Invoice) - Type 33

**Required Fields:**
- `emisor`: Company issuing the invoice
- `receptor`: Customer receiving the invoice
- `folio`: Sequential document number
- `fecha_emision`: Issue date (YYYY-MM-DD)
- `detalle`: List of items/services

**Optional Fields:**
- `referencias`: References to other documents
- `descuentos_recargos`: Global discounts or charges
- `observaciones`: Additional notes

**Example:**
```python
factura = factory.create_factura_afecta(
    emisor=emisor,
    receptor=receptor,
    folio=1001,
    fecha_emision="2023-12-01",
    detalle=[
        {
            "NmbItem": "Consultoría IT",
            "QtyItem": 40,
            "PrcItem": 25000,
            "UnmdItem": "HR"  # Hours
        }
    ],
    observaciones="Proyecto desarrollo web"
)
```

#### Boleta Afecta (Taxable Receipt) - Type 39

**Use Case:** Final consumer sales
**Key Differences from Factura:**
- Simplified receptor (can be anonymous)
- Different validation rules
- Specific SII endpoints

```python
boleta = factory.create_boleta_afecta(
    emisor=emisor,
    receptor=Contribuyente("66666666-6", "Cliente Final"),
    folio=2001,
    fecha_emision="2023-12-01",
    detalle=[
        {
            "NmbItem": "Producto Retail",
            "QtyItem": 2,
            "PrcItem": 15000
        }
    ]
)
```

#### Nota de Crédito (Credit Note) - Type 61

**Use Case:** Cancellations, corrections, discounts
**Required Fields:** All factura fields plus reference to original document

```python
nota_credito = factory.create_nota_credito(
    emisor=emisor,
    receptor=receptor,
    folio=3001,
    fecha_emision="2023-12-01",
    detalle=[
        {
            "NmbItem": "Corrección factura 1001",
            "QtyItem": 1,
            "PrcItem": -10000  # Negative amount
        }
    ],
    documento_referencia={
        "TpoDocRef": 33,      # Original document type
        "FolioRef": 1001,     # Original folio
        "FchRef": "2023-11-01",  # Original date
        "CodRef": 2,          # Correction code
        "RazonRef": "Error en cantidad"
    }
)
```

### Document Detail Items

Each document can contain multiple detail items with the following structure:

```python
detalle_item = {
    # Required fields
    "NmbItem": "Product/Service Name",
    "QtyItem": 100,        # Quantity
    "PrcItem": 1000,       # Unit price

    # Optional fields
    "UnmdItem": "UN",      # Unit of measure
    "DescuentoPct": 10,    # Discount percentage
    "DescuentoMonto": 100, # Discount amount
    "RecargoPct": 5,       # Surcharge percentage
    "RecargoMonto": 50,    # Surcharge amount

    # Tax information (automatic calculation)
    "MontoItem": 90000     # Total item amount (calculated)
}
```

---

## SII Integration

### Authentication Process

The library handles SII authentication automatically using digital certificates:

```python
from rypsystems_dte.config import SiiConfig

# Configure SII authentication
sii_config = SiiConfig.for_production()  # or for_certification()

# Authentication happens automatically when needed
# Certificate and private key paths are configured in config.yaml
```

### Document Submission Workflow

```python
from rypsystems_dte.sii.integration import SiiClient
from rypsystems_dte.logging import get_logger

logger = get_logger("sii")

# Initialize SII client
sii_client = SiiClient()

# Submit document
try:
    submission_result = sii_client.submit_document(
        document=factura,
        company_rut="76354771-K"
    )

    logger.info("Document submitted to SII", extra={
        "document_id": factura.get_id(),
        "track_id": submission_result.track_id,
        "status": submission_result.status
    })

except Exception as e:
    logger.error("SII submission failed", extra={
        "document_id": factura.get_id(),
        "error": str(e)
    }, exc_info=True)
```

### Status Tracking

```python
# Check document status
status_result = sii_client.get_document_status(
    track_id=submission_result.track_id,
    company_rut="76354771-K"
)

print(f"Status: {status_result.status}")
print(f"Details: {status_result.details}")
```

### Environment Management

#### Certification Environment
- **Purpose**: Testing and development
- **Endpoint**: `https://maullin.sii.cl/`
- **Documents**: Not legally valid
- **Access**: Requires certification credentials

#### Production Environment
- **Purpose**: Live document submission
- **Endpoint**: `https://palena.sii.cl/`
- **Documents**: Legally valid tax documents
- **Access**: Requires production credentials

```python
# Switch between environments
cert_config = SiiConfig.for_certification()
prod_config = SiiConfig.for_production()

# Environment is automatically detected from configuration
sii_client = SiiClient()  # Uses current environment configuration
```

---

## Error Handling

### Error Classification System

The library automatically classifies errors into categories:

```python
from rypsystems_dte.logging import ErrorSeverity, ErrorCategory

# Error severities
ErrorSeverity.LOW       # Minor issues, system continues
ErrorSeverity.MEDIUM    # Important issues, degraded functionality
ErrorSeverity.HIGH      # Critical issues, major functionality affected
ErrorSeverity.CRITICAL  # System failure, immediate attention required

# Error categories
ErrorCategory.VALIDATION    # Data validation errors
ErrorCategory.CONFIGURATION # Configuration issues
ErrorCategory.NETWORK       # Network connectivity problems
ErrorCategory.SII          # SII service errors
ErrorCategory.SYSTEM       # Internal system errors
```

### Error Recovery Mechanisms

```python
from rypsystems_dte.logging import ErrorHandler, RecoveryStrategy

error_handler = ErrorHandler()

try:
    # Document operation
    result = some_operation()
except Exception as e:
    # Automatic error classification and recovery
    classification = error_handler.handle_error(e, context={
        "operation": "document_creation",
        "document_type": "factura"
    })

    if classification.recoverable:
        # Attempt automatic recovery
        recovery_result = error_handler.attempt_recovery(
            error=e,
            strategy=classification.suggested_strategy
        )

        if recovery_result.success:
            # Operation recovered successfully
            pass
        else:
            # Manual intervention required
            pass
```

### Common Error Scenarios

#### Configuration Errors

```python
# Missing certificate
ConfigurationError: Certificate file not found: /path/to/cert.pem

# Invalid RUT format
ValidationError: Invalid RUT format: 12345678

# Missing required configuration
ConfigurationError: SII environment not configured
```

#### Document Validation Errors

```python
# Invalid document data
ValidationError: Folio must be a positive integer

# Missing required fields
ValidationError: Field 'NmbItem' is required for all detail items

# Business rule violations
ValidationError: Credit note amount cannot exceed original document amount
```

#### SII Communication Errors

```python
# Network connectivity
NetworkError: Unable to connect to SII endpoint

# Authentication failure
AuthenticationError: Invalid certificate or expired credentials

# SII service error
SiiError: Document rejected by SII: Invalid document format
```

### Custom Error Handling

```python
from rypsystems_dte.logging import get_logger, ErrorHandler

logger = get_logger("custom")
error_handler = ErrorHandler()

def custom_error_handler(operation_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log error with context
                logger.error(
                    f"Error in {operation_name}",
                    extra={
                        "operation": operation_name,
                        "args": str(args),
                        "kwargs": str(kwargs)
                    },
                    exc_info=True
                )

                # Handle error
                classification = error_handler.handle_error(e, {
                    "operation": operation_name
                })

                # Re-raise if not recoverable
                if not classification.recoverable:
                    raise

                # Attempt recovery
                recovery = error_handler.attempt_recovery(e, classification.suggested_strategy)
                if not recovery.success:
                    raise

                return recovery.result

        return wrapper
    return decorator

# Usage
@custom_error_handler("document_creation")
def create_custom_document():
    # Your document creation logic
    pass
```

---

## Multi-Language Integration Patterns

### Pattern 1: HTTP REST API Wrapper

Create a REST API service that wraps the Python library:

```python
# api_server.py
from flask import Flask, request, jsonify
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.logging import get_logger

app = Flask(__name__)
factory = DTEFactory()
logger = get_logger("api")

@app.route('/api/v1/documents/factura', methods=['POST'])
def create_factura():
    try:
        data = request.json

        # Create parties
        emisor = Contribuyente(data['emisor']['rut'], data['emisor']['nombre'])
        receptor = Contribuyente(data['receptor']['rut'], data['receptor']['nombre'])

        # Create document
        factura = factory.create_factura_afecta(
            emisor=emisor,
            receptor=receptor,
            folio=data['folio'],
            fecha_emision=data['fecha_emision'],
            detalle=data['detalle']
        )

        return jsonify({
            'success': True,
            'document_id': factura.get_id(),
            'xml': factura.save_xml(),
            'data': factura.get_datos()
        })

    except Exception as e:
        logger.error("API request failed", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

**Client Example (Node.js):**

```javascript
const axios = require('axios');

async function createInvoice(invoiceData) {
    try {
        const response = await axios.post('http://localhost:8000/api/v1/documents/factura', {
            emisor: {
                rut: '76354771-K',
                nombre: 'Mi Empresa SpA'
            },
            receptor: {
                rut: '12345678-9',
                nombre: 'Cliente SPA'
            },
            folio: 1001,
            fecha_emision: '2023-12-01',
            detalle: [
                {
                    NmbItem: 'Producto 1',
                    QtyItem: 100,
                    PrcItem: 1000
                }
            ]
        });

        console.log('Document created:', response.data.document_id);
        return response.data;

    } catch (error) {
        console.error('Error creating document:', error.response.data);
        throw error;
    }
}
```

### Pattern 2: Command Line Interface

```python
# cli.py
import argparse
import json
import sys
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente

def main():
    parser = argparse.ArgumentParser(description='RypSystems DTE CLI')
    parser.add_argument('--action', required=True, choices=['create-factura', 'create-boleta', 'create-nota-credito'])
    parser.add_argument('--data', required=True, help='JSON data file')
    parser.add_argument('--output', help='Output file for XML')

    args = parser.parse_args()

    # Load data
    with open(args.data, 'r') as f:
        data = json.load(f)

    factory = DTEFactory()

    try:
        if args.action == 'create-factura':
            document = factory.create_factura_afecta(
                emisor=Contribuyente(data['emisor']['rut'], data['emisor']['nombre']),
                receptor=Contribuyente(data['receptor']['rut'], data['receptor']['nombre']),
                folio=data['folio'],
                fecha_emision=data['fecha_emision'],
                detalle=data['detalle']
            )

        xml_content = document.save_xml()

        if args.output:
            with open(args.output, 'w') as f:
                f.write(xml_content)
        else:
            print(xml_content)

        print(f"SUCCESS: Document {document.get_id()} created", file=sys.stderr)

    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
```

**Usage from any language:**

```bash
# Create data file
cat > invoice_data.json << EOF
{
    "emisor": {"rut": "76354771-K", "nombre": "Mi Empresa SpA"},
    "receptor": {"rut": "12345678-9", "nombre": "Cliente SPA"},
    "folio": 1001,
    "fecha_emision": "2023-12-01",
    "detalle": [
        {"NmbItem": "Producto 1", "QtyItem": 100, "PrcItem": 1000}
    ]
}
EOF

# Execute from any language
python cli.py --action create-factura --data invoice_data.json --output factura_1001.xml
```

### Pattern 3: Message Queue Integration

```python
# worker.py
import json
import pika
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.logging import get_logger

logger = get_logger("worker")
factory = DTEFactory()

def process_document_request(ch, method, properties, body):
    try:
        # Parse request
        request = json.loads(body)

        # Create document
        if request['type'] == 'factura':
            document = factory.create_factura_afecta(
                emisor=Contribuyente(request['emisor']['rut'], request['emisor']['nombre']),
                receptor=Contribuyente(request['receptor']['rut'], request['receptor']['nombre']),
                folio=request['folio'],
                fecha_emision=request['fecha_emision'],
                detalle=request['detalle']
            )

        # Prepare response
        response = {
            'success': True,
            'document_id': document.get_id(),
            'xml': document.save_xml()
        }

        # Send response
        ch.basic_publish(
            exchange='',
            routing_key=properties.reply_to,
            properties=pika.BasicProperties(correlation_id=properties.correlation_id),
            body=json.dumps(response)
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("Document processed successfully", extra={
            'document_id': document.get_id(),
            'correlation_id': properties.correlation_id
        })

    except Exception as e:
        logger.error("Document processing failed", exc_info=True)

        error_response = {
            'success': False,
            'error': str(e)
        }

        ch.basic_publish(
            exchange='',
            routing_key=properties.reply_to,
            properties=pika.BasicProperties(correlation_id=properties.correlation_id),
            body=json.dumps(error_response)
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)

# Setup RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='dte_requests')
channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='dte_requests', on_message_callback=process_document_request)

print("Worker started. Waiting for messages...")
channel.start_consuming()
```

### Pattern 4: Docker Container Service

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Install RypSystems DTE
RUN pip install -e .

# Expose port
EXPOSE 8000

# Run API server
CMD ["python", "api_server.py"]
```

**docker-compose.yml:**

```yaml
version: '3.8'

services:
  rypsystems-dte:
    build: .
    ports:
      - "8000:8000"
    environment:
      - RYPSYSTEMS_DTE_ENVIRONMENT=production
      - RYPSYSTEMS_DTE_SII_ENVIRONMENT=produccion
    volumes:
      - ./certificates:/etc/ssl/certificates:ro
      - ./config.yaml:/app/config.yaml:ro
      - ./logs:/var/log/rypsystems_dte
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: dte_tracking
      POSTGRES_USER: dte_user
      POSTGRES_PASSWORD: dte_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Production Deployment

### System Requirements

**Minimum Requirements:**
- Python 3.9+
- 512 MB RAM
- 1 GB disk space
- Network access to SII endpoints

**Recommended Requirements:**
- Python 3.11+
- 2 GB RAM
- 10 GB disk space
- Redis for caching
- PostgreSQL for persistence
- Load balancer for high availability

### Security Configuration

```yaml
# production_config.yaml
environment: "production"
debug: false

sii:
  environment: "produccion"
  verify_ssl: true
  log_sensitive_data: false

  authentication:
    certificate_path: "/etc/ssl/certs/sii.pem"
    private_key_path: "/etc/ssl/private/sii.key"
    rut_contribuyente: "YOUR_RUT_HERE"

  rate_limit:
    enabled: true
    requests_per_minute: 100
    requests_per_hour: 2000

logging:
  level: "WARNING"
  format: "json"
  output: "file"
  file_path: "/var/log/rypsystems_dte/production.log"
  max_file_size: 10485760  # 10MB
  backup_count: 10

security:
  validate_certificates: true
  token_expiry: 1800

features:
  beta_features: false
  production_optimizations: true
  strict_validation: true
```

### Monitoring and Observability

```python
# monitoring.py
from rypsystems_dte.logging import PerformanceMonitor, get_logger
import time

monitor = PerformanceMonitor()
logger = get_logger("monitoring")

# Custom metrics collection
def track_document_creation(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)

            # Record success metrics
            monitor.record_metric("document_creation_success", 1, {
                "document_type": kwargs.get("document_type", "unknown"),
                "response_time": time.time() - start_time
            })

            return result

        except Exception as e:
            # Record error metrics
            monitor.record_metric("document_creation_error", 1, {
                "error_type": type(e).__name__,
                "document_type": kwargs.get("document_type", "unknown")
            })
            raise

    return wrapper

# Health check endpoint
def health_check():
    try:
        # Check SII connectivity
        sii_status = check_sii_connectivity()

        # Check certificate validity
        cert_status = check_certificate_validity()

        # Check system resources
        system_status = check_system_resources()

        return {
            "status": "healthy" if all([sii_status, cert_status, system_status]) else "unhealthy",
            "sii_connectivity": sii_status,
            "certificate_valid": cert_status,
            "system_resources": system_status,
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error("Health check failed", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }
```

### Backup and Disaster Recovery

```bash
#!/bin/bash
# backup.sh

# Backup certificates
tar -czf certificates_backup_$(date +%Y%m%d).tar.gz /etc/ssl/certificates/

# Backup configuration
cp /app/config.yaml config_backup_$(date +%Y%m%d).yaml

# Backup logs
tar -czf logs_backup_$(date +%Y%m%d).tar.gz /var/log/rypsystems_dte/

# Upload to cloud storage
aws s3 cp certificates_backup_$(date +%Y%m%d).tar.gz s3://backup-bucket/certificates/
aws s3 cp config_backup_$(date +%Y%m%d).yaml s3://backup-bucket/config/
aws s3 cp logs_backup_$(date +%Y%m%d).tar.gz s3://backup-bucket/logs/
```

---

## Examples & Use Cases

### Use Case 1: E-commerce Integration

```python
# ecommerce_integration.py
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.logging import get_logger

class EcommerceInvoiceService:
    def __init__(self):
        self.factory = DTEFactory()
        self.logger = get_logger("ecommerce")

    def process_order(self, order_data):
        """Convert e-commerce order to DTE invoice"""
        try:
            # Extract order information
            company = order_data['company']
            customer = order_data['customer']
            items = order_data['items']

            # Create parties
            emisor = Contribuyente(company['tax_id'], company['name'])
            receptor = Contribuyente(customer['tax_id'], customer['name'])

            # Convert items to DTE format
            detalle = []
            for item in items:
                detalle.append({
                    "NmbItem": item['product_name'],
                    "QtyItem": item['quantity'],
                    "PrcItem": item['unit_price'],
                    "UnmdItem": item.get('unit', 'UN')
                })

            # Create invoice
            factura = self.factory.create_factura_afecta(
                emisor=emisor,
                receptor=receptor,
                folio=order_data['invoice_number'],
                fecha_emision=order_data['order_date'],
                detalle=detalle
            )

            self.logger.info("E-commerce order converted to DTE", extra={
                "order_id": order_data['order_id'],
                "document_id": factura.get_id(),
                "total_amount": sum(item['quantity'] * item['unit_price'] for item in items)
            })

            return {
                "success": True,
                "document_id": factura.get_id(),
                "xml": factura.save_xml(),
                "order_id": order_data['order_id']
            }

        except Exception as e:
            self.logger.error("E-commerce order processing failed", extra={
                "order_id": order_data.get('order_id', 'unknown')
            }, exc_info=True)

            return {
                "success": False,
                "error": str(e),
                "order_id": order_data.get('order_id', 'unknown')
            }

# Usage example
service = EcommerceInvoiceService()

order = {
    "order_id": "ORD-2023-001",
    "company": {
        "tax_id": "76354771-K",
        "name": "TechStore SpA"
    },
    "customer": {
        "tax_id": "12345678-9",
        "name": "Juan Pérez"
    },
    "invoice_number": 1001,
    "order_date": "2023-12-01",
    "items": [
        {
            "product_name": "Laptop Dell XPS 13",
            "quantity": 1,
            "unit_price": 1200000,
            "unit": "UN"
        },
        {
            "product_name": "Mouse Inalámbrico",
            "quantity": 2,
            "unit_price": 25000,
            "unit": "UN"
        }
    ]
}

result = service.process_order(order)
```

### Use Case 2: Subscription Billing

```python
# subscription_billing.py
from datetime import datetime, timedelta
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente

class SubscriptionBillingService:
    def __init__(self):
        self.factory = DTEFactory()

    def generate_monthly_invoice(self, subscription_data):
        """Generate monthly subscription invoice"""

        company = Contribuyente("76354771-K", "CloudService SpA")
        customer = Contribuyente(
            subscription_data['customer_rut'],
            subscription_data['customer_name']
        )

        # Calculate billing period
        today = datetime.now()
        next_month = today.replace(day=1) + timedelta(days=32)
        billing_period = f"{today.strftime('%Y-%m')} to {next_month.strftime('%Y-%m')}"

        # Create subscription detail
        detalle = [{
            "NmbItem": f"Suscripción {subscription_data['plan_name']} - {billing_period}",
            "QtyItem": 1,
            "PrcItem": subscription_data['monthly_amount'],
            "UnmdItem": "MON"  # Month
        }]

        # Add usage charges if applicable
        if subscription_data.get('usage_charges'):
            for charge in subscription_data['usage_charges']:
                detalle.append({
                    "NmbItem": f"Cargo por uso - {charge['description']}",
                    "QtyItem": charge['quantity'],
                    "PrcItem": charge['unit_price'],
                    "UnmdItem": charge['unit']
                })

        factura = self.factory.create_factura_afecta(
            emisor=company,
            receptor=customer,
            folio=subscription_data['invoice_number'],
            fecha_emision=today.strftime('%Y-%m-%d'),
            detalle=detalle
        )

        return factura

# Usage
billing_service = SubscriptionBillingService()

subscription = {
    "customer_rut": "12345678-9",
    "customer_name": "Empresa Cliente SPA",
    "plan_name": "Professional",
    "monthly_amount": 50000,
    "invoice_number": 2001,
    "usage_charges": [
        {
            "description": "Storage adicional",
            "quantity": 100,
            "unit_price": 100,
            "unit": "GB"
        }
    ]
}

invoice = billing_service.generate_monthly_invoice(subscription)
```

### Use Case 3: Point of Sale Integration

```python
# pos_integration.py
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente

class POSService:
    def __init__(self, store_config):
        self.factory = DTEFactory()
        self.store = Contribuyente(store_config['rut'], store_config['name'])
        self.next_boleta_folio = store_config['next_folio']

    def process_sale(self, sale_data):
        """Process point of sale transaction"""

        # For POS, customer might be anonymous
        customer = Contribuyente("66666666-6", "Cliente Ocasional")

        # Convert sale items
        detalle = []
        for item in sale_data['items']:
            item_detail = {
                "NmbItem": item['description'],
                "QtyItem": item['quantity'],
                "PrcItem": item['unit_price']
            }

            # Apply discounts if any
            if item.get('discount_percent'):
                item_detail["DescuentoPct"] = item['discount_percent']

            detalle.append(item_detail)

        # Create boleta (receipt)
        boleta = self.factory.create_boleta_afecta(
            emisor=self.store,
            receptor=customer,
            folio=self.next_boleta_folio,
            fecha_emision=sale_data['sale_date'],
            detalle=detalle
        )

        # Increment folio for next sale
        self.next_boleta_folio += 1

        return {
            "document_id": boleta.get_id(),
            "xml": boleta.save_xml(),
            "folio": boleta.get_datos()['Documento']['Encabezado']['IdDoc']['Folio'],
            "total": sum(item['quantity'] * item['unit_price'] for item in sale_data['items'])
        }

# Store configuration
store_config = {
    "rut": "76354771-K",
    "name": "Minimarket El Centro",
    "next_folio": 1001
}

pos = POSService(store_config)

# Sale transaction
sale = {
    "sale_date": "2023-12-01",
    "items": [
        {
            "description": "Coca Cola 350ml",
            "quantity": 2,
            "unit_price": 800
        },
        {
            "description": "Pan Hallulla",
            "quantity": 4,
            "unit_price": 200
        }
    ]
}

receipt = pos.process_sale(sale)
print(f"Receipt created: {receipt['document_id']}")
print(f"Total: ${receipt['total']}")
```

---

## Performance Considerations

### Optimization Strategies

```python
# performance_optimization.py
from rypsystems_dte.config import ConfigManager
from rypsystems_dte.logging import PerformanceMonitor
import concurrent.futures
import time

class OptimizedDTEProcessor:
    def __init__(self):
        # Enable caching for better performance
        config = ConfigManager()
        config.set("cache.enabled", True)
        config.set("cache.ttl", 3600)

        self.performance_monitor = PerformanceMonitor()

    def batch_process_documents(self, document_requests, max_workers=4):
        """Process multiple documents in parallel"""

        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_request = {
                executor.submit(self.process_single_document, req): req
                for req in document_requests
            }

            # Collect results
            for future in concurrent.futures.as_completed(future_to_request):
                request = future_to_request[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "success": False,
                        "error": str(e),
                        "request_id": request.get("id", "unknown")
                    })

        return results

    def process_single_document(self, request):
        """Process a single document with performance monitoring"""

        start_time = time.time()

        try:
            # Your document processing logic here
            # ...

            processing_time = time.time() - start_time

            # Record performance metrics
            self.performance_monitor.record_metric("document_processing_time", processing_time, {
                "document_type": request.get("type", "unknown")
            })

            return {
                "success": True,
                "processing_time": processing_time
            }

        except Exception as e:
            self.performance_monitor.record_metric("document_processing_error", 1, {
                "error_type": type(e).__name__
            })
            raise
```

### Caching Strategy

```python
# caching.py
from rypsystems_dte.config import ConfigManager
import redis
import json
import hashlib

class DTECache:
    def __init__(self):
        config = ConfigManager()
        if config.get("cache.backend") == "redis":
            self.redis_client = redis.Redis.from_url(config.get("cache.redis_url"))
        else:
            self.redis_client = None
            self.memory_cache = {}

    def get_cached_document(self, cache_key):
        """Retrieve cached document"""
        if self.redis_client:
            cached = self.redis_client.get(cache_key)
            return json.loads(cached) if cached else None
        else:
            return self.memory_cache.get(cache_key)

    def cache_document(self, cache_key, document_data, ttl=3600):
        """Cache document data"""
        if self.redis_client:
            self.redis_client.setex(cache_key, ttl, json.dumps(document_data))
        else:
            self.memory_cache[cache_key] = document_data

    def generate_cache_key(self, document_data):
        """Generate unique cache key for document"""
        # Create hash from document content
        content = json.dumps(document_data, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
```

---

This comprehensive API reference provides all the necessary information for integrating any backend system with the RypSystems DTE library. The examples demonstrate practical implementation patterns and the documentation covers all aspects from basic usage to production deployment.