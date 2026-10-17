"""
Tests de firma XML-DSig en formato SII.

Incluye la comparación contra el ejemplo oficial del SII incluido en
LibreDTE PHP, reproduciendo los mismos resultados que sus tests.
"""

import os
from pathlib import Path

import pytest
from lxml import etree

from rypsystems_dte.firma import (
    DigitalCertificate,
    SelfSignedCertificate,
    SignatureError,
    XmlSigner,
)

PHP_FIXTURES = Path(__file__).resolve().parents[2] / 'libredte-php-original' / 'tests' / 'fixtures'
OFFICIAL_EXAMPLE = PHP_FIXTURES / 'xml' / 'documentos_ok' / 'F60T33-ejemplo-oficial-SII.xml'
DSIG = '{http://www.w3.org/2000/09/xmldsig#}'

DTE_XML = (
    '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
    '<DTE xmlns="http://www.sii.cl/SiiDte" version="1.0">'
    '<Documento ID="LibreDTE_T33F1">'
    '<Encabezado><IdDoc><TipoDTE>33</TipoDTE><Folio>1</Folio></IdDoc>'
    '<Emisor><RznSoc>Compañía Ñandú Limitada</RznSoc></Emisor></Encabezado>'
    '<TmstFirma>2026-10-17T12:00:00</TmstFirma>'
    '</Documento>'
    '</DTE>'
)


@pytest.fixture(scope='module')
def certificate() -> DigitalCertificate:
    return SelfSignedCertificate().create()


@pytest.fixture(scope='module')
def signer() -> XmlSigner:
    return XmlSigner()


class TestFirmaXml:

    def test_firma_con_referencia_es_valida(self, signer, certificate):
        signed = signer.sign_xml(DTE_XML, certificate, 'LibreDTE_T33F1')
        results = signer.validate_xml(signed)
        assert len(results) == 1
        assert results[0].is_valid, results[0].error
        assert results[0].reference == 'LibreDTE_T33F1'

    def test_estructura_de_la_firma(self, signer, certificate):
        signed = signer.sign_xml(DTE_XML, certificate, 'LibreDTE_T33F1')
        assert signed.startswith(b'<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        root = etree.fromstring(signed)
        signature = root[-1]
        assert signature.tag == f'{DSIG}Signature'
        assert [etree.QName(c).localname for c in signature] == ['SignedInfo', 'SignatureValue', 'KeyInfo']
        reference = signature.find(f'{DSIG}SignedInfo/{DSIG}Reference')
        assert reference.get('URI') == '#LibreDTE_T33F1'
        # Perfil de LibreDTE clásico: enveloped-signature y SignedInfo con su xmlns.
        assert reference.find(f'{DSIG}Transforms/{DSIG}Transform').get('Algorithm') == \
            'http://www.w3.org/2000/09/xmldsig#enveloped-signature'
        assert b'<SignedInfo xmlns="http://www.w3.org/2000/09/xmldsig#">' in signed
        assert len(signature.findall(f'.//{DSIG}X509Certificate')) == 1
        assert signature.findtext(f'.//{DSIG}Exponent') == 'AQAB'

    def test_conserva_iso_8859_1(self, signer, certificate):
        signed = signer.sign_xml(DTE_XML, certificate, 'LibreDTE_T33F1')
        assert 'Compañía Ñandú Limitada'.encode('iso-8859-1') in signed

    def test_firma_documento_completo(self, signer, certificate):
        xml = '<?xml version="1.0" encoding="ISO-8859-1"?>\n<getToken><item><Semilla>123</Semilla></item></getToken>'
        signed = signer.sign_xml(xml, certificate)
        root = etree.fromstring(signed)
        assert root[-1].find(f'{DSIG}SignedInfo/{DSIG}Reference').get('URI') == ''
        assert signer.is_valid_xml(signed)

    def test_modificacion_invalida_la_firma(self, signer, certificate):
        signed = signer.sign_xml(DTE_XML, certificate, 'LibreDTE_T33F1')
        tampered = signed.replace(b'<Folio>1</Folio>', b'<Folio>2</Folio>')
        result = signer.validate_xml(tampered)[0]
        assert not result.is_valid
        assert 'DigestValue' in result.error

    def test_firma_alterada_es_invalida(self, signer, certificate):
        signed = signer.sign_xml(DTE_XML, certificate, 'LibreDTE_T33F1')
        root = etree.fromstring(signed)
        value = root[-1].find(f'{DSIG}SignatureValue')
        value.text = ('A' if value.text[0] != 'A' else 'B') + value.text[1:]
        result = signer.validate_xml(etree.tostring(root))[0]
        assert not result.is_valid
        assert 'SignatureValue' in result.error

    def test_firmas_anidadas_como_envio_dte(self, signer, certificate):
        """Un DTE firmado dentro de un SetDTE que también se firma."""
        dte = signer.sign_xml(DTE_XML, certificate, 'LibreDTE_T33F1')
        dte_body = dte.split(b'?>', 1)[1].strip()
        envio = (
            b'<?xml version="1.0" encoding="ISO-8859-1"?>\n'
            b'<EnvioDTE xmlns="http://www.sii.cl/SiiDte" '
            b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0">'
            b'<SetDTE ID="LibreDTE_SetDoc"><Caratula version="1.0"/>'
            + dte_body.replace(b' xmlns="http://www.sii.cl/SiiDte"', b'', 1)
            + b'</SetDTE></EnvioDTE>'
        )
        signed = signer.sign_xml(envio, certificate, 'LibreDTE_SetDoc')
        results = signer.validate_xml(signed)
        assert [r.reference for r in results] == ['LibreDTE_T33F1', 'LibreDTE_SetDoc']
        assert all(r.is_valid for r in results), [r.error for r in results]

    def test_referencia_inexistente(self, signer, certificate):
        with pytest.raises(SignatureError):
            signer.sign_xml(DTE_XML, certificate, 'NoExiste')

    def test_xml_sin_firmas(self, signer):
        with pytest.raises(SignatureError):
            signer.validate_xml(DTE_XML)
        assert not signer.is_valid_xml(DTE_XML)


@pytest.mark.skipif(not OFFICIAL_EXAMPLE.is_file(), reason='Requiere repo libredte-php-original')
class TestEjemploOficialSii:
    """Mismos resultados que ValidarXmlSobreEnvioDocumentosOkTest de PHP."""

    def test_digest_del_sobre_coincide(self, signer):
        results = signer.validate_xml(OFFICIAL_EXAMPLE.read_bytes())
        set_doc = next(r for r in results if r.reference == 'SetDoc')
        assert 'DigestValue' not in (set_doc.error or '')

    def test_digest_c14n_igual_a_php(self, signer):
        # Valor calculado por PHP (DOMNode::C14N) que aparece en su test.
        assert signer.digest_value(OFFICIAL_EXAMPLE.read_bytes(), 'F60T33') == '4GXbxCc2Fhaiol1WYeMzcwRKnT4='

    def test_firmas_del_ejemplo_no_son_validas(self, signer):
        results = signer.validate_xml(OFFICIAL_EXAMPLE.read_bytes())
        assert len(results) == 2
        assert all('SignatureValue' in r.error for r in results)


def _real_certificate():
    pfx = os.environ.get('RYPSYSTEMS_DTE_PFX')
    pass_file = Path(os.environ.get(
        'RYPSYSTEMS_DTE_PFX_PASS_FILE', Path.home() / '.rypsystems-dte' / 'pfx.pass'
    ))
    if not pfx or not Path(pfx).is_file() or not pass_file.is_file():
        return None
    return DigitalCertificate.from_file(pfx, pass_file.read_text().strip())


@pytest.mark.skipif(_real_certificate() is None, reason='Sin certificado real configurado')
def test_firma_con_certificado_real(signer):
    signed = signer.sign_xml(DTE_XML, _real_certificate(), 'LibreDTE_T33F1')
    assert signer.is_valid_xml(signed)
