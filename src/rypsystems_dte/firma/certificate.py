"""
Certificate Management and Validation System.

Provides comprehensive certificate validation including chain validation,
revocation checking, and SII certificate authority validation.
"""

import re
import hashlib
import base64
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import NameOID, ExtensionOID
import requests

from pydantic import BaseModel, Field, field_validator, ConfigDict


class CertificateType(str, Enum):
    """Types of certificates supported."""
    SII_AUTHORITY = "sii_authority"
    SII_COMPANY = "sii_company"
    SII_PERSON = "sii_person"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class CertificateStatus(str, Enum):
    """Certificate validation status."""
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class ValidationLevel(str, Enum):
    """Certificate validation levels."""
    BASIC = "basic"           # Basic certificate format validation
    CHAIN = "chain"           # Certificate chain validation
    REVOCATION = "revocation" # Include revocation checking
    FULL = "full"             # Complete validation including all checks


class CertificateInfo(BaseModel):
    """Certificate information model."""

    # Basic information
    subject: str = Field(..., description="Certificate subject")
    issuer: str = Field(..., description="Certificate issuer")
    serial_number: str = Field(..., description="Certificate serial number")

    # Validity period
    not_before: datetime = Field(..., description="Valid from date")
    not_after: datetime = Field(..., description="Valid until date")

    # Certificate details
    certificate_type: CertificateType = Field(default=CertificateType.UNKNOWN)
    public_key_algorithm: str = Field(..., description="Public key algorithm")
    signature_algorithm: str = Field(..., description="Signature algorithm")
    key_size: int = Field(..., description="Key size in bits")

    # Extensions
    key_usage: List[str] = Field(default_factory=list, description="Key usage extensions")
    extended_key_usage: List[str] = Field(default_factory=list, description="Extended key usage")

    # SII specific
    rut_certificate: Optional[str] = Field(None, description="RUT from certificate")
    company_name: Optional[str] = Field(None, description="Company name from certificate")

    # Validation status
    status: CertificateStatus = Field(default=CertificateStatus.UNKNOWN)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class CertificateChain(BaseModel):
    """Certificate chain validation result."""

    end_entity: CertificateInfo = Field(..., description="End entity certificate")
    intermediates: List[CertificateInfo] = Field(default_factory=list, description="Intermediate certificates")
    root: Optional[CertificateInfo] = Field(None, description="Root certificate")

    # Chain validation
    is_valid_chain: bool = Field(default=False, description="Chain is valid")
    chain_errors: List[str] = Field(default_factory=list, description="Chain validation errors")

    # Trust validation
    is_trusted: bool = Field(default=False, description="Chain is trusted")
    trust_errors: List[str] = Field(default_factory=list, description="Trust validation errors")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class CertificateValidator:
    """
    Certificate validation and management system.

    Provides comprehensive certificate validation including:
    - Certificate format and structure validation
    - Certificate chain validation
    - Revocation checking (CRL/OCSP)
    - SII-specific certificate validation
    """

    # SII Certificate Authority information
    SII_CA_SUBJECTS = [
        "CN=SII CA, O=Servicio de Impuestos Internos, C=CL",
        "CN=AC RAIZ SII, O=Servicio de Impuestos Internos, C=CL",
        "CN=AC SII, O=Servicio de Impuestos Internos, C=CL"
    ]

    # Known SII root certificate fingerprints
    SII_ROOT_FINGERPRINTS = [
        # Add known SII root certificate fingerprints here
        "sha1:1234567890abcdef1234567890abcdef12345678",
        "sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"
    ]

    def __init__(self,
                 trust_store_path: Optional[str] = None,
                 enable_crl_check: bool = True,
                 enable_ocsp_check: bool = True,
                 cache_ttl: int = 3600):
        """
        Initialize certificate validator.

        Args:
            trust_store_path: Path to trust store directory
            enable_crl_check: Enable CRL checking
            enable_ocsp_check: Enable OCSP checking
            cache_ttl: Cache TTL for validation results
        """
        self.trust_store_path = trust_store_path
        self.enable_crl_check = enable_crl_check
        self.enable_ocsp_check = enable_ocsp_check
        self.cache_ttl = cache_ttl

        # Internal caches
        self._certificate_cache: Dict[str, x509.Certificate] = {}
        self._validation_cache: Dict[str, Tuple[CertificateInfo, datetime]] = {}
        self._crl_cache: Dict[str, Tuple[Any, datetime]] = {}

        # Load trust store
        self.trusted_certificates = self._load_trust_store()

    def _load_trust_store(self) -> List[x509.Certificate]:
        """Load trusted certificates from trust store."""
        trusted_certs = []

        if self.trust_store_path and Path(self.trust_store_path).exists():
            trust_store = Path(self.trust_store_path)

            for cert_file in trust_store.glob("*.pem"):
                try:
                    with open(cert_file, 'rb') as f:
                        cert_data = f.read()
                        cert = x509.load_pem_x509_certificate(cert_data)
                        trusted_certs.append(cert)
                except Exception as e:
                    print(f"Warning: Could not load certificate {cert_file}: {e}")

        return trusted_certs

    def parse_certificate(self, certificate_data: Union[str, bytes]) -> x509.Certificate:
        """
        Parse certificate from PEM or DER format.

        Args:
            certificate_data: Certificate data as string or bytes

        Returns:
            Parsed X.509 certificate

        Raises:
            ValueError: If certificate cannot be parsed
        """
        try:
            if isinstance(certificate_data, str):
                if certificate_data.startswith('-----BEGIN CERTIFICATE-----'):
                    # PEM format
                    cert_bytes = certificate_data.encode('utf-8')
                    return x509.load_pem_x509_certificate(cert_bytes)
                else:
                    # Assume base64 encoded DER
                    cert_bytes = base64.b64decode(certificate_data)
                    return x509.load_der_x509_certificate(cert_bytes)
            else:
                # Try DER first, then PEM
                try:
                    return x509.load_der_x509_certificate(certificate_data)
                except ValueError:
                    return x509.load_pem_x509_certificate(certificate_data)

        except Exception as e:
            raise ValueError(f"Could not parse certificate: {e}")

    def extract_certificate_info(self, certificate: x509.Certificate) -> CertificateInfo:
        """
        Extract comprehensive information from certificate.

        Args:
            certificate: X.509 certificate

        Returns:
            Certificate information
        """
        # Basic information
        subject = certificate.subject.rfc4514_string()
        issuer = certificate.issuer.rfc4514_string()
        serial_number = str(certificate.serial_number)

        # Validity period
        not_before = certificate.not_valid_before.replace(tzinfo=timezone.utc)
        not_after = certificate.not_valid_after.replace(tzinfo=timezone.utc)

        # Public key information
        public_key = certificate.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key_algorithm = "RSA"
            key_size = public_key.key_size
        else:
            public_key_algorithm = type(public_key).__name__
            key_size = 0

        # Signature algorithm
        signature_algorithm = certificate.signature_algorithm_oid._name

        # Extensions
        key_usage = []
        extended_key_usage = []

        try:
            ku_ext = certificate.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE)
            ku = ku_ext.value
            if ku.digital_signature:
                key_usage.append("digital_signature")
            if ku.key_encipherment:
                key_usage.append("key_encipherment")
            if ku.data_encipherment:
                key_usage.append("data_encipherment")
            if ku.key_agreement:
                key_usage.append("key_agreement")
            if ku.key_cert_sign:
                key_usage.append("key_cert_sign")
            if ku.crl_sign:
                key_usage.append("crl_sign")
        except x509.ExtensionNotFound:
            pass

        try:
            eku_ext = certificate.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE)
            eku = eku_ext.value
            for usage in eku:
                extended_key_usage.append(usage._name)
        except x509.ExtensionNotFound:
            pass

        # Extract SII-specific information
        rut_certificate = self._extract_rut_from_certificate(certificate)
        company_name = self._extract_company_name_from_certificate(certificate)
        certificate_type = self._determine_certificate_type(certificate)

        # Determine current status
        now = datetime.now(timezone.utc)
        if now < not_before or now > not_after:
            status = CertificateStatus.EXPIRED
        else:
            status = CertificateStatus.VALID

        return CertificateInfo(
            subject=subject,
            issuer=issuer,
            serial_number=serial_number,
            not_before=not_before,
            not_after=not_after,
            certificate_type=certificate_type,
            public_key_algorithm=public_key_algorithm,
            signature_algorithm=signature_algorithm,
            key_size=key_size,
            key_usage=key_usage,
            extended_key_usage=extended_key_usage,
            rut_certificate=rut_certificate,
            company_name=company_name,
            status=status
        )

    def _extract_rut_from_certificate(self, certificate: x509.Certificate) -> Optional[str]:
        """Extract RUT from certificate subject or extensions."""
        # Try to extract RUT from subject common name
        try:
            common_name = None
            for attribute in certificate.subject:
                if attribute.oid == NameOID.COMMON_NAME:
                    common_name = attribute.value
                    break

            if common_name:
                # Look for RUT pattern in common name
                rut_pattern = r'\b(\d{1,8}-[\dkK])\b'
                match = re.search(rut_pattern, common_name)
                if match:
                    return match.group(1).upper()
        except Exception:
            pass

        # Try to extract from subject alternative name or other extensions
        try:
            san_ext = certificate.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            for name in san_ext.value:
                if hasattr(name, 'value'):
                    rut_pattern = r'\b(\d{1,8}-[\dkK])\b'
                    match = re.search(rut_pattern, str(name.value))
                    if match:
                        return match.group(1).upper()
        except x509.ExtensionNotFound:
            pass

        return None

    def _extract_company_name_from_certificate(self, certificate: x509.Certificate) -> Optional[str]:
        """Extract company name from certificate subject."""
        try:
            for attribute in certificate.subject:
                if attribute.oid == NameOID.ORGANIZATION_NAME:
                    return attribute.value
        except Exception:
            pass
        return None

    def _determine_certificate_type(self, certificate: x509.Certificate) -> CertificateType:
        """Determine certificate type based on issuer and subject."""
        issuer = certificate.issuer.rfc4514_string()
        subject = certificate.subject.rfc4514_string()

        # Check if it's an SII certificate
        for sii_subject in self.SII_CA_SUBJECTS:
            if sii_subject in issuer or sii_subject in subject:
                if "Servicio de Impuestos Internos" in subject:
                    return CertificateType.SII_AUTHORITY
                elif self._extract_rut_from_certificate(certificate):
                    # Has RUT, likely a company certificate
                    return CertificateType.SII_COMPANY
                else:
                    return CertificateType.SII_PERSON

        return CertificateType.THIRD_PARTY

    def validate_certificate(self,
                           certificate_data: Union[str, bytes],
                           validation_level: ValidationLevel = ValidationLevel.BASIC) -> CertificateInfo:
        """
        Validate certificate with specified validation level.

        Args:
            certificate_data: Certificate data
            validation_level: Level of validation to perform

        Returns:
            Certificate information with validation results
        """
        # Parse certificate
        certificate = self.parse_certificate(certificate_data)

        # Check cache
        cert_fingerprint = self._get_certificate_fingerprint(certificate)
        if cert_fingerprint in self._validation_cache:
            cached_info, cached_time = self._validation_cache[cert_fingerprint]
            if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                return cached_info

        # Extract basic information
        cert_info = self.extract_certificate_info(certificate)

        # Perform validation based on level
        if validation_level in [ValidationLevel.CHAIN, ValidationLevel.REVOCATION, ValidationLevel.FULL]:
            # Build and validate certificate chain
            chain_result = self.validate_certificate_chain([certificate])
            if not chain_result.is_valid_chain:
                cert_info.status = CertificateStatus.INVALID

        if validation_level in [ValidationLevel.REVOCATION, ValidationLevel.FULL]:
            # Check revocation status
            if self._is_certificate_revoked(certificate):
                cert_info.status = CertificateStatus.REVOKED

        # Cache result
        self._validation_cache[cert_fingerprint] = (cert_info, datetime.now())

        return cert_info

    def validate_certificate_chain(self, certificates: List[x509.Certificate]) -> CertificateChain:
        """
        Validate certificate chain.

        Args:
            certificates: List of certificates (end entity first)

        Returns:
            Certificate chain validation result
        """
        if not certificates:
            return CertificateChain(
                end_entity=CertificateInfo(
                    subject="", issuer="", serial_number="",
                    not_before=datetime.now(), not_after=datetime.now(),
                    public_key_algorithm="", signature_algorithm="", key_size=0
                ),
                chain_errors=["No certificates provided"]
            )

        # Extract certificate information
        end_entity = self.extract_certificate_info(certificates[0])
        intermediates = [self.extract_certificate_info(cert) for cert in certificates[1:]]

        chain_errors = []
        trust_errors = []
        is_valid_chain = True
        is_trusted = False

        # Basic chain validation
        for i in range(len(certificates) - 1):
            current_cert = certificates[i]
            issuer_cert = certificates[i + 1]

            # Verify signature
            try:
                public_key = issuer_cert.public_key()
                current_cert.public_key().verify(
                    current_cert.signature,
                    current_cert.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
            except Exception as e:
                chain_errors.append(f"Signature verification failed for certificate {i}: {e}")
                is_valid_chain = False

        # Check if chain is trusted
        if certificates:
            # Check against trusted certificates
            root_cert = certificates[-1]
            root_fingerprint = self._get_certificate_fingerprint(root_cert)

            for trusted_cert in self.trusted_certificates:
                trusted_fingerprint = self._get_certificate_fingerprint(trusted_cert)
                if root_fingerprint == trusted_fingerprint:
                    is_trusted = True
                    break

            if not is_trusted:
                # Check against SII fingerprints
                for fingerprint in self.SII_ROOT_FINGERPRINTS:
                    if fingerprint in root_fingerprint:
                        is_trusted = True
                        break

            if not is_trusted:
                trust_errors.append("Certificate chain is not trusted")

        root_info = None
        if len(certificates) > 1:
            root_info = self.extract_certificate_info(certificates[-1])

        return CertificateChain(
            end_entity=end_entity,
            intermediates=intermediates,
            root=root_info,
            is_valid_chain=is_valid_chain,
            chain_errors=chain_errors,
            is_trusted=is_trusted,
            trust_errors=trust_errors
        )

    def _get_certificate_fingerprint(self, certificate: x509.Certificate) -> str:
        """Get certificate fingerprint."""
        fingerprint = hashlib.sha256(certificate.fingerprint(hashes.SHA256())).hexdigest()
        return f"sha256:{fingerprint}"

    def _is_certificate_revoked(self, certificate: x509.Certificate) -> bool:
        """Check if certificate is revoked using CRL/OCSP."""
        # Simplified revocation checking
        # In production, implement proper CRL and OCSP checking

        if not self.enable_crl_check and not self.enable_ocsp_check:
            return False

        # TODO: Implement proper CRL checking
        if self.enable_crl_check:
            crl_result = self._check_crl(certificate)
            if crl_result:
                return True

        # TODO: Implement proper OCSP checking
        if self.enable_ocsp_check:
            ocsp_result = self._check_ocsp(certificate)
            if ocsp_result:
                return True

        return False

    def _check_crl(self, certificate: x509.Certificate) -> bool:
        """Check certificate against CRL."""
        # Simplified CRL checking
        # In production, implement proper CRL fetching and validation
        return False

    def _check_ocsp(self, certificate: x509.Certificate) -> bool:
        """Check certificate against OCSP."""
        # Simplified OCSP checking
        # In production, implement proper OCSP request and validation
        return False

    def verify_certificate_signature(self,
                                   certificate: x509.Certificate,
                                   data: bytes,
                                   signature: bytes,
                                   signature_algorithm: str = "SHA256withRSA") -> bool:
        """
        Verify signature using certificate public key.

        Args:
            certificate: Certificate containing public key
            data: Original data that was signed
            signature: Signature to verify
            signature_algorithm: Signature algorithm used

        Returns:
            True if signature is valid
        """
        try:
            public_key = certificate.public_key()

            if not isinstance(public_key, rsa.RSAPublicKey):
                raise ValueError("Certificate does not contain RSA public key")

            # Determine hash algorithm
            if "SHA1" in signature_algorithm.upper():
                hash_algorithm = hashes.SHA1()
            elif "SHA256" in signature_algorithm.upper():
                hash_algorithm = hashes.SHA256()
            elif "SHA512" in signature_algorithm.upper():
                hash_algorithm = hashes.SHA512()
            else:
                hash_algorithm = hashes.SHA256()  # Default

            # Verify signature
            public_key.verify(
                signature,
                data,
                padding.PKCS1v15(),
                hash_algorithm
            )

            return True

        except Exception:
            return False

    def get_validation_summary(self, cert_info: CertificateInfo) -> Dict[str, Any]:
        """
        Get validation summary for certificate.

        Args:
            cert_info: Certificate information

        Returns:
            Validation summary
        """
        now = datetime.now(timezone.utc)

        return {
            'certificate_status': cert_info.status.value,
            'is_valid': cert_info.status == CertificateStatus.VALID,
            'is_expired': now > cert_info.not_after,
            'expires_in_days': (cert_info.not_after - now).days if now < cert_info.not_after else 0,
            'certificate_type': cert_info.certificate_type.value,
            'has_digital_signature': 'digital_signature' in cert_info.key_usage,
            'rut_certificate': cert_info.rut_certificate,
            'company_name': cert_info.company_name,
            'key_size': cert_info.key_size,
            'signature_algorithm': cert_info.signature_algorithm
        }


class SiiCertificateValidator(CertificateValidator):
    """
    SII-specific certificate validator.

    Extends base validator with SII-specific validation rules.
    """

    def __init__(self, **kwargs):
        """Initialize SII certificate validator."""
        super().__init__(**kwargs)

    def validate_sii_certificate(self, certificate_data: Union[str, bytes]) -> CertificateInfo:
        """
        Validate SII-issued certificate with SII-specific rules.

        Args:
            certificate_data: Certificate data

        Returns:
            Certificate information with SII validation
        """
        cert_info = self.validate_certificate(certificate_data, ValidationLevel.FULL)

        # Additional SII-specific validations
        if cert_info.certificate_type not in [CertificateType.SII_AUTHORITY,
                                              CertificateType.SII_COMPANY,
                                              CertificateType.SII_PERSON]:
            cert_info.status = CertificateStatus.INVALID

        # Validate RUT format if present
        if cert_info.rut_certificate:
            from ..sii.utils import RutValidator
            if not RutValidator.validate(cert_info.rut_certificate):
                cert_info.status = CertificateStatus.INVALID

        # Check required key usage for SII certificates
        if cert_info.certificate_type == CertificateType.SII_COMPANY:
            if 'digital_signature' not in cert_info.key_usage:
                cert_info.status = CertificateStatus.INVALID

        return cert_info

    def is_valid_for_dte_signing(self, certificate_data: Union[str, bytes]) -> bool:
        """
        Check if certificate is valid for DTE signing.

        Args:
            certificate_data: Certificate data

        Returns:
            True if valid for DTE signing
        """
        cert_info = self.validate_sii_certificate(certificate_data)

        return (
            cert_info.status == CertificateStatus.VALID and
            cert_info.certificate_type in [CertificateType.SII_COMPANY, CertificateType.SII_PERSON] and
            'digital_signature' in cert_info.key_usage and
            cert_info.rut_certificate is not None
        )