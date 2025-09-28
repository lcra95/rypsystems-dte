"""
Document Type Specific Validation Rules.

Provides document type specific validation including:
- Document structure validation per type
- Required fields per document type
- Document type specific business rules
- Format validation per document type
- SII compliance per document type
"""

from typing import Dict, List, Optional, Any, Set, Callable, Union
from enum import Enum
from decimal import Decimal
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, ConfigDict


class DocumentRule(BaseModel):
    """Document type specific rule."""

    # Rule identification
    rule_id: str = Field(..., description="Rule identifier")
    rule_name: str = Field(..., description="Rule name")
    rule_description: str = Field(..., description="Rule description")

    # Rule configuration
    document_types: List[str] = Field(..., description="Applicable document types")
    rule_type: str = Field(..., description="Rule type (structure, field, business)")
    severity: str = Field(default="high", description="Rule severity")

    # Field requirements
    required_fields: List[str] = Field(default_factory=list, description="Required field paths")
    optional_fields: List[str] = Field(default_factory=list, description="Optional field paths")
    prohibited_fields: List[str] = Field(default_factory=list, description="Prohibited field paths")

    # Validation logic
    validation_function: Optional[Callable] = Field(None, description="Custom validation function")
    condition_expression: Optional[str] = Field(None, description="Condition expression")

    # References
    legal_reference: Optional[str] = Field(None, description="Legal reference")
    sii_reference: Optional[str] = Field(None, description="SII reference")

    # Configuration
    is_active: bool = Field(default=True, description="Whether rule is active")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Rule parameters")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class DocumentTypeRule(BaseModel):
    """Complete document type validation rule set."""

    # Document type information
    document_type: str = Field(..., description="Document type code")
    document_name: str = Field(..., description="Document type name")
    description: str = Field(..., description="Document type description")

    # Structure requirements
    required_sections: List[str] = Field(default_factory=list, description="Required document sections")
    optional_sections: List[str] = Field(default_factory=list, description="Optional document sections")

    # Field requirements
    mandatory_fields: Dict[str, List[str]] = Field(default_factory=dict, description="Mandatory fields per section")
    conditional_fields: Dict[str, List[str]] = Field(default_factory=dict, description="Conditional fields per section")

    # Business rules
    business_rules: List[DocumentRule] = Field(default_factory=list, description="Document specific business rules")

    # Validation configuration
    strict_validation: bool = Field(default=True, description="Whether to use strict validation")
    allow_extensions: bool = Field(default=False, description="Whether to allow field extensions")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class DocumentContext(BaseModel):
    """Document validation context."""

    # Document information
    document_type: str = Field(..., description="Document type code")
    document_data: Dict[str, Any] = Field(..., description="Document data")

    # Validation settings
    strict_mode: bool = Field(default=True, description="Strict validation mode")
    validate_structure: bool = Field(default=True, description="Validate document structure")
    validate_fields: bool = Field(default=True, description="Validate field requirements")
    validate_business_rules: bool = Field(default=True, description="Validate business rules")

    # Environment
    ambiente: str = Field(default="produccion", description="SII environment")
    fecha_validacion: date = Field(default_factory=date.today, description="Validation date")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class DocumentRuleResult(BaseModel):
    """Document rule validation result."""

    # Rule information
    rule_id: str = Field(..., description="Rule identifier")
    rule_name: str = Field(..., description="Rule name")
    rule_type: str = Field(..., description="Rule type")

    # Validation result
    is_valid: bool = Field(..., description="Validation result")
    severity: str = Field(..., description="Result severity")

    # Details
    message: str = Field(..., description="Validation message")
    section: Optional[str] = Field(None, description="Document section")
    field_path: Optional[str] = Field(None, description="Field path")

    # Values
    expected_value: Optional[str] = Field(None, description="Expected value")
    actual_value: Optional[str] = Field(None, description="Actual value")

    # Context
    document_type: str = Field(..., description="Document type")
    reference: Optional[str] = Field(None, description="Reference")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class DocumentRuleValidator:
    """
    Document type specific validation engine.

    Provides comprehensive document type validation including:
    - Document structure validation
    - Required field validation
    - Document type specific business rules
    - SII compliance per document type
    """

    def __init__(self,
                 strict_mode: bool = True,
                 custom_rules: Optional[List[DocumentTypeRule]] = None):
        """
        Initialize document rule validator.

        Args:
            strict_mode: Whether to use strict validation
            custom_rules: Additional custom document type rules
        """
        self.strict_mode = strict_mode
        self.document_types: Dict[str, DocumentTypeRule] = {}

        # Load default document type rules
        self._load_default_document_types()

        # Add custom rules
        if custom_rules:
            for rule in custom_rules:
                self.add_document_type(rule)

    def _load_default_document_types(self):
        """Load default document type validation rules."""

        # Factura Electrónica (33)
        self.add_document_type(DocumentTypeRule(
            document_type="33",
            document_name="Factura Electrónica",
            description="Electronic invoice with VAT",
            required_sections=["Encabezado", "Detalle", "Totales"],
            optional_sections=["Referencia", "Descuentos", "DsctoGlobal"],
            mandatory_fields={
                "Encabezado": [
                    "IdDoc.TipoDTE",
                    "IdDoc.Folio",
                    "IdDoc.FchEmis",
                    "Emisor.RUTEmisor",
                    "Emisor.RznSoc",
                    "Receptor.RUTRecep",
                    "Receptor.RznSocRecep"
                ],
                "Detalle": [
                    "NroLinDet",
                    "NmbItem",
                    "QtyItem",
                    "PrcItem"
                ],
                "Totales": [
                    "MntNeto",
                    "IVA",
                    "MntTotal"
                ]
            },
            conditional_fields={
                "Encabezado": [
                    "IdDoc.FchVenc",  # Required if payment terms specified
                    "Receptor.DirRecep",  # Required for certain transactions
                    "Receptor.CmnaRecep"
                ]
            }
        ))

        # Factura Exenta (34)
        self.add_document_type(DocumentTypeRule(
            document_type="34",
            document_name="Factura Exenta",
            description="Tax-exempt invoice",
            required_sections=["Encabezado", "Detalle", "Totales"],
            optional_sections=["Referencia", "Descuentos"],
            mandatory_fields={
                "Encabezado": [
                    "IdDoc.TipoDTE",
                    "IdDoc.Folio",
                    "IdDoc.FchEmis",
                    "IdDoc.IndExe",  # Exemption indicator
                    "Emisor.RUTEmisor",
                    "Emisor.RznSoc",
                    "Receptor.RUTRecep",
                    "Receptor.RznSocRecep"
                ],
                "Detalle": [
                    "NroLinDet",
                    "NmbItem",
                    "QtyItem",
                    "PrcItem"
                ],
                "Totales": [
                    "MntExe",  # Exempt amount instead of MntNeto
                    "MntTotal"
                ]
            }
        ))

        # Nota de Crédito (61)
        self.add_document_type(DocumentTypeRule(
            document_type="61",
            document_name="Nota de Crédito Electrónica",
            description="Electronic credit note",
            required_sections=["Encabezado", "Detalle", "Totales", "Referencia"],
            mandatory_fields={
                "Encabezado": [
                    "IdDoc.TipoDTE",
                    "IdDoc.Folio",
                    "IdDoc.FchEmis",
                    "Emisor.RUTEmisor",
                    "Emisor.RznSoc",
                    "Receptor.RUTRecep",
                    "Receptor.RznSocRecep"
                ],
                "Referencia": [
                    "TpoDocRef",
                    "FolioRef",
                    "CodRef",
                    "RazonRef"
                ],
                "Detalle": [
                    "NroLinDet",
                    "NmbItem",
                    "QtyItem",
                    "PrcItem"
                ],
                "Totales": [
                    "MntTotal"
                ]
            }
        ))

        # Boleta Electrónica (39)
        self.add_document_type(DocumentTypeRule(
            document_type="39",
            document_name="Boleta Electrónica",
            description="Electronic receipt",
            required_sections=["Encabezado", "Detalle", "Totales"],
            optional_sections=["Descuentos"],
            mandatory_fields={
                "Encabezado": [
                    "IdDoc.TipoDTE",
                    "IdDoc.Folio",
                    "IdDoc.FchEmis",
                    "Emisor.RUTEmisor",
                    "Emisor.RznSoc"
                ],
                "Detalle": [
                    "NroLinDet",
                    "NmbItem",
                    "QtyItem",
                    "PrcItem"
                ],
                "Totales": [
                    "MntTotal"
                ]
            }
        ))

    def add_document_type(self, document_type_rule: DocumentTypeRule):
        """Add a document type validation rule."""
        self.document_types[document_type_rule.document_type] = document_type_rule

    def validate_document(self,
                         document_data: Dict[str, Any],
                         document_type: str) -> List[DocumentRuleResult]:
        """Validate document against type-specific rules."""
        results = []

        # Get document type rule
        if document_type not in self.document_types:
            results.append(DocumentRuleResult(
                rule_id="unknown_document_type",
                rule_name="Unknown Document Type",
                rule_type="structure",
                is_valid=False,
                severity="critical",
                message=f"Unknown document type: {document_type}",
                document_type=document_type
            ))
            return results

        doc_rule = self.document_types[document_type]

        # Validate document structure
        structure_results = self._validate_document_structure(document_data, doc_rule)
        results.extend(structure_results)

        # Validate required fields
        field_results = self._validate_required_fields(document_data, doc_rule)
        results.extend(field_results)

        # Validate business rules
        business_results = self._validate_business_rules(document_data, doc_rule)
        results.extend(business_results)

        return results

    def _validate_document_structure(self,
                                   document_data: Dict[str, Any],
                                   doc_rule: DocumentTypeRule) -> List[DocumentRuleResult]:
        """Validate document structure."""
        results = []

        # Check required sections
        for section in doc_rule.required_sections:
            if section not in document_data:
                results.append(DocumentRuleResult(
                    rule_id=f"required_section_{section.lower()}",
                    rule_name=f"Required Section {section}",
                    rule_type="structure",
                    is_valid=False,
                    severity="critical",
                    message=f"Required section '{section}' is missing",
                    section=section,
                    document_type=doc_rule.document_type,
                    reference="Resolución SII N° 80"
                ))

        # Check for unknown sections in strict mode
        if self.strict_mode and not doc_rule.allow_extensions:
            allowed_sections = set(doc_rule.required_sections + doc_rule.optional_sections)
            for section in document_data.keys():
                if section not in allowed_sections:
                    results.append(DocumentRuleResult(
                        rule_id=f"unknown_section_{section.lower()}",
                        rule_name=f"Unknown Section {section}",
                        rule_type="structure",
                        is_valid=False,
                        severity="medium",
                        message=f"Unknown section '{section}' in document",
                        section=section,
                        document_type=doc_rule.document_type
                    ))

        return results

    def _validate_required_fields(self,
                                 document_data: Dict[str, Any],
                                 doc_rule: DocumentTypeRule) -> List[DocumentRuleResult]:
        """Validate required fields per section."""
        results = []

        for section, required_fields in doc_rule.mandatory_fields.items():
            if section not in document_data:
                continue  # Section validation handled separately

            section_data = document_data[section]

            for field_path in required_fields:
                field_value = self._get_nested_field_value(section_data, field_path)

                if field_value is None or field_value == "":
                    results.append(DocumentRuleResult(
                        rule_id=f"required_field_{field_path.lower().replace('.', '_')}",
                        rule_name=f"Required Field {field_path}",
                        rule_type="field",
                        is_valid=False,
                        severity="high",
                        message=f"Required field '{field_path}' is missing in section '{section}'",
                        section=section,
                        field_path=f"{section}.{field_path}",
                        document_type=doc_rule.document_type,
                        reference="Resolución SII N° 80"
                    ))

        return results

    def _validate_business_rules(self,
                               document_data: Dict[str, Any],
                               doc_rule: DocumentTypeRule) -> List[DocumentRuleResult]:
        """Validate document type specific business rules."""
        results = []

        # Apply document type specific validations
        if doc_rule.document_type == "33":  # Factura Electrónica
            results.extend(self._validate_factura_electronica_rules(document_data))
        elif doc_rule.document_type == "34":  # Factura Exenta
            results.extend(self._validate_factura_exenta_rules(document_data))
        elif doc_rule.document_type == "61":  # Nota de Crédito
            results.extend(self._validate_nota_credito_rules(document_data))
        elif doc_rule.document_type == "39":  # Boleta
            results.extend(self._validate_boleta_rules(document_data))

        # Apply custom business rules
        for rule in doc_rule.business_rules:
            if rule.is_active:
                rule_results = self._apply_document_rule(rule, document_data)
                results.extend(rule_results)

        return results

    def _validate_factura_electronica_rules(self, document_data: Dict[str, Any]) -> List[DocumentRuleResult]:
        """Validate Factura Electrónica specific rules."""
        results = []

        # Must have IVA
        totales = document_data.get('Totales', {})
        mnt_neto = totales.get('MntNeto', 0)
        iva = totales.get('IVA', 0)

        if mnt_neto > 0 and iva == 0:
            results.append(DocumentRuleResult(
                rule_id="factura_electronica_iva_required",
                rule_name="Factura Electrónica IVA Required",
                rule_type="business",
                is_valid=False,
                severity="critical",
                message="Factura Electrónica with net amount must include IVA",
                section="Totales",
                field_path="Totales.IVA",
                expected_value="> 0",
                actual_value=str(iva),
                document_type="33",
                reference="Resolución SII N° 80"
            ))

        # Validate IVA calculation
        if mnt_neto > 0 and iva > 0:
            expected_iva = round(Decimal(str(mnt_neto)) * Decimal('0.19'))
            if abs(Decimal(str(iva)) - expected_iva) > 1:  # 1 peso tolerance
                results.append(DocumentRuleResult(
                    rule_id="factura_electronica_iva_calculation",
                    rule_name="Factura Electrónica IVA Calculation",
                    rule_type="business",
                    is_valid=False,
                    severity="high",
                    message=f"IVA calculation incorrect. Expected: {expected_iva}, Got: {iva}",
                    section="Totales",
                    field_path="Totales.IVA",
                    expected_value=str(expected_iva),
                    actual_value=str(iva),
                    document_type="33",
                    reference="Ley del IVA Art. 14"
                ))

        return results

    def _validate_factura_exenta_rules(self, document_data: Dict[str, Any]) -> List[DocumentRuleResult]:
        """Validate Factura Exenta specific rules."""
        results = []

        # Must have exemption indicator
        encabezado = document_data.get('Encabezado', {})
        id_doc = encabezado.get('IdDoc', {})
        ind_exe = id_doc.get('IndExe')

        if not ind_exe:
            results.append(DocumentRuleResult(
                rule_id="factura_exenta_indicator_required",
                rule_name="Factura Exenta Indicator Required",
                rule_type="business",
                is_valid=False,
                severity="critical",
                message="Factura Exenta must have exemption indicator (IndExe)",
                section="Encabezado",
                field_path="Encabezado.IdDoc.IndExe",
                document_type="34",
                reference="Resolución SII N° 80"
            ))

        # Must not have IVA
        totales = document_data.get('Totales', {})
        iva = totales.get('IVA', 0)

        if iva > 0:
            results.append(DocumentRuleResult(
                rule_id="factura_exenta_no_iva",
                rule_name="Factura Exenta No IVA",
                rule_type="business",
                is_valid=False,
                severity="critical",
                message="Factura Exenta must not include IVA",
                section="Totales",
                field_path="Totales.IVA",
                expected_value="0",
                actual_value=str(iva),
                document_type="34",
                reference="Resolución SII N° 80"
            ))

        return results

    def _validate_nota_credito_rules(self, document_data: Dict[str, Any]) -> List[DocumentRuleResult]:
        """Validate Nota de Crédito specific rules."""
        results = []

        # Must have reference to original document
        referencias = document_data.get('Referencia', [])
        if not referencias:
            results.append(DocumentRuleResult(
                rule_id="nota_credito_reference_required",
                rule_name="Nota Crédito Reference Required",
                rule_type="business",
                is_valid=False,
                severity="critical",
                message="Nota de Crédito must reference original document",
                section="Referencia",
                field_path="Referencia",
                document_type="61",
                reference="Resolución SII N° 80"
            ))
        else:
            # Validate reference structure
            if isinstance(referencias, list) and len(referencias) > 0:
                ref = referencias[0]
                required_ref_fields = ['TpoDocRef', 'FolioRef', 'CodRef']
                for field in required_ref_fields:
                    if field not in ref or not ref[field]:
                        results.append(DocumentRuleResult(
                            rule_id=f"nota_credito_reference_{field.lower()}",
                            rule_name=f"Nota Crédito Reference {field}",
                            rule_type="business",
                            is_valid=False,
                            severity="high",
                            message=f"Reference field '{field}' is required in Nota de Crédito",
                            section="Referencia",
                            field_path=f"Referencia.{field}",
                            document_type="61",
                            reference="Resolución SII N° 80"
                        ))

        return results

    def _validate_boleta_rules(self, document_data: Dict[str, Any]) -> List[DocumentRuleResult]:
        """Validate Boleta specific rules."""
        results = []

        # Boleta does not require receptor details (optional)
        # But if present, must be valid
        encabezado = document_data.get('Encabezado', {})
        receptor = encabezado.get('Receptor', {})

        if receptor:
            rut_recep = receptor.get('RUTRecep')
            if rut_recep and rut_recep != "66666666-6":  # Generic consumer RUT
                rzn_soc = receptor.get('RznSocRecep')
                if not rzn_soc:
                    results.append(DocumentRuleResult(
                        rule_id="boleta_receptor_name_required",
                        rule_name="Boleta Receptor Name Required",
                        rule_type="business",
                        is_valid=False,
                        severity="medium",
                        message="Boleta with specific receptor RUT must include receptor name",
                        section="Encabezado",
                        field_path="Encabezado.Receptor.RznSocRecep",
                        document_type="39",
                        reference="Resolución SII N° 80"
                    ))

        return results

    def _apply_document_rule(self,
                           rule: DocumentRule,
                           document_data: Dict[str, Any]) -> List[DocumentRuleResult]:
        """Apply a custom document rule."""
        results = []

        try:
            if rule.validation_function:
                # Apply custom validation function
                is_valid, message = rule.validation_function(document_data)
                if not is_valid:
                    results.append(DocumentRuleResult(
                        rule_id=rule.rule_id,
                        rule_name=rule.rule_name,
                        rule_type=rule.rule_type,
                        is_valid=False,
                        severity=rule.severity,
                        message=message,
                        document_type=rule.document_types[0] if rule.document_types else "unknown",
                        reference=rule.legal_reference or rule.sii_reference
                    ))
            else:
                # Apply field-based validation
                for field_path in rule.required_fields:
                    value = self._get_nested_field_value(document_data, field_path)
                    if value is None or value == "":
                        results.append(DocumentRuleResult(
                            rule_id=rule.rule_id,
                            rule_name=rule.rule_name,
                            rule_type=rule.rule_type,
                            is_valid=False,
                            severity=rule.severity,
                            message=f"Required field '{field_path}' is missing",
                            field_path=field_path,
                            document_type=rule.document_types[0] if rule.document_types else "unknown",
                            reference=rule.legal_reference or rule.sii_reference
                        ))

                for field_path in rule.prohibited_fields:
                    value = self._get_nested_field_value(document_data, field_path)
                    if value is not None and value != "":
                        results.append(DocumentRuleResult(
                            rule_id=rule.rule_id,
                            rule_name=rule.rule_name,
                            rule_type=rule.rule_type,
                            is_valid=False,
                            severity=rule.severity,
                            message=f"Prohibited field '{field_path}' is present",
                            field_path=field_path,
                            actual_value=str(value),
                            document_type=rule.document_types[0] if rule.document_types else "unknown",
                            reference=rule.legal_reference or rule.sii_reference
                        ))

        except Exception as e:
            results.append(DocumentRuleResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                rule_type=rule.rule_type,
                is_valid=False,
                severity="critical",
                message=f"Rule evaluation error: {e}",
                document_type=rule.document_types[0] if rule.document_types else "unknown"
            ))

        return results

    def _get_nested_field_value(self, data: Union[Dict[str, Any], List[Any]], field_path: str) -> Any:
        """Get nested field value using dot notation."""
        if '.' not in field_path:
            if isinstance(data, dict):
                return data.get(field_path)
            elif isinstance(data, list):
                # For list data (like Detalle), check if any item has the field
                for item in data:
                    if isinstance(item, dict) and field_path in item:
                        return item.get(field_path)
                return None
            else:
                return None

        keys = field_path.split('.')
        value = data

        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    index = int(key)
                    value = value[index] if 0 <= index < len(value) else None
                elif isinstance(value, list):
                    # For non-numeric keys on lists, check first item
                    if value and isinstance(value[0], dict):
                        value = value[0].get(key)
                    else:
                        return None
                else:
                    return None
            return value
        except (KeyError, TypeError, IndexError):
            return None

    def get_document_type_info(self, document_type: str) -> Optional[DocumentTypeRule]:
        """Get document type rule information."""
        return self.document_types.get(document_type)

    def get_supported_document_types(self) -> List[str]:
        """Get list of supported document types."""
        return list(self.document_types.keys())

    def get_validation_summary(self, results: List[DocumentRuleResult]) -> Dict[str, Any]:
        """Get document validation summary."""
        total_rules = len(results)
        passed = sum(1 for r in results if r.is_valid)
        failed = total_rules - passed

        # Count by severity
        severity_counts = {}
        severities = ["critical", "high", "medium", "low", "info"]
        for severity in severities:
            severity_counts[severity] = sum(
                1 for r in results
                if not r.is_valid and r.severity == severity
            )

        # Count by rule type
        rule_type_counts = {}
        rule_types = ["structure", "field", "business"]
        for rule_type in rule_types:
            rule_type_counts[rule_type] = sum(
                1 for r in results
                if r.rule_type == rule_type
            )

        return {
            'total_rules': total_rules,
            'passed': passed,
            'failed': failed,
            'success_rate': (passed / total_rules * 100) if total_rules > 0 else 100,
            'has_critical_errors': severity_counts.get('critical', 0) > 0,
            'has_high_errors': severity_counts.get('high', 0) > 0,
            'severity_breakdown': severity_counts,
            'rule_type_breakdown': rule_type_counts,
            'is_valid': failed == 0 or all(
                r.severity in ["low", "info"]
                for r in results if not r.is_valid
            )
        }


class SiiDocumentRuleValidator(DocumentRuleValidator):
    """
    SII-specific document rule validator.

    Extends base validator with additional Chilean SII-specific rules.
    """

    def __init__(self, **kwargs):
        """Initialize SII document rule validator."""
        super().__init__(**kwargs)
        self._load_sii_document_types()

    def _load_sii_document_types(self):
        """Load additional SII-specific document types."""

        # Guía de Despacho (52)
        self.add_document_type(DocumentTypeRule(
            document_type="52",
            document_name="Guía de Despacho Electrónica",
            description="Electronic dispatch guide",
            required_sections=["Encabezado", "Detalle"],
            optional_sections=["Totales", "Referencia"],
            mandatory_fields={
                "Encabezado": [
                    "IdDoc.TipoDTE",
                    "IdDoc.Folio",
                    "IdDoc.FchEmis",
                    "IdDoc.IndTraslado",  # Transfer indicator
                    "Emisor.RUTEmisor",
                    "Emisor.RznSoc",
                    "Receptor.RUTRecep",
                    "Receptor.RznSocRecep",
                    "Transporte"
                ],
                "Detalle": [
                    "NroLinDet",
                    "NmbItem",
                    "QtyItem"
                ]
            }
        ))

        # Factura de Compra (46)
        self.add_document_type(DocumentTypeRule(
            document_type="46",
            document_name="Factura de Compra Electrónica",
            description="Electronic purchase invoice",
            required_sections=["Encabezado", "Detalle", "Totales"],
            mandatory_fields={
                "Encabezado": [
                    "IdDoc.TipoDTE",
                    "IdDoc.Folio",
                    "IdDoc.FchEmis",
                    "Emisor.RUTEmisor",
                    "Emisor.RznSoc",
                    "Receptor.RUTRecep",
                    "Receptor.RznSocRecep"
                ],
                "Detalle": [
                    "NroLinDet",
                    "NmbItem",
                    "QtyItem",
                    "PrcItem"
                ],
                "Totales": [
                    "MntNeto",
                    "IVA",
                    "MntTotal"
                ]
            }
        ))

    def validate_sii_document(self,
                            document_data: Dict[str, Any],
                            document_type: str,
                            ambiente: str = "produccion") -> List[DocumentRuleResult]:
        """Validate document with SII-specific rules."""
        results = super().validate_document(document_data, document_type)

        # Apply additional SII validations
        sii_results = self._validate_sii_compliance(document_data, document_type, ambiente)
        results.extend(sii_results)

        return results

    def _validate_sii_compliance(self,
                               document_data: Dict[str, Any],
                               document_type: str,
                               ambiente: str) -> List[DocumentRuleResult]:
        """Validate SII compliance rules."""
        results = []

        # Common SII validations for all document types
        results.extend(self._validate_sii_common_rules(document_data, document_type))

        # Environment-specific validations
        if ambiente == "produccion":
            results.extend(self._validate_production_rules(document_data, document_type))

        return results

    def _validate_sii_common_rules(self,
                                 document_data: Dict[str, Any],
                                 document_type: str) -> List[DocumentRuleResult]:
        """Validate common SII rules for all documents."""
        results = []

        # Validate document type matches content
        encabezado = document_data.get('Encabezado', {})
        id_doc = encabezado.get('IdDoc', {})
        declared_type = str(id_doc.get('TipoDTE', ''))

        if declared_type != document_type:
            results.append(DocumentRuleResult(
                rule_id="sii_document_type_mismatch",
                rule_name="SII Document Type Mismatch",
                rule_type="business",
                is_valid=False,
                severity="critical",
                message=f"Document type mismatch. Expected: {document_type}, Declared: {declared_type}",
                section="Encabezado",
                field_path="Encabezado.IdDoc.TipoDTE",
                expected_value=document_type,
                actual_value=declared_type,
                document_type=document_type,
                reference="Resolución SII N° 80"
            ))

        return results

    def _validate_production_rules(self,
                                 document_data: Dict[str, Any],
                                 document_type: str) -> List[DocumentRuleResult]:
        """Validate production environment specific rules."""
        results = []

        # In production, certain test values are not allowed
        encabezado = document_data.get('Encabezado', {})
        emisor = encabezado.get('Emisor', {})
        receptor = encabezado.get('Receptor', {})

        # Check for test RUTs in production
        test_ruts = ["66666666-6", "11111111-1", "22222222-2"]

        emisor_rut = emisor.get('RUTEmisor', '')
        if emisor_rut in test_ruts:
            results.append(DocumentRuleResult(
                rule_id="sii_production_test_emisor",
                rule_name="SII Production Test Emisor",
                rule_type="business",
                is_valid=False,
                severity="critical",
                message=f"Test RUT not allowed in production: {emisor_rut}",
                section="Encabezado",
                field_path="Encabezado.Emisor.RUTEmisor",
                actual_value=emisor_rut,
                document_type=document_type,
                reference="SII Production Guidelines"
            ))

        # Receptor can be generic consumer (66666666-6) for boletas
        if document_type not in ["39", "41"]:  # Not boletas
            receptor_rut = receptor.get('RUTRecep', '')
            if receptor_rut in test_ruts and receptor_rut != "66666666-6":
                results.append(DocumentRuleResult(
                    rule_id="sii_production_test_receptor",
                    rule_name="SII Production Test Receptor",
                    rule_type="business",
                    is_valid=False,
                    severity="high",
                    message=f"Test RUT not recommended in production: {receptor_rut}",
                    section="Encabezado",
                    field_path="Encabezado.Receptor.RUTRecep",
                    actual_value=receptor_rut,
                    document_type=document_type,
                    reference="SII Production Guidelines"
                ))

        return results