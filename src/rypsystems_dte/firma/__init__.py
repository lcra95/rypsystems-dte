"""
RypSystems DTE - Módulo de Firma Digital
Manejo de firmas digitales y TED (Timbre Electrónico DTE)

Componentes:
- TED: Generación y validación de Timbre Electrónico
- DigitalCertificate: Carga de certificados (.pfx/.p12/PEM) y firma RSA
- Certificate: Validación de certificados digitales
- XmlSigner: Firma y validación XML-DSig en formato SII
- Signature: Validación de firmas digitales XML
- Timestamp: Validación de sellos de tiempo
"""

from .ted import TEDBuilder, TEDValidator, TEDData, create_ted_from_document, generate_ted_barcode_from_data
from .digital_certificate import DigitalCertificate, SelfSignedCertificate, CertificateError
from .xml_signer import XmlSigner, SignatureError, SignatureValidationResult
from .certificate import (
    CertificateValidator,
    SiiCertificateValidator,
    CertificateInfo,
    CertificateChain,
    CertificateType,
    CertificateStatus,
    ValidationLevel
)
from .signature import (
    DigitalSignatureValidator,
    SiiSignatureValidator,
    SignatureInfo,
    SignatureReference,
    SignatureType,
    SignatureStatus,
    HashAlgorithm,
    SignatureAlgorithm
)
from .timestamp import (
    TimestampValidator,
    SiiTimestampValidator,
    TimestampInfo,
    TimestampRequest,
    TimestampStatus,
    TimestampPolicy
)

__all__ = [
    # TED components
    'TEDBuilder',
    'TEDValidator',
    'TEDData',
    'create_ted_from_document',
    'generate_ted_barcode_from_data',

    # Certificate loading
    'DigitalCertificate',
    'SelfSignedCertificate',
    'CertificateError',

    # XML signing
    'XmlSigner',
    'SignatureError',
    'SignatureValidationResult',

    # Certificate validation
    'CertificateValidator',
    'SiiCertificateValidator',
    'CertificateInfo',
    'CertificateChain',
    'CertificateType',
    'CertificateStatus',
    'ValidationLevel',

    # Digital signature validation
    'DigitalSignatureValidator',
    'SiiSignatureValidator',
    'SignatureInfo',
    'SignatureReference',
    'SignatureType',
    'SignatureStatus',
    'HashAlgorithm',
    'SignatureAlgorithm',

    # Timestamp validation
    'TimestampValidator',
    'SiiTimestampValidator',
    'TimestampInfo',
    'TimestampRequest',
    'TimestampStatus',
    'TimestampPolicy'
]