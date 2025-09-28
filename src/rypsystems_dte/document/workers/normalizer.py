"""
NormalizerWorker - Format standardization.

Implements document format normalization including field standardization,
unit conversion, currency formatting, and SII-compliant data structures.
"""

from typing import Dict, Any, List, Optional, Union
from decimal import Decimal
from datetime import datetime, date
import re

from .base import BaseWorker, WorkerResult, WorkerStatus
from ...dte.document import BaseDocument
from ...sii.utils import RutValidator


class NormalizerWorker(BaseWorker):
    """
    Normalizer worker for format standardization.

    Standardizes document formats to ensure consistency and
    compliance with SII requirements and best practices.
    """

    def __init__(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize normalizer worker."""
        super().__init__(name, config)

        # Default normalization rules
        self.default_config = {
            'normalize_rut_format': True,
            'normalize_dates': True,
            'normalize_amounts': True,
            'normalize_field_names': True,
            'normalize_document_structure': True,
            'add_missing_fields': True,
            'standardize_units': True,
            'normalize_text_case': False,  # Disabled by default to preserve user input
            'currency_code': 'CLP',
            'date_format': '%Y-%m-%d',
            'decimal_places': 0  # Chilean pesos don't use decimals
        }

        # Merge with provided config
        self.config = {**self.default_config, **(config or {})}

        # Field mappings for normalization
        self.field_mappings = {
            'rut_emisor': ['RUTEmisor', 'RutEmisor', 'rut_emisor', 'emisor_rut'],
            'rut_receptor': ['RUTRecep', 'RutRecep', 'rut_receptor', 'receptor_rut'],
            'fecha_emision': ['FchEmis', 'FechaEmision', 'fecha_emision'],
            'folio': ['Folio', 'folio', 'numero'],
            'tipo_documento': ['TipoDTE', 'TipoDocumento', 'tipo_documento', 'tipo_dte']
        }

    def process(self, document: BaseDocument, context: Optional[Dict[str, Any]] = None) -> WorkerResult:
        """
        Normalize document format.

        Args:
            document: Document to normalize
            context: Normalization context

        Returns:
            Normalization result with standardized document
        """
        result = WorkerResult(
            worker_name=self.name,
            status=WorkerStatus.SUCCESS,
            document=document
        )

        try:
            # Get document data
            datos = document.get_datos().copy()

            # Track normalization actions
            normalization_actions = []

            # Apply normalization rules
            normalized_datos = self._normalize_document_structure(datos, normalization_actions)

            # Update document if changes were made
            if normalization_actions:
                # Update the document's internal data rather than creating new instance
                document._datos = normalized_datos
                result.document = document

                result.data['normalization_actions'] = normalization_actions
                result.data['actions_count'] = len(normalization_actions)

                result.add_info(
                    "data_normalized",
                    f"Applied {len(normalization_actions)} normalization actions"
                )
            else:
                result.add_info("no_normalization_needed", "No normalization required")

        except Exception as e:
            self.logger.exception("Error during document normalization")
            result.status = WorkerStatus.ERROR
            result.add_error(
                "normalization_error",
                f"Error during normalization: {str(e)}"
            )

        return result

    def _normalize_document_structure(self, datos: Dict[str, Any], actions: List[str]) -> Dict[str, Any]:
        """
        Normalize document structure to SII standards.

        Args:
            datos: Document data
            actions: List to track actions

        Returns:
            Normalized document data
        """
        if not self.config['normalize_document_structure']:
            return datos

        # Ensure proper document structure
        if 'Encabezado' not in datos:
            datos['Encabezado'] = {}
            actions.append("Added missing Encabezado section")

        if 'IdDoc' not in datos['Encabezado']:
            datos['Encabezado']['IdDoc'] = {}
            actions.append("Added missing IdDoc section")

        if 'Emisor' not in datos['Encabezado']:
            datos['Encabezado']['Emisor'] = {}
            actions.append("Added missing Emisor section")

        if 'Receptor' not in datos['Encabezado']:
            datos['Encabezado']['Receptor'] = {}
            actions.append("Added missing Receptor section")

        # Normalize each section
        datos['Encabezado']['IdDoc'] = self._normalize_id_doc(datos['Encabezado']['IdDoc'], actions)
        datos['Encabezado']['Emisor'] = self._normalize_party(datos['Encabezado']['Emisor'], 'Emisor', actions)
        datos['Encabezado']['Receptor'] = self._normalize_party(datos['Encabezado']['Receptor'], 'Receptor', actions)

        # Normalize totals if present
        if 'Totales' in datos['Encabezado']:
            datos['Encabezado']['Totales'] = self._normalize_totales(datos['Encabezado']['Totales'], actions)

        # Normalize detail if present
        if 'Detalle' in datos:
            datos['Detalle'] = self._normalize_detalle(datos['Detalle'], actions)

        # Normalize reference if present
        if 'Referencia' in datos:
            datos['Referencia'] = self._normalize_referencia(datos['Referencia'], actions)

        return datos

    def _normalize_id_doc(self, id_doc: Dict[str, Any], actions: List[str]) -> Dict[str, Any]:
        """Normalize IdDoc section."""
        normalized = id_doc.copy()

        # Normalize document type
        if 'TipoDTE' in normalized:
            tipo_dte = normalized['TipoDTE']
            if isinstance(tipo_dte, str) and tipo_dte.isdigit():
                normalized['TipoDTE'] = int(tipo_dte)
                actions.append("Converted TipoDTE to integer")

        # Normalize folio
        if 'Folio' in normalized:
            folio = normalized['Folio']
            if isinstance(folio, str) and folio.isdigit():
                normalized['Folio'] = int(folio)
                actions.append("Converted Folio to integer")

        # Normalize emission date
        if 'FchEmis' in normalized and self.config['normalize_dates']:
            normalized['FchEmis'] = self._normalize_date(normalized['FchEmis'], actions, 'FchEmis')

        # Add missing required fields with defaults
        if self.config['add_missing_fields']:
            if 'FchEmis' not in normalized:
                normalized['FchEmis'] = date.today().strftime(self.config['date_format'])
                actions.append("Added default emission date")

        return normalized

    def _normalize_party(self, party: Dict[str, Any], party_type: str, actions: List[str]) -> Dict[str, Any]:
        """Normalize party (Emisor/Receptor) data."""
        normalized = party.copy()

        # Normalize RUT
        rut_field = f'RUT{party_type}' if party_type == 'Emisor' else 'RUTRecep'
        if rut_field in normalized and self.config['normalize_rut_format']:
            original_rut = normalized[rut_field]
            normalized_rut = self._normalize_rut(original_rut)
            if normalized_rut != original_rut:
                normalized[rut_field] = normalized_rut
                actions.append(f"Normalized {party_type} RUT format")

        # Normalize party name
        name_field = f'Rzn{party_type}' if party_type == 'Emisor' else 'RznSocRecep'
        if name_field in normalized:
            original_name = normalized[name_field]
            normalized_name = self._normalize_text(original_name)
            if normalized_name != original_name:
                normalized[name_field] = normalized_name
                actions.append(f"Normalized {party_type} name")

        # Normalize address fields
        address_fields = ['DirOrigen', 'CmnaOrigen'] if party_type == 'Emisor' else ['DirRecep', 'CmnaRecep']
        for field in address_fields:
            if field in normalized:
                original_value = normalized[field]
                normalized_value = self._normalize_text(original_value)
                if normalized_value != original_value:
                    normalized[field] = normalized_value
                    actions.append(f"Normalized {party_type} {field}")

        return normalized

    def _normalize_totales(self, totales: Dict[str, Any], actions: List[str]) -> Dict[str, Any]:
        """Normalize totals section."""
        normalized = totales.copy()

        if not self.config['normalize_amounts']:
            return normalized

        # Amount fields to normalize
        amount_fields = ['MntNeto', 'MntExe', 'IVA', 'MntTotal', 'TasaIVA']

        for field in amount_fields:
            if field in normalized:
                original_value = normalized[field]
                normalized_value = self._normalize_amount(original_value, field)
                if normalized_value != original_value:
                    normalized[field] = normalized_value
                    actions.append(f"Normalized amount {field}")

        return normalized

    def _normalize_detalle(self, detalle: Union[Dict, List], actions: List[str]) -> List[Dict[str, Any]]:
        """Normalize detail items."""
        # Ensure detalle is a list
        if isinstance(detalle, dict):
            detalle = [detalle]
            actions.append("Converted single detail item to list")

        normalized_items = []
        for i, item in enumerate(detalle):
            normalized_item = self._normalize_detail_item(item, i, actions)
            normalized_items.append(normalized_item)

        return normalized_items

    def _normalize_detail_item(self, item: Dict[str, Any], index: int, actions: List[str]) -> Dict[str, Any]:
        """Normalize individual detail item."""
        normalized = item.copy()

        # Normalize item name
        if 'NmbItem' in normalized:
            original_name = normalized['NmbItem']
            normalized_name = self._normalize_text(original_name)
            if normalized_name != original_name:
                normalized['NmbItem'] = normalized_name
                actions.append(f"Normalized item {index+1} name")

        # Normalize numeric fields
        numeric_fields = ['QtyItem', 'PrcItem', 'MontoItem']
        for field in numeric_fields:
            if field in normalized:
                original_value = normalized[field]
                normalized_value = self._normalize_amount(original_value, field)
                if normalized_value != original_value:
                    normalized[field] = normalized_value
                    actions.append(f"Normalized item {index+1} {field}")

        # Add line number if missing
        if 'NroLinDet' not in normalized:
            normalized['NroLinDet'] = index + 1
            actions.append(f"Added line number to item {index+1}")

        return normalized

    def _normalize_referencia(self, referencia: Union[Dict, List], actions: List[str]) -> List[Dict[str, Any]]:
        """Normalize reference section."""
        # Ensure referencia is a list
        if isinstance(referencia, dict):
            referencia = [referencia]
            actions.append("Converted single reference to list")

        normalized_refs = []
        for i, ref in enumerate(referencia):
            normalized_ref = self._normalize_reference_item(ref, i, actions)
            normalized_refs.append(normalized_ref)

        return normalized_refs

    def _normalize_reference_item(self, ref: Dict[str, Any], index: int, actions: List[str]) -> Dict[str, Any]:
        """Normalize individual reference item."""
        normalized = ref.copy()

        # Normalize document type
        if 'TpoDocRef' in normalized:
            tipo_doc = normalized['TpoDocRef']
            if isinstance(tipo_doc, str) and tipo_doc.isdigit():
                normalized['TpoDocRef'] = int(tipo_doc)
                actions.append(f"Converted reference {index+1} TpoDocRef to integer")

        # Normalize folio
        if 'FolioRef' in normalized:
            folio = normalized['FolioRef']
            if isinstance(folio, str) and folio.isdigit():
                normalized['FolioRef'] = int(folio)
                actions.append(f"Converted reference {index+1} FolioRef to integer")

        # Normalize date
        if 'FchRef' in normalized and self.config['normalize_dates']:
            normalized['FchRef'] = self._normalize_date(normalized['FchRef'], actions, f'reference {index+1} FchRef')

        # Add line number if missing
        if 'NroLinRef' not in normalized:
            normalized['NroLinRef'] = index + 1
            actions.append(f"Added line number to reference {index+1}")

        return normalized

    def _normalize_rut(self, rut: str) -> str:
        """Normalize RUT format to XX.XXX.XXX-X."""
        if not isinstance(rut, str):
            return str(rut)

        # Remove all formatting
        clean_rut = re.sub(r'[^0-9kK]', '', rut.upper())

        # Validate minimum length
        if len(clean_rut) < 2:
            return rut  # Return original if too short

        # Split number and verification digit
        if len(clean_rut) > 1:
            number = clean_rut[:-1]
            dv = clean_rut[-1]

            # Format number with dots
            if len(number) > 6:
                formatted_number = f"{number[:-6]}.{number[-6:-3]}.{number[-3:]}"
            elif len(number) > 3:
                formatted_number = f"{number[:-3]}.{number[-3:]}"
            else:
                formatted_number = number

            return f"{formatted_number}-{dv}"

        return rut

    def _normalize_date(self, date_value: Any, actions: List[str], field_name: str) -> str:
        """Normalize date to standard format."""
        if isinstance(date_value, str):
            # Try to parse different date formats
            date_patterns = [
                '%Y-%m-%d',
                '%d-%m-%Y',
                '%d/%m/%Y',
                '%Y/%m/%d',
                '%d.%m.%Y',
                '%Y.%m.%d'
            ]

            for pattern in date_patterns:
                try:
                    parsed_date = datetime.strptime(date_value, pattern).date()
                    formatted_date = parsed_date.strftime(self.config['date_format'])
                    if formatted_date != date_value:
                        actions.append(f"Normalized date format for {field_name}")
                    return formatted_date
                except ValueError:
                    continue

            # If no pattern matched, return original
            return date_value

        elif isinstance(date_value, date):
            formatted_date = date_value.strftime(self.config['date_format'])
            actions.append(f"Converted date object to string for {field_name}")
            return formatted_date

        elif isinstance(date_value, datetime):
            formatted_date = date_value.date().strftime(self.config['date_format'])
            actions.append(f"Converted datetime to date string for {field_name}")
            return formatted_date

        else:
            return str(date_value)

    def _normalize_amount(self, amount: Any, field_name: str) -> Union[int, Decimal]:
        """Normalize monetary amount."""
        if isinstance(amount, str):
            # Remove currency symbols and thousand separators
            clean_amount = re.sub(r'[^\d.,\-+]', '', amount)
            # Replace comma with dot for decimal separator
            clean_amount = clean_amount.replace(',', '.')

            try:
                decimal_amount = Decimal(clean_amount)
            except Exception:
                return 0
        else:
            try:
                decimal_amount = Decimal(str(amount))
            except Exception:
                return 0

        # Round to configured decimal places
        decimal_places = self.config['decimal_places']
        if decimal_places == 0:
            return int(decimal_amount.quantize(Decimal('1')))
        else:
            quantizer = Decimal('0.' + '0' * decimal_places)
            return decimal_amount.quantize(quantizer)

    def _normalize_text(self, text: str) -> str:
        """Normalize text content."""
        if not isinstance(text, str):
            return str(text)

        normalized = text

        # Normalize case if configured
        if self.config['normalize_text_case']:
            # Title case for names, upper case for specific fields
            normalized = normalized.title()

        # Remove extra whitespace (already done in sanitizer, but ensure consistency)
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def should_process(self, document: BaseDocument, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if document needs normalization."""
        return context.get('enable_normalization', True) if context else True

    def validate_config(self) -> List[str]:
        """Validate worker configuration."""
        errors = []

        # Validate decimal places
        decimal_places = self.config.get('decimal_places')
        if decimal_places is not None and (not isinstance(decimal_places, int) or decimal_places < 0):
            errors.append("decimal_places must be a non-negative integer")

        # Validate date format
        date_format = self.config.get('date_format')
        if date_format is not None:
            try:
                datetime.now().strftime(date_format)
            except (ValueError, TypeError):
                errors.append("date_format must be a valid strftime format")

        return errors