"""
Configuration Validation - Sistema de validación de configuraciones

Valida configuraciones antes de su uso para prevenir errores de runtime
y asegurar consistencia entre componentes.
"""

import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, ValidationError as PydanticValidationError


class ValidationType(str, Enum):
    """Tipos de validación"""
    REQUIRED = "required"
    TYPE_CHECK = "type_check"
    RANGE = "range"
    REGEX = "regex"
    FILE_EXISTS = "file_exists"
    URL_FORMAT = "url_format"
    EMAIL_FORMAT = "email_format"
    RUT_FORMAT = "rut_format"
    CUSTOM = "custom"


class ValidationSeverity(str, Enum):
    """Severidad de errores de validación"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Resultado de una validación"""
    is_valid: bool
    severity: ValidationSeverity
    message: str
    field_path: str
    suggested_fix: Optional[str] = None


class ValidationRule(BaseModel):
    """Regla de validación para configuraciones"""
    model_config = ConfigDict(extra='allow')

    # Identificación
    name: str = Field(description="Nombre de la regla")
    field_path: str = Field(description="Ruta del campo a validar")
    validation_type: ValidationType = Field(description="Tipo de validación")

    # Configuración de la regla
    required: bool = Field(default=True, description="Si el campo es requerido")
    severity: ValidationSeverity = Field(default=ValidationSeverity.ERROR)

    # Configuración específica por tipo
    expected_type: Optional[str] = Field(None, description="Tipo esperado")
    min_value: Optional[Union[int, float]] = Field(None, description="Valor mínimo")
    max_value: Optional[Union[int, float]] = Field(None, description="Valor máximo")
    regex_pattern: Optional[str] = Field(None, description="Patrón regex")
    allowed_values: List[Any] = Field(default_factory=list, description="Valores permitidos")

    # Mensajes personalizados
    error_message: Optional[str] = Field(None, description="Mensaje de error personalizado")
    suggested_fix: Optional[str] = Field(None, description="Fix sugerido")

    # Función de validación personalizada
    custom_validator: Optional[Callable] = Field(None, description="Validador personalizado")

    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Ejecuta la validación

        Args:
            config: Configuración a validar

        Returns:
            Resultado de la validación
        """
        # Obtener valor del campo
        value = self._get_nested_value(config, self.field_path)

        # Validar requerido
        if value is None:
            if self.required:
                return ValidationResult(
                    is_valid=False,
                    severity=self.severity,
                    message=self.error_message or f"Required field '{self.field_path}' is missing",
                    field_path=self.field_path,
                    suggested_fix=self.suggested_fix or f"Add '{self.field_path}' to configuration"
                )
            else:
                return ValidationResult(
                    is_valid=True,
                    severity=ValidationSeverity.INFO,
                    message=f"Optional field '{self.field_path}' is not set",
                    field_path=self.field_path
                )

        # Ejecutar validación específica
        if self.validation_type == ValidationType.TYPE_CHECK:
            return self._validate_type(value)
        elif self.validation_type == ValidationType.RANGE:
            return self._validate_range(value)
        elif self.validation_type == ValidationType.REGEX:
            return self._validate_regex(value)
        elif self.validation_type == ValidationType.FILE_EXISTS:
            return self._validate_file_exists(value)
        elif self.validation_type == ValidationType.URL_FORMAT:
            return self._validate_url_format(value)
        elif self.validation_type == ValidationType.EMAIL_FORMAT:
            return self._validate_email_format(value)
        elif self.validation_type == ValidationType.RUT_FORMAT:
            return self._validate_rut_format(value)
        elif self.validation_type == ValidationType.CUSTOM:
            return self._validate_custom(value)

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Field '{self.field_path}' is valid",
            field_path=self.field_path
        )

    def _get_nested_value(self, config: Dict[str, Any], path: str) -> Any:
        """Obtiene valor usando notación de punto"""
        keys = path.split('.')
        value = config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def _validate_type(self, value: Any) -> ValidationResult:
        """Valida el tipo del valor"""
        if not self.expected_type:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message=f"No type specified for '{self.field_path}'",
                field_path=self.field_path
            )

        type_map = {
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict
        }

        expected_type_class = type_map.get(self.expected_type.lower())
        if not expected_type_class:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Unknown expected type: {self.expected_type}",
                field_path=self.field_path
            )

        if not isinstance(value, expected_type_class):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=self.error_message or f"Field '{self.field_path}' must be of type {self.expected_type}, got {type(value).__name__}",
                field_path=self.field_path,
                suggested_fix=self.suggested_fix or f"Convert value to {self.expected_type}"
            )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Field '{self.field_path}' has correct type",
            field_path=self.field_path
        )

    def _validate_range(self, value: Any) -> ValidationResult:
        """Valida rango numérico"""
        if not isinstance(value, (int, float)):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=f"Field '{self.field_path}' must be numeric for range validation",
                field_path=self.field_path
            )

        if self.min_value is not None and value < self.min_value:
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=self.error_message or f"Field '{self.field_path}' value {value} is below minimum {self.min_value}",
                field_path=self.field_path,
                suggested_fix=self.suggested_fix or f"Set value to at least {self.min_value}"
            )

        if self.max_value is not None and value > self.max_value:
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=self.error_message or f"Field '{self.field_path}' value {value} is above maximum {self.max_value}",
                field_path=self.field_path,
                suggested_fix=self.suggested_fix or f"Set value to at most {self.max_value}"
            )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Field '{self.field_path}' is within valid range",
            field_path=self.field_path
        )

    def _validate_regex(self, value: Any) -> ValidationResult:
        """Valida patrón regex"""
        if not self.regex_pattern:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message=f"No regex pattern specified for '{self.field_path}'",
                field_path=self.field_path
            )

        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=f"Field '{self.field_path}' must be string for regex validation",
                field_path=self.field_path
            )

        if not re.match(self.regex_pattern, value):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=self.error_message or f"Field '{self.field_path}' does not match pattern {self.regex_pattern}",
                field_path=self.field_path,
                suggested_fix=self.suggested_fix or f"Adjust value to match pattern {self.regex_pattern}"
            )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Field '{self.field_path}' matches required pattern",
            field_path=self.field_path
        )

    def _validate_file_exists(self, value: Any) -> ValidationResult:
        """Valida que el archivo existe"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=f"Field '{self.field_path}' must be string for file validation",
                field_path=self.field_path
            )

        file_path = Path(value).expanduser()
        if not file_path.exists():
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=self.error_message or f"File '{value}' specified in '{self.field_path}' does not exist",
                field_path=self.field_path,
                suggested_fix=self.suggested_fix or f"Create file at {value} or update path"
            )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"File '{value}' exists",
            field_path=self.field_path
        )

    def _validate_url_format(self, value: Any) -> ValidationResult:
        """Valida formato de URL"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=f"Field '{self.field_path}' must be string for URL validation",
                field_path=self.field_path
            )

        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, value):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=self.error_message or f"Field '{self.field_path}' is not a valid URL",
                field_path=self.field_path,
                suggested_fix=self.suggested_fix or "Use format: http://example.com or https://example.com"
            )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Field '{self.field_path}' is a valid URL",
            field_path=self.field_path
        )

    def _validate_email_format(self, value: Any) -> ValidationResult:
        """Valida formato de email"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=f"Field '{self.field_path}' must be string for email validation",
                field_path=self.field_path
            )

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=self.error_message or f"Field '{self.field_path}' is not a valid email",
                field_path=self.field_path,
                suggested_fix=self.suggested_fix or "Use format: user@domain.com"
            )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Field '{self.field_path}' is a valid email",
            field_path=self.field_path
        )

    def _validate_rut_format(self, value: Any) -> ValidationResult:
        """Valida formato de RUT chileno"""
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=f"Field '{self.field_path}' must be string for RUT validation",
                field_path=self.field_path
            )

        # Formato básico de RUT: XXXXXXXX-X
        rut_pattern = r'^\d{7,8}-[0-9K]$'
        if not re.match(rut_pattern, value):
            return ValidationResult(
                is_valid=False,
                severity=self.severity,
                message=self.error_message or f"Field '{self.field_path}' is not a valid RUT format",
                field_path=self.field_path,
                suggested_fix=self.suggested_fix or "Use format: 12345678-9 or 1234567-K"
            )

        return ValidationResult(
            is_valid=True,
            severity=ValidationSeverity.INFO,
            message=f"Field '{self.field_path}' has valid RUT format",
            field_path=self.field_path
        )

    def _validate_custom(self, value: Any) -> ValidationResult:
        """Ejecuta validador personalizado"""
        if not self.custom_validator:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message=f"No custom validator specified for '{self.field_path}'",
                field_path=self.field_path
            )

        try:
            result = self.custom_validator(value)
            if isinstance(result, bool):
                return ValidationResult(
                    is_valid=result,
                    severity=self.severity if not result else ValidationSeverity.INFO,
                    message=self.error_message or f"Custom validation {'passed' if result else 'failed'} for '{self.field_path}'",
                    field_path=self.field_path,
                    suggested_fix=self.suggested_fix
                )
            elif isinstance(result, ValidationResult):
                return result
            else:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Custom validator returned invalid type for '{self.field_path}'",
                    field_path=self.field_path
                )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Custom validator failed for '{self.field_path}': {e}",
                field_path=self.field_path
            )


class ConfigValidator(BaseModel):
    """
    Validador de configuraciones

    Ejecuta múltiples reglas de validación sobre configuraciones.
    """
    model_config = ConfigDict(extra='allow')

    # Reglas de validación
    rules: List[ValidationRule] = Field(default_factory=list, description="Reglas de validación")

    # Configuración del validador
    fail_on_warning: bool = Field(default=False, description="Fallar en warnings")
    collect_all_errors: bool = Field(default=True, description="Recolectar todos los errores")

    def add_rule(self, rule: ValidationRule) -> None:
        """
        Agrega una regla de validación

        Args:
            rule: Regla a agregar
        """
        self.rules.append(rule)

    def add_required_field(self, field_path: str, expected_type: str = None) -> None:
        """
        Agrega regla para campo requerido

        Args:
            field_path: Ruta del campo
            expected_type: Tipo esperado (opcional)
        """
        rule = ValidationRule(
            name=f"required_{field_path}",
            field_path=field_path,
            validation_type=ValidationType.REQUIRED,
            required=True
        )

        if expected_type:
            rule.validation_type = ValidationType.TYPE_CHECK
            rule.expected_type = expected_type

        self.add_rule(rule)

    def add_file_check(self, field_path: str, required: bool = True) -> None:
        """
        Agrega regla para verificar que archivo existe

        Args:
            field_path: Ruta del campo
            required: Si es requerido
        """
        rule = ValidationRule(
            name=f"file_check_{field_path}",
            field_path=field_path,
            validation_type=ValidationType.FILE_EXISTS,
            required=required
        )
        self.add_rule(rule)

    def add_url_check(self, field_path: str, required: bool = True) -> None:
        """
        Agrega regla para verificar formato URL

        Args:
            field_path: Ruta del campo
            required: Si es requerido
        """
        rule = ValidationRule(
            name=f"url_check_{field_path}",
            field_path=field_path,
            validation_type=ValidationType.URL_FORMAT,
            required=required
        )
        self.add_rule(rule)

    def validate(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """
        Valida configuración completa

        Args:
            config: Configuración a validar

        Returns:
            Lista de resultados de validación
        """
        results = []

        for rule in self.rules:
            try:
                result = rule.validate(config)
                results.append(result)

                # Si no recolectamos todos los errores, parar en el primer error
                if not self.collect_all_errors and not result.is_valid:
                    break

            except Exception as e:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Validation rule '{rule.name}' failed: {e}",
                    field_path=rule.field_path
                ))

        return results

    def is_valid(self, config: Dict[str, Any]) -> bool:
        """
        Verifica si configuración es válida

        Args:
            config: Configuración a validar

        Returns:
            True si es válida
        """
        results = self.validate(config)

        for result in results:
            if not result.is_valid:
                if result.severity == ValidationSeverity.ERROR:
                    return False
                elif result.severity == ValidationSeverity.WARNING and self.fail_on_warning:
                    return False

        return True

    def get_errors(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """
        Obtiene solo los errores de validación

        Args:
            config: Configuración a validar

        Returns:
            Lista de errores
        """
        results = self.validate(config)
        return [r for r in results if not r.is_valid]

    def get_warnings(self, config: Dict[str, Any]) -> List[ValidationResult]:
        """
        Obtiene solo los warnings de validación

        Args:
            config: Configuración a validar

        Returns:
            Lista de warnings
        """
        results = self.validate(config)
        return [r for r in results if not r.is_valid and r.severity == ValidationSeverity.WARNING]


class ValidationError(Exception):
    """Excepción para errores de validación de configuración"""

    def __init__(self, message: str, validation_results: List[ValidationResult] = None):
        """
        Inicializa la excepción

        Args:
            message: Mensaje de error
            validation_results: Resultados de validación
        """
        super().__init__(message)
        self.validation_results = validation_results or []


def create_default_validator() -> ConfigValidator:
    """
    Crea un validador con reglas por defecto

    Returns:
        Validador configurado
    """
    validator = ConfigValidator()

    # Reglas básicas del sistema
    validator.add_required_field("environment", "str")
    validator.add_required_field("logging.level", "str")

    # Reglas para SII
    validator.add_url_check("sii.endpoints.get_token.url", required=False)
    validator.add_url_check("sii.endpoints.send_dte.url", required=False)

    # Reglas para certificados
    validator.add_file_check("sii.authentication.certificate_path", required=False)
    validator.add_file_check("sii.authentication.private_key_path", required=False)

    # Reglas para base de datos
    validator.add_required_field("database.host", "str")
    validator.add_rule(ValidationRule(
        name="database_port_range",
        field_path="database.port",
        validation_type=ValidationType.RANGE,
        min_value=1,
        max_value=65535,
        required=False
    ))

    return validator


def validate_config(config: Dict[str, Any],
                   validator: Optional[ConfigValidator] = None,
                   raise_on_error: bool = True) -> List[ValidationResult]:
    """
    Función conveniente para validar configuración

    Args:
        config: Configuración a validar
        validator: Validador a usar (opcional)
        raise_on_error: Si lanzar excepción en errores

    Returns:
        Lista de resultados de validación

    Raises:
        ValidationError: Si hay errores y raise_on_error es True
    """
    if validator is None:
        validator = create_default_validator()

    results = validator.validate(config)

    if raise_on_error:
        errors = [r for r in results if not r.is_valid and r.severity == ValidationSeverity.ERROR]
        if errors:
            error_messages = [f"{r.field_path}: {r.message}" for r in errors]
            raise ValidationError(
                f"Configuration validation failed with {len(errors)} errors:\n" + "\n".join(error_messages),
                errors
            )

    return results