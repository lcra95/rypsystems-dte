"""
RypSystems DTE - Advanced Validation Module
Comprehensive business logic validation beyond schema validation

Components:
- Business Rules: SII-specific business validation rules
- Tax Calculation: Tax computation and validation logic
- Cross-Field: Inter-field validation and consistency checks
- Document Rules: Document type specific validation rules
- Field Validation: Individual field validation with SII rules
"""

from .business_rules import (
    BusinessRuleValidator,
    SiiBusinessRuleValidator,
    BusinessRule,
    RuleType,
    RuleLevel,
    RuleSeverity,
    ValidationContext,
    RuleResult
)
from .tax_calculation import (
    TaxCalculationValidator,
    SiiTaxCalculationValidator,
    TaxCalculation,
    TaxType,
    TaxRateType,
    TaxResult,
    TaxValidationError
)
from .cross_field import (
    CrossFieldValidator,
    SiiCrossFieldValidator,
    FieldDependency,
    DependencyType,
    CrossFieldRule,
    CrossFieldResult
)
from .document_rules import (
    DocumentRuleValidator,
    SiiDocumentRuleValidator,
    DocumentTypeRule,
    DocumentRule,
    DocumentContext,
    DocumentRuleResult
)
from .field_validation import (
    FieldValidator,
    SiiFieldValidator,
    FieldRule,
    FieldType,
    FieldConstraint,
    FieldValidationResult
)

__all__ = [
    # Business rules validation
    'BusinessRuleValidator',
    'SiiBusinessRuleValidator',
    'BusinessRule',
    'RuleType',
    'RuleLevel',
    'RuleSeverity',
    'ValidationContext',
    'RuleResult',

    # Tax calculation validation
    'TaxCalculationValidator',
    'SiiTaxCalculationValidator',
    'TaxCalculation',
    'TaxType',
    'TaxRateType',
    'TaxResult',
    'TaxValidationError',

    # Cross-field validation
    'CrossFieldValidator',
    'SiiCrossFieldValidator',
    'FieldDependency',
    'DependencyType',
    'CrossFieldRule',
    'CrossFieldResult',

    # Document type rules
    'DocumentRuleValidator',
    'SiiDocumentRuleValidator',
    'DocumentTypeRule',
    'DocumentRule',
    'DocumentContext',
    'DocumentRuleResult',

    # Field validation
    'FieldValidator',
    'SiiFieldValidator',
    'FieldRule',
    'FieldType',
    'FieldConstraint',
    'FieldValidationResult'
]