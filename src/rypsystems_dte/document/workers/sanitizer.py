"""
SanitizerWorker - Data cleaning and normalization.

Implements comprehensive data sanitization including text cleaning,
encoding normalization, dangerous character removal, and input validation.
"""

import re
import unicodedata
from typing import Dict, Any, List, Optional, Union
from decimal import Decimal, InvalidOperation
from datetime import datetime

from .base import BaseWorker, WorkerResult, WorkerStatus
from ...dte.document import BaseDocument


class SanitizerWorker(BaseWorker):
    """
    Sanitizer worker for data cleaning and normalization.

    Cleans and normalizes document data to ensure consistency,
    security, and compliance with SII requirements.
    """

    def __init__(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize sanitizer worker."""
        super().__init__(name, config)

        # Default sanitization rules
        self.default_config = {
            'normalize_unicode': True,
            'remove_dangerous_chars': True,
            'normalize_whitespace': True,
            'validate_encoding': True,
            'normalize_numbers': True,
            'normalize_dates': True,
            'max_string_length': 1000,
            'allowed_html_tags': [],
            'remove_control_chars': True,
            'normalize_rut_format': True
        }

        # Merge with provided config
        self.config = {**self.default_config, **(config or {})}

    def process(self, document: BaseDocument, context: Optional[Dict[str, Any]] = None) -> WorkerResult:
        """
        Sanitize document data.

        Args:
            document: Document to sanitize
            context: Sanitization context

        Returns:
            Sanitization result with cleaned document
        """
        result = WorkerResult(
            worker_name=self.name,
            status=WorkerStatus.SUCCESS,
            document=document
        )

        try:
            # Get document data
            datos = document.get_datos().copy()

            # Track sanitization actions
            sanitization_actions = []

            # Sanitize document data recursively
            sanitized_datos = self._sanitize_data(datos, sanitization_actions)

            # Update document if changes were made
            if sanitization_actions:
                # Update the document's internal data rather than creating new instance
                document._datos = sanitized_datos
                result.document = document

                result.data['sanitization_actions'] = sanitization_actions
                result.data['actions_count'] = len(sanitization_actions)

                result.add_info(
                    "data_sanitized",
                    f"Applied {len(sanitization_actions)} sanitization actions"
                )
            else:
                result.add_info("no_sanitization_needed", "No sanitization required")

        except Exception as e:
            self.logger.exception("Error during document sanitization")
            result.status = WorkerStatus.ERROR
            result.add_error(
                "sanitization_error",
                f"Error during sanitization: {str(e)}"
            )

        return result

    def _sanitize_data(self, data: Any, actions: List[str], path: str = "") -> Any:
        """
        Recursively sanitize data structure.

        Args:
            data: Data to sanitize
            actions: List to track sanitization actions
            path: Current data path for tracking

        Returns:
            Sanitized data
        """
        if isinstance(data, dict):
            return {key: self._sanitize_data(value, actions, f"{path}.{key}" if path else key)
                   for key, value in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_data(item, actions, f"{path}[{i}]")
                   for i, item in enumerate(data)]
        elif isinstance(data, str):
            return self._sanitize_string(data, actions, path)
        elif isinstance(data, (int, float, Decimal)):
            return self._sanitize_number(data, actions, path)
        else:
            return data

    def _sanitize_string(self, value: str, actions: List[str], path: str) -> str:
        """
        Sanitize string value.

        Args:
            value: String to sanitize
            actions: List to track actions
            path: Data path

        Returns:
            Sanitized string
        """
        original_value = value

        # Unicode normalization
        if self.config['normalize_unicode']:
            normalized = unicodedata.normalize('NFKC', value)
            if normalized != value:
                actions.append(f"Unicode normalized at {path}")
                value = normalized

        # Remove control characters
        if self.config['remove_control_chars']:
            cleaned = self._remove_control_characters(value)
            if cleaned != value:
                actions.append(f"Control characters removed at {path}")
                value = cleaned

        # Remove dangerous characters
        if self.config['remove_dangerous_chars']:
            safe = self._remove_dangerous_characters(value)
            if safe != value:
                actions.append(f"Dangerous characters removed at {path}")
                value = safe

        # Normalize whitespace
        if self.config['normalize_whitespace']:
            normalized_ws = self._normalize_whitespace(value)
            if normalized_ws != value:
                actions.append(f"Whitespace normalized at {path}")
                value = normalized_ws

        # Validate and fix encoding
        if self.config['validate_encoding']:
            encoding_fixed = self._fix_encoding_issues(value)
            if encoding_fixed != value:
                actions.append(f"Encoding issues fixed at {path}")
                value = encoding_fixed

        # Length validation
        max_length = self.config['max_string_length']
        if len(value) > max_length:
            value = value[:max_length]
            actions.append(f"String truncated at {path} (max: {max_length})")

        # Special field sanitization
        if path.endswith('RUTEmisor') or path.endswith('RUTRecep'):
            sanitized_rut = self._sanitize_rut(value)
            if sanitized_rut != value:
                actions.append(f"RUT normalized at {path}")
                value = sanitized_rut

        return value

    def _sanitize_number(self, value: Union[int, float, Decimal], actions: List[str], path: str) -> Union[int, float, Decimal]:
        """
        Sanitize numeric value.

        Args:
            value: Number to sanitize
            actions: List to track actions
            path: Data path

        Returns:
            Sanitized number
        """
        if not self.config['normalize_numbers']:
            return value

        try:
            # Convert to Decimal for precise handling
            if isinstance(value, str):
                # Clean string representation
                cleaned_str = re.sub(r'[^\d.,\-+]', '', value)
                # Normalize decimal separator (use dot)
                cleaned_str = cleaned_str.replace(',', '.')
                decimal_value = Decimal(cleaned_str)
            else:
                decimal_value = Decimal(str(value))

            # Validate reasonable ranges for money amounts
            if path.endswith(('Mnt', 'IVA', 'Total', 'PrcItem')):
                if decimal_value < 0 and not path.endswith('PrcItem'):
                    # Only allow negative prices for discounts
                    actions.append(f"Negative amount corrected at {path}")
                    decimal_value = abs(decimal_value)

                # Check for unreasonably large amounts
                max_amount = Decimal('999999999999')  # 999 billion
                if decimal_value > max_amount:
                    actions.append(f"Amount capped at {path}")
                    decimal_value = max_amount

            # Round to appropriate precision (usually 0 decimal places for Chilean pesos)
            if path.endswith(('Mnt', 'IVA', 'Total', 'PrcItem')):
                rounded_value = decimal_value.quantize(Decimal('1'))
                if rounded_value != decimal_value:
                    actions.append(f"Amount rounded at {path}")
                    decimal_value = rounded_value

            # Return as appropriate type
            if isinstance(value, int):
                return int(decimal_value)
            elif isinstance(value, float):
                return float(decimal_value)
            else:
                return decimal_value

        except (InvalidOperation, ValueError) as e:
            actions.append(f"Invalid number format corrected at {path}: {str(e)}")
            return 0

    def _remove_control_characters(self, text: str) -> str:
        """Remove control characters except common ones."""
        # Keep tab, newline, carriage return
        allowed_control = {'\t', '\n', '\r'}
        return ''.join(char for char in text
                      if not unicodedata.category(char).startswith('C') or char in allowed_control)

    def _remove_dangerous_characters(self, text: str) -> str:
        """Remove potentially dangerous characters."""
        # Remove common injection patterns
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',                # JavaScript URLs
            r'vbscript:',                 # VBScript URLs
            r'onload\s*=',                # Event handlers
            r'onerror\s*=',
            r'onclick\s*=',
        ]

        for pattern in dangerous_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

        # Remove null bytes and other dangerous characters
        text = text.replace('\x00', '')
        text = text.replace('\ufeff', '')  # BOM

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace characters."""
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def _fix_encoding_issues(self, text: str) -> str:
        """Fix common encoding issues."""
        # Common encoding fixes for Chilean text
        encoding_fixes = {
            'Ã±': 'ñ',
            'Ã¡': 'á',
            'Ã©': 'é',
            'Ã­': 'í',
            'Ã³': 'ó',
            'Ãº': 'ú',
            'Ã': 'Á',
            'Ã‰': 'É',
            'Ã': 'Í',
            'Ã"': 'Ó',
            'Ãš': 'Ú',
            'Ã¼': 'ü',
            'Ã': 'Ü',
        }

        for wrong, correct in encoding_fixes.items():
            text = text.replace(wrong, correct)

        return text

    def _sanitize_rut(self, rut: str) -> str:
        """
        Sanitize and normalize RUT format.

        Args:
            rut: RUT string to sanitize

        Returns:
            Normalized RUT
        """
        if not self.config['normalize_rut_format']:
            return rut

        # Remove all non-alphanumeric characters except hyphen
        clean_rut = re.sub(r'[^0-9kK\-]', '', rut.upper())

        # Ensure proper format: 12345678-9
        if '-' not in clean_rut and len(clean_rut) > 1:
            # Add hyphen before last character
            clean_rut = clean_rut[:-1] + '-' + clean_rut[-1]

        return clean_rut

    def _sanitize_html(self, text: str) -> str:
        """Remove or escape HTML content."""
        allowed_tags = self.config.get('allowed_html_tags', [])

        if not allowed_tags:
            # Remove all HTML tags
            text = re.sub(r'<[^>]+>', '', text)
        else:
            # Remove only non-allowed tags
            # This is a simplified implementation
            # For production, use a proper HTML sanitizer like bleach
            allowed_pattern = '|'.join(re.escape(tag) for tag in allowed_tags)
            disallowed_pattern = f'<(?!/?(?:{allowed_pattern})\\b)[^>]+>'
            text = re.sub(disallowed_pattern, '', text, flags=re.IGNORECASE)

        # Decode HTML entities
        html_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&apos;': "'",
        }

        for entity, char in html_entities.items():
            text = text.replace(entity, char)

        return text

    def should_process(self, document: BaseDocument, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if document needs sanitization."""
        # Always process unless explicitly disabled
        return context.get('enable_sanitization', True) if context else True

    def validate_config(self) -> List[str]:
        """Validate worker configuration."""
        errors = []

        # Validate max string length
        max_length = self.config.get('max_string_length')
        if max_length is not None and (not isinstance(max_length, int) or max_length <= 0):
            errors.append("max_string_length must be a positive integer")

        # Validate allowed HTML tags
        allowed_tags = self.config.get('allowed_html_tags')
        if allowed_tags is not None and not isinstance(allowed_tags, list):
            errors.append("allowed_html_tags must be a list")

        return errors