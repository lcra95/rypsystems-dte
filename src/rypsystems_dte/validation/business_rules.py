"""
Business Rules Validation System.

Provides comprehensive SII business rule validation including:
- Document compliance with SII regulations
- Business logic validation beyond schema
- Tax authority specific rules
- Compliance with Chilean tax law
"""

import re
from datetime import datetime, date, timezone
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, Field, field_validator, ConfigDict

from ..sii.base import Contribuyente
from ..sii.utils import RutValidator


class RuleType(str, Enum):
    """Business rule types."""
    MANDATORY = "mandatory"
    CONDITIONAL = "conditional"
    FORMAT = "format"
    RANGE = "range"
    CALCULATION = "calculation"
    REFERENCE = "reference"
    TEMPORAL = "temporal"
    CONSISTENCY = "consistency"


class RuleLevel(str, Enum):
    """Rule enforcement levels."""
    STRICT = "strict"
    WARNING = "warning"
    INFO = "info"
    DISABLED = "disabled"


class RuleSeverity(str, Enum):
    """Rule violation severity."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ValidationContext(BaseModel):
    """Validation context information."""

    # Document information
    document_type: str = Field(..., description="Document type code")
    document_date: date = Field(..., description="Document date")
    document_folio: int = Field(..., description="Document folio number")

    # Parties information
    emisor: Optional[Contribuyente] = Field(None, description="Document issuer")
    receptor: Optional[Contribuyente] = Field(None, description="Document receptor")

    # Environment information
    ambiente: str = Field(default="produccion", description="SII environment")
    casa_matriz: bool = Field(default=True, description="Is main office")

    # Validation settings
    validation_level: RuleLevel = Field(default=RuleLevel.STRICT)
    ignore_warnings: bool = Field(default=False)

    # Additional context
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class RuleResult(BaseModel):
    """Business rule validation result."""

    # Rule identification
    rule_id: str = Field(..., description="Rule identifier")
    rule_name: str = Field(..., description="Rule name")
    rule_type: RuleType = Field(..., description="Rule type")

    # Validation result
    is_valid: bool = Field(..., description="Validation result")
    severity: RuleSeverity = Field(..., description="Violation severity")

    # Details
    message: str = Field(..., description="Validation message")
    field_path: Optional[str] = Field(None, description="Field path if applicable")
    expected_value: Optional[str] = Field(None, description="Expected value")
    actual_value: Optional[str] = Field(None, description="Actual value")

    # Context
    rule_description: Optional[str] = Field(None, description="Rule description")
    reference: Optional[str] = Field(None, description="Legal/regulatory reference")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class BusinessRule(BaseModel):
    """Business rule definition."""

    # Rule identification
    rule_id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")

    # Rule configuration
    rule_type: RuleType = Field(..., description="Rule type")
    severity: RuleSeverity = Field(..., description="Default severity")
    level: RuleLevel = Field(default=RuleLevel.STRICT, description="Enforcement level")

    # Application scope
    document_types: List[str] = Field(default_factory=list, description="Applicable document types")
    field_paths: List[str] = Field(default_factory=list, description="Applicable field paths")

    # Rule logic
    validation_function: Optional[Callable] = Field(None, description="Validation function")
    condition_expression: Optional[str] = Field(None, description="Condition expression")

    # References
    legal_reference: Optional[str] = Field(None, description="Legal reference")
    sii_reference: Optional[str] = Field(None, description="SII reference")

    # Configuration
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Rule parameters")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class BusinessRuleValidator:
    """
    Business rule validation engine.

    Provides comprehensive business logic validation including:
    - SII compliance rules
    - Tax calculation validation
    - Document consistency checks
    - Field format validation
    """

    def __init__(self,
                 validation_level: RuleLevel = RuleLevel.STRICT,
                 custom_rules: Optional[List[BusinessRule]] = None):
        """
        Initialize business rule validator.

        Args:
            validation_level: Default validation level
            custom_rules: Additional custom rules
        """
        self.validation_level = validation_level
        self.rules: Dict[str, BusinessRule] = {}
        self._load_default_rules()

        if custom_rules:
            for rule in custom_rules:
                self.add_rule(rule)

    def _load_default_rules(self):
        """Load default business rules."""
        # This would typically load from configuration files
        # For now, we'll define some key rules programmatically

        # Document folio rules
        self.add_rule(BusinessRule(
            rule_id="folio_positive",
            name="Folio Must Be Positive",
            description="Document folio must be a positive integer",
            rule_type=RuleType.RANGE,
            severity=RuleSeverity.CRITICAL,
            field_paths=["Folio"],
            legal_reference="Ley 19.983 Art. 3"
        ))

        # RUT validation rules
        self.add_rule(BusinessRule(
            rule_id="emisor_rut_valid",
            name="Emisor RUT Valid",
            description="Emisor RUT must be valid according to Chilean format",
            rule_type=RuleType.FORMAT,
            severity=RuleSeverity.CRITICAL,
            field_paths=["Emisor.RUTEmisor"],
            legal_reference="Resolución SII N° 80"
        ))

        # Date validation rules
        self.add_rule(BusinessRule(
            rule_id="fecha_emision_valid",
            name="Emission Date Valid",
            description="Emission date must be valid and not future",
            rule_type=RuleType.TEMPORAL,
            severity=RuleSeverity.HIGH,
            field_paths=["FchEmis"],
            legal_reference="Resolución SII N° 80"
        ))

        # Amount validation rules
        self.add_rule(BusinessRule(
            rule_id="monto_neto_positive",
            name="Net Amount Positive",
            description="Net amount must be positive",
            rule_type=RuleType.RANGE,
            severity=RuleSeverity.HIGH,
            field_paths=["MntNeto"],
            legal_reference="Ley del IVA Art. 12"
        ))

    def add_rule(self, rule: BusinessRule):
        """Add a business rule to the validator."""
        self.rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str):
        """Remove a business rule from the validator."""
        if rule_id in self.rules:
            del self.rules[rule_id]

    def get_applicable_rules(self,
                           document_type: str,
                           field_path: Optional[str] = None) -> List[BusinessRule]:
        """Get rules applicable to document type and field path."""
        applicable_rules = []

        for rule in self.rules.values():
            # Check if rule applies to document type
            if rule.document_types and document_type not in rule.document_types:
                continue

            # Check if rule applies to field path
            if field_path and rule.field_paths:
                if not any(fp in field_path for fp in rule.field_paths):
                    continue

            # Check enforcement level
            if rule.level == RuleLevel.DISABLED:
                continue

            applicable_rules.append(rule)

        return applicable_rules

    def validate_field_value(self,
                           field_path: str,
                           value: Any,
                           context: ValidationContext) -> List[RuleResult]:
        """Validate a single field value against applicable rules."""
        results = []
        applicable_rules = self.get_applicable_rules(
            context.document_type,
            field_path
        )

        for rule in applicable_rules:
            result = self._apply_rule(rule, field_path, value, context)
            if result:
                results.append(result)

        return results

    def validate_document(self,
                         document_data: Dict[str, Any],
                         context: ValidationContext) -> List[RuleResult]:
        """Validate entire document against all applicable rules."""
        results = []

        # Get all applicable rules for document type
        applicable_rules = self.get_applicable_rules(context.document_type)

        for rule in applicable_rules:
            # Apply rule to document
            if rule.field_paths:
                for field_path in rule.field_paths:
                    value = self._get_nested_value(document_data, field_path)
                    result = self._apply_rule(rule, field_path, value, context)
                    if result:
                        results.append(result)
            else:
                # Document-level rule
                result = self._apply_rule(rule, None, document_data, context)
                if result:
                    results.append(result)

        return results

    def _apply_rule(self,
                   rule: BusinessRule,
                   field_path: Optional[str],
                   value: Any,
                   context: ValidationContext) -> Optional[RuleResult]:
        """Apply a single rule to a value."""
        try:
            # Check if rule should be applied based on level
            if rule.level == RuleLevel.DISABLED:
                return None

            # Apply rule based on type
            is_valid = True
            message = ""

            if rule.rule_id == "folio_positive":
                is_valid, message = self._validate_folio_positive(value)
            elif rule.rule_id == "emisor_rut_valid":
                is_valid, message = self._validate_rut_format(value)
            elif rule.rule_id == "fecha_emision_valid":
                is_valid, message = self._validate_emission_date(value)
            elif rule.rule_id == "monto_neto_positive":
                is_valid, message = self._validate_amount_positive(value)
            elif rule.validation_function:
                is_valid, message = rule.validation_function(value, context)
            else:
                # Default validation
                is_valid = value is not None
                message = "Field is required" if not is_valid else "Valid"

            # Create result only if validation failed or level is info
            if not is_valid or rule.level == RuleLevel.INFO:
                return RuleResult(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    rule_type=rule.rule_type,
                    is_valid=is_valid,
                    severity=rule.severity,
                    message=message,
                    field_path=field_path,
                    actual_value=str(value) if value is not None else None,
                    rule_description=rule.description,
                    reference=rule.legal_reference
                )

            return None

        except Exception as e:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                is_valid=False,
                severity=RuleSeverity.CRITICAL,
                message=f"Rule evaluation error: {e}",
                field_path=field_path,
                actual_value=str(value) if value is not None else None,
                rule_description=rule.description
            )

    def _validate_folio_positive(self, value: Any) -> Tuple[bool, str]:
        """Validate folio is positive integer."""
        try:
            folio = int(value)
            if folio <= 0:
                return False, f"Folio must be positive, got {folio}"
            return True, "Valid folio"
        except (ValueError, TypeError):
            return False, f"Folio must be integer, got {type(value).__name__}"

    def _validate_rut_format(self, value: Any) -> Tuple[bool, str]:
        """Validate RUT format."""
        try:
            if not value:
                return False, "RUT is required"

            rut_str = str(value)
            if RutValidator.validate(rut_str):
                return True, "Valid RUT format"
            else:
                return False, f"Invalid RUT format: {rut_str}"
        except Exception as e:
            return False, f"RUT validation error: {e}"

    def _validate_emission_date(self, value: Any) -> Tuple[bool, str]:
        """Validate emission date."""
        try:
            if isinstance(value, str):
                # Parse date string
                date_obj = datetime.strptime(value, "%Y-%m-%d").date()
            elif isinstance(value, datetime):
                date_obj = value.date()
            elif isinstance(value, date):
                date_obj = value
            else:
                return False, f"Invalid date type: {type(value).__name__}"

            today = date.today()

            # Check if date is not in future
            if date_obj > today:
                return False, f"Emission date cannot be in future: {date_obj}"

            # Check if date is not too old (configurable)
            max_age_days = 365 * 5  # 5 years
            if (today - date_obj).days > max_age_days:
                return False, f"Emission date too old: {date_obj}"

            return True, "Valid emission date"

        except ValueError as e:
            return False, f"Invalid date format: {e}"
        except Exception as e:
            return False, f"Date validation error: {e}"

    def _validate_amount_positive(self, value: Any) -> Tuple[bool, str]:
        """Validate amount is positive."""
        try:
            if value is None:
                return True, "Amount not specified"  # Optional field

            amount = Decimal(str(value))
            if amount < 0:
                return False, f"Amount must be non-negative, got {amount}"

            return True, "Valid amount"

        except (ValueError, TypeError):
            return False, f"Amount must be numeric, got {type(value).__name__}"

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = path.split('.')
        value = data

        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
            return value
        except (KeyError, TypeError):
            return None

    def get_validation_summary(self, results: List[RuleResult]) -> Dict[str, Any]:
        """Get validation summary from results."""
        total_rules = len(results)
        passed = sum(1 for r in results if r.is_valid)
        failed = total_rules - passed

        severity_counts = {}
        for severity in RuleSeverity:
            severity_counts[severity.value] = sum(
                1 for r in results
                if not r.is_valid and r.severity == severity
            )

        return {
            'total_rules': total_rules,
            'passed': passed,
            'failed': failed,
            'success_rate': (passed / total_rules * 100) if total_rules > 0 else 100,
            'has_critical_errors': severity_counts.get('critical', 0) > 0,
            'has_high_errors': severity_counts.get('high', 0) > 0,
            'severity_breakdown': severity_counts,
            'is_valid': failed == 0 or all(
                r.severity in [RuleSeverity.LOW, RuleSeverity.INFO]
                for r in results if not r.is_valid
            )
        }


class SiiBusinessRuleValidator(BusinessRuleValidator):
    """
    SII-specific business rule validator.

    Extends base validator with Chilean SII-specific rules.
    """

    def __init__(self, **kwargs):
        """Initialize SII business rule validator."""
        super().__init__(**kwargs)
        self._load_sii_rules()

    def _load_sii_rules(self):
        """Load SII-specific business rules."""

        # Document type specific rules
        self.add_rule(BusinessRule(
            rule_id="factura_electronica_format",
            name="Factura Electrónica Format",
            description="Factura electrónica must comply with SII format",
            rule_type=RuleType.FORMAT,
            severity=RuleSeverity.CRITICAL,
            document_types=["33"],
            legal_reference="Resolución SII N° 80"
        ))

        # Tax calculation rules
        self.add_rule(BusinessRule(
            rule_id="iva_calculation_correct",
            name="IVA Calculation Correct",
            description="IVA must be calculated correctly (19%)",
            rule_type=RuleType.CALCULATION,
            severity=RuleSeverity.HIGH,
            field_paths=["IVA", "MntNeto"],
            legal_reference="Ley del IVA Art. 14"
        ))

        # Giro validation
        self.add_rule(BusinessRule(
            rule_id="giro_emisor_valid",
            name="Emisor Giro Valid",
            description="Emisor must have valid business activity code",
            rule_type=RuleType.REFERENCE,
            severity=RuleSeverity.MEDIUM,
            field_paths=["Emisor.GiroEmis"],
            sii_reference="Codificación SII Actividades Económicas"
        ))

        # Municipality code validation
        self.add_rule(BusinessRule(
            rule_id="comuna_valid",
            name="Comuna Code Valid",
            description="Comuna code must be valid according to SII",
            rule_type=RuleType.REFERENCE,
            severity=RuleSeverity.MEDIUM,
            field_paths=["Emisor.CmnaOrigen", "Receptor.CmnaRecep"],
            sii_reference="Tabla de Comunas SII"
        ))

        # Document sequence rules
        self.add_rule(BusinessRule(
            rule_id="folio_sequence_valid",
            name="Folio Sequence Valid",
            description="Folio must be within authorized sequence",
            rule_type=RuleType.RANGE,
            severity=RuleSeverity.CRITICAL,
            field_paths=["Folio"],
            legal_reference="Resolución SII N° 80"
        ))

    def validate_dte_document(self,
                            dte_data: Dict[str, Any],
                            context: ValidationContext) -> List[RuleResult]:
        """Validate DTE document with SII-specific rules."""
        results = super().validate_document(dte_data, context)

        # Apply additional SII-specific validations
        results.extend(self._validate_sii_specific_rules(dte_data, context))

        return results

    def _validate_sii_specific_rules(self,
                                   dte_data: Dict[str, Any],
                                   context: ValidationContext) -> List[RuleResult]:
        """Apply SII-specific validation rules."""
        results = []

        # Validate IVA calculation
        if context.document_type in ["33", "34"]:  # Factura, Factura Exenta
            iva_result = self._validate_iva_calculation(dte_data)
            if iva_result:
                results.append(iva_result)

        # Validate document type specific requirements
        type_result = self._validate_document_type_requirements(dte_data, context)
        if type_result:
            results.append(type_result)

        return results

    def _validate_iva_calculation(self, dte_data: Dict[str, Any]) -> Optional[RuleResult]:
        """Validate IVA calculation is correct."""
        try:
            mnt_neto = dte_data.get('Totales', {}).get('MntNeto', 0)
            iva = dte_data.get('Totales', {}).get('IVA', 0)

            if mnt_neto > 0:
                expected_iva = Decimal(str(mnt_neto)) * Decimal('0.19')
                expected_iva = expected_iva.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
                actual_iva = Decimal(str(iva))

                if abs(expected_iva - actual_iva) > Decimal('1'):  # Allow 1 peso difference for rounding
                    return RuleResult(
                        rule_id="iva_calculation_correct",
                        rule_name="IVA Calculation Correct",
                        rule_type=RuleType.CALCULATION,
                        is_valid=False,
                        severity=RuleSeverity.HIGH,
                        message=f"IVA calculation incorrect. Expected: {expected_iva}, Got: {actual_iva}",
                        field_path="Totales.IVA",
                        expected_value=str(expected_iva),
                        actual_value=str(actual_iva),
                        reference="Ley del IVA Art. 14"
                    )

            return None

        except Exception as e:
            return RuleResult(
                rule_id="iva_calculation_correct",
                rule_name="IVA Calculation Correct",
                rule_type=RuleType.CALCULATION,
                is_valid=False,
                severity=RuleSeverity.CRITICAL,
                message=f"Error validating IVA calculation: {e}",
                field_path="Totales.IVA"
            )

    def _validate_document_type_requirements(self,
                                           dte_data: Dict[str, Any],
                                           context: ValidationContext) -> Optional[RuleResult]:
        """Validate document type specific requirements."""
        doc_type = context.document_type

        # Factura Electrónica (33) requirements
        if doc_type == "33":
            # Must have IVA
            if not dte_data.get('Totales', {}).get('IVA'):
                return RuleResult(
                    rule_id="factura_electronica_format",
                    rule_name="Factura Electrónica Format",
                    rule_type=RuleType.MANDATORY,
                    is_valid=False,
                    severity=RuleSeverity.CRITICAL,
                    message="Factura Electrónica must include IVA",
                    field_path="Totales.IVA",
                    reference="Resolución SII N° 80"
                )

        # Factura Exenta (34) requirements
        elif doc_type == "34":
            # Must not have IVA
            if dte_data.get('Totales', {}).get('IVA', 0) > 0:
                return RuleResult(
                    rule_id="factura_exenta_format",
                    rule_name="Factura Exenta Format",
                    rule_type=RuleType.MANDATORY,
                    is_valid=False,
                    severity=RuleSeverity.CRITICAL,
                    message="Factura Exenta must not include IVA",
                    field_path="Totales.IVA",
                    reference="Resolución SII N° 80"
                )

        return None

    def validate_contribuyente_rules(self, contribuyente: Contribuyente) -> List[RuleResult]:
        """Validate contribuyente-specific rules."""
        results = []

        # Validate RUT
        if not RutValidator.validate(contribuyente.rut):
            results.append(RuleResult(
                rule_id="contribuyente_rut_valid",
                rule_name="Contribuyente RUT Valid",
                rule_type=RuleType.FORMAT,
                is_valid=False,
                severity=RuleSeverity.CRITICAL,
                message=f"Invalid RUT format: {contribuyente.rut}",
                field_path="RUT",
                actual_value=contribuyente.rut,
                reference="Resolución SII N° 80"
            ))

        # Validate business name length
        if len(contribuyente.razon_social) > 100:
            results.append(RuleResult(
                rule_id="razon_social_length",
                rule_name="Razón Social Length",
                rule_type=RuleType.FORMAT,
                is_valid=False,
                severity=RuleSeverity.MEDIUM,
                message=f"Razón social too long: {len(contribuyente.razon_social)} characters",
                field_path="RznSoc",
                actual_value=str(len(contribuyente.razon_social)),
                expected_value="≤100",
                reference="Resolución SII N° 80"
            ))

        return results