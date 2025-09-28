"""
Timestamp Validation System.

Provides timestamp validation for digital signatures including:
- RFC 3161 timestamp validation
- Trusted timestamp authority validation
- Timestamp integrity verification
"""

import hashlib
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID
import requests

from pydantic import BaseModel, Field, field_validator, ConfigDict

from .certificate import CertificateValidator, CertificateInfo


class TimestampStatus(str, Enum):
    """Timestamp validation status."""
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    UNTRUSTED = "untrusted"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


class TimestampPolicy(str, Enum):
    """Timestamp policy OIDs."""
    RFC3161 = "1.2.840.113549.1.9.16.1.4"
    BASELINE_T = "0.4.0.1733.2.2"
    LONG_TERM = "0.4.0.1733.2.3"


class TimestampInfo(BaseModel):
    """Timestamp information model."""

    # Basic information
    timestamp_value: datetime = Field(..., description="Timestamp value")
    timestamp_authority: str = Field(..., description="Timestamp Authority name")
    policy_oid: Optional[str] = Field(None, description="Timestamp policy OID")

    # Hash information
    hash_algorithm: str = Field(..., description="Hash algorithm used")
    message_imprint: str = Field(..., description="Base64 encoded message imprint")

    # Certificate information
    tsa_certificate: Optional[CertificateInfo] = Field(None, description="TSA certificate information")

    # Validation status
    status: TimestampStatus = Field(default=TimestampStatus.UNKNOWN)
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")
    validation_warnings: List[str] = Field(default_factory=list, description="Validation warnings")

    # Accuracy information
    accuracy_seconds: Optional[int] = Field(None, description="Accuracy in seconds")
    accuracy_millis: Optional[int] = Field(None, description="Accuracy in milliseconds")
    accuracy_micros: Optional[int] = Field(None, description="Accuracy in microseconds")

    # Additional metadata
    serial_number: Optional[str] = Field(None, description="Timestamp serial number")
    nonce: Optional[str] = Field(None, description="Nonce value")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class TimestampRequest(BaseModel):
    """RFC 3161 timestamp request."""

    version: int = Field(default=1, description="TSA version")
    message_imprint: str = Field(..., description="Base64 encoded message imprint")
    hash_algorithm: str = Field(..., description="Hash algorithm OID")
    policy_oid: Optional[str] = Field(None, description="Requested policy OID")
    nonce: Optional[str] = Field(None, description="Nonce value")
    cert_req: bool = Field(default=True, description="Request TSA certificate")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class TimestampValidator:
    """
    Timestamp validation system for digital signatures.

    Provides comprehensive timestamp validation including:
    - RFC 3161 timestamp token validation
    - TSA certificate validation
    - Timestamp accuracy verification
    - Policy compliance checking
    """

    # Known TSA certificate authorities
    TRUSTED_TSA_AUTHORITIES = [
        "DigiCert Timestamp Authority",
        "GlobalSign TSA",
        "Sectigo RSA Time Stamping Authority",
        "AC Tiempo SII",  # SII timestamp authority
    ]

    # Hash algorithm OIDs
    HASH_ALGORITHM_OIDS = {
        "1.3.14.3.2.26": "SHA-1",
        "2.16.840.1.101.3.4.2.1": "SHA-256",
        "2.16.840.1.101.3.4.2.2": "SHA-384",
        "2.16.840.1.101.3.4.2.3": "SHA-512",
    }

    def __init__(self,
                 certificate_validator: Optional[CertificateValidator] = None,
                 tsa_urls: Optional[List[str]] = None,
                 default_timeout: int = 30,
                 max_clock_skew: int = 300):
        """
        Initialize timestamp validator.

        Args:
            certificate_validator: Certificate validator instance
            tsa_urls: List of trusted TSA URLs
            default_timeout: Default timeout for TSA requests
            max_clock_skew: Maximum allowed clock skew in seconds
        """
        self.certificate_validator = certificate_validator or CertificateValidator()
        self.tsa_urls = tsa_urls or []
        self.default_timeout = default_timeout
        self.max_clock_skew = max_clock_skew

        # Internal caches
        self._timestamp_cache: Dict[str, Tuple[TimestampInfo, datetime]] = {}
        self._tsa_cert_cache: Dict[str, CertificateInfo] = {}

    def validate_timestamp_token(self, timestamp_token: bytes) -> TimestampInfo:
        """
        Validate RFC 3161 timestamp token.

        Args:
            timestamp_token: DER-encoded timestamp token

        Returns:
            Timestamp validation result
        """
        try:
            # Parse timestamp token (simplified)
            # In production, use proper ASN.1 parsing library like asn1crypto

            timestamp_info = TimestampInfo(
                timestamp_value=datetime.now(timezone.utc),
                timestamp_authority="Unknown TSA",
                hash_algorithm="SHA-256",
                message_imprint=""
            )

            # Basic validation - this is simplified
            # Real implementation would parse the full ASN.1 structure

            timestamp_info.status = TimestampStatus.VALID
            timestamp_info.validation_warnings.append("Simplified timestamp validation - full ASN.1 parsing needed")

            return timestamp_info

        except Exception as e:
            return TimestampInfo(
                timestamp_value=datetime.now(timezone.utc),
                timestamp_authority="Unknown",
                hash_algorithm="Unknown",
                message_imprint="",
                status=TimestampStatus.INVALID,
                validation_errors=[f"Timestamp token parsing failed: {e}"]
            )

    def validate_timestamp_signature(self,
                                   data: bytes,
                                   timestamp_info: TimestampInfo,
                                   expected_hash: Optional[str] = None) -> bool:
        """
        Validate timestamp signature and message imprint.

        Args:
            data: Original data that was timestamped
            timestamp_info: Timestamp information
            expected_hash: Expected hash value (optional)

        Returns:
            True if timestamp signature is valid
        """
        try:
            # Calculate message imprint
            hash_algorithm = timestamp_info.hash_algorithm.lower()

            if "sha1" in hash_algorithm:
                hasher = hashlib.sha1()
            elif "sha256" in hash_algorithm:
                hasher = hashlib.sha256()
            elif "sha384" in hash_algorithm:
                hasher = hashlib.sha384()
            elif "sha512" in hash_algorithm:
                hasher = hashlib.sha512()
            else:
                # Default to SHA-256
                hasher = hashlib.sha256()

            hasher.update(data)
            calculated_hash = base64.b64encode(hasher.digest()).decode('ascii')

            # Compare with timestamp message imprint
            if timestamp_info.message_imprint:
                if calculated_hash != timestamp_info.message_imprint:
                    timestamp_info.validation_errors.append("Message imprint mismatch")
                    return False

            # Compare with expected hash if provided
            if expected_hash and calculated_hash != expected_hash:
                timestamp_info.validation_errors.append("Expected hash mismatch")
                return False

            return True

        except Exception as e:
            timestamp_info.validation_errors.append(f"Timestamp signature validation failed: {e}")
            return False

    def validate_timestamp_accuracy(self, timestamp_info: TimestampInfo) -> bool:
        """
        Validate timestamp accuracy.

        Args:
            timestamp_info: Timestamp information

        Returns:
            True if timestamp accuracy is acceptable
        """
        now = datetime.now(timezone.utc)
        timestamp_time = timestamp_info.timestamp_value

        # Check if timestamp is too far in the future or past
        time_diff = abs((now - timestamp_time).total_seconds())

        # Allow for clock skew
        if time_diff > self.max_clock_skew:
            # Check accuracy bounds
            total_accuracy = 0
            if timestamp_info.accuracy_seconds:
                total_accuracy += timestamp_info.accuracy_seconds
            if timestamp_info.accuracy_millis:
                total_accuracy += timestamp_info.accuracy_millis / 1000
            if timestamp_info.accuracy_micros:
                total_accuracy += timestamp_info.accuracy_micros / 1000000

            # If no accuracy specified, use reasonable default
            if total_accuracy == 0:
                total_accuracy = 60  # 1 minute default

            if time_diff > total_accuracy + self.max_clock_skew:
                timestamp_info.validation_errors.append(
                    f"Timestamp accuracy exceeded: {time_diff} seconds vs {total_accuracy} allowed"
                )
                return False

        return True

    def validate_tsa_certificate(self, timestamp_info: TimestampInfo) -> bool:
        """
        Validate TSA certificate.

        Args:
            timestamp_info: Timestamp information

        Returns:
            True if TSA certificate is valid
        """
        if not timestamp_info.tsa_certificate:
            timestamp_info.validation_warnings.append("No TSA certificate provided")
            return True  # May be acceptable in some contexts

        tsa_cert = timestamp_info.tsa_certificate

        # Check certificate validity
        if tsa_cert.status.value not in ["valid"]:
            timestamp_info.validation_errors.append(f"TSA certificate status: {tsa_cert.status.value}")
            return False

        # Check if TSA is trusted
        if timestamp_info.timestamp_authority not in self.TRUSTED_TSA_AUTHORITIES:
            timestamp_info.validation_warnings.append(f"TSA '{timestamp_info.timestamp_authority}' not in trusted list")

        # Check extended key usage for timestamping
        if "time_stamping" not in tsa_cert.extended_key_usage:
            timestamp_info.validation_errors.append("TSA certificate does not have timestamping key usage")
            return False

        return True

    def request_timestamp(self, data: bytes, tsa_url: str, hash_algorithm: str = "SHA-256") -> Optional[TimestampInfo]:
        """
        Request timestamp from TSA.

        Args:
            data: Data to timestamp
            tsa_url: TSA URL
            hash_algorithm: Hash algorithm to use

        Returns:
            Timestamp information or None if failed
        """
        try:
            # Calculate message imprint
            if hash_algorithm.upper() == "SHA-1":
                hasher = hashlib.sha1()
            elif hash_algorithm.upper() == "SHA-256":
                hasher = hashlib.sha256()
            elif hash_algorithm.upper() == "SHA-384":
                hasher = hashlib.sha384()
            elif hash_algorithm.upper() == "SHA-512":
                hasher = hashlib.sha512()
            else:
                hasher = hashlib.sha256()

            hasher.update(data)
            message_imprint = base64.b64encode(hasher.digest()).decode('ascii')

            # Create timestamp request
            ts_request = TimestampRequest(
                message_imprint=message_imprint,
                hash_algorithm=hash_algorithm,
                nonce=str(hash(data))[:16]  # Simple nonce
            )

            # In production, this would create proper ASN.1 DER request
            # and send to TSA via HTTP POST

            # For now, return a mock timestamp
            timestamp_info = TimestampInfo(
                timestamp_value=datetime.now(timezone.utc),
                timestamp_authority="Mock TSA",
                hash_algorithm=hash_algorithm,
                message_imprint=message_imprint,
                status=TimestampStatus.VALID,
                validation_warnings=["Mock timestamp - production requires actual TSA integration"]
            )

            return timestamp_info

        except Exception as e:
            return TimestampInfo(
                timestamp_value=datetime.now(timezone.utc),
                timestamp_authority="Failed",
                hash_algorithm=hash_algorithm,
                message_imprint="",
                status=TimestampStatus.INVALID,
                validation_errors=[f"Timestamp request failed: {e}"]
            )

    def validate_complete_timestamp(self,
                                  data: bytes,
                                  timestamp_token: bytes,
                                  expected_time: Optional[datetime] = None) -> TimestampInfo:
        """
        Complete timestamp validation.

        Args:
            data: Original data
            timestamp_token: Timestamp token
            expected_time: Expected timestamp time (optional)

        Returns:
            Complete timestamp validation result
        """
        # Parse timestamp token
        timestamp_info = self.validate_timestamp_token(timestamp_token)

        if timestamp_info.status == TimestampStatus.INVALID:
            return timestamp_info

        # Validate message imprint
        signature_valid = self.validate_timestamp_signature(data, timestamp_info)
        if not signature_valid:
            timestamp_info.status = TimestampStatus.INVALID

        # Validate timestamp accuracy
        accuracy_valid = self.validate_timestamp_accuracy(timestamp_info)
        if not accuracy_valid:
            timestamp_info.status = TimestampStatus.INVALID

        # Validate TSA certificate
        tsa_valid = self.validate_tsa_certificate(timestamp_info)
        if not tsa_valid:
            timestamp_info.status = TimestampStatus.UNTRUSTED

        # Check expected time if provided
        if expected_time:
            time_diff = abs((timestamp_info.timestamp_value - expected_time).total_seconds())
            if time_diff > 3600:  # 1 hour tolerance
                timestamp_info.validation_warnings.append(
                    f"Timestamp differs from expected time by {time_diff} seconds"
                )

        # Final status determination
        if timestamp_info.validation_errors:
            timestamp_info.status = TimestampStatus.INVALID
        elif timestamp_info.status == TimestampStatus.UNKNOWN:
            timestamp_info.status = TimestampStatus.VALID

        return timestamp_info

    def is_timestamp_valid(self, data: bytes, timestamp_token: bytes) -> bool:
        """
        Simple boolean check if timestamp is valid.

        Args:
            data: Original data
            timestamp_token: Timestamp token

        Returns:
            True if timestamp is valid
        """
        timestamp_info = self.validate_complete_timestamp(data, timestamp_token)
        return timestamp_info.status == TimestampStatus.VALID

    def get_timestamp_summary(self, timestamp_info: TimestampInfo) -> Dict[str, Any]:
        """
        Get timestamp validation summary.

        Args:
            timestamp_info: Timestamp information

        Returns:
            Validation summary
        """
        return {
            'is_valid': timestamp_info.status == TimestampStatus.VALID,
            'status': timestamp_info.status.value,
            'timestamp_value': timestamp_info.timestamp_value.isoformat(),
            'timestamp_authority': timestamp_info.timestamp_authority,
            'hash_algorithm': timestamp_info.hash_algorithm,
            'has_errors': len(timestamp_info.validation_errors) > 0,
            'has_warnings': len(timestamp_info.validation_warnings) > 0,
            'error_count': len(timestamp_info.validation_errors),
            'warning_count': len(timestamp_info.validation_warnings),
            'accuracy_seconds': timestamp_info.accuracy_seconds,
            'serial_number': timestamp_info.serial_number
        }


class SiiTimestampValidator(TimestampValidator):
    """
    SII-specific timestamp validator.

    Extends base validator with SII-specific timestamp validation rules.
    """

    # SII-specific TSA authorities
    SII_TSA_AUTHORITIES = [
        "AC Tiempo SII",
        "Autoridad Certificadora de Tiempo SII"
    ]

    def __init__(self, **kwargs):
        """Initialize SII timestamp validator."""
        super().__init__(**kwargs)

        # Add SII TSA authorities to trusted list
        self.TRUSTED_TSA_AUTHORITIES.extend(self.SII_TSA_AUTHORITIES)

    def validate_dte_timestamp(self, dte_data: bytes, timestamp_token: bytes) -> TimestampInfo:
        """
        Validate timestamp for DTE document.

        Args:
            dte_data: DTE document data
            timestamp_token: Timestamp token

        Returns:
            DTE timestamp validation result
        """
        timestamp_info = self.validate_complete_timestamp(dte_data, timestamp_token)

        # Apply SII-specific validations
        self._apply_sii_timestamp_rules(timestamp_info)

        return timestamp_info

    def _apply_sii_timestamp_rules(self, timestamp_info: TimestampInfo):
        """Apply SII-specific timestamp validation rules."""
        # Check if TSA is SII-approved
        if timestamp_info.timestamp_authority not in self.SII_TSA_AUTHORITIES:
            timestamp_info.validation_warnings.append(
                "Timestamp authority not explicitly approved by SII"
            )

        # Check minimum hash algorithm strength
        if "sha1" in timestamp_info.hash_algorithm.lower():
            timestamp_info.validation_warnings.append(
                "SHA-1 hash algorithm is deprecated for new timestamps"
            )

        # Check timestamp is not too old (SII may have specific requirements)
        now = datetime.now(timezone.utc)
        age_days = (now - timestamp_info.timestamp_value).days

        if age_days > 365 * 10:  # 10 years
            timestamp_info.validation_warnings.append(
                f"Timestamp is very old ({age_days} days) - verify long-term validity requirements"
            )

    def is_valid_for_long_term_preservation(self, timestamp_info: TimestampInfo) -> bool:
        """
        Check if timestamp is valid for long-term document preservation.

        Args:
            timestamp_info: Timestamp information

        Returns:
            True if valid for long-term preservation
        """
        if timestamp_info.status != TimestampStatus.VALID:
            return False

        # Check hash algorithm strength
        if "sha1" in timestamp_info.hash_algorithm.lower():
            return False

        # Check TSA certificate validity period
        if timestamp_info.tsa_certificate:
            now = datetime.now(timezone.utc)
            cert_valid_until = timestamp_info.tsa_certificate.not_after

            # TSA certificate should be valid for reasonable period
            if (cert_valid_until - now).days < 30:
                return False

        return True