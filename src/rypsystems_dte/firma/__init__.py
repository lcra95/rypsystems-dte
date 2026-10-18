"""
RypSystems DTE - Módulo de Firma Digital
Manejo de firmas digitales y TED (Timbre Electrónico DTE)

Componentes:
- TED: Generación y validación de Timbre Electrónico
- DigitalCertificate: Carga de certificados (.pfx/.p12/PEM) y firma RSA
- XmlSigner: Firma y validación XML-DSig en formato SII
"""

from .ted import TEDBuilder, TEDValidator, TEDData, create_ted_from_document, generate_ted_barcode_from_data
from .digital_certificate import DigitalCertificate, SelfSignedCertificate, CertificateError
from .xml_signer import XmlSigner, SignatureError, SignatureValidationResult

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
]
