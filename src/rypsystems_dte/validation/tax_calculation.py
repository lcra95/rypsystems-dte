"""
Tax Calculation Validation System.

Provides comprehensive tax calculation validation including:
- IVA (VAT) calculation and verification
- Tax rate validation
- Tax exemption validation
- Special tax calculations (specific taxes)
- Cross-validation with document totals
"""

from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import date

from pydantic import BaseModel, Field, field_validator, ConfigDict


class TaxType(str, Enum):
    """Tax types supported in Chilean tax system."""
    IVA = "iva"  # Impuesto al Valor Agregado
    IMPUESTO_ESPECIFICO = "impuesto_especifico"  # Specific taxes
    IMPUESTO_ADICIONAL = "impuesto_adicional"  # Additional taxes
    RETENCION = "retencion"  # Withholding taxes
    CREDITO_ESPECIAL = "credito_especial"  # Special credits


class TaxRateType(str, Enum):
    """Tax rate types."""
    STANDARD = "standard"  # 19% IVA
    REDUCED = "reduced"  # Reduced rates
    EXEMPT = "exempt"  # Tax exempt
    ZERO = "zero"  # Zero rate
    SPECIAL = "special"  # Special rates


class TaxValidationError(Exception):
    """Tax validation specific error."""
    pass


class TaxCalculation(BaseModel):
    """Tax calculation model."""

    # Basic information
    tax_type: TaxType = Field(..., description="Type of tax")
    rate_type: TaxRateType = Field(..., description="Tax rate type")

    # Amounts
    base_amount: Decimal = Field(..., description="Base amount for tax calculation")
    tax_rate: Decimal = Field(..., description="Tax rate (as decimal, e.g., 0.19)")
    calculated_tax: Decimal = Field(..., description="Calculated tax amount")
    declared_tax: Decimal = Field(..., description="Declared tax amount")

    # Validation
    is_valid: bool = Field(default=False, description="Whether calculation is valid")
    tolerance: Decimal = Field(default=Decimal('1'), description="Tolerance for rounding differences")

    # Additional context
    calculation_method: str = Field(default="standard", description="Calculation method used")
    rounding_method: str = Field(default="ROUND_HALF_UP", description="Rounding method")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )

    @field_validator('base_amount', 'tax_rate', 'calculated_tax', 'declared_tax', 'tolerance')
    @classmethod
    def validate_decimal_fields(cls, v):
        """Ensure decimal fields are properly formatted."""
        if isinstance(v, (int, float, str)):
            return Decimal(str(v))
        return v


class TaxResult(BaseModel):
    """Tax validation result."""

    # Calculation details
    calculation: TaxCalculation = Field(..., description="Tax calculation details")

    # Validation result
    is_valid: bool = Field(..., description="Overall validation result")
    variance: Decimal = Field(..., description="Difference between calculated and declared")
    variance_percentage: Decimal = Field(..., description="Variance as percentage")

    # Messages
    messages: List[str] = Field(default_factory=list, description="Validation messages")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    errors: List[str] = Field(default_factory=list, description="Validation errors")

    # Context
    field_path: Optional[str] = Field(None, description="Field path in document")
    reference: Optional[str] = Field(None, description="Legal reference")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class TaxCalculationValidator:
    """
    Tax calculation validation engine.

    Provides comprehensive tax calculation validation including:
    - IVA calculation verification
    - Tax rate validation
    - Rounding and tolerance checks
    - Special tax calculations
    """

    # Standard Chilean tax rates
    STANDARD_IVA_RATE = Decimal('0.19')  # 19%
    ZERO_RATE = Decimal('0.00')

    # Tax rate tolerances
    DEFAULT_TOLERANCE = Decimal('1')  # 1 peso
    PERCENTAGE_TOLERANCE = Decimal('0.01')  # 1%

    def __init__(self,
                 tolerance: Decimal = None,
                 strict_mode: bool = False,
                 custom_rates: Optional[Dict[str, Decimal]] = None):
        """
        Initialize tax calculation validator.

        Args:
            tolerance: Tolerance for rounding differences
            strict_mode: Whether to use strict validation
            custom_rates: Custom tax rates for special cases
        """
        self.tolerance = tolerance or self.DEFAULT_TOLERANCE
        self.strict_mode = strict_mode
        self.custom_rates = custom_rates or {}

        # Load standard rates
        self.standard_rates = {
            'iva_standard': self.STANDARD_IVA_RATE,
            'iva_exempt': self.ZERO_RATE,
            'iva_zero': self.ZERO_RATE
        }

    def validate_iva_calculation(self,
                               base_amount: Decimal,
                               declared_iva: Decimal,
                               rate_type: TaxRateType = TaxRateType.STANDARD,
                               field_path: str = "IVA") -> TaxResult:
        """
        Validate IVA calculation.

        Args:
            base_amount: Net base amount
            declared_iva: Declared IVA amount
            rate_type: Type of IVA rate
            field_path: Field path in document

        Returns:
            Tax validation result
        """
        try:
            # Determine tax rate
            if rate_type == TaxRateType.STANDARD:
                tax_rate = self.STANDARD_IVA_RATE
            elif rate_type in [TaxRateType.EXEMPT, TaxRateType.ZERO]:
                tax_rate = self.ZERO_RATE
            else:
                tax_rate = self.custom_rates.get('iva_' + rate_type.value, self.STANDARD_IVA_RATE)

            # Calculate expected IVA
            calculated_iva = self._calculate_iva(base_amount, tax_rate)

            # Create calculation object
            calculation = TaxCalculation(
                tax_type=TaxType.IVA,
                rate_type=rate_type,
                base_amount=base_amount,
                tax_rate=tax_rate,
                calculated_tax=calculated_iva,
                declared_tax=declared_iva,
                tolerance=self.tolerance
            )

            # Validate calculation
            return self._validate_tax_calculation(calculation, field_path)

        except Exception as e:
            return TaxResult(
                calculation=TaxCalculation(
                    tax_type=TaxType.IVA,
                    rate_type=rate_type,
                    base_amount=base_amount,
                    tax_rate=Decimal('0'),
                    calculated_tax=Decimal('0'),
                    declared_tax=declared_iva
                ),
                is_valid=False,
                variance=Decimal('0'),
                variance_percentage=Decimal('0'),
                errors=[f"IVA calculation error: {e}"],
                field_path=field_path
            )

    def _calculate_iva(self, base_amount: Decimal, tax_rate: Decimal) -> Decimal:
        """Calculate IVA amount with proper rounding."""
        if base_amount <= 0 or tax_rate <= 0:
            return Decimal('0')

        # Calculate IVA
        iva_amount = base_amount * tax_rate

        # Round to nearest peso (standard SII practice)
        return iva_amount.quantize(Decimal('0'), rounding=ROUND_HALF_UP)

    def _validate_tax_calculation(self,
                                calculation: TaxCalculation,
                                field_path: str) -> TaxResult:
        """Validate tax calculation against declared amount."""
        messages = []
        warnings = []
        errors = []

        # Calculate variance
        variance = calculation.declared_tax - calculation.calculated_tax

        # Calculate percentage variance
        if calculation.calculated_tax > 0:
            variance_percentage = abs(variance) / calculation.calculated_tax * 100
        else:
            variance_percentage = Decimal('0') if variance == 0 else Decimal('100')

        # Check if within tolerance
        is_within_tolerance = abs(variance) <= calculation.tolerance

        # Validation logic
        is_valid = True

        if not is_within_tolerance:
            if self.strict_mode:
                is_valid = False
                errors.append(
                    f"Tax calculation outside tolerance. "
                    f"Expected: {calculation.calculated_tax}, "
                    f"Declared: {calculation.declared_tax}, "
                    f"Variance: {variance}"
                )
            else:
                # Check if variance is significant
                if variance_percentage > self.PERCENTAGE_TOLERANCE:
                    is_valid = False
                    errors.append(
                        f"Significant tax calculation variance: {variance_percentage:.2f}%"
                    )
                else:
                    warnings.append(
                        f"Minor tax calculation variance within tolerance: {variance}"
                    )
        else:
            messages.append("Tax calculation is correct")

        # Additional validations
        if calculation.base_amount < 0:
            errors.append("Base amount cannot be negative")
            is_valid = False

        if calculation.declared_tax < 0:
            errors.append("Tax amount cannot be negative")
            is_valid = False

        if calculation.tax_rate < 0 or calculation.tax_rate > 1:
            warnings.append(f"Unusual tax rate: {calculation.tax_rate * 100:.2f}%")

        # Mark calculation as valid
        calculation.is_valid = is_valid

        return TaxResult(
            calculation=calculation,
            is_valid=is_valid,
            variance=variance,
            variance_percentage=variance_percentage,
            messages=messages,
            warnings=warnings,
            errors=errors,
            field_path=field_path,
            reference="Ley del IVA Art. 14"
        )

    def validate_document_taxes(self, document_data: Dict[str, Any]) -> List[TaxResult]:
        """Validate all tax calculations in a document."""
        results = []

        totales = document_data.get('Totales', {})

        # Validate IVA
        mnt_neto = Decimal(str(totales.get('MntNeto', 0)))
        iva = Decimal(str(totales.get('IVA', 0)))

        if mnt_neto > 0 or iva > 0:
            iva_result = self.validate_iva_calculation(
                base_amount=mnt_neto,
                declared_iva=iva,
                field_path="Totales.IVA"
            )
            results.append(iva_result)

        # Validate specific taxes if present
        imp_especificos = totales.get('ImptoReten', [])
        if isinstance(imp_especificos, list):
            for i, impuesto in enumerate(imp_especificos):
                if isinstance(impuesto, dict):
                    result = self._validate_specific_tax(
                        impuesto,
                        f"Totales.ImptoReten[{i}]"
                    )
                    if result:
                        results.append(result)

        # Validate total calculations
        total_result = self._validate_total_calculation(document_data)
        if total_result:
            results.append(total_result)

        return results

    def _validate_specific_tax(self,
                             tax_data: Dict[str, Any],
                             field_path: str) -> Optional[TaxResult]:
        """Validate specific tax calculation."""
        try:
            tipo_imp = tax_data.get('TipoImp')
            monto_imp = Decimal(str(tax_data.get('MontoImp', 0)))

            # Basic validation
            if monto_imp < 0:
                return TaxResult(
                    calculation=TaxCalculation(
                        tax_type=TaxType.IMPUESTO_ESPECIFICO,
                        rate_type=TaxRateType.SPECIAL,
                        base_amount=Decimal('0'),
                        tax_rate=Decimal('0'),
                        calculated_tax=Decimal('0'),
                        declared_tax=monto_imp
                    ),
                    is_valid=False,
                    variance=Decimal('0'),
                    variance_percentage=Decimal('0'),
                    errors=["Specific tax amount cannot be negative"],
                    field_path=field_path
                )

            return None

        except Exception as e:
            return TaxResult(
                calculation=TaxCalculation(
                    tax_type=TaxType.IMPUESTO_ESPECIFICO,
                    rate_type=TaxRateType.SPECIAL,
                    base_amount=Decimal('0'),
                    tax_rate=Decimal('0'),
                    calculated_tax=Decimal('0'),
                    declared_tax=Decimal('0')
                ),
                is_valid=False,
                variance=Decimal('0'),
                variance_percentage=Decimal('0'),
                errors=[f"Specific tax validation error: {e}"],
                field_path=field_path
            )

    def _validate_total_calculation(self, document_data: Dict[str, Any]) -> Optional[TaxResult]:
        """Validate document total calculation."""
        try:
            totales = document_data.get('Totales', {})

            mnt_neto = Decimal(str(totales.get('MntNeto', 0)))
            iva = Decimal(str(totales.get('IVA', 0)))
            mnt_total = Decimal(str(totales.get('MntTotal', 0)))

            # Calculate expected total
            calculated_total = mnt_neto + iva

            # Add other taxes
            imp_especificos = totales.get('ImptoReten', [])
            if isinstance(imp_especificos, list):
                for impuesto in imp_especificos:
                    if isinstance(impuesto, dict):
                        monto = Decimal(str(impuesto.get('MontoImp', 0)))
                        calculated_total += monto

            # Create calculation
            calculation = TaxCalculation(
                tax_type=TaxType.IVA,  # Total validation
                rate_type=TaxRateType.STANDARD,
                base_amount=mnt_neto,
                tax_rate=Decimal('1'),  # Not applicable for total
                calculated_tax=calculated_total,
                declared_tax=mnt_total,
                tolerance=self.tolerance
            )

            return self._validate_tax_calculation(calculation, "Totales.MntTotal")

        except Exception as e:
            return TaxResult(
                calculation=TaxCalculation(
                    tax_type=TaxType.IVA,
                    rate_type=TaxRateType.STANDARD,
                    base_amount=Decimal('0'),
                    tax_rate=Decimal('0'),
                    calculated_tax=Decimal('0'),
                    declared_tax=Decimal('0')
                ),
                is_valid=False,
                variance=Decimal('0'),
                variance_percentage=Decimal('0'),
                errors=[f"Total calculation validation error: {e}"],
                field_path="Totales.MntTotal"
            )

    def get_tax_summary(self, results: List[TaxResult]) -> Dict[str, Any]:
        """Get tax validation summary."""
        total_validations = len(results)
        valid_calculations = sum(1 for r in results if r.is_valid)
        invalid_calculations = total_validations - valid_calculations

        total_variance = sum(abs(r.variance) for r in results)
        max_variance = max((abs(r.variance) for r in results), default=Decimal('0'))

        has_errors = any(r.errors for r in results)
        has_warnings = any(r.warnings for r in results)

        return {
            'total_validations': total_validations,
            'valid_calculations': valid_calculations,
            'invalid_calculations': invalid_calculations,
            'success_rate': (valid_calculations / total_validations * 100) if total_validations > 0 else 100,
            'total_variance': total_variance,
            'max_variance': max_variance,
            'has_errors': has_errors,
            'has_warnings': has_warnings,
            'is_valid': not has_errors,
            'validation_details': [
                {
                    'field_path': r.field_path,
                    'is_valid': r.is_valid,
                    'variance': str(r.variance),
                    'errors': r.errors,
                    'warnings': r.warnings
                }
                for r in results
            ]
        }


class SiiTaxCalculationValidator(TaxCalculationValidator):
    """
    SII-specific tax calculation validator.

    Extends base validator with Chilean SII-specific tax rules.
    """

    def __init__(self, **kwargs):
        """Initialize SII tax calculation validator."""
        super().__init__(**kwargs)

        # SII-specific configurations
        self.sii_rates = {
            'iva_standard': Decimal('0.19'),  # 19%
            'iva_export': Decimal('0.00'),    # Export exempt
            'iva_books': Decimal('0.00'),     # Books exempt
        }

        # Update custom rates
        self.custom_rates.update(self.sii_rates)

    def validate_sii_document_taxes(self,
                                  document_data: Dict[str, Any],
                                  document_type: str) -> List[TaxResult]:
        """Validate taxes for specific SII document types."""
        results = super().validate_document_taxes(document_data)

        # Apply SII-specific validations based on document type
        if document_type == "33":  # Factura Electrónica
            sii_results = self._validate_factura_electronica_taxes(document_data)
            results.extend(sii_results)
        elif document_type == "34":  # Factura Exenta
            sii_results = self._validate_factura_exenta_taxes(document_data)
            results.extend(sii_results)
        elif document_type == "61":  # Nota de Crédito
            sii_results = self._validate_nota_credito_taxes(document_data)
            results.extend(sii_results)

        return results

    def _validate_factura_electronica_taxes(self, document_data: Dict[str, Any]) -> List[TaxResult]:
        """Validate taxes for Factura Electrónica."""
        results = []
        totales = document_data.get('Totales', {})

        # Factura Electrónica must have IVA
        iva = Decimal(str(totales.get('IVA', 0)))
        mnt_neto = Decimal(str(totales.get('MntNeto', 0)))

        if mnt_neto > 0 and iva == 0:
            results.append(TaxResult(
                calculation=TaxCalculation(
                    tax_type=TaxType.IVA,
                    rate_type=TaxRateType.STANDARD,
                    base_amount=mnt_neto,
                    tax_rate=self.STANDARD_IVA_RATE,
                    calculated_tax=self._calculate_iva(mnt_neto, self.STANDARD_IVA_RATE),
                    declared_tax=iva
                ),
                is_valid=False,
                variance=iva,
                variance_percentage=Decimal('100'),
                errors=["Factura Electrónica with net amount must include IVA"],
                field_path="Totales.IVA",
                reference="Resolución SII N° 80"
            ))

        return results

    def _validate_factura_exenta_taxes(self, document_data: Dict[str, Any]) -> List[TaxResult]:
        """Validate taxes for Factura Exenta."""
        results = []
        totales = document_data.get('Totales', {})

        # Factura Exenta must not have IVA
        iva = Decimal(str(totales.get('IVA', 0)))

        if iva > 0:
            results.append(TaxResult(
                calculation=TaxCalculation(
                    tax_type=TaxType.IVA,
                    rate_type=TaxRateType.EXEMPT,
                    base_amount=Decimal('0'),
                    tax_rate=Decimal('0'),
                    calculated_tax=Decimal('0'),
                    declared_tax=iva
                ),
                is_valid=False,
                variance=iva,
                variance_percentage=Decimal('100'),
                errors=["Factura Exenta must not include IVA"],
                field_path="Totales.IVA",
                reference="Resolución SII N° 80"
            ))

        return results

    def _validate_nota_credito_taxes(self, document_data: Dict[str, Any]) -> List[TaxResult]:
        """Validate taxes for Nota de Crédito."""
        results = []

        # Nota de Crédito can have negative amounts
        # Override base validation for negative amounts
        totales = document_data.get('Totales', {})
        mnt_neto = Decimal(str(totales.get('MntNeto', 0)))
        iva = Decimal(str(totales.get('IVA', 0)))

        if mnt_neto < 0 and iva > 0:
            results.append(TaxResult(
                calculation=TaxCalculation(
                    tax_type=TaxType.IVA,
                    rate_type=TaxRateType.STANDARD,
                    base_amount=mnt_neto,
                    tax_rate=self.STANDARD_IVA_RATE,
                    calculated_tax=self._calculate_iva(abs(mnt_neto), self.STANDARD_IVA_RATE) * -1,
                    declared_tax=iva
                ),
                is_valid=False,
                variance=iva,
                variance_percentage=Decimal('100'),
                errors=["Nota de Crédito with negative net amount should have negative IVA"],
                field_path="Totales.IVA",
                reference="Resolución SII N° 80"
            ))

        return results