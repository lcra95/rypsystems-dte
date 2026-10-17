"""
Firma electrónica XML (XML-DSig) en el formato exigido por el SII.

Traducción de derafu/signature (SignatureGenerator, Signature y
SignatureValidator) usada por LibreDTE Core. Características del formato:

- Firma RSA-SHA1 y digest SHA1.
- Canonicalización C14N inclusiva (REC-xml-c14n-20010315).
- Firma ubicada como último hijo del nodo raíz del XML firmado.
- KeyInfo con RSAKeyValue (módulo y exponente) y un único X509Certificate.
"""

import base64
import hashlib
import re
import textwrap
from copy import deepcopy
from dataclasses import dataclass
from typing import List, Optional, Union

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from ..xml.canonical import c14n as _c14n, parse, to_bytes as _to_bytes
from .digital_certificate import DigitalCertificate

XMLDSIG_NS = 'http://www.w3.org/2000/09/xmldsig#'
C14N_ALGORITHM = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
ENVELOPED_ALGORITHM = 'http://www.w3.org/2000/09/xmldsig#enveloped-signature'
RSA_SHA1_ALGORITHM = 'http://www.w3.org/2000/09/xmldsig#rsa-sha1'
SHA1_ALGORITHM = 'http://www.w3.org/2000/09/xmldsig#sha1'

_XML_DECLARATION_RE = re.compile(rb'^\s*<\?xml[^>]*\?>', re.DOTALL)


class SignatureError(Exception):
    """Error al firmar o validar una firma XML."""


def _wordwrap(value: str, width: int = 64) -> str:
    return '\n'.join(textwrap.wrap(value, width))


def _parse(xml: Union[str, bytes]) -> etree._ElementTree:
    try:
        return parse(xml)
    except etree.XMLSyntaxError as e:
        raise SignatureError(f'El XML a firmar no es válido: {e}') from e


def _find_by_id(tree: etree._ElementTree, reference: str) -> etree._Element:
    ref = reference.lstrip('#')
    nodes = tree.xpath('//*[@ID=$id]', id=ref)
    if not nodes:
        raise SignatureError(f'No se encontró un elemento con ID "{ref}" en el XML.')
    return nodes[0]


def _signature_children(element: etree._Element) -> List[etree._Element]:
    return [child for child in element if etree.QName(child).localname == 'Signature']


@dataclass
class SignatureValidationResult:
    """Resultado de validar una firma XML."""
    reference: Optional[str]
    digest_value: Optional[str]
    certificate: Optional[x509.Certificate]
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None


class XmlSigner:
    """
    Firma y valida documentos XML con el formato XML-DSig del SII.

    Equivale a Derafu\\Signature\\Service\\SignatureGenerator y
    SignatureValidator.
    """

    # ------------------------------------------------------------------
    # Firma de datos
    # ------------------------------------------------------------------

    @staticmethod
    def sign(data: Union[str, bytes], private_key: rsa.RSAPrivateKey) -> str:
        """Firma datos con RSA-SHA1 y entrega la firma en base64."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        try:
            signature = private_key.sign(data, padding.PKCS1v15(), hashes.SHA1())
        except Exception as e:  # pragma: no cover - errores de la clave
            raise SignatureError('No fue posible firmar los datos.') from e
        return base64.b64encode(signature).decode('ascii')

    @staticmethod
    def verify(data: Union[str, bytes], signature: str, public_key: rsa.RSAPublicKey) -> bool:
        """Verifica una firma RSA-SHA1 en base64."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        try:
            public_key.verify(base64.b64decode(signature), data, padding.PKCS1v15(), hashes.SHA1())
            return True
        except (InvalidSignature, ValueError):
            return False

    # ------------------------------------------------------------------
    # Firma XML
    # ------------------------------------------------------------------

    def digest_value(self, xml: Union[str, bytes, etree._ElementTree], reference: Optional[str] = None) -> str:
        """
        Calcula el DigestValue (SHA1 en base64) del nodo referenciado.

        Si no hay referencia se usa el documento completo sin su firma
        (transformación enveloped-signature).
        """
        tree = xml if isinstance(xml, etree._ElementTree) else _parse(xml)

        if reference:
            data = _c14n(_find_by_id(tree, reference))
        else:
            root = etree.fromstring(etree.tostring(tree.getroot()))
            for sig in _signature_children(root)[:1]:
                root.remove(sig)
            data = _c14n(root)

        return base64.b64encode(hashlib.sha1(data).digest()).decode('ascii')

    def _build_signature(
        self,
        digest_value: str,
        certificate: DigitalCertificate,
        reference: Optional[str],
        namespace: Optional[str],
    ) -> etree._Element:
        uri = f'#{reference.lstrip("#")}' if reference else ''
        transform = C14N_ALGORITHM if reference else ENVELOPED_ALGORITHM
        ns = namespace or XMLDSIG_NS

        # Se arma como texto para controlar exactamente las declaraciones de
        # namespace y que no haya espacios entre nodos, igual que en PHP.
        xml = (
            f'<Signature xmlns="{ns}">'
            '<SignedInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<CanonicalizationMethod Algorithm="{C14N_ALGORITHM}"/>'
            f'<SignatureMethod Algorithm="{RSA_SHA1_ALGORITHM}"/>'
            f'<Reference URI="{uri}">'
            f'<Transforms><Transform Algorithm="{transform}"/></Transforms>'
            f'<DigestMethod Algorithm="{SHA1_ALGORITHM}"/>'
            f'<DigestValue>{digest_value}</DigestValue>'
            '</Reference>'
            '</SignedInfo>'
            '<SignatureValue/>'
            '<KeyInfo>'
            '<KeyValue><RSAKeyValue>'
            f'<Modulus>{certificate.get_modulus()}</Modulus>'
            f'<Exponent>{certificate.get_exponent()}</Exponent>'
            '</RSAKeyValue></KeyValue>'
            f'<X509Data><X509Certificate>{self._certificate_body(certificate)}</X509Certificate></X509Data>'
            '</KeyInfo>'
            '</Signature>'
        )
        return etree.fromstring(xml.encode('utf-8'))

    @staticmethod
    def _certificate_body(certificate: DigitalCertificate) -> str:
        """Certificado en base64 sin encabezados PEM, en líneas de 64 caracteres."""
        pem = certificate.get_certificate_pem()
        return '\n'.join(line for line in pem.strip().splitlines() if not line.startswith('-----'))

    def sign_xml(
        self,
        xml: Union[str, bytes],
        certificate: DigitalCertificate,
        reference: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> bytes:
        """
        Firma un XML y entrega el XML firmado.

        Args:
            xml: XML a firmar (bytes o str con declaración de encoding)
            certificate: Certificado con clave privada
            reference: Valor del atributo ID del nodo a firmar. Si es None se
                firma el documento completo (enveloped-signature).
            namespace: Namespace del nodo Signature (por defecto xmldsig)

        Returns:
            XML firmado, en bytes con el mismo encoding del XML de entrada.
        """
        source = _to_bytes(xml)
        tree = _parse(source)
        root = tree.getroot()

        digest = self.digest_value(tree, reference)
        signature = self._build_signature(digest, certificate, reference, namespace)

        signed_info = signature[0]
        signature_value = self.sign(_c14n(signed_info), certificate.private_key)
        signature[1].text = _wordwrap(signature_value, 64)

        signature_xml = etree.tostring(signature, encoding='unicode')

        # Serializar el documento original y agregar la firma como último
        # hijo del nodo raíz, sin reformatear el resto del XML.
        encoding = tree.docinfo.encoding or 'UTF-8'
        body = etree.tostring(root, encoding=encoding, xml_declaration=False)
        declaration = _XML_DECLARATION_RE.match(source)
        prefix = declaration.group(0).strip() + b'\n' if declaration else b''

        signature_bytes = signature_xml.encode(encoding, errors='xmlcharrefreplace')
        if body.endswith(b'/>'):
            raise SignatureError('El nodo raíz del XML a firmar no puede estar vacío.')
        close_index = body.rindex(b'</')
        signed = body[:close_index] + signature_bytes + body[close_index:]

        return prefix + signed

    # ------------------------------------------------------------------
    # Validación XML
    # ------------------------------------------------------------------

    def validate_xml(self, xml: Union[str, bytes]) -> List[SignatureValidationResult]:
        """
        Valida todas las firmas XML-DSig del documento.

        Raises:
            SignatureError: Si el documento no tiene firmas
        """
        tree = _parse(xml)
        signatures = tree.getroot().xpath('//*[local-name()="Signature"]')
        if not signatures:
            raise SignatureError('No se encontraron firmas en el XML a validar.')

        return [self._validate_signature(tree, sig) for sig in signatures]

    def is_valid_xml(self, xml: Union[str, bytes]) -> bool:
        try:
            return all(r.is_valid for r in self.validate_xml(xml))
        except SignatureError:
            return False

    def _validate_signature(self, tree: etree._ElementTree, signature: etree._Element) -> SignatureValidationResult:
        # Igual que en PHP, la firma se valida como documento independiente
        # obtenido desde su C14N en el contexto original.
        sig = etree.fromstring(_c14n(signature))

        def find(path: str) -> Optional[etree._Element]:
            nodes = sig.xpath(path)
            return nodes[0] if nodes else None

        reference_node = find('./*[local-name()="SignedInfo"]/*[local-name()="Reference"]')
        uri = reference_node.get('URI') if reference_node is not None else None
        reference = uri.lstrip('#') if uri else None
        digest_node = find('.//*[local-name()="DigestValue"]')
        digest_xml = (digest_node.text or '').strip() if digest_node is not None else None
        cert_node = find('.//*[local-name()="X509Certificate"]')

        certificate = None
        if cert_node is not None and cert_node.text:
            try:
                der = base64.b64decode(re.sub(r'\s+', '', cert_node.text))
                certificate = x509.load_der_x509_certificate(der)
            except ValueError:
                certificate = None

        result = SignatureValidationResult(reference, digest_xml, certificate)

        if not digest_xml:
            result.error = 'Falta el DigestValue en la firma.'
            return result

        try:
            digest_calculated = self.digest_value(tree, reference)
        except SignatureError as e:
            result.error = str(e)
            return result

        if digest_calculated != digest_xml and reference:
            digest_calculated = self._find_matching_digest(tree, reference, digest_xml) or digest_calculated

        if digest_calculated != digest_xml:
            result.error = (
                f'El DigestValue de la firma ({digest_xml}) no coincide con el calculado '
                f'({digest_calculated}) para la referencia "{reference}". Los datos podrían '
                'haber sido modificados después de firmar.'
            )
            return result

        signature_value_node = find('./*[local-name()="SignatureValue"]')
        signed_info = find('./*[local-name()="SignedInfo"]')
        if signature_value_node is None or not (signature_value_node.text or '').strip():
            result.error = 'Falta el SignatureValue en la firma.'
            return result

        public_key = self._public_key(sig, certificate)
        if public_key is None:
            result.error = 'No fue posible obtener la clave pública de la firma.'
            return result

        signature_value = re.sub(r'\s+', '', signature_value_node.text)
        if not self.verify(_c14n(signed_info), signature_value, public_key):
            result.error = 'El SignatureValue no es válido para el SignedInfo de la firma.'

        return result

    @staticmethod
    def _find_matching_digest(tree: etree._ElementTree, reference: str, expected: str) -> Optional[str]:
        """
        Alternativas de canonicalización aceptadas al validar, como en PHP.

        Algunos emisores (incluido el ejemplo oficial del SII) calculan el
        digest con C14N exclusiva o sobre el nodo sin declaraciones de
        namespace.
        """
        nodes = tree.xpath('//*[@ID=$id]', id=reference)
        if not nodes:
            return None
        node = nodes[0]

        def digest(data: bytes) -> str:
            return base64.b64encode(hashlib.sha1(data).digest()).decode('ascii')

        candidate = digest(etree.tostring(node, method='c14n', exclusive=True, with_comments=False))
        if candidate == expected:
            return candidate

        serialized = etree.tostring(deepcopy(node), encoding='unicode')
        stripped = re.sub(r' xmlns(?::[^=]*)?\s*=\s*"[^"]*"', '', serialized)
        try:
            candidate = digest(_c14n(etree.fromstring(stripped.encode('utf-8'))))
        except etree.XMLSyntaxError:
            return None
        return candidate if candidate == expected else None

    @staticmethod
    def _public_key(sig: etree._Element, certificate: Optional[x509.Certificate]) -> Optional[rsa.RSAPublicKey]:
        if certificate is not None:
            key = certificate.public_key()
            if isinstance(key, rsa.RSAPublicKey):
                return key
        modulus = sig.xpath('.//*[local-name()="Modulus"]')
        exponent = sig.xpath('.//*[local-name()="Exponent"]')
        if not modulus or not exponent:
            return None
        n = int.from_bytes(base64.b64decode(re.sub(r'\s+', '', modulus[0].text or '')), 'big')
        e = int.from_bytes(base64.b64decode(re.sub(r'\s+', '', exponent[0].text or '')), 'big')
        return rsa.RSAPublicNumbers(e, n).public_key()
