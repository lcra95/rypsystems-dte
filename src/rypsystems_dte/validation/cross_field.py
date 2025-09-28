"""
Cross-Field Validation System.

Provides comprehensive cross-field validation including:
- Inter-field dependency validation
- Consistency checks across document sections
- Conditional field requirements
- Data integrity validation
- Business logic consistency
"""

from typing import Dict, List, Optional, Any, Union, Callable, Tuple, Set
from enum import Enum
from decimal import Decimal
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, ConfigDict


class DependencyType(str, Enum):
    """Types of field dependencies."""
    REQUIRED = "required"  # Field B required when field A has value
    CONDITIONAL = "conditional"  # Field B required when field A meets condition
    MUTUALLY_EXCLUSIVE = "mutually_exclusive"  # Only one of the fields can have value
    DEPENDENT = "dependent"  # Field B depends on field A value
    CONSISTENCY = "consistency"  # Fields must be consistent
    CALCULATION = "calculation"  # Field B must be calculated from field A
    FORMAT = "format"  # Field B format depends on field A


class FieldDependency(BaseModel):
    """Field dependency definition."""

    # Dependency identification
    dependency_id: str = Field(..., description="Unique dependency identifier")
    name: str = Field(..., description="Dependency name")
    description: str = Field(..., description="Dependency description")

    # Dependency configuration
    dependency_type: DependencyType = Field(..., description="Type of dependency")
    source_field: str = Field(..., description="Source field path")
    target_field: str = Field(..., description="Target field path")

    # Conditions
    source_condition: Optional[str] = Field(None, description="Condition on source field")
    target_condition: Optional[str] = Field(None, description="Required condition on target field")

    # Validation function
    validation_function: Optional[Callable] = Field(None, description="Custom validation function")

    # Metadata
    document_types: List[str] = Field(default_factory=list, description="Applicable document types")
    severity: str = Field(default="high", description="Validation severity")
    reference: Optional[str] = Field(None, description="Legal or business reference")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class CrossFieldRule(BaseModel):
    """Cross-field validation rule."""

    # Rule identification
    rule_id: str = Field(..., description="Rule identifier")
    rule_name: str = Field(..., description="Rule name")
    rule_description: str = Field(..., description="Rule description")

    # Dependencies
    dependencies: List[FieldDependency] = Field(default_factory=list, description="Field dependencies")

    # Validation logic
    validation_expression: Optional[str] = Field(None, description="Validation expression")
    custom_validator: Optional[Callable] = Field(None, description="Custom validation function")

    # Configuration
    is_active: bool = Field(default=True, description="Whether rule is active")
    document_types: List[str] = Field(default_factory=list, description="Applicable document types")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class CrossFieldResult(BaseModel):
    """Cross-field validation result."""

    # Rule information
    rule_id: str = Field(..., description="Rule identifier")
    rule_name: str = Field(..., description="Rule name")
    dependency_id: Optional[str] = Field(None, description="Specific dependency ID")

    # Validation result
    is_valid: bool = Field(..., description="Validation result")
    severity: str = Field(..., description="Result severity")

    # Details
    message: str = Field(..., description="Validation message")
    source_field: str = Field(..., description="Source field path")
    target_field: str = Field(..., description="Target field path")
    source_value: Optional[str] = Field(None, description="Source field value")
    target_value: Optional[str] = Field(None, description="Target field value")

    # Context
    expected_condition: Optional[str] = Field(None, description="Expected condition")
    actual_condition: Optional[str] = Field(None, description="Actual condition")
    reference: Optional[str] = Field(None, description="Reference")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class CrossFieldValidator:
    """
    Cross-field validation engine.

    Provides comprehensive cross-field validation including:
    - Field dependency validation
    - Consistency checks
    - Conditional requirements
    - Business logic validation
    """

    def __init__(self,
                 document_type: Optional[str] = None,
                 custom_rules: Optional[List[CrossFieldRule]] = None):
        """
        Initialize cross-field validator.

        Args:
            document_type: Default document type for validation
            custom_rules: Additional custom rules
        """
        self.document_type = document_type
        self.rules: Dict[str, CrossFieldRule] = {}
        self.dependencies: Dict[str, FieldDependency] = {}

        # Load default rules
        self._load_default_rules()

        # Add custom rules
        if custom_rules:
            for rule in custom_rules:
                self.add_rule(rule)

    def _load_default_rules(self):
        """Load default cross-field validation rules."""

        # Emisor-Receptor consistency
        self.add_rule(CrossFieldRule(
            rule_id="emisor_receptor_different",
            rule_name="Emisor and Receptor Must Be Different",
            rule_description="Emisor and Receptor RUT must be different",
            dependencies=[
                FieldDependency(
                    dependency_id="emisor_receptor_rut",
                    name="Emisor Receptor RUT Different",
                    description="Emisor RUT must be different from Receptor RUT",
                    dependency_type=DependencyType.CONSISTENCY,
                    source_field="Emisor.RUTEmisor",
                    target_field="Receptor.RUTRecep",
                    severity="high"
                )
            ]
        ))

        # Date consistency
        self.add_rule(CrossFieldRule(
            rule_id="fecha_vencimiento_after_emision",
            rule_name="Due Date After Emission Date",
            rule_description="Due date must be after or equal to emission date",
            dependencies=[
                FieldDependency(
                    dependency_id="fecha_venc_emis",
                    name="Vencimiento After Emisión",
                    description="FchVenc must be >= FchEmis",
                    dependency_type=DependencyType.CONSISTENCY,
                    source_field="FchEmis",
                    target_field="FchVenc",
                    severity="medium"
                )
            ]
        ))

        # Total calculations
        self.add_rule(CrossFieldRule(
            rule_id="total_calculation_consistency",
            rule_name="Total Calculation Consistency",
            rule_description="Total amount must equal sum of components",
            dependencies=[
                FieldDependency(
                    dependency_id="total_components",
                    name="Total Components Consistency",
                    description="MntTotal = MntNeto + IVA + other taxes",
                    dependency_type=DependencyType.CALCULATION,
                    source_field="Totales.MntNeto",
                    target_field="Totales.MntTotal",
                    severity="critical"
                )
            ]
        ))

        # Document reference consistency
        self.add_rule(CrossFieldRule(
            rule_id="document_reference_consistency",
            rule_name="Document Reference Consistency",
            rule_description="Referenced document must have consistent data",
            dependencies=[
                FieldDependency(
                    dependency_id="ref_doc_type_folio",
                    name="Reference Document Type and Folio",
                    description="Referenced document type and folio must be consistent",
                    dependency_type=DependencyType.CONSISTENCY,
                    source_field="Referencia.TpoDocRef",
                    target_field="Referencia.FolioRef",
                    severity="high"
                )
            ]
        ))

    def add_rule(self, rule: CrossFieldRule):
        """Add a cross-field validation rule."""
        self.rules[rule.rule_id] = rule

        # Add dependencies
        for dependency in rule.dependencies:
            self.dependencies[dependency.dependency_id] = dependency

    def remove_rule(self, rule_id: str):
        """Remove a cross-field validation rule."""
        if rule_id in self.rules:
            rule = self.rules[rule_id]
            # Remove dependencies
            for dependency in rule.dependencies:
                if dependency.dependency_id in self.dependencies:
                    del self.dependencies[dependency.dependency_id]
            del self.rules[rule_id]

    def validate_document(self,
                         document_data: Dict[str, Any],
                         document_type: Optional[str] = None) -> List[CrossFieldResult]:
        """Validate entire document for cross-field consistency."""
        doc_type = document_type or self.document_type
        results = []

        # Get applicable rules
        applicable_rules = self._get_applicable_rules(doc_type)

        for rule in applicable_rules:
            if not rule.is_active:
                continue

            rule_results = self._validate_rule(rule, document_data, doc_type)
            results.extend(rule_results)

        return results

    def validate_dependency(self,
                          dependency: FieldDependency,
                          document_data: Dict[str, Any]) -> Optional[CrossFieldResult]:
        """Validate a specific field dependency."""
        source_value = self._get_field_value(document_data, dependency.source_field)
        target_value = self._get_field_value(document_data, dependency.target_field)

        # Apply dependency validation based on type
        if dependency.dependency_type == DependencyType.REQUIRED:
            return self._validate_required_dependency(dependency, source_value, target_value)
        elif dependency.dependency_type == DependencyType.CONDITIONAL:
            return self._validate_conditional_dependency(dependency, source_value, target_value)
        elif dependency.dependency_type == DependencyType.MUTUALLY_EXCLUSIVE:
            return self._validate_mutually_exclusive_dependency(dependency, source_value, target_value)
        elif dependency.dependency_type == DependencyType.CONSISTENCY:
            return self._validate_consistency_dependency(dependency, source_value, target_value)
        elif dependency.dependency_type == DependencyType.CALCULATION:
            return self._validate_calculation_dependency(dependency, document_data)
        elif dependency.validation_function:
            return self._validate_custom_dependency(dependency, source_value, target_value, document_data)

        return None

    def _get_applicable_rules(self, document_type: Optional[str]) -> List[CrossFieldRule]:
        """Get rules applicable to document type."""
        applicable_rules = []

        for rule in self.rules.values():
            if not rule.document_types or not document_type:
                applicable_rules.append(rule)
            elif document_type in rule.document_types:
                applicable_rules.append(rule)

        return applicable_rules

    def _validate_rule(self,
                      rule: CrossFieldRule,
                      document_data: Dict[str, Any],
                      document_type: Optional[str]) -> List[CrossFieldResult]:
        """Validate a specific cross-field rule."""
        results = []

        for dependency in rule.dependencies:
            # Check if dependency applies to document type
            if dependency.document_types and document_type:
                if document_type not in dependency.document_types:
                    continue

            result = self.validate_dependency(dependency, document_data)
            if result:
                # Set rule information
                result.rule_id = rule.rule_id
                result.rule_name = rule.rule_name
                results.append(result)

        return results

    def _validate_required_dependency(self,
                                    dependency: FieldDependency,
                                    source_value: Any,
                                    target_value: Any) -> Optional[CrossFieldResult]:
        """Validate required field dependency."""
        # If source has value, target is required
        if source_value is not None and source_value != "":
            if target_value is None or target_value == "":
                return CrossFieldResult(
                    rule_id="",
                    rule_name="",
                    dependency_id=dependency.dependency_id,
                    is_valid=False,
                    severity=dependency.severity,
                    message=f"Field '{dependency.target_field}' is required when '{dependency.source_field}' has value",
                    source_field=dependency.source_field,
                    target_field=dependency.target_field,
                    source_value=str(source_value),
                    target_value=str(target_value) if target_value is not None else None,
                    reference=dependency.reference
                )
        return None

    def _validate_conditional_dependency(self,
                                       dependency: FieldDependency,
                                       source_value: Any,
                                       target_value: Any) -> Optional[CrossFieldResult]:
        """Validate conditional field dependency."""
        # Check if source condition is met
        if dependency.source_condition:
            condition_met = self._evaluate_condition(source_value, dependency.source_condition)
            if condition_met:
                if dependency.target_condition:
                    target_meets_condition = self._evaluate_condition(target_value, dependency.target_condition)
                    if not target_meets_condition:
                        return CrossFieldResult(
                            rule_id="",
                            rule_name="",
                            dependency_id=dependency.dependency_id,
                            is_valid=False,
                            severity=dependency.severity,
                            message=f"Field '{dependency.target_field}' must meet condition '{dependency.target_condition}' when '{dependency.source_field}' meets '{dependency.source_condition}'",
                            source_field=dependency.source_field,
                            target_field=dependency.target_field,
                            source_value=str(source_value),
                            target_value=str(target_value) if target_value is not None else None,
                            expected_condition=dependency.target_condition,
                            reference=dependency.reference
                        )
                elif target_value is None or target_value == "":
                    return CrossFieldResult(
                        rule_id="",
                        rule_name="",
                        dependency_id=dependency.dependency_id,
                        is_valid=False,
                        severity=dependency.severity,
                        message=f"Field '{dependency.target_field}' is required when '{dependency.source_field}' meets condition '{dependency.source_condition}'",
                        source_field=dependency.source_field,
                        target_field=dependency.target_field,
                        source_value=str(source_value),
                        target_value=str(target_value) if target_value is not None else None,
                        expected_condition="not empty",
                        reference=dependency.reference
                    )
        return None

    def _validate_mutually_exclusive_dependency(self,
                                              dependency: FieldDependency,
                                              source_value: Any,
                                              target_value: Any) -> Optional[CrossFieldResult]:
        """Validate mutually exclusive fields."""
        source_has_value = source_value is not None and source_value != ""
        target_has_value = target_value is not None and target_value != ""

        if source_has_value and target_has_value:
            return CrossFieldResult(
                rule_id="",
                rule_name="",
                dependency_id=dependency.dependency_id,
                is_valid=False,
                severity=dependency.severity,
                message=f"Fields '{dependency.source_field}' and '{dependency.target_field}' are mutually exclusive",
                source_field=dependency.source_field,
                target_field=dependency.target_field,
                source_value=str(source_value),
                target_value=str(target_value),
                reference=dependency.reference
            )
        return None

    def _validate_consistency_dependency(self,
                                       dependency: FieldDependency,
                                       source_value: Any,
                                       target_value: Any) -> Optional[CrossFieldResult]:
        """Validate field consistency."""
        # Apply specific consistency checks based on dependency
        if dependency.dependency_id == "emisor_receptor_rut":
            if source_value and target_value and str(source_value) == str(target_value):
                return CrossFieldResult(
                    rule_id="",
                    rule_name="",
                    dependency_id=dependency.dependency_id,
                    is_valid=False,
                    severity=dependency.severity,
                    message="Emisor and Receptor RUT must be different",
                    source_field=dependency.source_field,
                    target_field=dependency.target_field,
                    source_value=str(source_value),
                    target_value=str(target_value),
                    reference=dependency.reference
                )

        elif dependency.dependency_id == "fecha_venc_emis":
            if source_value and target_value:
                try:
                    # Parse dates
                    if isinstance(source_value, str):
                        source_date = datetime.strptime(source_value, "%Y-%m-%d").date()
                    else:
                        source_date = source_value

                    if isinstance(target_value, str):
                        target_date = datetime.strptime(target_value, "%Y-%m-%d").date()
                    else:
                        target_date = target_value

                    if target_date < source_date:
                        return CrossFieldResult(
                            rule_id="",
                            rule_name="",
                            dependency_id=dependency.dependency_id,
                            is_valid=False,
                            severity=dependency.severity,
                            message="Due date must be after or equal to emission date",
                            source_field=dependency.source_field,
                            target_field=dependency.target_field,
                            source_value=str(source_value),
                            target_value=str(target_value),
                            reference=dependency.reference
                        )
                except (ValueError, TypeError):
                    return CrossFieldResult(
                        rule_id="",
                        rule_name="",
                        dependency_id=dependency.dependency_id,
                        is_valid=False,
                        severity=dependency.severity,
                        message="Invalid date format for date comparison",
                        source_field=dependency.source_field,
                        target_field=dependency.target_field,
                        source_value=str(source_value),
                        target_value=str(target_value),
                        reference=dependency.reference
                    )

        return None

    def _validate_calculation_dependency(self,
                                       dependency: FieldDependency,
                                       document_data: Dict[str, Any]) -> Optional[CrossFieldResult]:
        """Validate calculation dependencies."""
        if dependency.dependency_id == "total_components":
            try:
                totales = document_data.get('Totales', {})
                mnt_neto = Decimal(str(totales.get('MntNeto', 0)))
                iva = Decimal(str(totales.get('IVA', 0)))
                mnt_total = Decimal(str(totales.get('MntTotal', 0)))

                # Calculate expected total
                expected_total = mnt_neto + iva

                # Add other taxes if present
                imp_especificos = totales.get('ImptoReten', [])
                if isinstance(imp_especificos, list):
                    for impuesto in imp_especificos:
                        if isinstance(impuesto, dict):
                            monto = Decimal(str(impuesto.get('MontoImp', 0)))
                            expected_total += monto

                # Check if totals match (allow 1 peso tolerance for rounding)
                if abs(expected_total - mnt_total) > 1:
                    return CrossFieldResult(
                        rule_id="",
                        rule_name="",
                        dependency_id=dependency.dependency_id,
                        is_valid=False,
                        severity=dependency.severity,
                        message=f"Total calculation inconsistency. Expected: {expected_total}, Actual: {mnt_total}",
                        source_field="Totales.MntNeto",
                        target_field="Totales.MntTotal",
                        source_value=str(mnt_neto),
                        target_value=str(mnt_total),
                        expected_condition=str(expected_total),
                        reference=dependency.reference
                    )

            except (ValueError, TypeError, KeyError) as e:
                return CrossFieldResult(
                    rule_id="",
                    rule_name="",
                    dependency_id=dependency.dependency_id,
                    is_valid=False,
                    severity=dependency.severity,
                    message=f"Error validating total calculation: {e}",
                    source_field=dependency.source_field,
                    target_field=dependency.target_field,
                    reference=dependency.reference
                )

        return None

    def _validate_custom_dependency(self,
                                  dependency: FieldDependency,
                                  source_value: Any,
                                  target_value: Any,
                                  document_data: Dict[str, Any]) -> Optional[CrossFieldResult]:
        """Validate custom dependency using provided function."""
        try:
            if dependency.validation_function:
                is_valid, message = dependency.validation_function(
                    source_value, target_value, document_data
                )

                if not is_valid:
                    return CrossFieldResult(
                        rule_id="",
                        rule_name="",
                        dependency_id=dependency.dependency_id,
                        is_valid=False,
                        severity=dependency.severity,
                        message=message,
                        source_field=dependency.source_field,
                        target_field=dependency.target_field,
                        source_value=str(source_value) if source_value is not None else None,
                        target_value=str(target_value) if target_value is not None else None,
                        reference=dependency.reference
                    )
        except Exception as e:
            return CrossFieldResult(
                rule_id="",
                rule_name="",
                dependency_id=dependency.dependency_id,
                is_valid=False,
                severity="critical",
                message=f"Custom validation error: {e}",
                source_field=dependency.source_field,
                target_field=dependency.target_field,
                reference=dependency.reference
            )

        return None

    def _evaluate_condition(self, value: Any, condition: str) -> bool:
        """Evaluate a condition against a value."""
        try:
            if condition == "not_empty":
                return value is not None and value != ""
            elif condition == "empty":
                return value is None or value == ""
            elif condition.startswith("equals:"):
                expected = condition.split(":", 1)[1]
                return str(value) == expected
            elif condition.startswith("not_equals:"):
                expected = condition.split(":", 1)[1]
                return str(value) != expected
            elif condition.startswith("greater_than:"):
                threshold = float(condition.split(":", 1)[1])
                return float(value) > threshold
            elif condition.startswith("less_than:"):
                threshold = float(condition.split(":", 1)[1])
                return float(value) < threshold
            else:
                # Default: check if value exists
                return value is not None and value != ""
        except (ValueError, TypeError):
            return False

    def _get_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get field value using dot notation path."""
        keys = field_path.split('.')
        value = data

        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    index = int(key)
                    value = value[index] if 0 <= index < len(value) else None
                else:
                    return None
            return value
        except (KeyError, TypeError, IndexError):
            return None

    def get_validation_summary(self, results: List[CrossFieldResult]) -> Dict[str, Any]:
        """Get cross-field validation summary."""
        total_validations = len(results)
        passed = sum(1 for r in results if r.is_valid)
        failed = total_validations - passed

        severity_counts = {}
        severities = ["critical", "high", "medium", "low", "info"]
        for severity in severities:
            severity_counts[severity] = sum(
                1 for r in results
                if not r.is_valid and r.severity == severity
            )

        return {
            'total_validations': total_validations,
            'passed': passed,
            'failed': failed,
            'success_rate': (passed / total_validations * 100) if total_validations > 0 else 100,
            'has_critical_errors': severity_counts.get('critical', 0) > 0,
            'has_high_errors': severity_counts.get('high', 0) > 0,
            'severity_breakdown': severity_counts,
            'is_valid': failed == 0 or all(
                r.severity in ["low", "info"]
                for r in results if not r.is_valid
            ),
            'validation_details': [
                {
                    'dependency_id': r.dependency_id,
                    'is_valid': r.is_valid,
                    'severity': r.severity,
                    'message': r.message,
                    'source_field': r.source_field,
                    'target_field': r.target_field
                }
                for r in results
            ]
        }


class SiiCrossFieldValidator(CrossFieldValidator):
    """
    SII-specific cross-field validator.

    Extends base validator with Chilean SII-specific cross-field rules.
    """

    def __init__(self, **kwargs):
        """Initialize SII cross-field validator."""
        super().__init__(**kwargs)
        self._load_sii_rules()

    def _load_sii_rules(self):
        """Load SII-specific cross-field validation rules."""

        # Folio authorization range
        self.add_rule(CrossFieldRule(
            rule_id="folio_authorization_range",
            rule_name="Folio Within Authorization Range",
            rule_description="Document folio must be within authorized range",
            document_types=["33", "34", "39", "41", "43", "46", "52", "56", "61"],
            dependencies=[
                FieldDependency(
                    dependency_id="folio_range_check",
                    name="Folio Range Validation",
                    description="Folio must be within CAF authorized range",
                    dependency_type=DependencyType.CONDITIONAL,
                    source_field="Folio",
                    target_field="CAF.Range",
                    severity="critical",
                    reference="Resolución SII N° 80"
                )
            ]
        ))

        # Document type and content consistency
        self.add_rule(CrossFieldRule(
            rule_id="document_type_content_consistency",
            rule_name="Document Type and Content Consistency",
            rule_description="Document content must match document type requirements",
            dependencies=[
                FieldDependency(
                    dependency_id="factura_iva_consistency",
                    name="Factura IVA Consistency",
                    description="Factura Electrónica must have IVA, Factura Exenta must not",
                    dependency_type=DependencyType.CONDITIONAL,
                    source_field="TipoDTE",
                    target_field="Totales.IVA",
                    severity="critical",
                    reference="Resolución SII N° 80"
                )
            ]
        ))

        # Reference document consistency
        self.add_rule(CrossFieldRule(
            rule_id="reference_document_consistency",
            rule_name="Reference Document Consistency",
            rule_description="Referenced document data must be consistent",
            document_types=["61", "56"],  # Credit notes, debit notes
            dependencies=[
                FieldDependency(
                    dependency_id="ref_emisor_consistency",
                    name="Reference Emisor Consistency",
                    description="Referenced document emisor must match current receptor",
                    dependency_type=DependencyType.CONSISTENCY,
                    source_field="Receptor.RUTRecep",
                    target_field="Referencia.RUTOtro",
                    severity="high",
                    reference="Resolución SII N° 80"
                )
            ]
        ))

    def validate_sii_document(self,
                            document_data: Dict[str, Any],
                            document_type: str) -> List[CrossFieldResult]:
        """Validate SII document with specific rules."""
        results = super().validate_document(document_data, document_type)

        # Apply additional SII-specific validations
        sii_results = self._validate_sii_specific_cross_fields(document_data, document_type)
        results.extend(sii_results)

        return results

    def _validate_sii_specific_cross_fields(self,
                                          document_data: Dict[str, Any],
                                          document_type: str) -> List[CrossFieldResult]:
        """Apply SII-specific cross-field validations."""
        results = []

        # Document type specific validations
        if document_type == "33":  # Factura Electrónica
            results.extend(self._validate_factura_electronica_cross_fields(document_data))
        elif document_type == "34":  # Factura Exenta
            results.extend(self._validate_factura_exenta_cross_fields(document_data))
        elif document_type in ["61", "56"]:  # Credit/Debit notes
            results.extend(self._validate_note_cross_fields(document_data))

        return results

    def _validate_factura_electronica_cross_fields(self, document_data: Dict[str, Any]) -> List[CrossFieldResult]:
        """Validate Factura Electrónica specific cross-field rules."""
        results = []

        # Factura Electrónica must have net amount and IVA consistency
        totales = document_data.get('Totales', {})
        mnt_neto = totales.get('MntNeto', 0)
        iva = totales.get('IVA', 0)

        if mnt_neto > 0 and iva == 0:
            results.append(CrossFieldResult(
                rule_id="document_type_content_consistency",
                rule_name="Document Type and Content Consistency",
                dependency_id="factura_iva_consistency",
                is_valid=False,
                severity="critical",
                message="Factura Electrónica with net amount must include IVA",
                source_field="TipoDTE",
                target_field="Totales.IVA",
                source_value="33",
                target_value=str(iva),
                expected_condition="IVA > 0 when MntNeto > 0",
                reference="Resolución SII N° 80"
            ))

        return results

    def _validate_factura_exenta_cross_fields(self, document_data: Dict[str, Any]) -> List[CrossFieldResult]:
        """Validate Factura Exenta specific cross-field rules."""
        results = []

        # Factura Exenta must not have IVA
        totales = document_data.get('Totales', {})
        iva = totales.get('IVA', 0)

        if iva > 0:
            results.append(CrossFieldResult(
                rule_id="document_type_content_consistency",
                rule_name="Document Type and Content Consistency",
                dependency_id="factura_iva_consistency",
                is_valid=False,
                severity="critical",
                message="Factura Exenta must not include IVA",
                source_field="TipoDTE",
                target_field="Totales.IVA",
                source_value="34",
                target_value=str(iva),
                expected_condition="IVA = 0",
                reference="Resolución SII N° 80"
            ))

        return results

    def _validate_note_cross_fields(self, document_data: Dict[str, Any]) -> List[CrossFieldResult]:
        """Validate Credit/Debit note specific cross-field rules."""
        results = []

        # Notes must have reference to original document
        referencias = document_data.get('Referencia', [])
        if not referencias:
            results.append(CrossFieldResult(
                rule_id="reference_document_consistency",
                rule_name="Reference Document Consistency",
                dependency_id="ref_document_required",
                is_valid=False,
                severity="critical",
                message="Credit/Debit notes must reference original document",
                source_field="TipoDTE",
                target_field="Referencia",
                source_value=document_data.get('Encabezado', {}).get('IdDoc', {}).get('TipoDTE'),
                target_value="missing",
                expected_condition="Referencia required",
                reference="Resolución SII N° 80"
            ))

        return results