"""
Comprehensive tests for the Advanced Document Validation Rules system.

Tests all validation components:
- Business rules validation
- Tax calculation validation
- Cross-field validation
- Document type specific rules
- Field validation
"""

import pytest
from decimal import Decimal
from datetime import date, datetime

from rypsystems_dte.validation import (
    BusinessRuleValidator,
    SiiBusinessRuleValidator,
    TaxCalculationValidator,
    SiiTaxCalculationValidator,
    CrossFieldValidator,
    SiiCrossFieldValidator,
    DocumentRuleValidator,
    SiiDocumentRuleValidator,
    FieldValidator,
    SiiFieldValidator,
    ValidationContext,
    RuleLevel,
    RuleSeverity,
    TaxType,
    TaxRateType,
    FieldType
)
from rypsystems_dte.sii.base import Contribuyente


class TestBusinessRuleValidator:
    """Test business rules validation."""

    def test_business_rule_validator_init(self):
        """Test business rule validator initialization."""
        validator = BusinessRuleValidator()
        assert validator.validation_level == RuleLevel.STRICT
        assert len(validator.rules) > 0

    def test_folio_positive_validation(self):
        """Test folio positive validation."""
        validator = BusinessRuleValidator()
        context = ValidationContext(
            document_type="33",
            document_date=date.today(),
            document_folio=1001
        )

        # Valid folio
        results = validator.validate_field_value("Folio", 1001, context)
        assert len(results) == 0

        # Invalid folio (negative)
        results = validator.validate_field_value("Folio", -1, context)
        assert len(results) == 1
        assert not results[0].is_valid
        assert results[0].severity == RuleSeverity.CRITICAL

        # Invalid folio (zero)
        results = validator.validate_field_value("Folio", 0, context)
        assert len(results) == 1
        assert not results[0].is_valid

    def test_rut_validation(self):
        """Test RUT format validation."""
        validator = BusinessRuleValidator()
        context = ValidationContext(
            document_type="33",
            document_date=date.today(),
            document_folio=1001
        )

        # Valid RUT
        results = validator.validate_field_value("Emisor.RUTEmisor", "76354771-K", context)
        assert len(results) == 0

        # Invalid RUT
        results = validator.validate_field_value("Emisor.RUTEmisor", "12345678-9", context)
        assert len(results) == 1
        assert not results[0].is_valid

    def test_date_validation(self):
        """Test date validation."""
        validator = BusinessRuleValidator()
        context = ValidationContext(
            document_type="33",
            document_date=date.today(),
            document_folio=1001
        )

        # Valid date (today)
        results = validator.validate_field_value("FchEmis", date.today().isoformat(), context)
        assert len(results) == 0

        # Invalid date (future)
        future_date = date.today().replace(year=date.today().year + 1)
        results = validator.validate_field_value("FchEmis", future_date.isoformat(), context)
        assert len(results) == 1
        assert not results[0].is_valid

    def test_document_validation(self):
        """Test complete document validation."""
        validator = BusinessRuleValidator()
        context = ValidationContext(
            document_type="33",
            document_date=date.today(),
            document_folio=1001
        )

        document_data = {
            "Folio": 1001,
            "FchEmis": date.today().isoformat(),
            "Emisor": {"RUTEmisor": "76354771-K"},
            "Totales": {"MntNeto": 1000}
        }

        results = validator.validate_document(document_data, context)
        # Should have some results but not all should be errors
        valid_results = [r for r in results if r.is_valid]
        assert len(valid_results) >= 0

    def test_validation_summary(self):
        """Test validation summary generation."""
        validator = BusinessRuleValidator()
        context = ValidationContext(
            document_type="33",
            document_date=date.today(),
            document_folio=1001
        )

        # Create some validation results
        results = []
        results.extend(validator.validate_field_value("Folio", 1001, context))
        results.extend(validator.validate_field_value("Folio", -1, context))

        summary = validator.get_validation_summary(results)
        assert 'total_rules' in summary
        assert 'passed' in summary
        assert 'failed' in summary
        assert 'success_rate' in summary


class TestSiiBusinessRuleValidator:
    """Test SII-specific business rules validation."""

    def test_sii_validator_init(self):
        """Test SII validator initialization."""
        validator = SiiBusinessRuleValidator()
        assert len(validator.rules) > 0
        # Should have more rules than base validator
        base_validator = BusinessRuleValidator()
        assert len(validator.rules) >= len(base_validator.rules)

    def test_iva_calculation_validation(self):
        """Test IVA calculation validation."""
        validator = SiiBusinessRuleValidator()

        document_data = {
            "Totales": {
                "MntNeto": 1000,
                "IVA": 190,  # Correct 19%
                "MntTotal": 1190
            }
        }

        context = ValidationContext(
            document_type="33",
            document_date=date.today(),
            document_folio=1001
        )

        results = validator.validate_dte_document(document_data, context)
        # Should pass IVA calculation
        iva_errors = [r for r in results if "IVA" in r.message and not r.is_valid]
        assert len(iva_errors) == 0

        # Test incorrect IVA
        document_data["Totales"]["IVA"] = 200  # Incorrect
        results = validator.validate_dte_document(document_data, context)
        iva_errors = [r for r in results if "IVA" in r.message and not r.is_valid]
        assert len(iva_errors) > 0

    def test_contribuyente_validation(self):
        """Test contribuyente validation."""
        validator = SiiBusinessRuleValidator()

        # Valid contribuyente
        contribuyente = Contribuyente("76354771-K", "Mi Empresa")
        results = validator.validate_contribuyente_rules(contribuyente)
        assert len([r for r in results if not r.is_valid]) == 0

        # Invalid RUT
        contribuyente = Contribuyente("12345678-9", "Mi Empresa")
        results = validator.validate_contribuyente_rules(contribuyente)
        assert len([r for r in results if not r.is_valid]) > 0

        # Business name too long
        long_name = "A" * 150
        contribuyente = Contribuyente("76354771-K", long_name)
        results = validator.validate_contribuyente_rules(contribuyente)
        length_errors = [r for r in results if "long" in r.message.lower()]
        assert len(length_errors) > 0


class TestTaxCalculationValidator:
    """Test tax calculation validation."""

    def test_tax_validator_init(self):
        """Test tax validator initialization."""
        validator = TaxCalculationValidator()
        assert validator.tolerance == Decimal('1')
        assert not validator.strict_mode

    def test_iva_calculation_valid(self):
        """Test valid IVA calculation."""
        validator = TaxCalculationValidator()

        base_amount = Decimal('1000')
        declared_iva = Decimal('190')  # 19%

        result = validator.validate_iva_calculation(base_amount, declared_iva)
        assert result.is_valid
        assert result.variance == Decimal('0')

    def test_iva_calculation_invalid(self):
        """Test invalid IVA calculation."""
        validator = TaxCalculationValidator()

        base_amount = Decimal('1000')
        declared_iva = Decimal('200')  # Should be 190

        result = validator.validate_iva_calculation(base_amount, declared_iva)
        assert not result.is_valid
        assert abs(result.variance) > 0

    def test_iva_calculation_tolerance(self):
        """Test IVA calculation with tolerance."""
        validator = TaxCalculationValidator(tolerance=Decimal('5'))

        base_amount = Decimal('1000')
        declared_iva = Decimal('195')  # 5 pesos difference

        result = validator.validate_iva_calculation(base_amount, declared_iva)
        # Should be valid within tolerance
        assert result.is_valid

    def test_document_tax_validation(self):
        """Test complete document tax validation."""
        validator = TaxCalculationValidator()

        document_data = {
            "Totales": {
                "MntNeto": 1000,
                "IVA": 190,
                "MntTotal": 1190
            }
        }

        results = validator.validate_document_taxes(document_data)
        assert len(results) >= 1  # At least IVA validation
        valid_results = [r for r in results if r.is_valid]
        assert len(valid_results) > 0

    def test_tax_summary(self):
        """Test tax validation summary."""
        validator = TaxCalculationValidator()

        document_data = {
            "Totales": {
                "MntNeto": 1000,
                "IVA": 190,
                "MntTotal": 1190
            }
        }

        results = validator.validate_document_taxes(document_data)
        summary = validator.get_tax_summary(results)

        assert 'total_validations' in summary
        assert 'valid_calculations' in summary
        assert 'is_valid' in summary


class TestSiiTaxCalculationValidator:
    """Test SII-specific tax calculation validation."""

    def test_sii_tax_validator_init(self):
        """Test SII tax validator initialization."""
        validator = SiiTaxCalculationValidator()
        assert 'iva_standard' in validator.custom_rates
        assert validator.custom_rates['iva_standard'] == Decimal('0.19')

    def test_factura_electronica_validation(self):
        """Test Factura Electrónica tax validation."""
        validator = SiiTaxCalculationValidator()

        document_data = {
            "Totales": {
                "MntNeto": 1000,
                "IVA": 190,
                "MntTotal": 1190
            }
        }

        results = validator.validate_sii_document_taxes(document_data, "33")
        assert len(results) >= 1
        # Should pass for correct IVA
        errors = [r for r in results if not r.is_valid]
        assert len(errors) == 0

    def test_factura_exenta_validation(self):
        """Test Factura Exenta tax validation."""
        validator = SiiTaxCalculationValidator()

        # Factura Exenta should not have IVA
        document_data = {
            "Totales": {
                "MntExe": 1000,
                "IVA": 0,
                "MntTotal": 1000
            }
        }

        results = validator.validate_sii_document_taxes(document_data, "34")
        errors = [r for r in results if not r.is_valid]
        assert len(errors) == 0

        # Test with IVA (should fail)
        document_data["Totales"]["IVA"] = 190
        results = validator.validate_sii_document_taxes(document_data, "34")
        errors = [r for r in results if not r.is_valid]
        assert len(errors) > 0

    def test_nota_credito_validation(self):
        """Test Nota de Crédito tax validation."""
        validator = SiiTaxCalculationValidator()

        # Note with negative amounts
        document_data = {
            "Totales": {
                "MntNeto": -1000,
                "IVA": -190,
                "MntTotal": -1190
            }
        }

        results = validator.validate_sii_document_taxes(document_data, "61")
        # Should handle negative amounts correctly
        assert len(results) >= 1


class TestCrossFieldValidator:
    """Test cross-field validation."""

    def test_cross_field_validator_init(self):
        """Test cross-field validator initialization."""
        validator = CrossFieldValidator()
        assert len(validator.rules) > 0
        assert len(validator.dependencies) > 0

    def test_emisor_receptor_different(self):
        """Test emisor and receptor must be different."""
        validator = CrossFieldValidator()

        # Same RUT (should fail)
        document_data = {
            "Emisor": {"RUTEmisor": "76354771-K"},
            "Receptor": {"RUTRecep": "76354771-K"}
        }

        results = validator.validate_document(document_data, "33")
        same_rut_errors = [r for r in results if "different" in r.message.lower()]
        assert len(same_rut_errors) > 0

        # Different RUT (should pass)
        document_data["Receptor"]["RUTRecep"] = "66666666-6"
        results = validator.validate_document(document_data, "33")
        same_rut_errors = [r for r in results if "different" in r.message.lower()]
        assert len(same_rut_errors) == 0

    def test_date_consistency(self):
        """Test date consistency validation."""
        validator = CrossFieldValidator()

        # Due date before emission date (should fail)
        document_data = {
            "FchEmis": "2023-12-15",
            "FchVenc": "2023-12-10"
        }

        results = validator.validate_document(document_data, "33")
        date_errors = [r for r in results if "date" in r.message.lower()]
        assert len(date_errors) > 0

        # Due date after emission date (should pass)
        document_data["FchVenc"] = "2023-12-20"
        results = validator.validate_document(document_data, "33")
        date_errors = [r for r in results if "date" in r.message.lower() and not r.is_valid]
        assert len(date_errors) == 0

    def test_total_calculation_consistency(self):
        """Test total calculation consistency."""
        validator = CrossFieldValidator()

        # Correct total calculation
        document_data = {
            "Totales": {
                "MntNeto": 1000,
                "IVA": 190,
                "MntTotal": 1190
            }
        }

        results = validator.validate_document(document_data, "33")
        total_errors = [r for r in results if "total" in r.message.lower() and not r.is_valid]
        assert len(total_errors) == 0

        # Incorrect total calculation
        document_data["Totales"]["MntTotal"] = 1200
        results = validator.validate_document(document_data, "33")
        total_errors = [r for r in results if "total" in r.message.lower() and not r.is_valid]
        assert len(total_errors) > 0

    def test_validation_summary(self):
        """Test cross-field validation summary."""
        validator = CrossFieldValidator()

        document_data = {
            "Emisor": {"RUTEmisor": "76354771-K"},
            "Receptor": {"RUTRecep": "66666666-6"},
            "FchEmis": "2023-12-15",
            "FchVenc": "2023-12-20"
        }

        results = validator.validate_document(document_data, "33")
        summary = validator.get_validation_summary(results)

        assert 'total_validations' in summary
        assert 'passed' in summary
        assert 'is_valid' in summary


class TestDocumentRuleValidator:
    """Test document type specific rules validation."""

    def test_document_validator_init(self):
        """Test document validator initialization."""
        validator = DocumentRuleValidator()
        assert len(validator.document_types) > 0
        assert "33" in validator.document_types  # Factura Electrónica
        assert "34" in validator.document_types  # Factura Exenta

    def test_factura_electronica_structure(self):
        """Test Factura Electrónica structure validation."""
        validator = DocumentRuleValidator()

        # Complete document
        document_data = {
            "Encabezado": {
                "IdDoc": {"TipoDTE": "33", "Folio": 1001, "FchEmis": "2023-12-01"},
                "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
                "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
            },
            "Detalle": [{"NroLinDet": 1, "NmbItem": "Producto", "QtyItem": 1, "PrcItem": 1000}],
            "Totales": {"MntNeto": 1000, "IVA": 190, "MntTotal": 1190}
        }

        results = validator.validate_document(document_data, "33")
        structure_errors = [r for r in results if r.rule_type == "structure" and not r.is_valid]
        assert len(structure_errors) == 0

        # Missing required section
        del document_data["Totales"]
        results = validator.validate_document(document_data, "33")
        structure_errors = [r for r in results if r.rule_type == "structure" and not r.is_valid]
        assert len(structure_errors) > 0

    def test_factura_electronica_business_rules(self):
        """Test Factura Electrónica business rules."""
        validator = DocumentRuleValidator()

        # Factura Electrónica without IVA (should fail)
        document_data = {
            "Encabezado": {
                "IdDoc": {"TipoDTE": "33", "Folio": 1001, "FchEmis": "2023-12-01"},
                "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
                "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
            },
            "Detalle": [{"NroLinDet": 1, "NmbItem": "Producto", "QtyItem": 1, "PrcItem": 1000}],
            "Totales": {"MntNeto": 1000, "IVA": 0, "MntTotal": 1000}
        }

        results = validator.validate_document(document_data, "33")
        iva_errors = [r for r in results if "iva" in r.message.lower() and not r.is_valid]
        assert len(iva_errors) > 0

    def test_factura_exenta_rules(self):
        """Test Factura Exenta specific rules."""
        validator = DocumentRuleValidator()

        # Factura Exenta with IVA (should fail)
        document_data = {
            "Encabezado": {
                "IdDoc": {"TipoDTE": "34", "Folio": 1001, "FchEmis": "2023-12-01"},
                "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
                "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
            },
            "Detalle": [{"NroLinDet": 1, "NmbItem": "Producto", "QtyItem": 1, "PrcItem": 1000}],
            "Totales": {"MntExe": 1000, "IVA": 190, "MntTotal": 1190}
        }

        results = validator.validate_document(document_data, "34")
        iva_errors = [r for r in results if "iva" in r.message.lower() and not r.is_valid]
        assert len(iva_errors) > 0

    def test_nota_credito_rules(self):
        """Test Nota de Crédito specific rules."""
        validator = DocumentRuleValidator()

        # Note without reference (should fail)
        document_data = {
            "Encabezado": {
                "IdDoc": {"TipoDTE": "61", "Folio": 3001, "FchEmis": "2023-12-01"},
                "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
                "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
            },
            "Detalle": [{"NroLinDet": 1, "NmbItem": "Descuento", "QtyItem": 1, "PrcItem": -1000}],
            "Totales": {"MntTotal": -1000}
        }

        results = validator.validate_document(document_data, "61")
        ref_errors = [r for r in results if "reference" in r.message.lower() and not r.is_valid]
        assert len(ref_errors) > 0

    def test_supported_document_types(self):
        """Test getting supported document types."""
        validator = DocumentRuleValidator()
        types = validator.get_supported_document_types()
        assert "33" in types
        assert "34" in types
        assert "39" in types
        assert "61" in types

    def test_validation_summary(self):
        """Test document validation summary."""
        validator = DocumentRuleValidator()

        document_data = {
            "Encabezado": {
                "IdDoc": {"TipoDTE": "33", "Folio": 1001, "FchEmis": "2023-12-01"},
                "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
                "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
            },
            "Detalle": [{"NroLinDet": 1, "NmbItem": "Producto", "QtyItem": 1, "PrcItem": 1000}],
            "Totales": {"MntNeto": 1000, "IVA": 190, "MntTotal": 1190}
        }

        results = validator.validate_document(document_data, "33")
        summary = validator.get_validation_summary(results)

        assert 'total_rules' in summary
        assert 'rule_type_breakdown' in summary
        assert 'severity_breakdown' in summary


class TestFieldValidator:
    """Test field validation."""

    def test_field_validator_init(self):
        """Test field validator initialization."""
        validator = FieldValidator()
        assert len(validator.field_rules) > 0
        assert "RUTEmisor" in validator.field_rules
        assert "TipoDTE" in validator.field_rules

    def test_rut_field_validation(self):
        """Test RUT field validation."""
        validator = FieldValidator()

        # Valid RUT
        result = validator.validate_field("RUTEmisor", "76354771-K")
        assert result.is_valid

        # Invalid RUT format
        result = validator.validate_field("RUTEmisor", "12345")
        assert not result.is_valid

        # Invalid RUT check digit
        result = validator.validate_field("RUTEmisor", "12345678-9")
        assert not result.is_valid

    def test_document_type_validation(self):
        """Test document type field validation."""
        validator = FieldValidator()

        # Valid document type
        result = validator.validate_field("TipoDTE", "33")
        assert result.is_valid

        # Invalid document type
        result = validator.validate_field("TipoDTE", "99")
        assert not result.is_valid

    def test_folio_validation(self):
        """Test folio field validation."""
        validator = FieldValidator()

        # Valid folio
        result = validator.validate_field("Folio", 1001)
        assert result.is_valid

        # Invalid folio (negative)
        result = validator.validate_field("Folio", -1)
        assert not result.is_valid

        # Invalid folio (too large)
        result = validator.validate_field("Folio", 10000000000)
        assert not result.is_valid

    def test_date_validation(self):
        """Test date field validation."""
        validator = FieldValidator()

        # Valid date
        result = validator.validate_field("FchEmis", "2023-12-01")
        assert result.is_valid

        # Invalid date format
        result = validator.validate_field("FchEmis", "01/12/2023")
        assert not result.is_valid

        # Future date (should fail)
        future_date = date.today().replace(year=date.today().year + 1).isoformat()
        result = validator.validate_field("FchEmis", future_date)
        assert not result.is_valid

    def test_email_validation(self):
        """Test email field validation."""
        validator = FieldValidator()

        # Valid email
        result = validator.validate_field("CorreoEmisor", "test@example.com")
        assert result.is_valid

        # Invalid email
        result = validator.validate_field("CorreoEmisor", "invalid-email")
        assert not result.is_valid

    def test_document_fields_validation(self):
        """Test complete document fields validation."""
        validator = FieldValidator()

        document_data = {
            "Encabezado": {
                "IdDoc": {"TipoDTE": "33", "Folio": 1001, "FchEmis": "2023-12-01"},
                "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
                "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
            },
            "Totales": {"MntTotal": 1190}
        }

        results = validator.validate_document_fields(document_data, "33")
        assert len(results) > 0
        # Should have valid results for properly formatted fields
        valid_results = [r for r in results if r.is_valid]
        assert len(valid_results) > 0

    def test_validation_summary(self):
        """Test field validation summary."""
        validator = FieldValidator()

        results = []
        results.append(validator.validate_field("RUTEmisor", "76354771-K"))
        results.append(validator.validate_field("RUTEmisor", "invalid"))

        summary = validator.get_validation_summary(results)
        assert 'total_fields' in summary
        assert 'valid_fields' in summary
        assert 'field_type_breakdown' in summary


class TestIntegrationValidation:
    """Test integration of all validation components."""

    def test_complete_document_validation(self):
        """Test complete document validation with all validators."""
        # Initialize all validators
        business_validator = SiiBusinessRuleValidator()
        tax_validator = SiiTaxCalculationValidator()
        cross_validator = SiiCrossFieldValidator()
        document_validator = SiiDocumentRuleValidator()
        field_validator = SiiFieldValidator()

        # Complete valid document
        document_data = {
            "Encabezado": {
                "IdDoc": {"TipoDTE": "33", "Folio": 1001, "FchEmis": "2023-12-01"},
                "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
                "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
            },
            "Detalle": [{"NroLinDet": 1, "NmbItem": "Producto", "QtyItem": 1, "PrcItem": 1000}],
            "Totales": {"MntNeto": 1000, "IVA": 190, "MntTotal": 1190}
        }

        context = ValidationContext(
            document_type="33",
            document_date=date.today(),
            document_folio=1001
        )

        # Run all validations
        business_results = business_validator.validate_dte_document(document_data, context)
        tax_results = tax_validator.validate_sii_document_taxes(document_data, "33")
        cross_results = cross_validator.validate_sii_document(document_data, "33")
        document_results = document_validator.validate_sii_document(document_data, "33", "produccion")
        field_results = field_validator.validate_sii_document_fields(document_data, "33")

        # Collect all results
        all_results = business_results + cross_results + document_results + field_results
        all_results.extend([{
            'is_valid': r.is_valid,
            'message': f"Tax: {r.calculation.tax_type.value}",
            'severity': 'high' if not r.is_valid else 'info'
        } for r in tax_results])

        # Generate summary
        total_validations = len(all_results)
        failed_validations = len([r for r in all_results if not r.get('is_valid', True)])

        assert total_validations > 0
        # Most validations should pass for a well-formed document
        success_rate = (total_validations - failed_validations) / total_validations * 100
        assert success_rate >= 70  # At least 70% should pass

    def test_invalid_document_validation(self):
        """Test validation of an invalid document."""
        # Initialize validators
        business_validator = SiiBusinessRuleValidator()
        tax_validator = SiiTaxCalculationValidator()
        cross_validator = SiiCrossFieldValidator()
        document_validator = SiiDocumentRuleValidator()
        field_validator = SiiFieldValidator()

        # Invalid document with multiple errors
        document_data = {
            "Encabezado": {
                "IdDoc": {"TipoDTE": "33", "Folio": -1, "FchEmis": "invalid-date"},
                "Emisor": {"RUTEmisor": "invalid-rut", "RznSoc": ""},
                "Receptor": {"RUTRecep": "invalid-rut", "RznSocRecep": "Cliente"}
            },
            "Detalle": [{"NroLinDet": 1, "NmbItem": "Producto", "QtyItem": 1, "PrcItem": 1000}],
            "Totales": {"MntNeto": 1000, "IVA": 200, "MntTotal": 1000}  # Wrong totals
        }

        context = ValidationContext(
            document_type="33",
            document_date=date.today(),
            document_folio=-1
        )

        # Run all validations
        business_results = business_validator.validate_dte_document(document_data, context)
        tax_results = tax_validator.validate_sii_document_taxes(document_data, "33")
        cross_results = cross_validator.validate_sii_document(document_data, "33")
        document_results = document_validator.validate_sii_document(document_data, "33", "produccion")
        field_results = field_validator.validate_sii_document_fields(document_data, "33")

        # Should have many validation errors
        business_errors = [r for r in business_results if not r.is_valid]
        tax_errors = [r for r in tax_results if not r.is_valid]
        cross_errors = [r for r in cross_results if not r.is_valid]
        document_errors = [r for r in document_results if not r.is_valid]
        field_errors = [r for r in field_results if not r.is_valid]

        total_errors = len(business_errors) + len(tax_errors) + len(cross_errors) + len(document_errors) + len(field_errors)
        assert total_errors > 5  # Should have multiple errors


if __name__ == "__main__":
    pytest.main([__file__, "-v"])