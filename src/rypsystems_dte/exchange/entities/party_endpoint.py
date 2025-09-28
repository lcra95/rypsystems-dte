"""
Party Endpoint Entity - Entidad endpoint de participante

Traducción de PartyEndpoint de LibreDTE PHP.
Representa el endpoint de un participante en el intercambio de documentos.
"""

from typing import Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from ...sii.base import Contribuyente


class PartyEndpoint(BaseModel):
    """
    Entidad que representa el endpoint de un participante en el intercambio.

    Maneja la información de conexión y comunicación con un participante
    del intercambio de documentos tributarios electrónicos.
    """

    contribuyente: Contribuyente = Field(
        ...,
        description="Contribuyente asociado al endpoint"
    )

    endpoint_url: str = Field(
        ...,
        description="URL del endpoint",
        max_length=500
    )

    endpoint_type: str = Field(
        "rest",
        description="Tipo de endpoint (rest, soap, etc.)",
        max_length=50
    )

    authentication_type: str = Field(
        "none",
        description="Tipo de autenticación (none, basic, bearer, certificate)",
        max_length=50
    )

    username: Optional[str] = Field(
        None,
        description="Usuario para autenticación",
        max_length=100
    )

    password: Optional[str] = Field(
        None,
        description="Contraseña para autenticación",
        max_length=255
    )

    api_key: Optional[str] = Field(
        None,
        description="API key para autenticación",
        max_length=255
    )

    certificate_path: Optional[str] = Field(
        None,
        description="Ruta al certificado para autenticación",
        max_length=255
    )

    private_key_path: Optional[str] = Field(
        None,
        description="Ruta a la clave privada",
        max_length=255
    )

    timeout: int = Field(
        30,
        description="Timeout en segundos para las conexiones",
        ge=1,
        le=300
    )

    retry_attempts: int = Field(
        3,
        description="Número de intentos de reintento",
        ge=0,
        le=10
    )

    is_active: bool = Field(
        True,
        description="Si el endpoint está activo"
    )

    last_connection: Optional[datetime] = Field(
        None,
        description="Última conexión exitosa"
    )

    extra_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Headers adicionales para las requests"
    )

    extra_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parámetros adicionales del endpoint"
    )

    @validator('endpoint_url')
    def validate_url(cls, v):
        """Valida que la URL sea válida."""
        import re
        url_pattern = r'^https?://.+'
        if not re.match(url_pattern, v):
            raise ValueError("endpoint_url debe ser una URL válida (http:// o https://)")
        return v

    @validator('endpoint_type')
    def validate_endpoint_type(cls, v):
        """Valida el tipo de endpoint."""
        valid_types = ['rest', 'soap', 'graphql', 'websocket']
        if v.lower() not in valid_types:
            raise ValueError(f"endpoint_type debe ser uno de: {', '.join(valid_types)}")
        return v.lower()

    @validator('authentication_type')
    def validate_auth_type(cls, v):
        """Valida el tipo de autenticación."""
        valid_types = ['none', 'basic', 'bearer', 'api_key', 'certificate']
        if v.lower() not in valid_types:
            raise ValueError(f"authentication_type debe ser uno de: {', '.join(valid_types)}")
        return v.lower()

    def get_id(self) -> str:
        """
        Obtiene el ID único del endpoint.

        Returns:
            ID único del endpoint basado en RUT del contribuyente
        """
        return f"endpoint_{self.contribuyente.get_rut()}"

    def get_rut(self) -> str:
        """
        Obtiene el RUT del contribuyente asociado.

        Returns:
            RUT del contribuyente
        """
        return self.contribuyente.get_rut()

    def get_name(self) -> str:
        """
        Obtiene el nombre del contribuyente asociado.

        Returns:
            Nombre del contribuyente
        """
        return self.contribuyente.razon_social

    def requires_authentication(self) -> bool:
        """
        Verifica si el endpoint requiere autenticación.

        Returns:
            True si requiere autenticación, False en caso contrario
        """
        return self.authentication_type != 'none'

    def has_basic_auth(self) -> bool:
        """
        Verifica si el endpoint usa autenticación básica.

        Returns:
            True si usa basic auth, False en caso contrario
        """
        return (
            self.authentication_type == 'basic' and
            self.username is not None and
            self.password is not None
        )

    def has_api_key(self) -> bool:
        """
        Verifica si el endpoint usa API key.

        Returns:
            True si usa API key, False en caso contrario
        """
        return self.authentication_type == 'api_key' and self.api_key is not None

    def has_certificate_auth(self) -> bool:
        """
        Verifica si el endpoint usa autenticación por certificado.

        Returns:
            True si usa certificado, False en caso contrario
        """
        return (
            self.authentication_type == 'certificate' and
            self.certificate_path is not None and
            self.private_key_path is not None
        )

    def is_ready_for_connection(self) -> bool:
        """
        Verifica si el endpoint está listo para establecer conexión.

        Returns:
            True si está listo, False en caso contrario
        """
        if not self.is_active:
            return False

        if not self.requires_authentication():
            return True

        if self.authentication_type == 'basic':
            return self.has_basic_auth()
        elif self.authentication_type == 'api_key':
            return self.has_api_key()
        elif self.authentication_type == 'certificate':
            return self.has_certificate_auth()
        elif self.authentication_type == 'bearer':
            return self.api_key is not None

        return False

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Obtiene los headers de autenticación.

        Returns:
            Diccionario con los headers de autenticación
        """
        headers = {}

        if self.authentication_type == 'basic' and self.has_basic_auth():
            import base64
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_credentials}"

        elif self.authentication_type in ['bearer', 'api_key'] and self.api_key:
            if self.authentication_type == 'bearer':
                headers['Authorization'] = f"Bearer {self.api_key}"
            else:
                headers['X-API-Key'] = self.api_key

        # Agregar headers adicionales
        headers.update(self.extra_headers)

        return headers

    def update_last_connection(self):
        """Actualiza la timestamp de la última conexión."""
        self.last_connection = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte la entidad a diccionario.

        Returns:
            Diccionario con los datos del endpoint
        """
        return {
            'rut': self.get_rut(),
            'name': self.get_name(),
            'endpoint_url': self.endpoint_url,
            'endpoint_type': self.endpoint_type,
            'authentication_type': self.authentication_type,
            'is_active': self.is_active,
            'timeout': self.timeout,
            'retry_attempts': self.retry_attempts,
            'requires_auth': self.requires_authentication(),
            'is_ready': self.is_ready_for_connection(),
            'last_connection': self.last_connection.isoformat() if self.last_connection else None,
            'extra_params': self.extra_params
        }

    class Config:
        """Configuración de Pydantic."""
        arbitrary_types_allowed = True
        validate_assignment = True