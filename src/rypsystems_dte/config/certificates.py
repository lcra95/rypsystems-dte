"""
Certificate Management - Sistema de gestión de certificados digitales

Maneja el almacenamiento, validación y uso de certificados digitales
para la firma y autenticación con el SII.
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


class CertificateType(str, Enum):
    """Tipos de certificados"""
    SIGNING = "signing"  # Certificado para firma digital
    AUTHENTICATION = "authentication"  # Certificado para autenticación
    SSL_CLIENT = "ssl_client"  # Certificado SSL cliente
    CA_ROOT = "ca_root"  # Certificado CA raíz
    CA_INTERMEDIATE = "ca_intermediate"  # Certificado CA intermedio


class CertificateFormat(str, Enum):
    """Formatos de certificados soportados"""
    PEM = "pem"
    DER = "der"
    P12 = "p12"
    PFX = "pfx"


class CertificateStatus(str, Enum):
    """Estados de certificados"""
    VALID = "valid"
    EXPIRED = "expired"
    NOT_YET_VALID = "not_yet_valid"
    REVOKED = "revoked"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass
class CertificateInfo:
    """Información de un certificado"""
    subject: str
    issuer: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    fingerprint_sha1: str
    fingerprint_sha256: str
    public_key_algorithm: str
    signature_algorithm: str
    key_size: Optional[int] = None
    extensions: Dict[str, Any] = None


class CertificateConfig(BaseModel):
    """Configuración de un certificado específico"""
    model_config = ConfigDict(extra='allow')

    # Identificación
    name: str = Field(description="Nombre del certificado")
    certificate_type: CertificateType = Field(description="Tipo de certificado")
    description: Optional[str] = Field(None, description="Descripción del certificado")

    # Rutas de archivos
    certificate_path: str = Field(description="Ruta del archivo de certificado")
    private_key_path: Optional[str] = Field(None, description="Ruta de la llave privada")
    ca_bundle_path: Optional[str] = Field(None, description="Ruta del bundle CA")

    # Configuración de acceso
    password: Optional[str] = Field(None, description="Contraseña del certificado/llave")
    password_file: Optional[str] = Field(None, description="Archivo con contraseña")

    # Metadatos
    format: CertificateFormat = Field(default=CertificateFormat.PEM, description="Formato del certificado")
    rut_titular: Optional[str] = Field(None, description="RUT del titular")
    empresa: Optional[str] = Field(None, description="Empresa asociada")

    # Configuración de validación
    validate_chain: bool = Field(default=True, description="Validar cadena de certificados")
    check_revocation: bool = Field(default=True, description="Verificar revocación")
    allow_self_signed: bool = Field(default=False, description="Permitir certificados auto-firmados")

    # Configuración de uso
    auto_load: bool = Field(default=True, description="Cargar automáticamente al inicio")
    cache_duration: int = Field(default=3600, description="Duración del cache (segundos)")

    @field_validator('certificate_path', 'private_key_path', 'ca_bundle_path')
    @classmethod
    def validate_paths(cls, v):
        """Valida que las rutas existan"""
        if v is not None:
            path = Path(v).expanduser()
            if not path.exists():
                raise ValueError(f"Archivo no encontrado: {path}")
        return v

    def get_password(self) -> Optional[str]:
        """
        Obtiene la contraseña del certificado

        Returns:
            Contraseña del certificado
        """
        if self.password:
            return self.password
        elif self.password_file:
            try:
                return Path(self.password_file).read_text().strip()
            except Exception:
                return None
        return None


class CertificateStore(BaseModel):
    """
    Almacén de certificados digitales

    Gestiona múltiples certificados y sus configuraciones.
    """
    model_config = ConfigDict(extra='allow')

    # Configuración del store
    store_path: Optional[str] = Field(None, description="Ruta del directorio de certificados")
    default_format: CertificateFormat = Field(default=CertificateFormat.PEM)

    # Certificados registrados
    certificates: Dict[str, CertificateConfig] = Field(
        default_factory=dict,
        description="Certificados registrados"
    )

    # Configuración de validación global
    global_validation: bool = Field(default=True, description="Validación global habilitada")
    strict_mode: bool = Field(default=False, description="Modo estricto de validación")

    # Cache de certificados cargados
    _loaded_certificates: Dict[str, Any] = {}
    _certificate_info: Dict[str, CertificateInfo] = {}

    def add_certificate(self,
                       name: str,
                       certificate_path: str,
                       certificate_type: CertificateType,
                       **kwargs) -> bool:
        """
        Agrega un certificado al store

        Args:
            name: Nombre del certificado
            certificate_path: Ruta del certificado
            certificate_type: Tipo de certificado
            **kwargs: Configuración adicional

        Returns:
            True si se agregó exitosamente
        """
        try:
            config = CertificateConfig(
                name=name,
                certificate_path=certificate_path,
                certificate_type=certificate_type,
                **kwargs
            )

            self.certificates[name] = config

            # Auto-cargar si está habilitado
            if config.auto_load:
                return self.load_certificate(name)

            return True

        except Exception as e:
            print(f"Error adding certificate {name}: {e}")
            return False

    def remove_certificate(self, name: str) -> bool:
        """
        Remueve un certificado del store

        Args:
            name: Nombre del certificado

        Returns:
            True si se removió exitosamente
        """
        if name in self.certificates:
            del self.certificates[name]

            # Limpiar cache
            if name in self._loaded_certificates:
                del self._loaded_certificates[name]
            if name in self._certificate_info:
                del self._certificate_info[name]

            return True

        return False

    def load_certificate(self, name: str) -> bool:
        """
        Carga un certificado en memoria

        Args:
            name: Nombre del certificado

        Returns:
            True si se cargó exitosamente
        """
        if name not in self.certificates:
            return False

        config = self.certificates[name]

        try:
            # Aquí iría la carga real del certificado usando cryptography
            # Por ahora simulamos la carga
            cert_path = Path(config.certificate_path).expanduser()

            if not cert_path.exists():
                return False

            # Simular carga del certificado
            cert_data = {
                'path': str(cert_path),
                'type': config.certificate_type,
                'format': config.format,
                'loaded_at': datetime.now(timezone.utc)
            }

            self._loaded_certificates[name] = cert_data

            # Simular extracción de información del certificado
            self._certificate_info[name] = self._extract_certificate_info(cert_path, config)

            return True

        except Exception as e:
            print(f"Error loading certificate {name}: {e}")
            return False

    def get_certificate(self, name: str) -> Optional[Any]:
        """
        Obtiene un certificado cargado

        Args:
            name: Nombre del certificado

        Returns:
            Certificado cargado o None
        """
        if name in self._loaded_certificates:
            return self._loaded_certificates[name]

        # Intentar cargar si no está en cache
        if self.load_certificate(name):
            return self._loaded_certificates.get(name)

        return None

    def get_certificate_info(self, name: str) -> Optional[CertificateInfo]:
        """
        Obtiene información de un certificado

        Args:
            name: Nombre del certificado

        Returns:
            Información del certificado o None
        """
        if name not in self._certificate_info:
            self.load_certificate(name)

        return self._certificate_info.get(name)

    def validate_certificate(self, name: str) -> CertificateStatus:
        """
        Valida un certificado

        Args:
            name: Nombre del certificado

        Returns:
            Estado del certificado
        """
        info = self.get_certificate_info(name)
        if not info:
            return CertificateStatus.ERROR

        now = datetime.now(timezone.utc)

        # Verificar fechas de validez
        if now < info.not_before:
            return CertificateStatus.NOT_YET_VALID
        elif now > info.not_after:
            return CertificateStatus.EXPIRED

        # Aquí se harían más validaciones (revocación, cadena, etc.)
        return CertificateStatus.VALID

    def list_certificates(self, certificate_type: Optional[CertificateType] = None) -> List[str]:
        """
        Lista certificados registrados

        Args:
            certificate_type: Filtrar por tipo (opcional)

        Returns:
            Lista de nombres de certificados
        """
        if certificate_type is None:
            return list(self.certificates.keys())

        return [
            name for name, config in self.certificates.items()
            if config.certificate_type == certificate_type
        ]

    def get_signing_certificate(self) -> Optional[str]:
        """
        Obtiene el primer certificado de firma disponible

        Returns:
            Nombre del certificado de firma o None
        """
        signing_certs = self.list_certificates(CertificateType.SIGNING)
        return signing_certs[0] if signing_certs else None

    def get_authentication_certificate(self) -> Optional[str]:
        """
        Obtiene el primer certificado de autenticación disponible

        Returns:
            Nombre del certificado de autenticación o None
        """
        auth_certs = self.list_certificates(CertificateType.AUTHENTICATION)
        return auth_certs[0] if auth_certs else None

    def _extract_certificate_info(self, cert_path: Path, config: CertificateConfig) -> CertificateInfo:
        """
        Extrae información de un certificado

        Args:
            cert_path: Ruta del certificado
            config: Configuración del certificado

        Returns:
            Información del certificado
        """
        # Simulación de extracción de información
        # En implementación real se usaría cryptography library

        file_content = cert_path.read_bytes()
        sha1_hash = hashlib.sha1(file_content).hexdigest()
        sha256_hash = hashlib.sha256(file_content).hexdigest()

        return CertificateInfo(
            subject=f"CN=Mock Certificate {config.name}",
            issuer="CN=Mock CA",
            serial_number="123456789",
            not_before=datetime.now(timezone.utc),
            not_after=datetime(2025, 12, 31, tzinfo=timezone.utc),
            fingerprint_sha1=sha1_hash,
            fingerprint_sha256=sha256_hash,
            public_key_algorithm="RSA",
            signature_algorithm="SHA256withRSA",
            key_size=2048,
            extensions={}
        )


class CertificateValidator:
    """
    Validador de certificados digitales

    Proporciona funcionalidades avanzadas de validación de certificados.
    """

    def __init__(self, store: CertificateStore):
        """
        Inicializa el validador

        Args:
            store: Store de certificados
        """
        self.store = store

    def validate_certificate_chain(self, certificate_name: str) -> bool:
        """
        Valida la cadena de certificados

        Args:
            certificate_name: Nombre del certificado

        Returns:
            True si la cadena es válida
        """
        # Implementación simulada
        info = self.store.get_certificate_info(certificate_name)
        return info is not None

    def check_certificate_revocation(self, certificate_name: str) -> bool:
        """
        Verifica si un certificado está revocado

        Args:
            certificate_name: Nombre del certificado

        Returns:
            True si el certificado está revocado
        """
        # Implementación simulada - en producción consultar OCSP/CRL
        return False

    def validate_certificate_purpose(self,
                                   certificate_name: str,
                                   purpose: CertificateType) -> bool:
        """
        Valida si un certificado es válido para un propósito específico

        Args:
            certificate_name: Nombre del certificado
            purpose: Propósito deseado

        Returns:
            True si es válido para el propósito
        """
        if certificate_name not in self.store.certificates:
            return False

        config = self.store.certificates[certificate_name]
        return config.certificate_type == purpose

    def get_certificate_expiry_warning(self, certificate_name: str, days: int = 30) -> Optional[str]:
        """
        Obtiene advertencia si el certificado expira pronto

        Args:
            certificate_name: Nombre del certificado
            days: Días de anticipación para la advertencia

        Returns:
            Mensaje de advertencia o None
        """
        info = self.store.get_certificate_info(certificate_name)
        if not info:
            return None

        from datetime import timedelta
        warning_date = datetime.now(timezone.utc) + timedelta(days=days)

        if info.not_after <= warning_date:
            days_until_expiry = (info.not_after - datetime.now(timezone.utc)).days
            return f"Certificate '{certificate_name}' expires in {days_until_expiry} days"

        return None


# Store global de certificados
_certificate_store: Optional[CertificateStore] = None


def get_certificate_store() -> CertificateStore:
    """
    Obtiene el store global de certificados

    Returns:
        Store de certificados
    """
    global _certificate_store

    if _certificate_store is None:
        _certificate_store = CertificateStore()

        # Auto-descobrir certificados en ubicaciones comunes
        _auto_discover_certificates(_certificate_store)

    return _certificate_store


def set_certificate_store(store: CertificateStore) -> None:
    """
    Establece el store global de certificados

    Args:
        store: Nuevo store de certificados
    """
    global _certificate_store
    _certificate_store = store


def _auto_discover_certificates(store: CertificateStore) -> None:
    """
    Auto-descubre certificados en ubicaciones comunes

    Args:
        store: Store donde agregar certificados encontrados
    """
    common_paths = [
        "~/.rypsystems_dte/certificates/",
        "/etc/rypsystems_dte/certificates/",
        "./certificates/",
        "./certs/"
    ]

    for path_str in common_paths:
        path = Path(path_str).expanduser()
        if path.exists() and path.is_dir():
            for cert_file in path.glob("*.{pem,crt,cer,p12,pfx}"):
                if cert_file.is_file():
                    # Determinar tipo por nombre de archivo
                    name = cert_file.stem
                    cert_type = CertificateType.SIGNING

                    if "auth" in name.lower():
                        cert_type = CertificateType.AUTHENTICATION
                    elif "ssl" in name.lower():
                        cert_type = CertificateType.SSL_CLIENT

                    store.add_certificate(
                        name=name,
                        certificate_path=str(cert_file),
                        certificate_type=cert_type,
                        auto_load=False  # No auto-cargar certificados descubiertos
                    )


def load_certificate_config_from_dict(config_dict: Dict[str, Any]) -> CertificateStore:
    """
    Carga configuración de certificados desde diccionario

    Args:
        config_dict: Diccionario con configuración

    Returns:
        Store de certificados configurado
    """
    return CertificateStore.model_validate(config_dict)