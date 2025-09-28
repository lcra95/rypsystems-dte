"""
Excepciones específicas para servicios web del SII.

Define las excepciones específicas para manejar errores en la comunicación
con los servicios web del SII chileno.
"""

from typing import Optional, Dict, Any


class SiiWebServiceException(Exception):
    """Excepción base para errores de servicios web del SII."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        sii_response: Optional[Dict[str, Any]] = None,
        endpoint: Optional[str] = None
    ):
        """
        Initialize SII web service exception.

        Args:
            message: Error message
            error_code: SII error code if available
            sii_response: Full SII response if available
            endpoint: SII endpoint that caused the error
        """
        super().__init__(message)
        self.error_code = error_code
        self.sii_response = sii_response or {}
        self.endpoint = endpoint

    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.error_code:
            return f"{base_msg} (Código SII: {self.error_code})"
        return base_msg


class SiiAuthenticationError(SiiWebServiceException):
    """Error de autenticación con servicios SII."""

    def __init__(
        self,
        message: str = "Error de autenticación con SII",
        **kwargs
    ):
        super().__init__(message, **kwargs)


class SiiValidationError(SiiWebServiceException):
    """Error de validación de documentos en SII."""

    def __init__(
        self,
        message: str,
        validation_errors: Optional[list] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.validation_errors = validation_errors or []

    def get_validation_details(self) -> str:
        """Get formatted validation error details."""
        if not self.validation_errors:
            return "No hay detalles de validación disponibles"

        details = ["Errores de validación:"]
        for i, error in enumerate(self.validation_errors, 1):
            if isinstance(error, dict):
                code = error.get('codigo', 'N/A')
                desc = error.get('descripcion', str(error))
                details.append(f"  {i}. [{code}] {desc}")
            else:
                details.append(f"  {i}. {error}")

        return "\n".join(details)


class SiiCommunicationError(SiiWebServiceException):
    """Error de comunicación con servicios SII."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.status_code = status_code


class SiiTimeoutError(SiiWebServiceException):
    """Error de timeout en comunicación con SII."""

    def __init__(
        self,
        message: str = "Timeout en comunicación con SII",
        timeout_seconds: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds


class SiiDocumentRejectedError(SiiWebServiceException):
    """Error cuando SII rechaza un documento."""

    def __init__(
        self,
        message: str,
        rejection_reasons: Optional[list] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.rejection_reasons = rejection_reasons or []

    def get_rejection_details(self) -> str:
        """Get formatted rejection details."""
        if not self.rejection_reasons:
            return "No hay detalles de rechazo disponibles"

        details = ["Razones de rechazo:"]
        for i, reason in enumerate(self.rejection_reasons, 1):
            if isinstance(reason, dict):
                code = reason.get('codigo', 'N/A')
                desc = reason.get('descripcion', str(reason))
                details.append(f"  {i}. [{code}] {desc}")
            else:
                details.append(f"  {i}. {reason}")

        return "\n".join(details)


class SiiServiceUnavailableError(SiiWebServiceException):
    """Error cuando servicios SII no están disponibles."""

    def __init__(
        self,
        message: str = "Servicios SII no disponibles",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after  # Seconds to wait before retry


class SiiRateLimitError(SiiWebServiceException):
    """Error por límite de velocidad en API SII."""

    def __init__(
        self,
        message: str = "Límite de velocidad de API SII excedido",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class SiiMaintenanceError(SiiWebServiceException):
    """Error durante mantenimiento de servicios SII."""

    def __init__(
        self,
        message: str = "Servicios SII en mantenimiento",
        maintenance_window: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.maintenance_window = maintenance_window