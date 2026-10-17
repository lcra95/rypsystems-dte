"""
Tests de emisión de DTE: timbraje con CAF (TED) y firma con certificado.

Incluye verificaciones contra el ejemplo oficial del SII (TED y CAF reales).
"""

import base64
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

from rypsystems_dte.dte import DocumentBag, DTEBuilder
from rypsystems_dte.dte.builder import BuilderError
from rypsystems_dte.firma import DigitalCertificate, SelfSignedCertificate, XmlSigner
from rypsystems_dte.firma.ted import TEDValidator, _ted_element
from rypsystems_dte.identifier import CafFaker, CafValidator
from rypsystems_dte.xml.canonical import c14n_encoded_flattened
from rypsystems_dte.xml.encoder import XmlEncoder

PHP_FIXTURES = Path(__file__).resolve().parents[2] / 'libredte-php-original' / 'tests' / 'fixtures'
OFFICIAL_EXAMPLE = PHP_FIXTURES / 'xml' / 'documentos_ok' / 'F60T33-ejemplo-oficial-SII.xml'
SII = '{http://www.sii.cl/SiiDte}'
# Hora actual: el certificado autofirmado de prueba es válido desde ahora.
TIMESTAMP = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def datos_factura(folio: int = 1) -> dict:
    return {
        'Encabezado': {
            'IdDoc': {'TipoDTE': 33, 'Folio': folio, 'FchEmis': TIMESTAMP[:10]},
            'Emisor': {
                'RUTEmisor': '76192083-9',
                'RznSoc': 'SASCO SpA',
                'GiroEmis': 'Tecnología',
                'Acteco': 726000,
                'DirOrigen': 'Santa Cruz',
                'CmnaOrigen': 'Santa Cruz',
            },
            'Receptor': {
                'RUTRecep': '60803000-K',
                'RznSocRecep': 'Servicio de Impuestos Internos "SII" de Chile',
                'GiroRecep': 'Gobierno',
                'DirRecep': 'Santiago',
                'CmnaRecep': 'Santiago',
            },
        },
        # Neto 1000, IVA 190 y total 1190 los calcula el normalizador.
        'Detalle': [{'NmbItem': 'Desarrollo de software Ñandú', 'QtyItem': 1, 'PrcItem': 1000}],
    }


@pytest.fixture(scope='module')
def certificate() -> DigitalCertificate:
    return SelfSignedCertificate(rut='11222333-9').create()


@pytest.fixture(scope='module')
def caf():
    return CafFaker(rut='76192083-9', tipo_documento=33, desde=1, hasta=100).create()


def emitir(datos, caf=None, certificate=None, timestamp=TIMESTAMP):
    bag = DocumentBag(33, datos)
    bag.get_builder_options()['timestamp'] = timestamp
    if caf:
        bag.set_caf(caf)
    if certificate:
        bag.set_certificate(certificate)
    documento = DTEBuilder().build(bag)
    return bag, documento, documento.get_xml_document().get_xml_bytes()


class TestEmisionDte:

    def test_documento_timbrado_y_firmado(self, caf, certificate):
        bag, documento, xml = emitir(datos_factura(), caf, certificate)

        assert xml.startswith(b'<?xml version="1.0" encoding="ISO-8859-1"?>\n')
        root = etree.fromstring(xml)
        assert root.tag == f'{SII}DTE'
        documento_node = root.find(f'{SII}Documento')
        assert documento_node.get('ID') == 'LibreDTE_76192083-9_T033F000000001'

        # TED y TmstFirma al final del Documento, firma al final del DTE.
        assert [etree.QName(c).localname for c in documento_node][-2:] == ['TED', 'TmstFirma']
        assert documento_node.findtext(f'{SII}TmstFirma') == TIMESTAMP
        assert etree.QName(root[-1]).localname == 'Signature'

        # Firma y timbre válidos.
        results = XmlSigner().validate_xml(xml)
        assert len(results) == 1 and results[0].is_valid, results[0].error
        assert results[0].reference == bag.get_id()
        assert TEDValidator.verify_ted_signature(xml, caf)

        # Los datos del documento se pueden consultar pese al namespace.
        assert documento.get_folio() == 1
        assert documento.get_rut_emisor() == '76192083-9'
        totales = bag.get_datos()['Encabezado']['Totales']
        assert (totales['MntNeto'], totales['IVA'], totales['MntTotal']) == (1000, 190, 1190)

    def test_texto_iso_8859_1(self, caf, certificate):
        _, _, xml = emitir(datos_factura(), caf, certificate)
        assert 'Desarrollo de software Ñandú'.encode('iso-8859-1') in xml
        assert b'Servicio de Impuestos Internos &quot;SII&quot; de Chile' in xml

    def test_ted_contiene_caf_y_datos(self, caf, certificate):
        _, _, xml = emitir(datos_factura(7), caf, certificate)
        dd = etree.fromstring(xml).find(f'{SII}Documento/{SII}TED/{SII}DD')
        assert [etree.QName(c).localname for c in dd] == [
            'RE', 'TD', 'F', 'FE', 'RR', 'RSR', 'MNT', 'IT1', 'CAF', 'TSTED'
        ]
        assert dd.findtext(f'{SII}F') == '7'
        assert dd.findtext(f'{SII}RSR') == 'Servicio de Impuestos Internos "SII" de '  # 40 caracteres
        assert dd.findtext(f'{SII}TSTED') == TIMESTAMP
        assert dd.find(f'{SII}CAF/{SII}DA/{SII}IDK').text == '666'

    def test_modificar_monto_invalida_firma_y_timbre(self, caf, certificate):
        _, _, xml = emitir(datos_factura(), caf, certificate)
        tampered = xml.replace(b'<MntTotal>1190</MntTotal>', b'<MntTotal>9990</MntTotal>')
        assert not XmlSigner().is_valid_xml(tampered)
        tampered_ted = xml.replace(b'<MNT>1190</MNT>', b'<MNT>9990</MNT>')
        assert not TEDValidator.verify_ted_signature(tampered_ted, caf)

    def test_solo_timbre_sin_firma(self, caf):
        _, _, xml = emitir(datos_factura(), caf)
        assert b'<TED version="1.0">' in xml
        assert b'Signature' not in xml and b'TmstFirma' not in xml

    def test_folio_fuera_de_rango(self, caf):
        with pytest.raises(BuilderError, match='no está disponible en el rango del CAF'):
            emitir(datos_factura(101), caf)

    def test_caf_de_otro_tipo(self):
        caf_61 = CafFaker(rut='76192083-9', tipo_documento=61).create()
        with pytest.raises(BuilderError, match='es para documentos tipo 61'):
            emitir(datos_factura(), caf_61)

    def test_caf_vencido(self):
        caf_viejo = CafFaker(rut='76192083-9', tipo_documento=33, fecha_autorizacion='2025-01-01').create()
        with pytest.raises(BuilderError, match='no está vigente'):
            emitir(datos_factura(), caf_viejo)

    def test_certificado_no_vigente(self, caf, certificate):
        with pytest.raises(BuilderError, match='no está vigente'):
            emitir(datos_factura(), caf, certificate, timestamp='2000-01-01T00:00:00')

    @pytest.mark.skipif(shutil.which('xmllint') is None or shutil.which('openssl') is None,
                        reason='Requiere xmllint y openssl')
    def test_firma_verificada_con_xmllint_y_openssl(self, caf, certificate, tmp_path):
        """Verificación independiente de lxml: C14N de xmllint y RSA de openssl."""
        bag, _, xml = emitir(datos_factura(), caf, certificate)
        text = xml.decode('iso-8859-1')
        documento = text[text.index('<Documento'):text.index('</Documento>') + len('</Documento>')]
        documento = documento.replace('<Documento ', f'<Documento xmlns="{SII[1:-1]}" ', 1)
        signed_info = text[text.index('<SignedInfo'):text.index('</SignedInfo>') + len('</SignedInfo>')]
        signed_info = signed_info.replace('<SignedInfo ', '<SignedInfo xmlns="http://www.w3.org/2000/09/xmldsig#" ', 1)
        (tmp_path / 'documento.xml').write_text(documento, encoding='utf-8')
        (tmp_path / 'signed_info.xml').write_text(signed_info, encoding='utf-8')
        (tmp_path / 'pub.pem').write_bytes(certificate.public_key.public_bytes(
            encoding=__import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding']).Encoding.PEM,
            format=__import__('cryptography.hazmat.primitives.serialization', fromlist=['PublicFormat']).PublicFormat.SubjectPublicKeyInfo,
        ))
        root = etree.fromstring(xml)
        ns = '{http://www.w3.org/2000/09/xmldsig#}'
        (tmp_path / 'sig.bin').write_bytes(base64.b64decode(''.join(root.findtext(f'.//{ns}SignatureValue').split())))

        c14n_doc = subprocess.run(['xmllint', '--c14n', str(tmp_path / 'documento.xml')], capture_output=True, check=True).stdout
        import hashlib
        assert base64.b64encode(hashlib.sha1(c14n_doc).digest()).decode() == root.findtext(f'.//{ns}DigestValue')

        c14n_si = subprocess.run(['xmllint', '--c14n', str(tmp_path / 'signed_info.xml')], capture_output=True, check=True).stdout
        result = subprocess.run(
            ['openssl', 'dgst', '-sha1', '-verify', str(tmp_path / 'pub.pem'), '-signature', str(tmp_path / 'sig.bin')],
            input=c14n_si, capture_output=True,
        )
        assert result.stdout.strip() == b'Verified OK'


@pytest.mark.skipif(not OFFICIAL_EXAMPLE.is_file(), reason='Requiere repo libredte-php-original')
class TestArtefactosOficialesSii:

    def test_ted_oficial_verifica(self):
        """El TED del ejemplo oficial fue timbrado por el SII con un CAF real."""
        assert TEDValidator.verify_ted_signature(OFFICIAL_EXAMPLE.read_bytes())

    def test_ted_oficial_adulterado_no_verifica(self):
        xml = OFFICIAL_EXAMPLE.read_bytes().replace(b'<MNT>119000</MNT>', b'<MNT>119001</MNT>')
        assert not TEDValidator.verify_ted_signature(xml)

    def test_firma_sii_del_caf_oficial(self):
        """La firma del SII sobre el DA del CAF se valida con resources/certificates/100.cer."""
        caf = _ted_element(OFFICIAL_EXAMPLE.read_bytes()).find(f'{SII}DD/{SII}CAF')
        tree = XmlEncoder().encode({'AUTORIZACION': {'CAF': caf}})
        da = c14n_encoded_flattened(tree, '/AUTORIZACION/CAF/DA', 'ISO-8859-1')
        key = CafValidator()._sii_public_key(int(caf.findtext(f'{SII}DA/{SII}IDK')))
        key.verify(base64.b64decode(caf.findtext(f'{SII}FRMA')), da, padding.PKCS1v15(), hashes.SHA1())


def _real_certificate():
    pfx = os.environ.get('RYPSYSTEMS_DTE_PFX')
    pass_file = Path(os.environ.get(
        'RYPSYSTEMS_DTE_PFX_PASS_FILE', Path.home() / '.rypsystems-dte' / 'pfx.pass'
    ))
    if not pfx or not Path(pfx).is_file() or not pass_file.is_file():
        return None
    return DigitalCertificate.from_file(pfx, pass_file.read_text().strip())


@pytest.mark.skipif(_real_certificate() is None, reason='Sin certificado real configurado')
def test_emision_con_certificado_real(caf):
    _, _, xml = emitir(datos_factura(), caf, _real_certificate())
    assert XmlSigner().is_valid_xml(xml)
    assert TEDValidator.verify_ted_signature(xml, caf)
