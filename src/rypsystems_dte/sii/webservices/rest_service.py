"""
Servicio REST para comunicación con SII.

Implementa la comunicación REST con los servicios web modernos del SII chileno,
para operaciones que soportan API REST.
"""

import json
from typing import Dict, Any, Optional, List
import requests
from datetime import datetime, timedelta
import logging

from .sii_endpoints import SiiEndpoints, SiiEnvironment
from .exceptions import (
    SiiWebServiceException,
    SiiAuthenticationError,
    SiiCommunicationError,
    SiiTimeoutError,
    SiiValidationError,
    SiiRateLimitError
)


logger = logging.getLogger(__name__)


class RestService:
    """
    Servicio REST para comunicación con SII.

    Maneja la comunicación REST con los servicios web modernos del SII
    que soportan API REST para operaciones específicas como boletas.
    """

    def __init__(
        self,
        environment: SiiEnvironment = SiiEnvironment.CERTIFICACION,
        timeout: int = 30,
        retry_attempts: int = 3
    ):
        """
        Initialize REST service.

        Args:
            environment: SII environment
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
        """
        self.endpoints = SiiEndpoints(environment)
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.session = requests.Session()

        # Authentication state
        self.api_key = None
        self.api_secret = None
        self.access_token = None
        self.token_expiry = None

        # Configure session
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'rypsystems-dte/1.0.0'
        })

    def authenticate(self, rut_company: str, api_key: str, api_secret: str) -> str:
        """
        Autenticación usando API key y secret.

        Args:
            rut_company: RUT de la empresa
            api_key: Clave API del SII
            api_secret: Secret API del SII

        Returns:
            Token de acceso

        Raises:
            SiiAuthenticationError: Si falla la autenticación
        """
        try:
            # Store credentials
            self.api_key = api_key
            self.api_secret = api_secret

            # Prepare authentication request
            auth_data = {
                'rut_company': rut_company,
                'api_key': api_key,
                'api_secret': api_secret,
                'grant_type': 'client_credentials'
            }

            # Get base URL and make request
            base_url = self.endpoints.base_urls['rest']
            auth_url = f"{base_url}/auth/token"

            response = self._make_rest_request('POST', auth_url, data=auth_data)

            # Extract token
            access_token = response.get('access_token')
            if not access_token:
                raise SiiAuthenticationError("No se recibió token de acceso en respuesta")

            # Store token and expiry
            self.access_token = access_token
            expires_in = response.get('expires_in', 3600)  # Default 1 hour
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

            # Update session headers
            self.session.headers['Authorization'] = f'Bearer {access_token}'

            logger.info(f"Autenticación REST exitosa para RUT {rut_company}")
            return access_token

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiAuthenticationError(f"Error en autenticación REST: {str(e)}")

    def upload_boleta(
        self,
        rut_sender: str,
        rut_company: str,
        document_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Envía una boleta electrónica via REST.

        Args:
            rut_sender: RUT del emisor
            rut_company: RUT de la empresa
            document_data: Datos del documento

        Returns:
            Respuesta del SII

        Raises:
            SiiAuthenticationError: Si no hay token válido
            SiiValidationError: Si el documento es rechazado
        """
        self._ensure_authenticated()

        try:
            # Prepare request data
            payload = {
                'rut_sender': rut_sender,
                'rut_company': rut_company,
                'document': document_data,
                'timestamp': datetime.now().isoformat()
            }

            # Get upload URL
            rest_url = self.endpoints.get_rest_url('upload_dte')
            if not rest_url:
                raise SiiCommunicationError("Servicio REST no disponible para envío de documentos")

            # Send request
            response = self._make_rest_request('POST', rest_url, data=payload)

            logger.info(f"Boleta enviada exitosamente via REST para RUT {rut_sender}")
            return response

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiValidationError(f"Error enviando boleta via REST: {str(e)}")

    def query_document_status_rest(
        self,
        rut_sender: str,
        rut_company: str,
        document_type: int,
        folio: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Consulta estado de documento via REST.

        Args:
            rut_sender: RUT del emisor
            rut_company: RUT de la empresa
            document_type: Tipo de documento
            folio: Folio del documento
            date_from: Fecha desde (opcional)
            date_to: Fecha hasta (opcional)

        Returns:
            Estado del documento

        Raises:
            SiiAuthenticationError: Si no hay token válido
        """
        self._ensure_authenticated()

        try:
            # Prepare query parameters
            params = {
                'rut_sender': rut_sender,
                'rut_company': rut_company,
                'document_type': document_type,
                'folio': folio
            }

            if date_from:
                params['date_from'] = date_from
            if date_to:
                params['date_to'] = date_to

            # Get query URL
            rest_url = self.endpoints.get_rest_url('query_estado')
            if not rest_url:
                raise SiiCommunicationError("Servicio REST no disponible para consulta de estado")

            # Send request
            response = self._make_rest_request('GET', rest_url, params=params)

            logger.info(f"Estado consultado via REST para documento {document_type}-{folio}")
            return response

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiCommunicationError(f"Error consultando estado via REST: {str(e)}")

    def get_available_folios(
        self,
        rut_company: str,
        document_type: int
    ) -> Dict[str, Any]:
        """
        Consulta folios disponibles via REST.

        Args:
            rut_company: RUT de la empresa
            document_type: Tipo de documento

        Returns:
            Información de folios disponibles

        Raises:
            SiiAuthenticationError: Si no hay token válido
        """
        self._ensure_authenticated()

        try:
            params = {
                'rut_company': rut_company,
                'document_type': document_type
            }

            # Get folios URL
            rest_url = self.endpoints.get_rest_url('consulta_folios')
            if not rest_url:
                raise SiiCommunicationError("Servicio REST no disponible para consulta de folios")

            response = self._make_rest_request('GET', rest_url, params=params)

            logger.info(f"Folios consultados para tipo {document_type}")
            return response

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiCommunicationError(f"Error consultando folios: {str(e)}")

    def upload_bulk_documents(
        self,
        rut_sender: str,
        rut_company: str,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Envío masivo de documentos via REST.

        Args:
            rut_sender: RUT del emisor
            rut_company: RUT de la empresa
            documents: Lista de documentos

        Returns:
            Respuesta del envío masivo

        Raises:
            SiiAuthenticationError: Si no hay token válido
            SiiValidationError: Si hay errores en documentos
        """
        self._ensure_authenticated()

        if not documents:
            raise SiiValidationError("No se proporcionaron documentos para envío masivo")

        if len(documents) > 100:  # Límite típico del SII
            raise SiiValidationError("Demasiados documentos para envío masivo (máximo 100)")

        try:
            payload = {
                'rut_sender': rut_sender,
                'rut_company': rut_company,
                'documents': documents,
                'batch_size': len(documents),
                'timestamp': datetime.now().isoformat()
            }

            # Use upload endpoint for bulk
            rest_url = self.endpoints.get_rest_url('upload_dte')
            if not rest_url:
                raise SiiCommunicationError("Servicio REST no disponible para envío masivo")

            # Add bulk parameter
            bulk_url = f"{rest_url}/bulk"

            response = self._make_rest_request('POST', bulk_url, data=payload)

            logger.info(f"Envío masivo exitoso: {len(documents)} documentos")
            return response

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiValidationError(f"Error en envío masivo: {str(e)}")

    def get_consumption_report(
        self,
        rut_company: str,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """
        Obtiene reporte de consumo de folios.

        Args:
            rut_company: RUT de la empresa
            year: Año del reporte
            month: Mes del reporte

        Returns:
            Reporte de consumo

        Raises:
            SiiAuthenticationError: Si no hay token válido
        """
        self._ensure_authenticated()

        try:
            params = {
                'rut_company': rut_company,
                'year': year,
                'month': month
            }

            rest_url = self.endpoints.get_rest_url('reporte_consumo')
            if not rest_url:
                raise SiiCommunicationError("Servicio REST no disponible para reportes")

            response = self._make_rest_request('GET', rest_url, params=params)

            logger.info(f"Reporte de consumo obtenido para {month}/{year}")
            return response

        except Exception as e:
            if isinstance(e, SiiWebServiceException):
                raise
            raise SiiCommunicationError(f"Error obteniendo reporte: {str(e)}")

    def _make_rest_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Realiza una petición REST al SII.

        Args:
            method: Método HTTP
            url: URL del servicio
            data: Datos para POST/PUT
            params: Parámetros para GET

        Returns:
            Respuesta JSON del servidor

        Raises:
            SiiCommunicationError: Si hay error de comunicación
            SiiTimeoutError: Si hay timeout
            SiiRateLimitError: Si se excede límite de velocidad
        """
        for attempt in range(self.retry_attempts):
            try:
                logger.debug(f"Haciendo petición REST {method} a {url} (intento {attempt + 1})")

                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, timeout=self.timeout)
                elif method.upper() == 'POST':
                    response = self.session.post(url, json=data, timeout=self.timeout)
                elif method.upper() == 'PUT':
                    response = self.session.put(url, json=data, timeout=self.timeout)
                elif method.upper() == 'DELETE':
                    response = self.session.delete(url, timeout=self.timeout)
                else:
                    raise ValueError(f"Método HTTP no soportado: {method}")

                # Handle successful responses
                if response.status_code in [200, 201, 202]:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        return {'success': True, 'raw_response': response.text}

                # Handle specific error codes
                elif response.status_code == 401:
                    raise SiiAuthenticationError("Token de autenticación inválido o expirado")

                elif response.status_code == 429:
                    # Rate limit exceeded
                    retry_after = int(response.headers.get('Retry-After', 60))
                    raise SiiRateLimitError(
                        "Límite de velocidad de API excedido",
                        retry_after=retry_after
                    )

                elif response.status_code in [400, 422]:
                    # Validation errors
                    try:
                        error_data = response.json()
                        validation_errors = error_data.get('errors', [])
                        raise SiiValidationError(
                            error_data.get('message', 'Error de validación'),
                            validation_errors=validation_errors
                        )
                    except json.JSONDecodeError:
                        raise SiiValidationError(f"Error de validación: {response.text}")

                elif response.status_code in [500, 502, 503, 504]:
                    # Server errors, retry
                    if attempt == self.retry_attempts - 1:
                        raise SiiCommunicationError(
                            f"Error del servidor SII: HTTP {response.status_code}",
                            status_code=response.status_code,
                            endpoint=url
                        )
                    continue

                else:
                    raise SiiCommunicationError(
                        f"Error HTTP {response.status_code}: {response.text}",
                        status_code=response.status_code,
                        endpoint=url
                    )

            except requests.exceptions.Timeout:
                if attempt == self.retry_attempts - 1:
                    raise SiiTimeoutError(
                        f"Timeout después de {self.timeout} segundos",
                        timeout_seconds=self.timeout,
                        endpoint=url
                    )

            except requests.exceptions.ConnectionError as e:
                if attempt == self.retry_attempts - 1:
                    raise SiiCommunicationError(
                        f"Error de conexión: {str(e)}",
                        endpoint=url
                    )

        # Should not reach here
        raise SiiCommunicationError("Error inesperado en petición REST")

    def _ensure_authenticated(self):
        """
        Verifica que hay una sesión autenticada válida.

        Raises:
            SiiAuthenticationError: Si no hay autenticación válida
        """
        if not self.access_token:
            raise SiiAuthenticationError("No hay token de autenticación. Debe autenticarse primero.")

        # Check token expiry
        if self.token_expiry and datetime.now() >= self.token_expiry:
            raise SiiAuthenticationError("Token de autenticación expirado. Debe re-autenticarse.")

    def is_authenticated(self) -> bool:
        """Verifica si hay una sesión autenticada válida."""
        if not self.access_token:
            return False

        if self.token_expiry and datetime.now() >= self.token_expiry:
            return False

        return True

    def refresh_token(self) -> str:
        """
        Renueva el token de autenticación.

        Returns:
            Nuevo token de acceso

        Raises:
            SiiAuthenticationError: Si no se puede renovar
        """
        if not self.api_key or not self.api_secret:
            raise SiiAuthenticationError("No hay credenciales para renovar token")

        try:
            # Re-authenticate with stored credentials
            # This is a simplified approach - real implementation might use refresh tokens
            return self.authenticate("", self.api_key, self.api_secret)

        except Exception as e:
            raise SiiAuthenticationError(f"Error renovando token: {str(e)}")

    def logout(self):
        """Limpia token de autenticación."""
        self.access_token = None
        self.token_expiry = None
        self.api_key = None
        self.api_secret = None

        # Remove authorization header
        if 'Authorization' in self.session.headers:
            del self.session.headers['Authorization']

    def ping(self) -> bool:
        """
        Verifica conectividad con servicios REST del SII.

        Returns:
            True si hay conectividad
        """
        try:
            base_url = self.endpoints.base_urls['rest']
            ping_url = f"{base_url}/ping"

            response = self.session.get(ping_url, timeout=10)
            return response.status_code == 200

        except Exception:
            return False

    def get_service_info(self) -> Dict[str, Any]:
        """
        Obtiene información del servicio REST.

        Returns:
            Información del servicio y conectividad
        """
        return {
            'environment': self.endpoints.environment.value,
            'authenticated': self.is_authenticated(),
            'connectivity': self.ping(),
            'base_url': self.endpoints.base_urls['rest'],
            'timeout': self.timeout,
            'retry_attempts': self.retry_attempts,
            'token_expiry': self.token_expiry.isoformat() if self.token_expiry else None
        }

    def get_supported_operations(self) -> List[str]:
        """
        Obtiene lista de operaciones soportadas por REST API.

        Returns:
            Lista de operaciones disponibles
        """
        operations = []

        # Check which services support REST
        for service_name in self.endpoints.SERVICES.keys():
            if self.endpoints.supports_rest(service_name):
                operations.append(service_name)

        return operations