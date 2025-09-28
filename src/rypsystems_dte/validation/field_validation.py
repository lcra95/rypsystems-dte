"""
Field Validation System.

Provides comprehensive field-level validation including:
- Field format validation
- Field length validation
- Field type validation
- SII-specific field rules
- Custom field validators
"""

import re
from typing import Dict, List, Optional, Any, Union, Callable, Pattern
from enum import Enum
from decimal import Decimal
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, ConfigDict

from ..sii.utils import RutValidator


class FieldType(str, Enum):
    """Field data types."""
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    RUT = "rut"
    EMAIL = "email"
    PHONE = "phone"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"


class FieldConstraint(BaseModel):
    """Field validation constraint."""

    # Constraint identification
    constraint_id: str = Field(..., description="Constraint identifier")
    constraint_type: str = Field(..., description="Constraint type")
    description: str = Field(..., description="Constraint description")

    # Validation parameters
    min_length: Optional[int] = Field(None, description="Minimum length")
    max_length: Optional[int] = Field(None, description="Maximum length")
    min_value: Optional[Union[int, float, Decimal]] = Field(None, description="Minimum value")
    max_value: Optional[Union[int, float, Decimal]] = Field(None, description="Maximum value")

    # Pattern validation
    pattern: Optional[str] = Field(None, description="Regex pattern")
    allowed_values: Optional[List[str]] = Field(None, description="Allowed values")
    forbidden_values: Optional[List[str]] = Field(None, description="Forbidden values")

    # Custom validation
    validation_function: Optional[Callable] = Field(None, description="Custom validation function")

    # Configuration
    severity: str = Field(default="high", description="Constraint severity")
    is_active: bool = Field(default=True, description="Whether constraint is active")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class FieldRule(BaseModel):
    """Field validation rule."""

    # Rule identification
    field_name: str = Field(..., description="Field name or path")
    field_type: FieldType = Field(..., description="Field data type")
    description: str = Field(..., description="Field description")

    # Validation constraints
    constraints: List[FieldConstraint] = Field(default_factory=list, description="Field constraints")

    # Field properties
    is_required: bool = Field(default=False, description="Whether field is required")
    is_conditional: bool = Field(default=False, description="Whether field is conditionally required")
    condition_expression: Optional[str] = Field(None, description="Condition for conditional requirement")

    # SII specific
    sii_field_code: Optional[str] = Field(None, description="SII field code")
    document_types: List[str] = Field(default_factory=list, description="Applicable document types")

    # References
    legal_reference: Optional[str] = Field(None, description="Legal reference")
    sii_reference: Optional[str] = Field(None, description="SII reference")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class FieldValidationResult(BaseModel):
    """Field validation result."""

    # Field information
    field_name: str = Field(..., description="Field name")
    field_path: str = Field(..., description="Full field path")
    field_type: FieldType = Field(..., description="Field type")

    # Validation result
    is_valid: bool = Field(..., description="Overall validation result")
    value: Optional[str] = Field(None, description="Field value")

    # Constraint results
    passed_constraints: List[str] = Field(default_factory=list, description="Passed constraint IDs")
    failed_constraints: List[str] = Field(default_factory=list, description="Failed constraint IDs")

    # Messages
    messages: List[str] = Field(default_factory=list, description="Validation messages")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    errors: List[str] = Field(default_factory=list, description="Validation errors")

    # Context
    severity: str = Field(default="medium", description="Highest severity of failures")
    reference: Optional[str] = Field(None, description="Reference")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class FieldValidator:
    """
    Field validation engine.

    Provides comprehensive field-level validation including:
    - Type validation
    - Format validation
    - Length validation
    - Value range validation
    - Custom validation rules
    """

    def __init__(self,
                 strict_mode: bool = True,
                 custom_rules: Optional[List[FieldRule]] = None):
        """
        Initialize field validator.

        Args:
            strict_mode: Whether to use strict validation
            custom_rules: Additional custom field rules
        """
        self.strict_mode = strict_mode
        self.field_rules: Dict[str, FieldRule] = {}

        # Load default field rules
        self._load_default_field_rules()

        # Add custom rules
        if custom_rules:
            for rule in custom_rules:
                self.add_field_rule(rule)

        # Compile regex patterns
        self._compile_patterns()

    def _load_default_field_rules(self):
        """Load default field validation rules."""

        # RUT fields
        self.add_field_rule(FieldRule(
            field_name="RUTEmisor",
            field_type=FieldType.RUT,
            description="Emisor RUT",
            is_required=True,
            constraints=[
                FieldConstraint(
                    constraint_id="rut_format",
                    constraint_type="format",
                    description="Valid Chilean RUT format",
                    pattern=r"^\d{1,8}-[0-9Kk]$",
                    severity="critical"
                ),
                FieldConstraint(
                    constraint_id="rut_validation",
                    constraint_type="custom",
                    description="Valid RUT check digit",
                    severity="critical"
                )
            ],
            sii_field_code="RUTEmisor",
            sii_reference="Resolución SII N° 80"
        ))

        self.add_field_rule(FieldRule(
            field_name="RUTRecep",
            field_type=FieldType.RUT,
            description="Receptor RUT",
            is_required=True,
            constraints=[
                FieldConstraint(
                    constraint_id="rut_format",
                    constraint_type="format",
                    description="Valid Chilean RUT format",
                    pattern=r"^\d{1,8}-[0-9Kk]$",
                    severity="critical"
                ),
                FieldConstraint(
                    constraint_id="rut_validation",
                    constraint_type="custom",
                    description="Valid RUT check digit",
                    severity="critical"
                )
            ],
            sii_field_code="RUTRecep",
            sii_reference="Resolución SII N° 80"
        ))

        # Business name fields
        self.add_field_rule(FieldRule(
            field_name="RznSoc",
            field_type=FieldType.STRING,
            description="Business name",
            is_required=True,
            constraints=[
                FieldConstraint(
                    constraint_id="length_limit",
                    constraint_type="length",
                    description="Maximum 100 characters",
                    max_length=100,
                    severity="high"
                ),
                FieldConstraint(
                    constraint_id="not_empty",
                    constraint_type="required",
                    description="Cannot be empty",
                    severity="critical"
                )
            ],
            sii_field_code="RznSoc",
            sii_reference="Resolución SII N° 80"
        ))

        # Document type field
        self.add_field_rule(FieldRule(
            field_name="TipoDTE",
            field_type=FieldType.INTEGER,
            description="Document type",
            is_required=True,
            constraints=[
                FieldConstraint(
                    constraint_id="valid_dte_types",
                    constraint_type="enumeration",
                    description="Valid DTE type codes",
                    allowed_values=["33", "34", "39", "41", "43", "46", "52", "56", "61"],
                    severity="critical"
                )
            ],
            sii_field_code="TipoDTE",
            sii_reference="Resolución SII N° 80"
        ))

        # Folio field
        self.add_field_rule(FieldRule(
            field_name="Folio",
            field_type=FieldType.INTEGER,
            description="Document folio",
            is_required=True,
            constraints=[
                FieldConstraint(
                    constraint_id="positive_value",
                    constraint_type="range",
                    description="Must be positive",
                    min_value=1,
                    max_value=999999999,
                    severity="critical"
                )
            ],
            sii_field_code="Folio",
            sii_reference="Resolución SII N° 80"
        ))

        # Date fields
        self.add_field_rule(FieldRule(
            field_name="FchEmis",
            field_type=FieldType.DATE,
            description="Emission date",
            is_required=True,
            constraints=[
                FieldConstraint(
                    constraint_id="date_format",
                    constraint_type="format",
                    description="YYYY-MM-DD format",
                    pattern=r"^\d{4}-\d{2}-\d{2}$",
                    severity="critical"
                ),
                FieldConstraint(
                    constraint_id="not_future",
                    constraint_type="custom",
                    description="Cannot be in future",
                    severity="high"
                )
            ],
            sii_field_code="FchEmis",
            sii_reference="Resolución SII N° 80"
        ))

        # Amount fields
        self.add_field_rule(FieldRule(
            field_name="MntTotal",
            field_type=FieldType.CURRENCY,
            description="Total amount",
            is_required=True,
            constraints=[
                FieldConstraint(
                    constraint_id="non_negative",
                    constraint_type="range",
                    description="Must be non-negative",
                    min_value=0,
                    severity="high"
                ),
                FieldConstraint(
                    constraint_id="max_amount",
                    constraint_type="range",
                    description="Maximum amount limit",
                    max_value=999999999999,
                    severity="medium"
                )
            ],
            sii_field_code="MntTotal",
            sii_reference="Resolución SII N° 80"
        ))

        # Email field
        self.add_field_rule(FieldRule(
            field_name="CorreoEmisor",
            field_type=FieldType.EMAIL,
            description="Emisor email",
            is_required=False,
            constraints=[
                FieldConstraint(
                    constraint_id="email_format",
                    constraint_type="format",
                    description="Valid email format",
                    pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                    severity="medium"
                ),
                FieldConstraint(
                    constraint_id="email_length",
                    constraint_type="length",
                    description="Maximum 80 characters",
                    max_length=80,
                    severity="medium"
                )
            ],
            sii_field_code="CorreoEmisor"
        ))

    def add_field_rule(self, field_rule: FieldRule):
        """Add a field validation rule."""
        self.field_rules[field_rule.field_name] = field_rule

    def _compile_patterns(self):
        """Compile regex patterns for performance."""
        self._compiled_patterns: Dict[str, Pattern] = {}

        for rule in self.field_rules.values():
            for constraint in rule.constraints:
                if constraint.pattern and constraint.constraint_id not in self._compiled_patterns:
                    try:
                        self._compiled_patterns[constraint.constraint_id] = re.compile(constraint.pattern)
                    except re.error:
                        # Invalid regex pattern
                        pass

    def validate_field(self,
                      field_name: str,
                      field_value: Any,
                      field_path: str = None,
                      document_context: Dict[str, Any] = None) -> FieldValidationResult:
        """Validate a single field value."""
        field_path = field_path or field_name

        # Get field rule
        if field_name not in self.field_rules:
            return FieldValidationResult(
                field_name=field_name,
                field_path=field_path,
                field_type=FieldType.STRING,
                is_valid=True,
                value=str(field_value) if field_value is not None else None,
                warnings=[f"No validation rule defined for field '{field_name}'"]
            )

        rule = self.field_rules[field_name]

        # Initialize result
        result = FieldValidationResult(
            field_name=field_name,
            field_path=field_path,
            field_type=rule.field_type,
            is_valid=True,
            value=str(field_value) if field_value is not None else None,
            reference=rule.legal_reference or rule.sii_reference
        )

        # Check if field is required
        if rule.is_required and (field_value is None or field_value == ""):
            result.is_valid = False
            result.errors.append(f"Required field '{field_name}' is missing or empty")
            result.failed_constraints.append("required")
            result.severity = "critical"
            return result

        # Skip validation if field is empty and not required
        if field_value is None or field_value == "":
            return result

        # Validate type
        type_valid, type_message = self._validate_field_type(field_value, rule.field_type)
        if not type_valid:
            result.is_valid = False
            result.errors.append(type_message)
            result.failed_constraints.append("type_validation")
            result.severity = "critical"
            return result

        # Apply constraints
        for constraint in rule.constraints:
            if not constraint.is_active:
                continue

            constraint_result = self._apply_constraint(field_value, constraint, rule.field_type)

            if constraint_result["is_valid"]:
                result.passed_constraints.append(constraint.constraint_id)
                if constraint_result.get("message"):
                    result.messages.append(constraint_result["message"])
            else:
                result.failed_constraints.append(constraint.constraint_id)
                result.errors.append(constraint_result["message"])
                result.is_valid = False

                # Update severity
                if constraint.severity == "critical":
                    result.severity = "critical"
                elif constraint.severity == "high" and result.severity != "critical":
                    result.severity = "high"

        return result

    def _validate_field_type(self, value: Any, field_type: FieldType) -> tuple[bool, str]:
        """Validate field data type."""
        try:
            if field_type == FieldType.STRING:
                return True, "Valid string"

            elif field_type == FieldType.INTEGER:
                int(value)
                return True, "Valid integer"

            elif field_type == FieldType.DECIMAL:
                Decimal(str(value))
                return True, "Valid decimal"

            elif field_type == FieldType.DATE:
                if isinstance(value, str):
                    datetime.strptime(value, "%Y-%m-%d")
                elif not isinstance(value, (date, datetime)):
                    return False, "Invalid date type"
                return True, "Valid date"

            elif field_type == FieldType.DATETIME:
                if isinstance(value, str):
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                elif not isinstance(value, datetime):
                    return False, "Invalid datetime type"
                return True, "Valid datetime"

            elif field_type == FieldType.BOOLEAN:
                if isinstance(value, bool):
                    return True, "Valid boolean"
                elif isinstance(value, str) and value.lower() in ['true', 'false', '1', '0']:
                    return True, "Valid boolean"
                else:
                    return False, "Invalid boolean value"

            elif field_type == FieldType.RUT:
                return True, "RUT type - validation in constraints"

            elif field_type == FieldType.EMAIL:
                return True, "Email type - validation in constraints"

            elif field_type == FieldType.CURRENCY:
                Decimal(str(value))
                return True, "Valid currency"

            else:
                return True, "Unknown type - no validation"

        except (ValueError, TypeError) as e:
            return False, f"Invalid {field_type.value}: {e}"

    def _apply_constraint(self,
                         value: Any,
                         constraint: FieldConstraint,
                         field_type: FieldType) -> Dict[str, Any]:
        """Apply a validation constraint to a field value."""
        try:
            if constraint.constraint_type == "format":
                return self._validate_format_constraint(value, constraint)
            elif constraint.constraint_type == "length":
                return self._validate_length_constraint(value, constraint)
            elif constraint.constraint_type == "range":
                return self._validate_range_constraint(value, constraint)
            elif constraint.constraint_type == "enumeration":
                return self._validate_enumeration_constraint(value, constraint)
            elif constraint.constraint_type == "custom":
                return self._validate_custom_constraint(value, constraint, field_type)
            elif constraint.constraint_type == "required":
                return self._validate_required_constraint(value, constraint)
            else:
                return {"is_valid": True, "message": f"Unknown constraint type: {constraint.constraint_type}"}

        except Exception as e:
            return {"is_valid": False, "message": f"Constraint validation error: {e}"}

    def _validate_format_constraint(self, value: Any, constraint: FieldConstraint) -> Dict[str, Any]:
        """Validate format constraint using regex pattern."""
        if not constraint.pattern:
            return {"is_valid": True, "message": "No pattern specified"}

        value_str = str(value)

        # Use compiled pattern if available
        if constraint.constraint_id in self._compiled_patterns:
            pattern = self._compiled_patterns[constraint.constraint_id]
            if pattern.match(value_str):
                return {"is_valid": True, "message": "Format valid"}
            else:
                return {"is_valid": False, "message": f"Format invalid. Expected pattern: {constraint.pattern}"}
        else:
            # Fallback to re.match
            if re.match(constraint.pattern, value_str):
                return {"is_valid": True, "message": "Format valid"}
            else:
                return {"is_valid": False, "message": f"Format invalid. Expected pattern: {constraint.pattern}"}

    def _validate_length_constraint(self, value: Any, constraint: FieldConstraint) -> Dict[str, Any]:
        """Validate length constraint."""
        value_str = str(value)
        length = len(value_str)

        if constraint.min_length is not None and length < constraint.min_length:
            return {"is_valid": False, "message": f"Length too short. Minimum: {constraint.min_length}, Got: {length}"}

        if constraint.max_length is not None and length > constraint.max_length:
            return {"is_valid": False, "message": f"Length too long. Maximum: {constraint.max_length}, Got: {length}"}

        return {"is_valid": True, "message": "Length valid"}

    def _validate_range_constraint(self, value: Any, constraint: FieldConstraint) -> Dict[str, Any]:
        """Validate range constraint."""
        try:
            numeric_value = Decimal(str(value))

            if constraint.min_value is not None and numeric_value < Decimal(str(constraint.min_value)):
                return {"is_valid": False, "message": f"Value too small. Minimum: {constraint.min_value}, Got: {value}"}

            if constraint.max_value is not None and numeric_value > Decimal(str(constraint.max_value)):
                return {"is_valid": False, "message": f"Value too large. Maximum: {constraint.max_value}, Got: {value}"}

            return {"is_valid": True, "message": "Range valid"}

        except (ValueError, TypeError):
            return {"is_valid": False, "message": f"Cannot validate range for non-numeric value: {value}"}

    def _validate_enumeration_constraint(self, value: Any, constraint: FieldConstraint) -> Dict[str, Any]:
        """Validate enumeration constraint."""
        value_str = str(value)

        if constraint.allowed_values and value_str not in constraint.allowed_values:
            return {"is_valid": False, "message": f"Value not allowed. Allowed: {constraint.allowed_values}, Got: {value}"}

        if constraint.forbidden_values and value_str in constraint.forbidden_values:
            return {"is_valid": False, "message": f"Value forbidden. Forbidden: {constraint.forbidden_values}, Got: {value}"}

        return {"is_valid": True, "message": "Enumeration valid"}

    def _validate_custom_constraint(self,
                                   value: Any,
                                   constraint: FieldConstraint,
                                   field_type: FieldType) -> Dict[str, Any]:
        """Validate custom constraint."""
        # Apply built-in custom validations
        if constraint.constraint_id == "rut_validation":
            return self._validate_rut(value)
        elif constraint.constraint_id == "not_future":
            return self._validate_not_future_date(value)
        elif constraint.validation_function:
            try:
                is_valid, message = constraint.validation_function(value)
                return {"is_valid": is_valid, "message": message}
            except Exception as e:
                return {"is_valid": False, "message": f"Custom validation error: {e}"}
        else:
            return {"is_valid": True, "message": "No custom validation specified"}

    def _validate_required_constraint(self, value: Any, constraint: FieldConstraint) -> Dict[str, Any]:
        """Validate required constraint."""
        if value is None or value == "":
            return {"is_valid": False, "message": "Field is required"}
        return {"is_valid": True, "message": "Required field present"}

    def _validate_rut(self, value: Any) -> Dict[str, Any]:
        """Validate Chilean RUT."""
        try:
            rut_str = str(value)
            if RutValidator.validate(rut_str):
                return {"is_valid": True, "message": "Valid RUT"}
            else:
                return {"is_valid": False, "message": f"Invalid RUT check digit: {rut_str}"}
        except Exception as e:
            return {"is_valid": False, "message": f"RUT validation error: {e}"}

    def _validate_not_future_date(self, value: Any) -> Dict[str, Any]:
        """Validate date is not in future."""
        try:
            if isinstance(value, str):
                date_obj = datetime.strptime(value, "%Y-%m-%d").date()
            elif isinstance(value, datetime):
                date_obj = value.date()
            elif isinstance(value, date):
                date_obj = value
            else:
                return {"is_valid": False, "message": "Invalid date type for future check"}

            today = date.today()
            if date_obj > today:
                return {"is_valid": False, "message": f"Date cannot be in future: {date_obj}"}

            return {"is_valid": True, "message": "Date not in future"}

        except Exception as e:
            return {"is_valid": False, "message": f"Date validation error: {e}"}

    def validate_document_fields(self,
                                document_data: Dict[str, Any],
                                document_type: str = None) -> List[FieldValidationResult]:
        """Validate all fields in a document."""
        results = []

        # Get applicable field rules
        applicable_rules = self._get_applicable_rules(document_type)

        # Validate fields recursively
        for field_name, rule in applicable_rules.items():
            field_value = self._get_field_value_from_document(document_data, field_name)
            field_path = self._get_field_path(document_data, field_name)

            if field_path:  # Field exists in document
                result = self.validate_field(field_name, field_value, field_path, document_data)
                results.append(result)
            elif rule.is_required:
                # Required field is missing
                result = FieldValidationResult(
                    field_name=field_name,
                    field_path=field_name,
                    field_type=rule.field_type,
                    is_valid=False,
                    errors=[f"Required field '{field_name}' is missing from document"],
                    failed_constraints=["required"],
                    severity="critical",
                    reference=rule.legal_reference or rule.sii_reference
                )
                results.append(result)

        return results

    def _get_applicable_rules(self, document_type: str = None) -> Dict[str, FieldRule]:
        """Get field rules applicable to document type."""
        if not document_type:
            return self.field_rules

        applicable_rules = {}
        for field_name, rule in self.field_rules.items():
            if not rule.document_types or document_type in rule.document_types:
                applicable_rules[field_name] = rule

        return applicable_rules

    def _get_field_value_from_document(self, document_data: Dict[str, Any], field_name: str) -> Any:
        """Get field value from document data."""
        # Try common locations for fields
        locations = [
            f"Encabezado.IdDoc.{field_name}",
            f"Encabezado.Emisor.{field_name}",
            f"Encabezado.Receptor.{field_name}",
            f"Encabezado.{field_name}",
            f"Totales.{field_name}",
            field_name
        ]

        for location in locations:
            value = self._get_nested_value(document_data, location)
            if value is not None:
                return value

        return None

    def _get_field_path(self, document_data: Dict[str, Any], field_name: str) -> Optional[str]:
        """Get field path in document."""
        # Try common locations for fields
        locations = [
            f"Encabezado.IdDoc.{field_name}",
            f"Encabezado.Emisor.{field_name}",
            f"Encabezado.Receptor.{field_name}",
            f"Encabezado.{field_name}",
            f"Totales.{field_name}",
            field_name
        ]

        for location in locations:
            value = self._get_nested_value(document_data, location)
            if value is not None:
                return location

        return None

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value using dot notation."""
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

    def get_validation_summary(self, results: List[FieldValidationResult]) -> Dict[str, Any]:
        """Get field validation summary."""
        total_fields = len(results)
        valid_fields = sum(1 for r in results if r.is_valid)
        invalid_fields = total_fields - valid_fields

        # Count by severity
        severity_counts = {}
        severities = ["critical", "high", "medium", "low"]
        for severity in severities:
            severity_counts[severity] = sum(
                1 for r in results
                if not r.is_valid and r.severity == severity
            )

        # Count by field type
        type_counts = {}
        for field_type in FieldType:
            type_counts[field_type.value] = sum(
                1 for r in results if r.field_type == field_type
            )

        return {
            'total_fields': total_fields,
            'valid_fields': valid_fields,
            'invalid_fields': invalid_fields,
            'success_rate': (valid_fields / total_fields * 100) if total_fields > 0 else 100,
            'severity_breakdown': severity_counts,
            'field_type_breakdown': type_counts,
            'has_critical_errors': severity_counts.get('critical', 0) > 0,
            'has_high_errors': severity_counts.get('high', 0) > 0,
            'is_valid': invalid_fields == 0
        }


class SiiFieldValidator(FieldValidator):
    """
    SII-specific field validator.

    Extends base validator with Chilean SII-specific field rules.
    """

    def __init__(self, **kwargs):
        """Initialize SII field validator."""
        super().__init__(**kwargs)
        self._load_sii_field_rules()

    def _load_sii_field_rules(self):
        """Load SII-specific field validation rules."""

        # Comuna (municipality) codes
        self.add_field_rule(FieldRule(
            field_name="CmnaOrigen",
            field_type=FieldType.STRING,
            description="Origin municipality code",
            is_required=False,
            constraints=[
                FieldConstraint(
                    constraint_id="comuna_code_format",
                    constraint_type="format",
                    description="Valid municipality code format",
                    pattern=r"^[A-Z\s]{1,20}$",
                    severity="medium"
                )
            ],
            sii_field_code="CmnaOrigen",
            sii_reference="Tabla de Comunas SII"
        ))

        # Business activity code (Giro)
        self.add_field_rule(FieldRule(
            field_name="GiroEmis",
            field_type=FieldType.STRING,
            description="Business activity description",
            is_required=False,
            constraints=[
                FieldConstraint(
                    constraint_id="giro_length",
                    constraint_type="length",
                    description="Maximum 80 characters",
                    max_length=80,
                    severity="medium"
                )
            ],
            sii_field_code="GiroEmis",
            sii_reference="Codificación SII Actividades Económicas"
        ))

        # Tax exemption indicator
        self.add_field_rule(FieldRule(
            field_name="IndExe",
            field_type=FieldType.INTEGER,
            description="Tax exemption indicator",
            is_conditional=True,
            condition_expression="TipoDTE == '34'",  # Factura Exenta
            constraints=[
                FieldConstraint(
                    constraint_id="exemption_codes",
                    constraint_type="enumeration",
                    description="Valid exemption codes",
                    allowed_values=["1", "2", "3", "4", "5", "6"],
                    severity="high"
                )
            ],
            document_types=["34"],
            sii_field_code="IndExe",
            sii_reference="Resolución SII N° 80"
        ))

        # Document sequence indicator
        self.add_field_rule(FieldRule(
            field_name="IndServicio",
            field_type=FieldType.INTEGER,
            description="Service indicator",
            is_required=False,
            constraints=[
                FieldConstraint(
                    constraint_id="service_indicators",
                    constraint_type="enumeration",
                    description="Valid service indicators",
                    allowed_values=["1", "2", "3", "4"],
                    severity="medium"
                )
            ],
            sii_field_code="IndServicio",
            sii_reference="Resolución SII N° 80"
        ))

    def validate_sii_document_fields(self,
                                   document_data: Dict[str, Any],
                                   document_type: str) -> List[FieldValidationResult]:
        """Validate document fields with SII-specific rules."""
        results = super().validate_document_fields(document_data, document_type)

        # Apply additional SII validations
        sii_results = self._validate_sii_specific_fields(document_data, document_type)
        results.extend(sii_results)

        return results

    def _validate_sii_specific_fields(self,
                                    document_data: Dict[str, Any],
                                    document_type: str) -> List[FieldValidationResult]:
        """Validate SII-specific field requirements."""
        results = []

        # Document type specific field requirements
        if document_type == "34":  # Factura Exenta
            # Must have exemption indicator
            ind_exe = self._get_field_value_from_document(document_data, "IndExe")
            if not ind_exe:
                results.append(FieldValidationResult(
                    field_name="IndExe",
                    field_path="Encabezado.IdDoc.IndExe",
                    field_type=FieldType.INTEGER,
                    is_valid=False,
                    errors=["Factura Exenta must have exemption indicator (IndExe)"],
                    failed_constraints=["required"],
                    severity="critical",
                    reference="Resolución SII N° 80"
                ))

        elif document_type == "52":  # Guía de Despacho
            # Must have transfer indicator
            ind_traslado = self._get_field_value_from_document(document_data, "IndTraslado")
            if not ind_traslado:
                results.append(FieldValidationResult(
                    field_name="IndTraslado",
                    field_path="Encabezado.IdDoc.IndTraslado",
                    field_type=FieldType.INTEGER,
                    is_valid=False,
                    errors=["Guía de Despacho must have transfer indicator (IndTraslado)"],
                    failed_constraints=["required"],
                    severity="critical",
                    reference="Resolución SII N° 80"
                ))

        return results