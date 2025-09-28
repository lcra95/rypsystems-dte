"""
Advanced Document Validation Example.

Demonstrates the comprehensive Advanced Document Validation Rules system including:
- Business rules validation
- Tax calculation validation
- Cross-field validation
- Document type specific rules
- Field validation
- Complete document validation workflow
"""

from datetime import date, datetime
from decimal import Decimal
from pprint import pprint

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
    TaxRateType
)
from rypsystems_dte.sii.base import Contribuyente


def demo_business_rules_validation():
    """Demonstrate business rules validation."""
    print("=" * 60)
    print("BUSINESS RULES VALIDATION DEMO")
    print("=" * 60)

    # Initialize validator
    validator = SiiBusinessRuleValidator(validation_level=RuleLevel.STRICT)

    # Create validation context
    context = ValidationContext(
        document_type="33",
        document_date=date.today(),
        document_folio=1001,
        ambiente="produccion"
    )

    print(f"Validation Context: {context.document_type}, Folio: {context.document_folio}")
    print()

    # Test individual field validations
    print("Individual Field Validations:")
    print("-" * 30)

    # Valid folio
    results = validator.validate_field_value("Folio", 1001, context)
    print(f"Folio 1001: {'✓ PASS' if len(results) == 0 else '✗ FAIL'}")

    # Invalid folio
    results = validator.validate_field_value("Folio", -1, context)
    print(f"Folio -1: {'✓ PASS' if len(results) == 0 else '✗ FAIL'}")
    if results:
        print(f"  Error: {results[0].message}")

    # Valid RUT
    results = validator.validate_field_value("Emisor.RUTEmisor", "76354771-K", context)
    print(f"RUT 76354771-K: {'✓ PASS' if len(results) == 0 else '✗ FAIL'}")

    # Invalid RUT
    results = validator.validate_field_value("Emisor.RUTEmisor", "12345678-9", context)
    print(f"RUT 12345678-9: {'✓ PASS' if len(results) == 0 else '✗ FAIL'}")
    if results:
        print(f"  Error: {results[0].message}")

    print()

    # Test complete document validation
    print("Complete Document Validation:")
    print("-" * 30)

    document_data = {
        "Folio": 1001,
        "FchEmis": date.today().isoformat(),
        "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
        "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"},
        "Totales": {"MntNeto": 1000, "IVA": 190, "MntTotal": 1190}
    }

    results = validator.validate_document(document_data, context)
    summary = validator.get_validation_summary(results)

    print(f"Total rules applied: {summary['total_rules']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success rate: {summary['success_rate']:.1f}%")
    print(f"Document valid: {'✓ YES' if summary['is_valid'] else '✗ NO'}")

    if not summary['is_valid']:
        print("\nValidation Errors:")
        for result in results:
            if not result.is_valid:
                print(f"  - {result.rule_name}: {result.message}")

    print()


def demo_tax_calculation_validation():
    """Demonstrate tax calculation validation."""
    print("=" * 60)
    print("TAX CALCULATION VALIDATION DEMO")
    print("=" * 60)

    # Initialize validator
    validator = SiiTaxCalculationValidator(strict_mode=False)

    print("IVA Calculation Tests:")
    print("-" * 25)

    # Test correct IVA calculation
    base_amount = Decimal('1000')
    declared_iva = Decimal('190')  # 19%

    result = validator.validate_iva_calculation(base_amount, declared_iva)
    print(f"Base: $1,000, IVA: $190")
    print(f"Result: {'✓ VALID' if result.is_valid else '✗ INVALID'}")
    print(f"Variance: ${result.variance}")
    print()

    # Test incorrect IVA calculation
    declared_iva = Decimal('200')  # Incorrect
    result = validator.validate_iva_calculation(base_amount, declared_iva)
    print(f"Base: $1,000, IVA: $200 (incorrect)")
    print(f"Result: {'✓ VALID' if result.is_valid else '✗ INVALID'}")
    print(f"Variance: ${result.variance}")
    if result.errors:
        print(f"Error: {result.errors[0]}")
    print()

    # Test document tax validation
    print("Document Tax Validation:")
    print("-" * 25)

    # Factura Electrónica
    document_data = {
        "Totales": {
            "MntNeto": 1000,
            "IVA": 190,
            "MntTotal": 1190
        }
    }

    results = validator.validate_sii_document_taxes(document_data, "33")
    print("Factura Electrónica:")
    valid_results = [r for r in results if r.is_valid]
    invalid_results = [r for r in results if not r.is_valid]
    print(f"  Valid calculations: {len(valid_results)}")
    print(f"  Invalid calculations: {len(invalid_results)}")

    # Factura Exenta (should not have IVA)
    document_data = {
        "Totales": {
            "MntExe": 1000,
            "IVA": 0,
            "MntTotal": 1000
        }
    }

    results = validator.validate_sii_document_taxes(document_data, "34")
    print("Factura Exenta:")
    valid_results = [r for r in results if r.is_valid]
    invalid_results = [r for r in results if not r.is_valid]
    print(f"  Valid calculations: {len(valid_results)}")
    print(f"  Invalid calculations: {len(invalid_results)}")

    # Test tax summary
    summary = validator.get_tax_summary(results)
    print(f"\nTax Validation Summary:")
    print(f"  Success rate: {summary['success_rate']:.1f}%")
    print(f"  Has errors: {'YES' if summary['has_errors'] else 'NO'}")
    print()


def demo_cross_field_validation():
    """Demonstrate cross-field validation."""
    print("=" * 60)
    print("CROSS-FIELD VALIDATION DEMO")
    print("=" * 60)

    # Initialize validator
    validator = SiiCrossFieldValidator()

    print("Cross-Field Dependency Tests:")
    print("-" * 30)

    # Test emisor/receptor different RUTs
    print("1. Emisor/Receptor RUT Consistency:")
    document_data = {
        "Emisor": {"RUTEmisor": "76354771-K"},
        "Receptor": {"RUTRecep": "76354771-K"}  # Same RUT - should fail
    }

    results = validator.validate_document(document_data, "33")
    same_rut_errors = [r for r in results if "different" in r.message.lower()]
    print(f"  Same RUT test: {'✗ FAIL' if len(same_rut_errors) > 0 else '✓ PASS'}")
    if same_rut_errors:
        print(f"    Error: {same_rut_errors[0].message}")

    # Test with different RUTs
    document_data["Receptor"]["RUTRecep"] = "66666666-6"
    results = validator.validate_document(document_data, "33")
    same_rut_errors = [r for r in results if "different" in r.message.lower()]
    print(f"  Different RUT test: {'✓ PASS' if len(same_rut_errors) == 0 else '✗ FAIL'}")

    print()

    # Test date consistency
    print("2. Date Consistency:")
    document_data = {
        "FchEmis": "2023-12-15",
        "FchVenc": "2023-12-10"  # Before emission - should fail
    }

    results = validator.validate_document(document_data, "33")
    date_errors = [r for r in results if "date" in r.message.lower() and not r.is_valid]
    print(f"  Due before emission: {'✗ FAIL' if len(date_errors) > 0 else '✓ PASS'}")
    if date_errors:
        print(f"    Error: {date_errors[0].message}")

    # Test with correct dates
    document_data["FchVenc"] = "2023-12-20"  # After emission
    results = validator.validate_document(document_data, "33")
    date_errors = [r for r in results if "date" in r.message.lower() and not r.is_valid]
    print(f"  Due after emission: {'✓ PASS' if len(date_errors) == 0 else '✗ FAIL'}")

    print()

    # Test total calculation consistency
    print("3. Total Calculation Consistency:")
    document_data = {
        "Totales": {
            "MntNeto": 1000,
            "IVA": 190,
            "MntTotal": 1200  # Incorrect total
        }
    }

    results = validator.validate_document(document_data, "33")
    total_errors = [r for r in results if "total" in r.message.lower() and not r.is_valid]
    print(f"  Incorrect total: {'✗ FAIL' if len(total_errors) > 0 else '✓ PASS'}")
    if total_errors:
        print(f"    Error: {total_errors[0].message}")

    # Test with correct total
    document_data["Totales"]["MntTotal"] = 1190
    results = validator.validate_document(document_data, "33")
    total_errors = [r for r in results if "total" in r.message.lower() and not r.is_valid]
    print(f"  Correct total: {'✓ PASS' if len(total_errors) == 0 else '✗ FAIL'}")

    print()


def demo_document_rules_validation():
    """Demonstrate document type specific validation."""
    print("=" * 60)
    print("DOCUMENT TYPE RULES VALIDATION DEMO")
    print("=" * 60)

    # Initialize validator
    validator = SiiDocumentRuleValidator(strict_mode=True)

    print("Supported Document Types:")
    types = validator.get_supported_document_types()
    print(f"  {', '.join(types)}")
    print()

    # Test Factura Electrónica structure
    print("Factura Electrónica (33) Validation:")
    print("-" * 35)

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

    results = validator.validate_document(document_data, "33")
    summary = validator.get_validation_summary(results)

    print(f"Structure validation: {'✓ PASS' if summary['rule_type_breakdown'].get('structure', 0) == 0 else '✗ FAIL'}")
    print(f"Field validation: {'✓ PASS' if summary['rule_type_breakdown'].get('field', 0) == 0 else '✗ FAIL'}")
    print(f"Business rules: {'✓ PASS' if summary['rule_type_breakdown'].get('business', 0) == 0 else '✗ FAIL'}")
    print(f"Overall valid: {'✓ YES' if summary['is_valid'] else '✗ NO'}")

    print()

    # Test Factura Exenta
    print("Factura Exenta (34) Validation:")
    print("-" * 30)

    # Factura Exenta with IVA (should fail)
    document_data = {
        "Encabezado": {
            "IdDoc": {"TipoDTE": "34", "Folio": 1001, "FchEmis": "2023-12-01"},
            "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
            "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
        },
        "Detalle": [{"NroLinDet": 1, "NmbItem": "Producto", "QtyItem": 1, "PrcItem": 1000}],
        "Totales": {"MntExe": 1000, "IVA": 190, "MntTotal": 1190}  # Should not have IVA
    }

    results = validator.validate_document(document_data, "34")
    iva_errors = [r for r in results if "iva" in r.message.lower() and not r.is_valid]
    print(f"IVA in Factura Exenta: {'✗ FAIL' if len(iva_errors) > 0 else '✓ PASS'}")
    if iva_errors:
        print(f"  Error: {iva_errors[0].message}")

    print()

    # Test Nota de Crédito
    print("Nota de Crédito (61) Validation:")
    print("-" * 30)

    # Note without reference (should fail)
    document_data = {
        "Encabezado": {
            "IdDoc": {"TipoDTE": "61", "Folio": 3001, "FchEmis": "2023-12-01"},
            "Emisor": {"RUTEmisor": "76354771-K", "RznSoc": "Mi Empresa"},
            "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
        },
        "Detalle": [{"NroLinDet": 1, "NmbItem": "Descuento", "QtyItem": 1, "PrcItem": -1000}],
        "Totales": {"MntTotal": -1000}
        # Missing Referencia section
    }

    results = validator.validate_document(document_data, "61")
    ref_errors = [r for r in results if "reference" in r.message.lower() and not r.is_valid]
    print(f"Missing reference: {'✗ FAIL' if len(ref_errors) > 0 else '✓ PASS'}")
    if ref_errors:
        print(f"  Error: {ref_errors[0].message}")

    print()


def demo_field_validation():
    """Demonstrate field-level validation."""
    print("=" * 60)
    print("FIELD VALIDATION DEMO")
    print("=" * 60)

    # Initialize validator
    validator = SiiFieldValidator(strict_mode=True)

    print("Individual Field Validations:")
    print("-" * 30)

    # Test RUT validation
    test_cases = [
        ("RUTEmisor", "76354771-K", "Valid RUT"),
        ("RUTEmisor", "12345678-9", "Invalid RUT check digit"),
        ("RUTEmisor", "12345", "Invalid RUT format"),
        ("TipoDTE", "33", "Valid document type"),
        ("TipoDTE", "99", "Invalid document type"),
        ("Folio", 1001, "Valid folio"),
        ("Folio", -1, "Invalid folio (negative)"),
        ("FchEmis", "2023-12-01", "Valid date"),
        ("FchEmis", "01/12/2023", "Invalid date format"),
        ("CorreoEmisor", "test@example.com", "Valid email"),
        ("CorreoEmisor", "invalid-email", "Invalid email"),
    ]

    for field_name, value, description in test_cases:
        result = validator.validate_field(field_name, value)
        status = "✓ PASS" if result.is_valid else "✗ FAIL"
        print(f"{description}: {status}")
        if not result.is_valid and result.errors:
            print(f"  Error: {result.errors[0]}")

    print()

    # Test document fields validation
    print("Document Fields Validation:")
    print("-" * 27)

    document_data = {
        "Encabezado": {
            "IdDoc": {"TipoDTE": "33", "Folio": 1001, "FchEmis": "2023-12-01"},
            "Emisor": {
                "RUTEmisor": "76354771-K",
                "RznSoc": "Mi Empresa",
                "CorreoEmisor": "empresa@example.com"
            },
            "Receptor": {"RUTRecep": "66666666-6", "RznSocRecep": "Cliente"}
        },
        "Totales": {"MntTotal": 1190}
    }

    results = validator.validate_document_fields(document_data, "33")
    summary = validator.get_validation_summary(results)

    print(f"Total fields validated: {summary['total_fields']}")
    print(f"Valid fields: {summary['valid_fields']}")
    print(f"Invalid fields: {summary['invalid_fields']}")
    print(f"Success rate: {summary['success_rate']:.1f}%")
    print(f"Has critical errors: {'YES' if summary['has_critical_errors'] else 'NO'}")

    if summary['invalid_fields'] > 0:
        print("\nField Errors:")
        for result in results:
            if not result.is_valid:
                print(f"  - {result.field_name}: {result.errors[0] if result.errors else 'Unknown error'}")

    print()


def demo_complete_validation_workflow():
    """Demonstrate complete document validation workflow."""
    print("=" * 60)
    print("COMPLETE VALIDATION WORKFLOW DEMO")
    print("=" * 60)

    # Initialize all validators
    business_validator = SiiBusinessRuleValidator()
    tax_validator = SiiTaxCalculationValidator()
    cross_validator = SiiCrossFieldValidator()
    document_validator = SiiDocumentRuleValidator()
    field_validator = SiiFieldValidator()

    print("Validating Complete DTE Document...")
    print()

    # Create a complete test document
    document_data = {
        "Encabezado": {
            "IdDoc": {
                "TipoDTE": "33",
                "Folio": 1001,
                "FchEmis": "2023-12-01",
                "FchVenc": "2023-12-31"
            },
            "Emisor": {
                "RUTEmisor": "76354771-K",
                "RznSoc": "Mi Empresa Ltda.",
                "GiroEmis": "Venta de productos",
                "DirOrigen": "Av. Principal 123",
                "CmnaOrigen": "Santiago"
            },
            "Receptor": {
                "RUTRecep": "66666666-6",
                "RznSocRecep": "Cliente Final",
                "DirRecep": "Calle Cliente 456",
                "CmnaRecep": "Providencia"
            }
        },
        "Detalle": [
            {
                "NroLinDet": 1,
                "NmbItem": "Producto A",
                "DscItem": "Descripción del producto A",
                "QtyItem": 2,
                "UnmdItem": "UN",
                "PrcItem": 500,
                "MontoItem": 1000
            }
        ],
        "Totales": {
            "MntNeto": 1000,
            "IVA": 190,
            "MntTotal": 1190
        }
    }

    # Create validation context
    context = ValidationContext(
        document_type="33",
        document_date=date.today(),
        document_folio=1001,
        ambiente="produccion"
    )

    print("Running validation pipeline...")
    print()

    # 1. Business Rules Validation
    print("1. Business Rules Validation:")
    business_results = business_validator.validate_dte_document(document_data, context)
    business_summary = business_validator.get_validation_summary(business_results)
    print(f"   Result: {'✓ PASS' if business_summary['is_valid'] else '✗ FAIL'}")
    print(f"   Rules checked: {business_summary['total_rules']}")
    print(f"   Success rate: {business_summary['success_rate']:.1f}%")

    # 2. Tax Calculation Validation
    print("2. Tax Calculation Validation:")
    tax_results = tax_validator.validate_sii_document_taxes(document_data, "33")
    tax_summary = tax_validator.get_tax_summary(tax_results)
    print(f"   Result: {'✓ PASS' if tax_summary['is_valid'] else '✗ FAIL'}")
    print(f"   Calculations checked: {tax_summary['total_validations']}")
    print(f"   Success rate: {tax_summary['success_rate']:.1f}%")

    # 3. Cross-Field Validation
    print("3. Cross-Field Validation:")
    cross_results = cross_validator.validate_sii_document(document_data, "33")
    cross_summary = cross_validator.get_validation_summary(cross_results)
    print(f"   Result: {'✓ PASS' if cross_summary['is_valid'] else '✗ FAIL'}")
    print(f"   Dependencies checked: {cross_summary['total_validations']}")
    print(f"   Success rate: {cross_summary['success_rate']:.1f}%")

    # 4. Document Structure Validation
    print("4. Document Structure Validation:")
    document_results = document_validator.validate_sii_document(document_data, "33", "produccion")
    document_summary = document_validator.get_validation_summary(document_results)
    print(f"   Result: {'✓ PASS' if document_summary['is_valid'] else '✗ FAIL'}")
    print(f"   Rules checked: {document_summary['total_rules']}")
    print(f"   Success rate: {document_summary['success_rate']:.1f}%")

    # 5. Field Validation
    print("5. Field Validation:")
    field_results = field_validator.validate_sii_document_fields(document_data, "33")
    field_summary = field_validator.get_validation_summary(field_results)
    print(f"   Result: {'✓ PASS' if field_summary['is_valid'] else '✗ FAIL'}")
    print(f"   Fields checked: {field_summary['total_fields']}")
    print(f"   Success rate: {field_summary['success_rate']:.1f}%")

    print()

    # Overall validation result
    all_valid = (
        business_summary['is_valid'] and
        tax_summary['is_valid'] and
        cross_summary['is_valid'] and
        document_summary['is_valid'] and
        field_summary['is_valid']
    )

    print(f"OVERALL VALIDATION RESULT: {'✓ DOCUMENT VALID' if all_valid else '✗ DOCUMENT INVALID'}")

    # Show any errors
    if not all_valid:
        print("\nValidation Errors Found:")

        if not business_summary['is_valid']:
            print("  Business Rules Errors:")
            for result in business_results:
                if not result.is_valid:
                    print(f"    - {result.message}")

        if not tax_summary['is_valid']:
            print("  Tax Calculation Errors:")
            for result in tax_results:
                if not result.is_valid:
                    print(f"    - {result.errors[0] if result.errors else 'Tax calculation error'}")

        if not cross_summary['is_valid']:
            print("  Cross-Field Errors:")
            for result in cross_results:
                if not result.is_valid:
                    print(f"    - {result.message}")

        if not document_summary['is_valid']:
            print("  Document Structure Errors:")
            for result in document_results:
                if not result.is_valid:
                    print(f"    - {result.message}")

        if not field_summary['is_valid']:
            print("  Field Validation Errors:")
            for result in field_results:
                if not result.is_valid:
                    print(f"    - {result.field_name}: {result.errors[0] if result.errors else 'Field error'}")

    print()


def main():
    """Run all validation demos."""
    print("RYPSYSTEMS DTE - ADVANCED VALIDATION SYSTEM DEMO")
    print("=" * 60)
    print()

    try:
        # Run individual component demos
        demo_business_rules_validation()
        demo_tax_calculation_validation()
        demo_cross_field_validation()
        demo_document_rules_validation()
        demo_field_validation()

        # Run complete workflow demo
        demo_complete_validation_workflow()

        print("=" * 60)
        print("DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print()
        print("The Advanced Validation System provides:")
        print("• Comprehensive business rules validation")
        print("• Accurate tax calculation verification")
        print("• Cross-field dependency checking")
        print("• Document type specific validation")
        print("• Field-level format and constraint validation")
        print("• Complete SII compliance checking")
        print()
        print("Ready for production use in Chilean DTE processing!")

    except Exception as e:
        print(f"Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()