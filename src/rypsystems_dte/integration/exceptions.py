"""
Exception classes for SII integration.

Defines specific exceptions for different types of failures when
communicating with Chilean SII web services.
"""

from typing import Optional, Dict, Any


class IntegrationException(Exception):
    """Base exception for SII integration errors."""

    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class SiiConnectionException(IntegrationException):
    """Exception raised when connection to SII fails."""

    def __init__(self, message: str, endpoint: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message, "SII_CONNECTION_ERROR")
        self.endpoint = endpoint
        self.status_code = status_code


class SiiAuthenticationException(IntegrationException):
    """Exception raised when SII authentication fails."""

    def __init__(self, message: str, token: Optional[str] = None):
        super().__init__(message, "SII_AUTH_ERROR")
        self.token = token


class SiiValidationException(IntegrationException):
    """Exception raised when SII validates and rejects a document."""

    def __init__(self, message: str, validation_errors: Optional[list] = None, document_id: Optional[str] = None):
        super().__init__(message, "SII_VALIDATION_ERROR")
        self.validation_errors = validation_errors or []
        self.document_id = document_id


class SiiTimeoutException(IntegrationException):
    """Exception raised when SII operations timeout."""

    def __init__(self, message: str, timeout_seconds: Optional[int] = None):
        super().__init__(message, "SII_TIMEOUT_ERROR")
        self.timeout_seconds = timeout_seconds


class SiiBusinessException(IntegrationException):
    """Exception raised for SII business rule violations."""

    def __init__(self, message: str, business_code: Optional[str] = None, rule_description: Optional[str] = None):
        super().__init__(message, "SII_BUSINESS_ERROR")
        self.business_code = business_code
        self.rule_description = rule_description