"""
Certificado digital para firma electrónica de documentos tributarios.

Traducción de derafu/certificate (Certificate, CertificateLoader y
SelfSignedCertificate) usada por LibreDTE Core para firmar DTE, sobres de
envío y la solicitud de token al SII.
"""

import base64
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Union

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ExtensionOID

from ..errors import RypDteError


class CertificateError(RypDteError):
    """Error al cargar o usar un certificado digital."""


def _int_to_base64(value: int, wordwrap: int = 64) -> str:
    """Codifica un entero (módulo o exponente RSA) en base64 big-endian."""
    raw = value.to_bytes((value.bit_length() + 7) // 8, 'big')
    encoded = base64.b64encode(raw).decode('ascii')
    if not wordwrap:
        return encoded
    return '\n'.join(textwrap.wrap(encoded, wordwrap))


def _strip_pem(pem: str) -> str:
    """Quita encabezado, pie y saltos de línea de un PEM."""
    lines = [line for line in pem.strip().splitlines() if not line.startswith('-----')]
    return ''.join(lines)


class DigitalCertificate:
    """
    Certificado digital X.509 con su clave privada RSA.

    Equivale a Derafu\\Certificate\\Certificate.
    """

    def __init__(
        self,
        certificate: x509.Certificate,
        private_key: Optional[rsa.RSAPrivateKey] = None,
        chain: Optional[List[x509.Certificate]] = None,
    ):
        self._certificate = certificate
        self._private_key = private_key
        self._chain = chain or []

    # ------------------------------------------------------------------
    # Carga
    # ------------------------------------------------------------------

    @classmethod
    def from_pkcs12(cls, data: bytes, password: Optional[str]) -> 'DigitalCertificate':
        """
        Carga un certificado desde el contenido de un archivo .pfx/.p12.

        Args:
            data: Contenido binario del archivo PKCS#12
            password: Contraseña (PIN) del archivo

        Raises:
            CertificateError: Si la contraseña es incorrecta o el archivo no es válido
        """
        pwd = password.encode('utf-8') if password else None
        try:
            key, cert, extra = pkcs12.load_key_and_certificates(data, pwd)
        except ValueError as e:
            raise CertificateError(
                'No fue posible leer el certificado digital. Verifique el archivo y su contraseña.'
            ) from e

        if cert is None:
            raise CertificateError('El archivo PKCS#12 no contiene un certificado.')
        if key is not None and not isinstance(key, rsa.RSAPrivateKey):
            raise CertificateError('La clave privada del certificado debe ser RSA.')

        return cls(cert, key, list(extra or []))

    @classmethod
    def from_file(cls, path: Union[str, Path], password: Optional[str]) -> 'DigitalCertificate':
        """Carga un certificado desde un archivo .pfx/.p12."""
        path = Path(path)
        if not path.is_file():
            raise CertificateError(f'No existe el archivo de certificado: {path}')
        return cls.from_pkcs12(path.read_bytes(), password)

    @classmethod
    def from_pem(
        cls,
        certificate_pem: Union[str, bytes],
        private_key_pem: Optional[Union[str, bytes]] = None,
        password: Optional[str] = None,
    ) -> 'DigitalCertificate':
        """Carga un certificado y su clave privada desde PEM."""
        if isinstance(certificate_pem, str):
            certificate_pem = certificate_pem.encode('utf-8')
        try:
            cert = x509.load_pem_x509_certificate(certificate_pem)
        except ValueError as e:
            raise CertificateError('El certificado PEM no es válido.') from e

        key = None
        if private_key_pem:
            if isinstance(private_key_pem, str):
                private_key_pem = private_key_pem.encode('utf-8')
            try:
                key = serialization.load_pem_private_key(
                    private_key_pem,
                    password=password.encode('utf-8') if password else None,
                )
            except (ValueError, TypeError) as e:
                raise CertificateError('La clave privada PEM no es válida o su contraseña es incorrecta.') from e
            if not isinstance(key, rsa.RSAPrivateKey):
                raise CertificateError('La clave privada del certificado debe ser RSA.')

        return cls(cert, key)

    # ------------------------------------------------------------------
    # Datos del certificado
    # ------------------------------------------------------------------

    @property
    def x509_certificate(self) -> x509.Certificate:
        return self._certificate

    @property
    def chain(self) -> List[x509.Certificate]:
        return list(self._chain)

    def has_private_key(self) -> bool:
        return self._private_key is not None

    @property
    def private_key(self) -> rsa.RSAPrivateKey:
        if self._private_key is None:
            raise CertificateError('La clave privada no está disponible en el certificado.')
        return self._private_key

    @property
    def public_key(self) -> rsa.RSAPublicKey:
        key = self._certificate.public_key()
        if not isinstance(key, rsa.RSAPublicKey):
            raise CertificateError('La clave pública del certificado debe ser RSA.')
        return key

    def _subject_values(self, oid) -> List[str]:
        return [str(attr.value) for attr in self._certificate.subject.get_attributes_for_oid(oid)]

    def get_ids(self, force_upper: bool = True) -> List[str]:
        """
        RUTs del titular del certificado.

        Se buscan primero en el campo serialNumber del subject y, si no existe,
        en el otherName de la extensión subjectAltName (formato usado por
        varias autoridades certificadoras chilenas).
        """
        ids = [value.strip().lstrip('0') for value in self._subject_values(NameOID.SERIAL_NUMBER)]

        if not ids:
            try:
                san = self._certificate.extensions.get_extension_for_oid(
                    ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                ).value
                for name in san:
                    if isinstance(name, x509.OtherName):
                        value = self._decode_ia5_string(name.value)
                        if value:
                            ids.append(value.strip().lstrip('0'))
                            break
            except x509.ExtensionNotFound:
                pass

        return [i.upper() for i in ids] if force_upper else ids

    @staticmethod
    def _decode_ia5_string(der: bytes) -> Optional[str]:
        """Decodifica un IA5String DER, posiblemente dentro de un tag explícito [0]."""
        data = der
        # Tag explícito de contexto [0] que envuelve el valor.
        if data and data[0] == 0xA0 and len(data) > 2:
            data = data[2:] if data[1] < 0x80 else data[2 + (data[1] & 0x7F):]
        if data and data[0] == 0x16 and len(data) > 2:
            length = data[1]
            offset = 2
            if length & 0x80:
                n = length & 0x7F
                length = int.from_bytes(data[2:2 + n], 'big')
                offset = 2 + n
            try:
                return data[offset:offset + length].decode('ascii')
            except UnicodeDecodeError:
                return None
        return None

    def get_id(self, force_upper: bool = True) -> str:
        """RUT del titular del certificado."""
        ids = self.get_ids(force_upper)
        if not ids:
            raise CertificateError(
                'No fue posible obtener el RUT del certificado digital. '
                'Verifique el formato y la contraseña del certificado.'
            )
        return ids[0]

    def get_name(self) -> str:
        names = self._subject_values(NameOID.COMMON_NAME)
        if not names:
            raise CertificateError('No fue posible obtener el nombre del certificado digital.')
        return names[0]

    def get_email(self) -> str:
        emails = self._subject_values(NameOID.EMAIL_ADDRESS)
        if not emails:
            raise CertificateError('No fue posible obtener el email del certificado digital.')
        return emails[0]

    def get_issuer(self) -> str:
        issuers = [str(a.value) for a in self._certificate.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)]
        if not issuers:
            raise CertificateError('No fue posible obtener el emisor del certificado digital.')
        return issuers[0]

    def _local_naive(self, value: datetime) -> datetime:
        """Convierte una fecha UTC del certificado a hora local sin zona (como PHP date())."""
        return value.astimezone().replace(tzinfo=None)

    def get_from(self) -> str:
        """Inicio de vigencia en formato Y-m-dTH:i:s (hora local)."""
        return self._local_naive(self._certificate.not_valid_before_utc).strftime('%Y-%m-%dT%H:%M:%S')

    def get_to(self) -> str:
        """Fin de vigencia en formato Y-m-dTH:i:s (hora local)."""
        return self._local_naive(self._certificate.not_valid_after_utc).strftime('%Y-%m-%dT%H:%M:%S')

    def get_expiration_days(self, when: Optional[str] = None) -> int:
        start = datetime.fromisoformat(when) if when else datetime.now()
        end = datetime.fromisoformat(self.get_to())
        return abs((end - start).days)

    def is_active(self, when: Optional[str] = None) -> bool:
        """
        Indica si el certificado está vigente en el momento indicado.

        Args:
            when: Fecha (Y-m-d) o fecha y hora (Y-m-dTH:i:s). Por defecto hoy.
        """
        if when is None:
            when = datetime.now().strftime('%Y-%m-%d')
        if len(when) <= 10:
            when += 'T23:59:59'
        return self.get_from() <= when <= self.get_to()

    def get_modulus(self, wordwrap: int = 64) -> str:
        """Módulo RSA en base64, usado en RSAKeyValue de la firma XML."""
        return _int_to_base64(self.public_key.public_numbers().n, wordwrap)

    def get_exponent(self, wordwrap: int = 64) -> str:
        """Exponente RSA en base64, usado en RSAKeyValue de la firma XML."""
        return _int_to_base64(self.public_key.public_numbers().e, wordwrap)

    def get_certificate_pem(self, clean: bool = False) -> str:
        pem = self._certificate.public_bytes(serialization.Encoding.PEM).decode('ascii')
        return _strip_pem(pem) if clean else pem

    def get_private_key_pem(self) -> str:
        return self.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode('ascii')

    def get_pkcs12(self, password: str) -> bytes:
        """Exporta el certificado, su clave privada y la cadena en PKCS#12."""
        return pkcs12.serialize_key_and_certificates(
            name=None,
            key=self.private_key,
            cert=self._certificate,
            cas=self._chain or None,
            encryption_algorithm=serialization.BestAvailableEncryption(password.encode('utf-8')),
        )

    # ------------------------------------------------------------------
    # Firma
    # ------------------------------------------------------------------

    def sign(self, data: Union[str, bytes]) -> str:
        """
        Firma datos con RSA-SHA1 (PKCS#1 v1.5) y entrega la firma en base64.

        Equivale a openssl_sign($data, $sig, $pkey, OPENSSL_ALGO_SHA1).
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        signature = self.private_key.sign(data, padding.PKCS1v15(), hashes.SHA1())
        return base64.b64encode(signature).decode('ascii')

    def to_dict(self) -> dict:
        return {
            'id': self.get_id(),
            'name': self.get_name(),
            'from': self.get_from(),
            'to': self.get_to(),
            'is_active': self.is_active(),
            'expiration_days': self.get_expiration_days(),
            'issuer': self.get_issuer(),
        }

    def __repr__(self) -> str:
        try:
            return f'<DigitalCertificate {self.get_id()} {self.get_name()!r}>'
        except CertificateError:
            return '<DigitalCertificate>'


class SelfSignedCertificate:
    """
    Generador de certificados autofirmados para pruebas.

    Equivale a Derafu\\Certificate\\SelfSignedCertificate: crea una CA de
    prueba y un certificado de titular firmado por ella. El SII no acepta
    estos certificados; sirven solo para desarrollo y tests.
    """

    def __init__(
        self,
        rut: str = '11222333-9',
        name: str = 'Daniel Bot',
        email: str = 'daniel.bot@example.com',
        days: int = 365,
        key_size: int = 2048,
    ):
        self.rut = rut.upper()
        self.name = name
        self.email = email
        self.days = days
        self.key_size = key_size

    def _subject(self) -> x509.Name:
        return x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, 'CL'),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Colchagua'),
            x509.NameAttribute(NameOID.LOCALITY_NAME, 'Santa Cruz'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Intergalactic Robots Organization'),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, 'Technology'),
            x509.NameAttribute(NameOID.COMMON_NAME, self.name),
            x509.NameAttribute(NameOID.EMAIL_ADDRESS, self.email),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, self.rut),
            x509.NameAttribute(NameOID.TITLE, 'Bot'),
        ])

    @staticmethod
    def _issuer() -> x509.Name:
        return x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, 'CL'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'RypSystems'),
            x509.NameAttribute(NameOID.COMMON_NAME, 'RypSystems Test Certificate Authority'),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, '76192083-9'),
        ])

    def create(self) -> DigitalCertificate:
        # Vigente desde el día anterior, para que las marcas de tiempo de
        # pruebas calculadas un poco antes de crear el certificado sean válidas.
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=1)
        until = now + timedelta(days=self.days)

        issuer_key = rsa.generate_private_key(public_exponent=65537, key_size=self.key_size)
        issuer_name = self._issuer()
        issuer_cert = (
            x509.CertificateBuilder()
            .subject_name(issuer_name)
            .issuer_name(issuer_name)
            .public_key(issuer_key.public_key())
            .serial_number(666)
            .not_valid_before(since)
            .not_valid_after(until)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(issuer_key, hashes.SHA256())
        )

        subject_key = rsa.generate_private_key(public_exponent=65537, key_size=self.key_size)
        subject_cert = (
            x509.CertificateBuilder()
            .subject_name(self._subject())
            .issuer_name(issuer_name)
            .public_key(subject_key.public_key())
            .serial_number(69)
            .not_valid_before(since)
            .not_valid_after(until)
            .sign(issuer_key, hashes.SHA256())
        )

        return DigitalCertificate(subject_cert, subject_key, [issuer_cert])

    def to_pkcs12(self, password: str = 'i_love_derafu') -> bytes:
        return self.create().get_pkcs12(password)
