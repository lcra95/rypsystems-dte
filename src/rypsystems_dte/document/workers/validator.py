"""
ValidatorWorker - Business rule validation beyond basic schema.

Implements comprehensive document validation including SII business rules,
tax calculations, cross-field validation, and document type specific rules.
"""

from typing import Dict, Any, List, Optional, Callable
from decimal import Decimal
from datetime import datetime, date
import re

from .base import BaseWorker, WorkerResult, WorkerStatus
from ...dte.document import BaseDocument
from ...sii.base import Contribuyente
from ...sii.utils import RutValidator


class ValidationRule:
    """Individual validation rule."""

    def __init__(
        self,
        name: str,
        description: str,
        validator: Callable[[BaseDocument, Dict[str, Any]], tuple[bool, str]],
        severity: str = "error",
        applies_to: Optional[List[int]] = None
    ):
        """
        Initialize validation rule.

        Args:
            name: Rule name/code
            description: Human-readable description
            validator: Function that validates the rule
            severity: error, warning, or info
            applies_to: Document types this rule applies to
        """
        self.name = name
        self.description = description
        self.validator = validator
        self.severity = severity
        self.applies_to = applies_to or []

    def applies_to_document(self, document: BaseDocument) -> bool:
        """Check if rule applies to document type."""
        if not self.applies_to:
            return True
        return document.get_tipo_documento() in self.applies_to

    def validate(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Execute validation rule."""
        return self.validator(document, context)


class ValidatorWorker(BaseWorker):
    """
    Validator worker for comprehensive business rule validation.

    Validates documents against SII business rules, tax calculations,
    and document-specific requirements beyond basic schema validation.
    """

    def __init__(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize validator worker."""
        super().__init__(name, config)
        self.rules: List[ValidationRule] = []
        self._setup_default_rules()

    def _setup_default_rules(self):
        """Setup default SII validation rules."""
        # RUT validation rules
        self.add_rule(ValidationRule(
            "rut_emisor_valid",
            "RUT del emisor debe ser válido",
            self._validate_rut_emisor,
            "error"
        ))

        self.add_rule(ValidationRule(
            "rut_receptor_valid",
            "RUT del receptor debe ser válido",
            self._validate_rut_receptor,
            "error"
        ))

        # Date validation rules
        self.add_rule(ValidationRule(
            "fecha_emision_valid",
            "Fecha de emisión debe ser válida y no futura",
            self._validate_fecha_emision,
            "error"
        ))

        # Folio validation rules
        self.add_rule(ValidationRule(
            "folio_positive",
            "Folio debe ser un número positivo",
            self._validate_folio_positive,
            "error"
        ))

        # Amount validation rules
        self.add_rule(ValidationRule(
            "amounts_consistent",
            "Montos deben ser consistentes con detalles",
            self._validate_amounts_consistent,
            "error"
        ))

        # Tax calculation rules
        self.add_rule(ValidationRule(
            "iva_calculation",
            "Cálculo de IVA debe ser correcto",
            self._validate_iva_calculation,
            "error",
            [33, 34]  # Facturas afectas/exentas
        ))

        # Detail validation rules
        self.add_rule(ValidationRule(
            "detalle_items_valid",
            "Items del detalle deben ser válidos",
            self._validate_detalle_items,
            "error"
        ))

        # Document type specific rules
        self.add_rule(ValidationRule(
            "nota_credito_reference",
            "Nota de crédito debe tener referencia válida",
            self._validate_nota_credito_reference,
            "error",
            [61]  # Nota de crédito
        ))

        self.add_rule(ValidationRule(
            "factura_exenta_no_iva",
            "Factura exenta no debe tener IVA",
            self._validate_factura_exenta_no_iva,
            "error",
            [34]  # Factura exenta
        ))

    def add_rule(self, rule: ValidationRule):
        """Add validation rule."""
        self.rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove validation rule by name."""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                del self.rules[i]
                return True
        return False

    def process(self, document: BaseDocument, context: Optional[Dict[str, Any]] = None) -> WorkerResult:
        """
        Validate document against business rules.

        Args:
            document: Document to validate
            context: Validation context

        Returns:
            Validation result with errors and warnings
        """
        result = WorkerResult(
            worker_name=self.name,
            status=WorkerStatus.SUCCESS,
            document=document
        )

        validation_context = context or {}
        validation_context.update({
            'strict_mode': self.get_config_value('strict_mode', True),
            'validate_taxes': self.get_config_value('validate_taxes', True),
            'validate_amounts': self.get_config_value('validate_amounts', True)
        })

        # Execute validation rules
        for rule in self.rules:
            try:
                if not rule.applies_to_document(document):
                    continue

                is_valid, error_message = rule.validate(document, validation_context)

                if not is_valid:
                    if rule.severity == "error":
                        result.add_error(rule.name, error_message)
                    elif rule.severity == "warning":
                        result.add_warning(rule.name, error_message)
                    else:
                        result.add_info(rule.name, error_message)

            except Exception as e:
                self.logger.exception(f"Error executing validation rule {rule.name}")
                result.add_error(
                    f"{rule.name}_execution_error",
                    f"Error executing validation rule: {str(e)}"
                )

        # Set final status
        if result.has_errors():
            result.status = WorkerStatus.ERROR
        elif result.has_warnings():
            result.status = WorkerStatus.WARNING

        result.data['rules_executed'] = len([r for r in self.rules if r.applies_to_document(document)])
        result.data['validation_context'] = validation_context

        return result

    # Validation rule implementations
    def _validate_rut_emisor(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Validate emisor RUT."""
        try:
            rut_emisor = document.get_rut_emisor()
            if not rut_emisor:
                return False, "RUT emisor es requerido"

            if not RutValidator.validate(rut_emisor):
                return False, f"RUT emisor inválido: {rut_emisor}"

            return True, ""
        except Exception as e:
            return False, f"Error validando RUT emisor: {str(e)}"

    def _validate_rut_receptor(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Validate receptor RUT."""
        try:
            rut_receptor = document.get_rut_receptor()
            if not rut_receptor:
                return False, "RUT receptor es requerido"

            if not RutValidator.validate(rut_receptor):
                return False, f"RUT receptor inválido: {rut_receptor}"

            return True, ""
        except Exception as e:
            return False, f"Error validando RUT receptor: {str(e)}"

    def _validate_fecha_emision(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Validate emission date."""
        try:
            datos = document.get_datos()
            fecha_emision = datos.get('Encabezado', {}).get('IdDoc', {}).get('FchEmis')

            if not fecha_emision:
                return False, "Fecha de emisión es requerida"

            # Parse date
            if isinstance(fecha_emision, str):
                try:
                    fecha_dt = datetime.strptime(fecha_emision, '%Y-%m-%d').date()
                except ValueError:
                    return False, f"Formato de fecha inválido: {fecha_emision}"
            elif isinstance(fecha_emision, date):
                fecha_dt = fecha_emision
            else:
                return False, f"Tipo de fecha inválido: {type(fecha_emision)}"

            # Check if date is not in the future
            today = date.today()
            if fecha_dt > today:
                return False, f"Fecha de emisión no puede ser futura: {fecha_dt}"

            # Check if date is not too old (configurable)
            max_days_old = context.get('max_days_old', 365)
            days_diff = (today - fecha_dt).days
            if days_diff > max_days_old:
                return False, f"Fecha de emisión muy antigua: {fecha_dt} ({days_diff} días)"

            return True, ""
        except Exception as e:
            return False, f"Error validando fecha de emisión: {str(e)}"

    def _validate_folio_positive(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Validate folio is positive."""
        try:
            folio = document.get_folio()
            if folio is None:
                return False, "Folio es requerido"

            if not isinstance(folio, int) or folio <= 0:
                return False, f"Folio debe ser un número positivo: {folio}"

            return True, ""
        except Exception as e:
            return False, f"Error validando folio: {str(e)}"

    def _validate_amounts_consistent(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Validate amount consistency."""
        if not context.get('validate_amounts', True):
            return True, ""

        try:
            datos = document.get_datos()
            totales = datos.get('Encabezado', {}).get('Totales', {})
            detalle = datos.get('Detalle', [])

            if not isinstance(detalle, list):
                detalle = [detalle]

            # Calculate totals from detail
            total_detalle = Decimal('0')
            for item in detalle:
                qty = Decimal(str(item.get('QtyItem', 1)))
                price = Decimal(str(item.get('PrcItem', 0)))
                total_detalle += qty * price

            # Compare with document total
            mnt_neto = totales.get('MntNeto')
            mnt_total = totales.get('MntTotal')

            if mnt_neto is not None:
                mnt_neto = Decimal(str(mnt_neto))
                if abs(total_detalle - mnt_neto) > Decimal('0.01'):
                    return False, f"Monto neto inconsistente: calculado {total_detalle}, documento {mnt_neto}"

            if mnt_total is not None:
                mnt_total = Decimal(str(mnt_total))
                # For simple validation, check if total matches detail (without taxes)
                # Real validation would include tax calculations

            return True, ""
        except Exception as e:
            return False, f"Error validando consistencia de montos: {str(e)}"

    def _validate_iva_calculation(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Validate IVA calculation."""
        if not context.get('validate_taxes', True):
            return True, ""

        try:
            datos = document.get_datos()
            totales = datos.get('Encabezado', {}).get('Totales', {})

            mnt_neto = totales.get('MntNeto')
            iva = totales.get('IVA')
            mnt_total = totales.get('MntTotal')

            if mnt_neto is None or iva is None or mnt_total is None:
                return True, ""  # Skip if values not present

            mnt_neto = Decimal(str(mnt_neto))
            iva_actual = Decimal(str(iva))
            mnt_total_actual = Decimal(str(mnt_total))

            # Calculate expected IVA (19% standard rate)
            tasa_iva = Decimal('0.19')
            iva_esperado = (mnt_neto * tasa_iva).quantize(Decimal('1'))
            mnt_total_esperado = mnt_neto + iva_esperado

            # Validate IVA calculation
            if abs(iva_actual - iva_esperado) > Decimal('1'):
                return False, f"IVA mal calculado: esperado {iva_esperado}, actual {iva_actual}"

            # Validate total
            if abs(mnt_total_actual - mnt_total_esperado) > Decimal('1'):
                return False, f"Monto total mal calculado: esperado {mnt_total_esperado}, actual {mnt_total_actual}"

            return True, ""
        except Exception as e:
            return False, f"Error validando cálculo IVA: {str(e)}"

    def _validate_detalle_items(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Validate detail items."""
        try:
            datos = document.get_datos()
            detalle = datos.get('Detalle', [])

            if not detalle:
                return False, "Documento debe tener al menos un item en el detalle"

            if not isinstance(detalle, list):
                detalle = [detalle]

            for i, item in enumerate(detalle):
                # Validate required fields
                if not item.get('NmbItem'):
                    return False, f"Item {i+1}: Nombre es requerido"

                qty = item.get('QtyItem')
                if qty is None:
                    return False, f"Item {i+1}: Cantidad es requerida"

                # Convert to numeric for validation
                try:
                    qty_numeric = Decimal(str(qty))
                    if qty_numeric <= 0:
                        return False, f"Item {i+1}: Cantidad debe ser positiva"
                except (ValueError, TypeError):
                    return False, f"Item {i+1}: Cantidad debe ser numérica"

                price = item.get('PrcItem')
                if price is None:
                    return False, f"Item {i+1}: Precio es requerido"

                # Validate price is numeric
                try:
                    Decimal(str(price))
                except (ValueError, TypeError):
                    return False, f"Item {i+1}: Precio debe ser numérico"

            return True, ""
        except Exception as e:
            return False, f"Error validando items del detalle: {str(e)}"

    def _validate_nota_credito_reference(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Validate credit note reference."""
        try:
            datos = document.get_datos()
            referencia = datos.get('Referencia')

            if not referencia:
                return False, "Nota de crédito debe tener documento de referencia"

            if isinstance(referencia, list):
                referencia = referencia[0]

            # Validate required reference fields
            if not referencia.get('TpoDocRef'):
                return False, "Referencia debe tener tipo de documento"

            if not referencia.get('FolioRef'):
                return False, "Referencia debe tener folio"

            if not referencia.get('FchRef'):
                return False, "Referencia debe tener fecha"

            # Validate reference document type
            tpo_doc_ref = referencia.get('TpoDocRef')
            valid_ref_types = [33, 34, 39, 41, 46, 56, 61]  # Valid reference document types
            if tpo_doc_ref not in valid_ref_types:
                return False, f"Tipo de documento de referencia inválido: {tpo_doc_ref}"

            return True, ""
        except Exception as e:
            return False, f"Error validando referencia de nota de crédito: {str(e)}"

    def _validate_factura_exenta_no_iva(self, document: BaseDocument, context: Dict[str, Any]) -> tuple[bool, str]:
        """Validate exempt invoice has no IVA."""
        try:
            datos = document.get_datos()
            totales = datos.get('Encabezado', {}).get('Totales', {})

            iva = totales.get('IVA', 0)
            if iva and Decimal(str(iva)) > 0:
                return False, "Factura exenta no debe tener IVA"

            return True, ""
        except Exception as e:
            return False, f"Error validando factura exenta: {str(e)}"

    def validate_config(self) -> List[str]:
        """Validate worker configuration."""
        errors = []

        # Check if any rules are configured
        if not self.rules:
            errors.append("No validation rules configured")

        return errors