"""
Comprehensive tests for digital signature validation system.

Tests certificate validation, digital signature validation,
and timestamp validation components.
"""

import pytest
import base64
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

from rypsystems_dte.firma import (
    CertificateValidator,
    SiiCertificateValidator,
    DigitalSignatureValidator,
    SiiSignatureValidator,
    TimestampValidator,
    SiiTimestampValidator,
    CertificateInfo,
    CertificateType,
    CertificateStatus,
    ValidationLevel,
    SignatureInfo,
    SignatureStatus,
    TimestampInfo,
    TimestampStatus
)


class TestCertificateValidator:
    """Tests for certificate validation."""

    @pytest.fixture
    def certificate_validator(self):
        """Create certificate validator instance."""
        return CertificateValidator()

    @pytest.fixture
    def sii_certificate_validator(self):
        """Create SII certificate validator instance."""
        return SiiCertificateValidator()

    @pytest.fixture
    def mock_certificate_pem(self):
        """Mock certificate in PEM format."""
        return """-----BEGIN CERTIFICATE-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAuE7w+FAKE_CERT_DATA
This is a mock certificate for testing purposes only
It contains fake data and should never be used in production
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAuE7w+FAKE_CERT_DATA
-----END CERTIFICATE-----"""

    def test_certificate_validator_initialization(self, certificate_validator):
        """Test certificate validator initialization."""
        assert certificate_validator.trust_store_path is None
        assert certificate_validator.enable_crl_check is True
        assert certificate_validator.enable_ocsp_check is True
        assert certificate_validator.cache_ttl == 3600

    def test_sii_certificate_validator_initialization(self, sii_certificate_validator):
        """Test SII certificate validator initialization."""
        assert isinstance(sii_certificate_validator, SiiCertificateValidator)
        assert isinstance(sii_certificate_validator, CertificateValidator)

    @patch('cryptography.x509.load_pem_x509_certificate')
    def test_parse_certificate_pem(self, mock_load_pem, certificate_validator, mock_certificate_pem):
        """Test parsing PEM certificate."""
        mock_cert = Mock()
        mock_load_pem.return_value = mock_cert

        result = certificate_validator.parse_certificate(mock_certificate_pem)

        assert result == mock_cert
        mock_load_pem.assert_called_once()

    @patch('cryptography.x509.load_der_x509_certificate')
    def test_parse_certificate_der(self, mock_load_der, certificate_validator):
        """Test parsing DER certificate."""
        mock_cert = Mock()
        mock_load_der.return_value = mock_cert

        cert_bytes = b"mock_der_certificate_data"
        result = certificate_validator.parse_certificate(cert_bytes)

        assert result == mock_cert
        mock_load_der.assert_called_once()

    def test_parse_certificate_invalid(self, certificate_validator):
        """Test parsing invalid certificate."""
        with pytest.raises(ValueError, match="Could not parse certificate"):
            certificate_validator.parse_certificate("invalid_certificate_data")

    @patch('rypsystems_dte.firma.certificate.CertificateValidator.parse_certificate')
    def test_extract_certificate_info(self, mock_parse, certificate_validator):
        """Test extracting certificate information."""
        # Mock certificate
        mock_cert = Mock()
        mock_cert.subject.rfc4514_string.return_value = "CN=Test Subject"
        mock_cert.issuer.rfc4514_string.return_value = "CN=Test Issuer"
        mock_cert.serial_number = 12345
        mock_cert.not_valid_before = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock_cert.not_valid_after = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_cert.signature_algorithm_oid._name = "sha256WithRSAEncryption"

        # Mock public key
        mock_public_key = Mock()
        mock_public_key.key_size = 2048
        mock_cert.public_key.return_value = mock_public_key

        # Mock extensions
        mock_cert.extensions.get_extension_for_oid.side_effect = Exception("Extension not found")

        mock_parse.return_value = mock_cert

        cert_info = certificate_validator.extract_certificate_info(mock_cert)

        assert cert_info.subject == "CN=Test Subject"
        assert cert_info.issuer == "CN=Test Issuer"
        assert cert_info.serial_number == "12345"
        assert cert_info.key_size == 2048

    def test_validate_certificate_basic(self, certificate_validator, mock_certificate_pem):
        """Test basic certificate validation."""
        with patch.object(certificate_validator, 'parse_certificate') as mock_parse, \
             patch.object(certificate_validator, 'extract_certificate_info') as mock_extract:

            mock_cert = Mock()
            mock_parse.return_value = mock_cert

            cert_info = CertificateInfo(
                subject="CN=Test",
                issuer="CN=Test CA",
                serial_number="12345",
                not_before=datetime.now(timezone.utc) - timedelta(days=30),
                not_after=datetime.now(timezone.utc) + timedelta(days=30),
                public_key_algorithm="RSA",
                signature_algorithm="sha256WithRSAEncryption",
                key_size=2048,
                status=CertificateStatus.VALID
            )
            mock_extract.return_value = cert_info

            result = certificate_validator.validate_certificate(
                mock_certificate_pem, ValidationLevel.BASIC
            )

            assert result.status == CertificateStatus.VALID
            assert result.subject == "CN=Test"

    def test_determine_certificate_type_sii_company(self, certificate_validator):
        """Test determining SII company certificate type."""
        mock_cert = Mock()
        mock_cert.issuer.rfc4514_string.return_value = "CN=SII CA, O=Servicio de Impuestos Internos, C=CL"
        mock_cert.subject.rfc4514_string.return_value = "CN=12345678-9, O=Test Company"

        # Mock RUT extraction
        with patch.object(certificate_validator, '_extract_rut_from_certificate', return_value="12345678-9"):
            cert_type = certificate_validator._determine_certificate_type(mock_cert)
            assert cert_type == CertificateType.SII_COMPANY

    def test_extract_rut_from_certificate(self, certificate_validator):
        """Test RUT extraction from certificate."""
        mock_cert = Mock()

        # Mock subject with RUT in common name
        mock_attribute = Mock()
        mock_attribute.oid = Mock()
        mock_attribute.oid.__eq__ = Mock(return_value=True)  # Mock NameOID.COMMON_NAME
        mock_attribute.value = "12345678-9"

        mock_cert.subject = [mock_attribute]

        # Mock NameOID.COMMON_NAME comparison
        with patch('rypsystems_dte.firma.certificate.NameOID') as mock_name_oid:
            mock_name_oid.COMMON_NAME = mock_attribute.oid

            rut = certificate_validator._extract_rut_from_certificate(mock_cert)
            assert rut == "12345678-9"


class TestDigitalSignatureValidator:
    """Tests for digital signature validation."""

    @pytest.fixture
    def signature_validator(self):
        """Create signature validator instance."""
        return DigitalSignatureValidator()

    @pytest.fixture
    def sii_signature_validator(self):
        """Create SII signature validator instance."""
        return SiiSignatureValidator()

    @pytest.fixture
    def sample_signed_xml(self):
        """Sample XML with signature."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
    <Data>Sample document content</Data>
    <ds:Signature Id="signature-1">
        <ds:SignedInfo>
            <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
            <ds:SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha256"/>
            <ds:Reference URI="">
                <ds:Transforms>
                    <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
                </ds:Transforms>
                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                <ds:DigestValue>mockDigestValue</ds:DigestValue>
            </ds:Reference>
        </ds:SignedInfo>
        <ds:SignatureValue>mockSignatureValue</ds:SignatureValue>
        <ds:KeyInfo>
            <ds:X509Data>
                <ds:X509Certificate>mockCertificateData</ds:X509Certificate>
            </ds:X509Data>
        </ds:KeyInfo>
    </ds:Signature>
</Document>"""

    def test_signature_validator_initialization(self, signature_validator):
        """Test signature validator initialization."""
        assert signature_validator.certificate_validator is not None
        assert signature_validator.strict_validation is True
        assert signature_validator.enable_timestamp_validation is True

    def test_validate_xml_signature_basic(self, signature_validator, sample_signed_xml):
        """Test basic XML signature validation."""
        with patch.object(signature_validator, '_validate_signature_element') as mock_validate:
            mock_sig_info = SignatureInfo(
                canonicalization_method="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
                signature_method="http://www.w3.org/2000/09/xmldsig#rsa-sha256",
                signature_value="mockSignatureValue",
                status=SignatureStatus.VALID
            )
            mock_validate.return_value = mock_sig_info

            results = signature_validator.validate_xml_signature(sample_signed_xml)

            assert len(results) == 1
            assert results[0].status == SignatureStatus.VALID

    def test_validate_xml_signature_invalid_xml(self, signature_validator):
        """Test validation with invalid XML."""
        invalid_xml = "This is not valid XML"

        results = signature_validator.validate_xml_signature(invalid_xml)

        assert len(results) == 1
        assert results[0].status == SignatureStatus.CORRUPTED
        assert "XML parsing error" in results[0].validation_errors[0]

    def test_extract_signature_info(self, signature_validator):
        """Test extracting signature information."""
        with patch('lxml.etree.fromstring') as mock_fromstring:
            # Mock signature element
            mock_sig_element = Mock()
            mock_sig_element.get.return_value = "signature-1"

            # Mock signed info
            mock_signed_info = Mock()
            mock_sig_element.find.return_value = mock_signed_info

            # Mock canonicalization method
            mock_c14n = Mock()
            mock_c14n.get.return_value = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
            mock_signed_info.find.side_effect = [mock_c14n, mock_c14n]  # c14n and sig method

            # Mock signature value
            mock_sig_value = Mock()
            mock_sig_value.text = "mockSignatureValue"
            mock_sig_element.find.side_effect = [mock_signed_info, mock_sig_value]

            sig_info = SignatureInfo(
                canonicalization_method="",
                signature_method="",
                signature_value=""
            )

            signature_validator._extract_signature_info(mock_sig_element, sig_info)

            assert sig_info.signature_id == "signature-1"

    def test_sii_signature_validator_validate_dte(self, sii_signature_validator, sample_signed_xml):
        """Test SII DTE signature validation."""
        with patch.object(sii_signature_validator, 'validate_xml_signature') as mock_validate:
            mock_sig_info = SignatureInfo(
                canonicalization_method="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
                signature_method="http://www.w3.org/2000/09/xmldsig#rsa-sha256",
                signature_value="mockSignatureValue",
                status=SignatureStatus.VALID
            )
            mock_validate.return_value = [mock_sig_info]

            results = sii_signature_validator.validate_dte_signature(sample_signed_xml)

            assert len(results) == 1
            assert results[0].status == SignatureStatus.VALID

    def test_validate_ted_signature_valid(self, sii_signature_validator):
        """Test TED signature validation."""
        ted_xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
<TED>
    <DD>
        <RE>76354771-K</RE>
        <TD>33</TD>
        <F>1001</F>
    </DD>
    <FRMT algoritmo="SHA1withRSA">mockSignatureValueThatIsLongEnough</FRMT>
</TED>"""

        result = sii_signature_validator.validate_ted_signature(ted_xml)

        assert result.status == SignatureStatus.VALID
        assert result.signature_method == "SHA1withRSA"

    def test_validate_ted_signature_invalid(self, sii_signature_validator):
        """Test TED signature validation with invalid signature."""
        ted_xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
<TED>
    <DD>
        <RE>76354771-K</RE>
        <TD>33</TD>
        <F>1001</F>
    </DD>
    <FRMT algoritmo="SHA1withRSA">short</FRMT>
</TED>"""

        result = sii_signature_validator.validate_ted_signature(ted_xml)

        assert result.status == SignatureStatus.INVALID
        assert "signature value too short" in result.validation_errors[0]

    def test_is_dte_signature_valid(self, sii_signature_validator, sample_signed_xml):
        """Test simple boolean signature validation."""
        with patch.object(sii_signature_validator, 'validate_dte_signature') as mock_validate:
            mock_sig_info = SignatureInfo(
                canonicalization_method="",
                signature_method="",
                signature_value="",
                status=SignatureStatus.VALID
            )
            mock_validate.return_value = [mock_sig_info]

            result = sii_signature_validator.is_dte_signature_valid(sample_signed_xml)
            assert result is True


class TestTimestampValidator:
    """Tests for timestamp validation."""

    @pytest.fixture
    def timestamp_validator(self):
        """Create timestamp validator instance."""
        return TimestampValidator()

    @pytest.fixture
    def sii_timestamp_validator(self):
        """Create SII timestamp validator instance."""
        return SiiTimestampValidator()

    @pytest.fixture
    def mock_timestamp_token(self):
        """Mock timestamp token."""
        return b"mock_timestamp_token_data"

    def test_timestamp_validator_initialization(self, timestamp_validator):
        """Test timestamp validator initialization."""
        assert timestamp_validator.certificate_validator is not None
        assert timestamp_validator.default_timeout == 30
        assert timestamp_validator.max_clock_skew == 300

    def test_validate_timestamp_token(self, timestamp_validator, mock_timestamp_token):
        """Test timestamp token validation."""
        result = timestamp_validator.validate_timestamp_token(mock_timestamp_token)

        assert isinstance(result, TimestampInfo)
        assert result.status == TimestampStatus.VALID
        assert "Simplified timestamp validation" in result.validation_warnings[0]

    def test_validate_timestamp_signature_valid(self, timestamp_validator):
        """Test timestamp signature validation."""
        data = b"test data to be timestamped"
        timestamp_info = TimestampInfo(
            timestamp_value=datetime.now(timezone.utc),
            timestamp_authority="Test TSA",
            hash_algorithm="SHA-256",
            message_imprint=""  # Will be calculated
        )

        # Calculate expected message imprint
        import hashlib
        hasher = hashlib.sha256()
        hasher.update(data)
        expected_imprint = base64.b64encode(hasher.digest()).decode('ascii')
        timestamp_info.message_imprint = expected_imprint

        result = timestamp_validator.validate_timestamp_signature(data, timestamp_info)
        assert result is True

    def test_validate_timestamp_signature_invalid(self, timestamp_validator):
        """Test timestamp signature validation with wrong hash."""
        data = b"test data to be timestamped"
        timestamp_info = TimestampInfo(
            timestamp_value=datetime.now(timezone.utc),
            timestamp_authority="Test TSA",
            hash_algorithm="SHA-256",
            message_imprint="wrong_hash_value"
        )

        result = timestamp_validator.validate_timestamp_signature(data, timestamp_info)
        assert result is False
        assert "Message imprint mismatch" in timestamp_info.validation_errors

    def test_validate_timestamp_accuracy_valid(self, timestamp_validator):
        """Test timestamp accuracy validation."""
        timestamp_info = TimestampInfo(
            timestamp_value=datetime.now(timezone.utc),
            timestamp_authority="Test TSA",
            hash_algorithm="SHA-256",
            message_imprint="test",
            accuracy_seconds=60
        )

        result = timestamp_validator.validate_timestamp_accuracy(timestamp_info)
        assert result is True

    def test_validate_timestamp_accuracy_invalid(self, timestamp_validator):
        """Test timestamp accuracy validation with old timestamp."""
        # Very old timestamp
        old_time = datetime.now(timezone.utc) - timedelta(days=365)
        timestamp_info = TimestampInfo(
            timestamp_value=old_time,
            timestamp_authority="Test TSA",
            hash_algorithm="SHA-256",
            message_imprint="test",
            accuracy_seconds=60
        )

        result = timestamp_validator.validate_timestamp_accuracy(timestamp_info)
        assert result is False
        assert "Timestamp accuracy exceeded" in timestamp_info.validation_errors[0]

    def test_request_timestamp(self, timestamp_validator):
        """Test requesting timestamp from TSA."""
        data = b"test data for timestamping"
        tsa_url = "https://tsa.example.com"

        result = timestamp_validator.request_timestamp(data, tsa_url)

        assert result is not None
        assert result.status == TimestampStatus.VALID
        assert "Mock timestamp" in result.validation_warnings[0]

    def test_validate_complete_timestamp(self, timestamp_validator, mock_timestamp_token):
        """Test complete timestamp validation."""
        data = b"test data for complete validation"

        with patch.object(timestamp_validator, 'validate_timestamp_token') as mock_token_val, \
             patch.object(timestamp_validator, 'validate_timestamp_signature') as mock_sig_val, \
             patch.object(timestamp_validator, 'validate_timestamp_accuracy') as mock_acc_val, \
             patch.object(timestamp_validator, 'validate_tsa_certificate') as mock_tsa_val:

            # Mock successful validations
            mock_timestamp_info = TimestampInfo(
                timestamp_value=datetime.now(timezone.utc),
                timestamp_authority="Test TSA",
                hash_algorithm="SHA-256",
                message_imprint="test",
                status=TimestampStatus.UNKNOWN
            )
            mock_token_val.return_value = mock_timestamp_info
            mock_sig_val.return_value = True
            mock_acc_val.return_value = True
            mock_tsa_val.return_value = True

            result = timestamp_validator.validate_complete_timestamp(data, mock_timestamp_token)

            assert result.status == TimestampStatus.VALID

    def test_is_timestamp_valid(self, timestamp_validator, mock_timestamp_token):
        """Test simple boolean timestamp validation."""
        data = b"test data"

        with patch.object(timestamp_validator, 'validate_complete_timestamp') as mock_complete:
            mock_timestamp_info = TimestampInfo(
                timestamp_value=datetime.now(timezone.utc),
                timestamp_authority="Test TSA",
                hash_algorithm="SHA-256",
                message_imprint="test",
                status=TimestampStatus.VALID
            )
            mock_complete.return_value = mock_timestamp_info

            result = timestamp_validator.is_timestamp_valid(data, mock_timestamp_token)
            assert result is True

    def test_sii_timestamp_validator_validate_dte(self, sii_timestamp_validator, mock_timestamp_token):
        """Test SII DTE timestamp validation."""
        dte_data = b"DTE document data"

        with patch.object(sii_timestamp_validator, 'validate_complete_timestamp') as mock_complete:
            mock_timestamp_info = TimestampInfo(
                timestamp_value=datetime.now(timezone.utc),
                timestamp_authority="AC Tiempo SII",
                hash_algorithm="SHA-256",
                message_imprint="test",
                status=TimestampStatus.VALID
            )
            mock_complete.return_value = mock_timestamp_info

            result = sii_timestamp_validator.validate_dte_timestamp(dte_data, mock_timestamp_token)

            assert result.status == TimestampStatus.VALID
            assert result.timestamp_authority == "AC Tiempo SII"

    def test_sii_timestamp_deprecated_algorithm_warning(self, sii_timestamp_validator):
        """Test SII timestamp validation with deprecated algorithm."""
        timestamp_info = TimestampInfo(
            timestamp_value=datetime.now(timezone.utc),
            timestamp_authority="AC Tiempo SII",
            hash_algorithm="SHA-1",  # Deprecated
            message_imprint="test"
        )

        sii_timestamp_validator._apply_sii_timestamp_rules(timestamp_info)

        assert any("SHA-1 hash algorithm is deprecated" in warning
                   for warning in timestamp_info.validation_warnings)

    def test_is_valid_for_long_term_preservation(self, sii_timestamp_validator):
        """Test long-term preservation validation."""
        # Valid timestamp for long-term preservation
        valid_timestamp_info = TimestampInfo(
            timestamp_value=datetime.now(timezone.utc),
            timestamp_authority="AC Tiempo SII",
            hash_algorithm="SHA-256",
            message_imprint="test",
            status=TimestampStatus.VALID
        )

        result = sii_timestamp_validator.is_valid_for_long_term_preservation(valid_timestamp_info)
        assert result is True

        # Invalid timestamp with SHA-1
        invalid_timestamp_info = TimestampInfo(
            timestamp_value=datetime.now(timezone.utc),
            timestamp_authority="AC Tiempo SII",
            hash_algorithm="SHA-1",
            message_imprint="test",
            status=TimestampStatus.VALID
        )

        result = sii_timestamp_validator.is_valid_for_long_term_preservation(invalid_timestamp_info)
        assert result is False


class TestIntegrationDigitalSignature:
    """Integration tests for digital signature validation."""

    @pytest.fixture
    def integrated_validator(self):
        """Create integrated validator setup."""
        cert_validator = SiiCertificateValidator()
        sig_validator = SiiSignatureValidator(certificate_validator=cert_validator)
        ts_validator = SiiTimestampValidator(certificate_validator=cert_validator)

        return {
            'certificate': cert_validator,
            'signature': sig_validator,
            'timestamp': ts_validator
        }

    def test_complete_validation_workflow(self, integrated_validator):
        """Test complete validation workflow."""
        # Mock DTE document with signature
        dte_xml = """<?xml version="1.0" encoding="UTF-8"?>
<DTE xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
    <Documento>Sample DTE content</Documento>
    <ds:Signature>
        <ds:SignedInfo>
            <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
            <ds:SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha256"/>
            <ds:Reference>
                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                <ds:DigestValue>mockDigest</ds:DigestValue>
            </ds:Reference>
        </ds:SignedInfo>
        <ds:SignatureValue>mockSignature</ds:SignatureValue>
        <ds:KeyInfo>
            <ds:X509Data>
                <ds:X509Certificate>mockCert</ds:X509Certificate>
            </ds:X509Data>
        </ds:KeyInfo>
    </ds:Signature>
</DTE>"""

        # Validate signature
        sig_validator = integrated_validator['signature']

        with patch.object(sig_validator, '_validate_signature_element') as mock_validate:
            mock_sig_info = SignatureInfo(
                canonicalization_method="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
                signature_method="http://www.w3.org/2000/09/xmldsig#rsa-sha256",
                signature_value="mockSignature",
                status=SignatureStatus.VALID
            )
            mock_validate.return_value = mock_sig_info

            signature_results = sig_validator.validate_dte_signature(dte_xml)

            assert len(signature_results) == 1
            assert signature_results[0].status == SignatureStatus.VALID

    def test_validation_summary_generation(self, integrated_validator):
        """Test validation summary generation."""
        cert_validator = integrated_validator['certificate']

        # Mock certificate info
        cert_info = CertificateInfo(
            subject="CN=Test Company, O=Test Org",
            issuer="CN=SII CA",
            serial_number="12345",
            not_before=datetime.now(timezone.utc) - timedelta(days=30),
            not_after=datetime.now(timezone.utc) + timedelta(days=365),
            public_key_algorithm="RSA",
            signature_algorithm="sha256WithRSAEncryption",
            key_size=2048,
            certificate_type=CertificateType.SII_COMPANY,
            key_usage=["digital_signature"],
            status=CertificateStatus.VALID,
            rut_certificate="12345678-9"
        )

        summary = cert_validator.get_validation_summary(cert_info)

        assert summary['is_valid'] is True
        assert summary['certificate_type'] == CertificateType.SII_COMPANY.value
        assert summary['has_digital_signature'] is True
        assert summary['rut_certificate'] == "12345678-9"

    def test_module_imports(self):
        """Test that all modules import correctly."""
        from rypsystems_dte.firma import (
            TEDBuilder,
            TEDValidator,
            CertificateValidator,
            SiiCertificateValidator,
            DigitalSignatureValidator,
            SiiSignatureValidator,
            TimestampValidator,
            SiiTimestampValidator,
            CertificateInfo,
            SignatureInfo,
            TimestampInfo
        )

        # Verify all classes exist and can be instantiated
        assert TEDBuilder is not None
        assert TEDValidator is not None
        assert CertificateValidator() is not None
        assert SiiCertificateValidator() is not None
        assert DigitalSignatureValidator() is not None
        assert SiiSignatureValidator() is not None
        assert TimestampValidator() is not None
        assert SiiTimestampValidator() is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])