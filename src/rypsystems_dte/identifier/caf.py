"""
Código de Autorización de Folios (CAF).

Traducción del componente Identifier de LibreDTE Core: entidad Caf,
CafFaker (CAF falsos para pruebas) y CafValidatorWorker.

El CAF es el XML que entrega el SII al autorizar un rango de folios. Contiene
los datos autorizados (DA) firmados por el SII y la clave privada (RSASK) con
la que se timbra cada documento (TED).
"""

import base64
import os
import re
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Union
from xml.sax.saxutils import escape

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from ..sii.base import SiiAmbiente
from ..xml.canonical import c14n_encoded_flattened, parse

_RESOURCES = Path(__file__).resolve().parent.parent / 'resources' / 'certificates'


class CafError(Exception):
    """Error al cargar, validar o usar un CAF."""


def _normalize_pem(pem: str) -> str:
    """
    Reconstruye un PEM que viene en una sola línea dentro del XML del CAF.

    Equivale a la normalización de Caf::getPrivateKey() y getPublicKey().
    """
    pem = pem.strip()
    match = re.match(r'-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----', pem, re.DOTALL)
    if not match:
        return pem
    label, body = match.group(1), re.sub(r'\s+', '', match.group(2))
    return f'-----BEGIN {label}-----\n' + '\n'.join(textwrap.wrap(body, 64)) + f'\n-----END {label}-----\n'


def _der_read(data: bytes, offset: int):
    """Lee un elemento DER: entrega (tag, inicio del contenido, fin)."""
    tag = data[offset]
    length = data[offset + 1]
    start = offset + 2
    if length & 0x80:
        n = length & 0x7F
        length = int.from_bytes(data[start:start + n], 'big')
        start += n
    return tag, start, start + length


def _public_key_from_certificate(pem: bytes) -> rsa.RSAPublicKey:
    """
    Obtiene la clave pública de un certificado X.509.

    Los certificados del SII de 2003 (100.cer y 300.cer) declaran una versión
    X.509 inválida (v4) y cryptography se niega a cargarlos, por lo que en ese
    caso se extrae el SubjectPublicKeyInfo directamente desde el DER. Igual
    que PHP, solo se usa la clave pública (no se valida vigencia ni cadena).
    """
    try:
        key = x509.load_pem_x509_certificate(pem).public_key()
    except (ValueError, x509.InvalidVersion):
        body = re.sub(rb'-----[A-Z ]+-----|\s+', b'', pem)
        der = base64.b64decode(body)
        _, cert_start, _ = _der_read(der, 0)              # Certificate
        _, offset, _ = _der_read(der, cert_start)          # tbsCertificate
        tag, _, _ = _der_read(der, offset)
        # [0] version (opcional), serial, signature, issuer, validity, subject, spki
        spki_index = 6 if tag == 0xA0 else 5
        for _ in range(spki_index):
            _, _, offset = _der_read(der, offset)
        _, _, spki_end = _der_read(der, offset)
        spki_start = offset
        key = serialization.load_der_public_key(der[spki_start:spki_end])
    if not isinstance(key, rsa.RSAPublicKey):
        raise CafError('La clave pública del certificado del SII debe ser RSA.')
    return key


class Caf:
    """
    Archivo CAF autorizado por el SII.

    Equivale a libredte\\...\\Identifier\\Entity\\Caf.
    """

    IDK_CERTIFICACION = 100
    IDK_PRODUCCION = 300
    IDK_FAKE = 666

    # Tipos de documento cuyos folios vencen a los 6 meses de autorizados.
    TIPOS_QUE_VENCEN = (33, 43, 46, 56, 61)
    DIAS_VIGENCIA = 180

    def __init__(self, xml: Union[str, bytes]):
        try:
            self._tree = parse(xml)
        except etree.XMLSyntaxError as e:
            raise CafError(f'El XML del CAF no es válido: {e}') from e
        if self._tree.getroot().tag != 'AUTORIZACION' or self._query('CAF/DA') is None:
            raise CafError('El XML entregado no corresponde a un CAF (falta AUTORIZACION/CAF/DA).')

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> 'Caf':
        path = Path(path)
        if not path.is_file():
            raise CafError(f'No existe el archivo CAF: {path}')
        return cls(path.read_bytes())

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def _query(self, path: str) -> Optional[etree._Element]:
        return self._tree.getroot().find(path)

    def _text(self, path: str) -> str:
        node = self._query(path)
        return (node.text or '').strip() if node is not None else ''

    @property
    def xml_tree(self) -> etree._ElementTree:
        return self._tree

    def get_xml(self) -> bytes:
        return etree.tostring(self._tree, xml_declaration=True, encoding=self._tree.docinfo.encoding or 'ISO-8859-1')

    def get_id(self) -> str:
        return f'CAF{self.get_tipo_documento()}D{self.get_folio_desde()}H{self.get_folio_hasta()}'

    def get_emisor(self) -> dict:
        return {'rut': self._text('CAF/DA/RE'), 'razon_social': self._text('CAF/DA/RS')}

    def get_tipo_documento(self) -> int:
        return int(self._text('CAF/DA/TD') or 0)

    def get_folio_desde(self) -> int:
        return int(self._text('CAF/DA/RNG/D') or 0)

    def get_folio_hasta(self) -> int:
        return int(self._text('CAF/DA/RNG/H') or 0)

    def get_cantidad_folios(self) -> int:
        return self.get_folio_hasta() - self.get_folio_desde() + 1

    def en_rango(self, folio: int) -> bool:
        return self.get_folio_desde() <= folio <= self.get_folio_hasta()

    def get_fecha_autorizacion(self) -> str:
        return self._text('CAF/DA/FA')

    def vence(self) -> bool:
        return self.get_tipo_documento() in self.TIPOS_QUE_VENCEN

    def get_fecha_vencimiento(self) -> Optional[str]:
        if not self.vence():
            return None
        fecha = self.get_fecha_autorizacion()
        if not fecha:
            raise CafError(f'No fue posible obtener la fecha de autorización del CAF {self.get_id()}.')
        return (date.fromisoformat(fecha) + timedelta(days=self.DIAS_VIGENCIA)).isoformat()

    def vigente(self, timestamp: Optional[str] = None) -> bool:
        """
        Indica si el CAF está vigente en el momento indicado.

        Args:
            timestamp: Fecha (Y-m-d) o fecha y hora (Y-m-dTH:i:s). Por defecto ahora.
        """
        if not self.vence():
            return True
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        if len(timestamp) <= 10:
            timestamp += 'T00:00:00'
        return timestamp < f'{self.get_fecha_vencimiento()}T00:00:00'

    def get_idk(self) -> int:
        return int(self._text('CAF/DA/IDK') or 0)

    def get_ambiente(self) -> Optional[SiiAmbiente]:
        """Ambiente del SII del CAF, o None si es un CAF falso (IDK 666)."""
        idk = self.get_idk()
        if idk == self.IDK_FAKE:
            return None
        if idk == self.IDK_CERTIFICACION:
            return SiiAmbiente.CERTIFICACION
        if idk == self.IDK_PRODUCCION:
            return SiiAmbiente.PRODUCCION
        raise CafError(f'El IDK {idk} del CAF {self.get_id()} no es conocido.')

    def es_falso(self) -> bool:
        return self.get_idk() == self.IDK_FAKE

    def get_autorizacion(self) -> etree._Element:
        """Nodo AUTORIZACION/CAF, que se incluye en el DD del TED."""
        return self._query('CAF')

    def get_private_key_pem(self) -> str:
        return _normalize_pem(self._text('RSASK'))

    def get_public_key_pem(self) -> str:
        return _normalize_pem(self._text('RSAPUBK'))

    def get_private_key(self) -> rsa.RSAPrivateKey:
        try:
            key = serialization.load_pem_private_key(self.get_private_key_pem().encode('ascii'), password=None)
        except ValueError as e:
            raise CafError(f'La clave privada del CAF {self.get_id()} no es válida.') from e
        if not isinstance(key, rsa.RSAPrivateKey):
            raise CafError(f'La clave privada del CAF {self.get_id()} debe ser RSA.')
        return key

    def get_public_key(self) -> rsa.RSAPublicKey:
        try:
            key = serialization.load_pem_public_key(self.get_public_key_pem().encode('ascii'))
        except ValueError as e:
            raise CafError(f'La clave pública del CAF {self.get_id()} no es válida.') from e
        if not isinstance(key, rsa.RSAPublicKey):
            raise CafError(f'La clave pública del CAF {self.get_id()} debe ser RSA.')
        return key

    def get_firma(self) -> str:
        return self._text('CAF/FRMA')

    def to_dict(self) -> dict:
        return {
            'id': self.get_id(),
            'emisor': self.get_emisor(),
            'tipo_documento': self.get_tipo_documento(),
            'folio_desde': self.get_folio_desde(),
            'folio_hasta': self.get_folio_hasta(),
            'cantidad_folios': self.get_cantidad_folios(),
            'fecha_autorizacion': self.get_fecha_autorizacion(),
            'fecha_vencimiento': self.get_fecha_vencimiento(),
            'vigente': self.vigente(),
            'vence': self.vence(),
            'idk': self.get_idk(),
            'ambiente': self.get_ambiente(),
        }

    def __repr__(self) -> str:
        return f'<Caf {self.get_id()} emisor={self.get_emisor()["rut"]} idk={self.get_idk()}>'


class CafValidator:
    """
    Valida un CAF: firma del SII sobre los datos autorizados (DA) y
    correspondencia entre su clave privada y pública.

    Equivale a CafValidatorWorker. La firma del SII no se valida en CAF
    falsos (IDK 666).
    """

    def __init__(self, certificates_path: Path = _RESOURCES):
        self.certificates_path = Path(certificates_path)

    def _sii_public_key(self, idk: int) -> Optional[rsa.RSAPublicKey]:
        if idk == Caf.IDK_FAKE:
            return None
        path = self.certificates_path / f'{idk}.cer'
        if not path.is_file():
            raise CafError(f'No fue posible obtener el certificado del SII {idk}.cer para validar el CAF.')
        return _public_key_from_certificate(path.read_bytes())

    def validate(self, caf: Caf) -> Caf:
        """
        Raises:
            CafError: Si el CAF no es válido
        """
        sii_key = self._sii_public_key(caf.get_idk())
        if sii_key is not None:
            signed_da = c14n_encoded_flattened(caf.xml_tree, '/AUTORIZACION/CAF/DA')
            try:
                sii_key.verify(base64.b64decode(caf.get_firma()), signed_da, padding.PKCS1v15(), hashes.SHA1())
            except Exception as e:
                raise CafError(
                    f'La firma del CAF {caf.get_id()} no es válida (no está autorizado por el SII).'
                ) from e

        # Equivale a cifrar con la privada y descifrar con la pública: se firma
        # un texto de prueba y se verifica con la clave pública del CAF.
        test = os.urandom(32)
        try:
            signature = caf.get_private_key().sign(test, padding.PKCS1v15(), hashes.SHA1())
        except CafError:
            raise
        except Exception as e:
            raise CafError(
                f'El CAF {caf.get_id()} no pasó la validación de su clave privada (posible archivo CAF corrupto).'
            ) from e
        try:
            caf.get_public_key().verify(signature, test, padding.PKCS1v15(), hashes.SHA1())
        except CafError:
            raise
        except Exception as e:
            raise CafError(
                f'Las claves privada y pública del CAF {caf.get_id()} no corresponden (posible archivo CAF corrupto).'
            ) from e

        return caf


class CafFaker:
    """
    Genera CAF falsos (IDK 666) para desarrollo y pruebas.

    Equivale a CafFaker de LibreDTE. Los documentos timbrados con estos CAF
    no son válidos ante el SII.
    """

    def __init__(
        self,
        rut: str = '76192083-9',
        razon_social: str = 'SASCO SpA',
        tipo_documento: int = 33,
        desde: int = 1,
        hasta: int = 100,
        fecha_autorizacion: Optional[str] = None,
    ):
        if desde > hasta:
            raise CafError(
                f'Al crear un CAF el folio desde ({desde}) no puede ser mayor que el folio hasta ({hasta}).'
            )
        self.rut = rut
        self.razon_social = razon_social
        self.tipo_documento = tipo_documento
        self.desde = desde
        self.hasta = hasta
        self.fecha_autorizacion = fecha_autorizacion or date.today().isoformat()

    def create(self) -> Caf:
        # Los CAF del SII usan claves de 512 bits; 1024 es el mínimo que permite cryptography.
        key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        private_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ).decode('ascii')
        public_pem = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode('ascii')
        # RSAPK con la clave pública real, para que el TED se pueda verificar
        # con la clave incluida en el timbre (como con un CAF del SII).
        numbers = key.public_key().public_numbers()
        modulus = base64.b64encode(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, 'big')).decode('ascii')
        exponent = base64.b64encode(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, 'big')).decode('ascii')

        xml = (
            '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
            '<AUTORIZACION>'
            '<CAF version="1.0">'
            '<DA>'
            f'<RE>{escape(self.rut)}</RE>'
            f'<RS>{escape(self.razon_social[:40])}</RS>'
            f'<TD>{self.tipo_documento}</TD>'
            f'<RNG><D>{self.desde}</D><H>{self.hasta}</H></RNG>'
            f'<FA>{self.fecha_autorizacion}</FA>'
            f'<RSAPK><M>{modulus}</M><E>{exponent}</E></RSAPK>'
            f'<IDK>{Caf.IDK_FAKE}</IDK>'
            '</DA>'
            '<FRMA algoritmo="SHA1withRSA">bGlicmVkdGUtY2FmLXNpZ25hdHVyZQ==</FRMA>'
            '</CAF>'
            f'<RSASK>{private_pem.strip()}</RSASK>'
            f'<RSAPUBK>{public_pem.strip()}</RSAPUBK>'
            '</AUTORIZACION>'
        )
        return Caf(xml.encode('iso-8859-1'))
