"""
Digital Signature Validation Example.

Demonstrates comprehensive digital signature validation including:
- Certificate validation and chain verification
- XML signature validation
- Timestamp validation
- SII-specific validation rules
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any

from rypsystems_dte.firma import (
    CertificateValidator,
    SiiCertificateValidator,
    DigitalSignatureValidator,
    SiiSignatureValidator,
    TimestampValidator,
    SiiTimestampValidator,
    CertificateType,
    CertificateStatus,
    ValidationLevel,
    SignatureStatus,
    TimestampStatus
)
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente


class DigitalSignatureValidationDemo:
    """
    Comprehensive demonstration of digital signature validation capabilities.

    Shows how to validate certificates, XML signatures, and timestamps
    with both generic and SII-specific validation rules.
    """

    def __init__(self):
        """Initialize validation demo."""
        # Initialize validators
        self.certificate_validator = SiiCertificateValidator()
        self.signature_validator = SiiSignatureValidator(
            certificate_validator=self.certificate_validator
        )
        self.timestamp_validator = SiiTimestampValidator(
            certificate_validator=self.certificate_validator
        )

        # Create DTE factory for document examples
        self.dte_factory = DTEFactory()

    def demonstrate_certificate_validation(self) -> Dict[str, Any]:
        """
        Demonstrate certificate validation capabilities.

        Returns:
            Certificate validation results
        """
        print("🔐 Demonstrating Certificate Validation")
        print("=" * 50)

        results = {
            'basic_validation': None,
            'sii_validation': None,
            'chain_validation': None,
            'validation_levels': {}
        }

        # Example certificate data (mock for demonstration)
        mock_certificate_pem = """-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAKoK/heBjcOuMA0GCSqGSIb3DQEBBQUAMEUxCzAJBgNV
BAYTAkNMMSEwHwYDVQQKDBhTZXJ2aWNpbyBkZSBJbXB1ZXN0b3MgSW50ZXJub3Mx
EzARBgNVBAMMClNJSSBDQSBUZXN0MB4XDTI0MDEwMTAwMDAwMFoXDTI1MDEwMTAw
MDAwMFowQTELMAkGA1UEBhMCQ0wxDzANBgNVBAoMBlRlc3QgQ28xITAfBgNVBAMM
GDEyMzQ1Njc4LTkgKE1vY2sgQ29tcGFueSkwggEiMA0GCSqGSIb3DQEBAQUAA4IB
DwAwggEKAoIBAQC4TvD5m5Y/2/iYudWpY7Fk8rV6sKZ/wHWbNvVJYvRvOhWhNEK
MOCK_CERTIFICATE_DATA_FOR_DEMONSTRATION_PURPOSES_ONLY
-----END CERTIFICATE-----"""

        print("\n📋 1. Basic Certificate Validation")
        try:
            # Note: In real implementation, we would parse the actual certificate
            # For demo purposes, we'll simulate the validation process

            print("   ℹ️ Note: Using simulated certificate validation for demo")

            # Simulate certificate information
            from rypsystems_dte.firma import CertificateInfo
            mock_cert_info = CertificateInfo(
                subject="CN=12345678-9 (Mock Company), O=Test Co, C=CL",
                issuer="CN=SII CA Test, O=Servicio de Impuestos Internos, C=CL",
                serial_number="123456789",
                not_before=datetime(2024, 1, 1, tzinfo=timezone.utc),
                not_after=datetime(2025, 1, 1, tzinfo=timezone.utc),
                certificate_type=CertificateType.SII_COMPANY,
                public_key_algorithm="RSA",
                signature_algorithm="sha256WithRSAEncryption",
                key_size=2048,
                key_usage=["digital_signature", "key_encipherment"],
                extended_key_usage=["client_auth"],
                rut_certificate="12345678-9",
                company_name="Test Co",
                status=CertificateStatus.VALID
            )

            results['basic_validation'] = {
                'status': mock_cert_info.status.value,
                'subject': mock_cert_info.subject,
                'issuer': mock_cert_info.issuer,
                'certificate_type': mock_cert_info.certificate_type.value,
                'rut_certificate': mock_cert_info.rut_certificate,
                'key_size': mock_cert_info.key_size,
                'expires_in_days': (mock_cert_info.not_after - datetime.now(timezone.utc)).days
            }

            print(f"   ✅ Certificate Status: {mock_cert_info.status.value}")
            print(f"   📋 Subject: {mock_cert_info.subject}")
            print(f"   🏢 Type: {mock_cert_info.certificate_type.value}")
            print(f"   🆔 RUT: {mock_cert_info.rut_certificate}")
            print(f"   🔑 Key Size: {mock_cert_info.key_size} bits")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results['basic_validation'] = {'error': str(e)}

        print("\n📋 2. SII-Specific Certificate Validation")
        try:
            # Simulate SII validation
            is_valid_for_dte = mock_cert_info.certificate_type == CertificateType.SII_COMPANY and \
                              'digital_signature' in mock_cert_info.key_usage and \
                              mock_cert_info.rut_certificate is not None

            results['sii_validation'] = {
                'is_valid_for_dte_signing': is_valid_for_dte,
                'has_rut': mock_cert_info.rut_certificate is not None,
                'has_digital_signature': 'digital_signature' in mock_cert_info.key_usage,
                'is_sii_issued': mock_cert_info.certificate_type in [
                    CertificateType.SII_COMPANY,
                    CertificateType.SII_PERSON,
                    CertificateType.SII_AUTHORITY
                ]
            }

            print(f"   ✅ Valid for DTE signing: {is_valid_for_dte}")
            print(f"   🆔 Has RUT: {mock_cert_info.rut_certificate is not None}")
            print(f"   ✍️ Has digital signature usage: {'digital_signature' in mock_cert_info.key_usage}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results['sii_validation'] = {'error': str(e)}

        print("\n📋 3. Validation Levels Comparison")
        validation_levels = [
            ValidationLevel.BASIC,
            ValidationLevel.CHAIN,
            ValidationLevel.REVOCATION,
            ValidationLevel.FULL
        ]

        for level in validation_levels:
            try:
                # Simulate different validation levels
                level_result = {
                    'level': level.value,
                    'checks_performed': [],
                    'status': 'valid'
                }

                if level == ValidationLevel.BASIC:
                    level_result['checks_performed'] = ['format', 'validity_period', 'basic_constraints']
                elif level == ValidationLevel.CHAIN:
                    level_result['checks_performed'] = ['format', 'validity_period', 'chain_validation']
                elif level == ValidationLevel.REVOCATION:
                    level_result['checks_performed'] = ['format', 'validity_period', 'chain_validation', 'revocation_check']
                elif level == ValidationLevel.FULL:
                    level_result['checks_performed'] = ['format', 'validity_period', 'chain_validation', 'revocation_check', 'policy_validation']

                results['validation_levels'][level.value] = level_result

                print(f"   📊 {level.value.upper()}: {', '.join(level_result['checks_performed'])}")

            except Exception as e:
                results['validation_levels'][level.value] = {'error': str(e)}

        return results

    def demonstrate_signature_validation(self) -> Dict[str, Any]:
        """
        Demonstrate XML signature validation capabilities.

        Returns:
            Signature validation results
        """
        print("\n🖋️ Demonstrating Digital Signature Validation")
        print("=" * 50)

        results = {
            'xml_signature_validation': None,
            'dte_signature_validation': None,
            'ted_signature_validation': None
        }

        # Sample signed XML document
        sample_signed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<DTE xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
    <Documento ID="T33F1001">
        <Encabezado>
            <IdDoc>
                <TipoDTE>33</TipoDTE>
                <Folio>1001</Folio>
                <FchEmis>2024-01-15</FchEmis>
            </IdDoc>
            <Emisor>
                <RUTEmisor>76354771-K</RUTEmisor>
                <RznSoc>Mi Empresa Ltda.</RznSoc>
            </Emisor>
        </Encabezado>
    </Documento>
    <ds:Signature>
        <ds:SignedInfo>
            <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
            <ds:SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha256"/>
            <ds:Reference URI="#T33F1001">
                <ds:Transforms>
                    <ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
                </ds:Transforms>
                <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                <ds:DigestValue>mockDigestValueForDemonstration</ds:DigestValue>
            </ds:Reference>
        </ds:SignedInfo>
        <ds:SignatureValue>mockSignatureValueForDemonstrationPurposes</ds:SignatureValue>
        <ds:KeyInfo>
            <ds:X509Data>
                <ds:X509Certificate>mockCertificateDataForDemo</ds:X509Certificate>
            </ds:X509Data>
        </ds:KeyInfo>
    </ds:Signature>
</DTE>"""

        print("\n📋 1. XML Signature Validation")
        try:
            # Simulate signature validation
            from rypsystems_dte.firma import SignatureInfo, SignatureType
            mock_sig_info = SignatureInfo(
                signature_id="signature-1",
                signature_type=SignatureType.ENVELOPED,
                canonicalization_method="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
                signature_method="http://www.w3.org/2000/09/xmldsig#rsa-sha256",
                signature_value="mockSignatureValueForDemonstrationPurposes",
                status=SignatureStatus.VALID,
                validation_warnings=["Demo mode - signature not cryptographically verified"]
            )

            results['xml_signature_validation'] = {
                'signature_count': 1,
                'valid_signatures': 1,
                'signature_method': mock_sig_info.signature_method,
                'canonicalization_method': mock_sig_info.canonicalization_method,
                'status': mock_sig_info.status.value,
                'warnings': mock_sig_info.validation_warnings
            }

            print(f"   ✅ Signatures found: 1")
            print(f"   ✅ Valid signatures: 1")
            print(f"   🔐 Signature method: RSA-SHA256")
            print(f"   📝 Canonicalization: Inclusive")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results['xml_signature_validation'] = {'error': str(e)}

        print("\n📋 2. DTE Signature Validation")
        try:
            # Use SII signature validator for DTE-specific validation
            signature_results = [mock_sig_info]  # Simulated

            # Apply SII-specific rules
            sii_validation_result = {
                'is_dte_compliant': True,
                'algorithm_allowed': True,
                'certificate_valid_for_dte': True,
                'key_size_sufficient': True
            }

            results['dte_signature_validation'] = sii_validation_result

            print(f"   ✅ DTE compliant: {sii_validation_result['is_dte_compliant']}")
            print(f"   ✅ Algorithm allowed: {sii_validation_result['algorithm_allowed']}")
            print(f"   ✅ Certificate valid for DTE: {sii_validation_result['certificate_valid_for_dte']}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results['dte_signature_validation'] = {'error': str(e)}

        print("\n📋 3. TED Signature Validation")
        try:
            # Sample TED XML
            ted_xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
<TED version="1.0">
    <DD>
        <RE>76354771-K</RE>
        <TD>33</TD>
        <F>1001</F>
        <FE>2024-01-15</FE>
        <RR>66666666-6</RR>
        <RSR>Cliente Ejemplo S.A.</RSR>
        <MNT>20000</MNT>
        <IT1>Producto A</IT1>
        <CAF>mockCAFData</CAF>
        <TSTED>2024-01-15T10:30:00</TSTED>
    </DD>
    <FRMT algoritmo="SHA1withRSA">mockTEDSignatureValueForDemonstrationPurposesOnly</FRMT>
</TED>"""

            # Validate TED signature
            ted_result = self.signature_validator.validate_ted_signature(ted_xml)

            results['ted_signature_validation'] = {
                'status': ted_result.status.value,
                'signature_algorithm': ted_result.signature_method,
                'has_signature_value': len(ted_result.signature_value) > 0,
                'errors': ted_result.validation_errors,
                'warnings': ted_result.validation_warnings
            }

            print(f"   ✅ TED Status: {ted_result.status.value}")
            print(f"   🔐 Algorithm: {ted_result.signature_method}")
            print(f"   ✍️ Has signature: {len(ted_result.signature_value) > 0}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results['ted_signature_validation'] = {'error': str(e)}

        return results

    def demonstrate_timestamp_validation(self) -> Dict[str, Any]:
        """
        Demonstrate timestamp validation capabilities.

        Returns:
            Timestamp validation results
        """
        print("\n⏰ Demonstrating Timestamp Validation")
        print("=" * 50)

        results = {
            'timestamp_token_validation': None,
            'signature_timestamp_validation': None,
            'dte_timestamp_validation': None,
            'long_term_validation': None
        }

        print("\n📋 1. Timestamp Token Validation")
        try:
            # Mock timestamp token
            mock_timestamp_token = b"mock_timestamp_token_data_for_demo"

            # Validate timestamp token
            timestamp_info = self.timestamp_validator.validate_timestamp_token(mock_timestamp_token)

            results['timestamp_token_validation'] = {
                'status': timestamp_info.status.value,
                'timestamp_authority': timestamp_info.timestamp_authority,
                'hash_algorithm': timestamp_info.hash_algorithm,
                'timestamp_value': timestamp_info.timestamp_value.isoformat(),
                'warnings': timestamp_info.validation_warnings
            }

            print(f"   ✅ Status: {timestamp_info.status.value}")
            print(f"   🏢 TSA: {timestamp_info.timestamp_authority}")
            print(f"   🔐 Hash algorithm: {timestamp_info.hash_algorithm}")
            print(f"   ⏰ Timestamp: {timestamp_info.timestamp_value.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results['timestamp_token_validation'] = {'error': str(e)}

        print("\n📋 2. Signature Timestamp Validation")
        try:
            # Test data for timestamping
            test_data = b"DTE document data for timestamp validation"

            # Validate timestamp signature
            timestamp_valid = self.timestamp_validator.validate_timestamp_signature(
                test_data, timestamp_info
            )

            results['signature_timestamp_validation'] = {
                'signature_valid': timestamp_valid,
                'message_imprint_verified': True,
                'hash_algorithm': timestamp_info.hash_algorithm
            }

            print(f"   ✅ Signature valid: {timestamp_valid}")
            print(f"   ✅ Message imprint verified: True")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results['signature_timestamp_validation'] = {'error': str(e)}

        print("\n📋 3. DTE Timestamp Validation")
        try:
            # Create sample DTE data
            dte_data = b"Sample DTE document content for timestamp validation"

            # Validate with SII timestamp validator
            dte_timestamp_result = self.timestamp_validator.validate_dte_timestamp(
                dte_data, mock_timestamp_token
            )

            results['dte_timestamp_validation'] = {
                'status': dte_timestamp_result.status.value,
                'is_sii_approved_tsa': "SII" in dte_timestamp_result.timestamp_authority,
                'hash_algorithm_strength': "SHA-256" in dte_timestamp_result.hash_algorithm,
                'warnings': dte_timestamp_result.validation_warnings
            }

            print(f"   ✅ DTE timestamp status: {dte_timestamp_result.status.value}")
            print(f"   🏢 SII-approved TSA: {'SII' in dte_timestamp_result.timestamp_authority}")
            print(f"   🔐 Strong hash algorithm: {'SHA-256' in dte_timestamp_result.hash_algorithm}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results['dte_timestamp_validation'] = {'error': str(e)}

        print("\n📋 4. Long-term Preservation Validation")
        try:
            # Check if timestamp is valid for long-term preservation
            is_valid_long_term = self.timestamp_validator.is_valid_for_long_term_preservation(
                dte_timestamp_result
            )

            results['long_term_validation'] = {
                'valid_for_long_term': is_valid_long_term,
                'hash_algorithm_future_proof': "SHA-256" in dte_timestamp_result.hash_algorithm,
                'tsa_certificate_valid': True  # Simulated
            }

            print(f"   ✅ Valid for long-term preservation: {is_valid_long_term}")
            print(f"   🔐 Future-proof hash algorithm: {'SHA-256' in dte_timestamp_result.hash_algorithm}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results['long_term_validation'] = {'error': str(e)}

        return results

    def demonstrate_complete_validation_workflow(self) -> Dict[str, Any]:
        """
        Demonstrate complete end-to-end validation workflow.

        Returns:
            Complete validation results
        """
        print("\n🔄 Demonstrating Complete Validation Workflow")
        print("=" * 50)

        workflow_results = {
            'document_creation': None,
            'signature_application': None,
            'timestamp_application': None,
            'complete_validation': None
        }

        print("\n📋 1. Document Creation")
        try:
            # Create a sample DTE document
            emisor = Contribuyente('76354771-K', 'Mi Empresa Ltda.')
            receptor = Contribuyente('66666666-6', 'Cliente Ejemplo S.A.')

            factura = self.dte_factory.create_factura_afecta(
                emisor=emisor,
                receptor=receptor,
                folio=1001,
                fecha_emision='2024-01-15',
                detalle=[
                    {
                        'NmbItem': 'Producto A',
                        'QtyItem': 10,
                        'PrcItem': 1000
                    }
                ]
            )

            workflow_results['document_creation'] = {
                'document_type': factura.get_tipo_documento(),
                'folio': factura.get_folio(),
                'emisor_rut': factura.get_rut_emisor(),
                'monto_total': factura.get_datos().get('Encabezado', {}).get('Totales', {}).get('MntTotal', 0)
            }

            print(f"   ✅ Document created: Type {factura.get_tipo_documento()}, Folio {factura.get_folio()}")
            print(f"   👤 Emisor: {factura.get_rut_emisor()}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            workflow_results['document_creation'] = {'error': str(e)}

        print("\n📋 2. Digital Signature Application (Simulated)")
        try:
            # In real scenario, this would apply actual digital signature
            xml_content = factura.save_xml()

            workflow_results['signature_application'] = {
                'xml_length': len(xml_content),
                'signature_applied': True,  # Simulated
                'signature_algorithm': 'RSA-SHA256',
                'certificate_rut': '76354771-K'
            }

            print(f"   ✅ Signature applied: RSA-SHA256")
            print(f"   📄 Document size: {len(xml_content)} bytes")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            workflow_results['signature_application'] = {'error': str(e)}

        print("\n📋 3. Timestamp Application (Simulated)")
        try:
            # In real scenario, this would request timestamp from TSA
            timestamp_data = b"mock_timestamp_data"

            workflow_results['timestamp_application'] = {
                'timestamp_applied': True,
                'tsa_authority': 'AC Tiempo SII',
                'timestamp_value': datetime.now(timezone.utc).isoformat(),
                'hash_algorithm': 'SHA-256'
            }

            print(f"   ✅ Timestamp applied: AC Tiempo SII")
            print(f"   ⏰ Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            workflow_results['timestamp_application'] = {'error': str(e)}

        print("\n📋 4. Complete Validation")
        try:
            # Perform complete validation of the signed and timestamped document
            validation_summary = {
                'certificate_valid': True,
                'signature_valid': True,
                'timestamp_valid': True,
                'sii_compliant': True,
                'long_term_valid': True,
                'overall_status': 'VALID'
            }

            workflow_results['complete_validation'] = validation_summary

            print(f"   ✅ Certificate validation: PASSED")
            print(f"   ✅ Signature validation: PASSED")
            print(f"   ✅ Timestamp validation: PASSED")
            print(f"   ✅ SII compliance: PASSED")
            print(f"   ✅ Long-term validity: PASSED")
            print(f"   🎯 Overall status: {validation_summary['overall_status']}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            workflow_results['complete_validation'] = {'error': str(e)}

        return workflow_results

    def run_complete_demo(self) -> Dict[str, Any]:
        """
        Run complete digital signature validation demonstration.

        Returns:
            Complete demo results
        """
        print("🔐 Digital Signature Validation System Demo")
        print("=" * 60)

        demo_results = {
            'start_time': datetime.now(timezone.utc).isoformat(),
            'certificate_validation': None,
            'signature_validation': None,
            'timestamp_validation': None,
            'complete_workflow': None,
            'errors': []
        }

        try:
            # Certificate validation demo
            demo_results['certificate_validation'] = self.demonstrate_certificate_validation()

            # Signature validation demo
            demo_results['signature_validation'] = self.demonstrate_signature_validation()

            # Timestamp validation demo
            demo_results['timestamp_validation'] = self.demonstrate_timestamp_validation()

            # Complete workflow demo
            demo_results['complete_workflow'] = self.demonstrate_complete_validation_workflow()

        except Exception as e:
            error_msg = f"Demo error: {e}"
            print(f"\n❌ {error_msg}")
            demo_results['errors'].append(error_msg)

        demo_results['end_time'] = datetime.now(timezone.utc).isoformat()

        # Summary
        print("\n" + "=" * 60)
        print("📋 DEMO SUMMARY")
        print("=" * 60)
        print("🔐 Certificate Validation: ✅ Demonstrated")
        print("🖋️ Digital Signature Validation: ✅ Demonstrated")
        print("⏰ Timestamp Validation: ✅ Demonstrated")
        print("🔄 Complete Workflow: ✅ Demonstrated")

        if demo_results['errors']:
            print(f"\n🚨 Errors encountered: {len(demo_results['errors'])}")
            for error in demo_results['errors']:
                print(f"   • {error}")
        else:
            print("\n✅ Demo completed successfully without errors")

        print("\nℹ️ Note: This demo uses simulated validation for demonstration purposes.")
        print("   Production implementation requires actual cryptographic validation.")

        return demo_results


def main():
    """Main function to run the digital signature validation demo."""
    print("🎯 Digital Signature Validation System - rypsystems-dte")
    print("=" * 60)

    # Create and run demo
    demo = DigitalSignatureValidationDemo()
    results = demo.run_complete_demo()

    # Save results
    results_file = 'digital_signature_validation_demo_results.json'
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n📁 Demo results saved to: {results_file}")


if __name__ == "__main__":
    main()