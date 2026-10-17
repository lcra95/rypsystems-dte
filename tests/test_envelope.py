"""
Tests del sobre de envío EnvioDTE.
"""

import base64
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from lxml import etree

from rypsystems_dte.dte.envelope import DocumentEnvelope, EnvelopeError, RUT_SII
from rypsystems_dte.firma import SelfSignedCertificate, XmlSigner
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.xml.schema import schema_errors

sys.path.insert(0, str(Path(__file__).parent))
from test_dte_emision import TIMESTAMP, _real_certificate, datos_factura, emitir  # noqa: E402

SII = '{http://www.sii.cl/SiiDte}'
DSIG = '{http://www.w3.org/2000/09/xmldsig#}'


@pytest.fixture(scope='module')
def certificate():
    return SelfSignedCertificate(rut='11222333-9').create()


@pytest.fixture(scope='module')
def caf33():
    return CafFaker(rut='76192083-9', tipo_documento=33, desde=1, hasta=100).create()


@pytest.fixture(scope='module')
def documentos(caf33, certificate):
    return [emitir(datos_factura(folio), caf33, certificate)[2] for folio in (1, 2)]


def build(certificate, documentos, **kwargs):
    envelope = DocumentEnvelope(certificate, fecha_resolucion='2026-10-17', **kwargs)
    for xml in documentos:
        envelope.add_document(xml)
    return envelope.build(TIMESTAMP)


class TestEnvioDte:

    def test_cumple_esquema_y_firmas_validas(self, certificate, documentos):
        xml = build(certificate, documentos)
        assert schema_errors(xml, 'EnvioDTE_v10.xsd') == []
        results = XmlSigner().validate_xml(xml)
        assert [r.reference for r in results] == [
            'LibreDTE_76192083-9_T033F000000001',
            'LibreDTE_76192083-9_T033F000000002',
            'LibreDTE_SetDoc',
        ]
        assert all(r.is_valid for r in results), [r.error for r in results]

    def test_caratula(self, certificate, documentos):
        xml = build(certificate, documentos)
        caratula = etree.fromstring(xml).find(f'{SII}SetDTE/{SII}Caratula')
        assert caratula.findtext(f'{SII}RutEmisor') == '76192083-9'
        assert caratula.findtext(f'{SII}RutEnvia') == '11222333-9'
        assert caratula.findtext(f'{SII}RutReceptor') == RUT_SII
        assert caratula.findtext(f'{SII}FchResol') == '2026-10-17'
        assert caratula.findtext(f'{SII}NroResol') == '0'
        assert caratula.findtext(f'{SII}TmstFirmaEnv') == TIMESTAMP
        assert caratula.findtext(f'{SII}SubTotDTE/{SII}TpoDTE') == '33'
        assert caratula.findtext(f'{SII}SubTotDTE/{SII}NroDTE') == '2'

    def test_firma_del_sobre_al_final(self, certificate, documentos):
        root = etree.fromstring(build(certificate, documentos))
        assert root[-1].tag == f'{DSIG}Signature'
        assert root[-1].find(f'{DSIG}SignedInfo/{DSIG}Reference').get('URI') == '#LibreDTE_SetDoc'

    def test_documentos_se_incluyen_sin_cambios(self, certificate, documentos):
        """Los DTE dentro del sobre conservan sus datos y firma."""
        xml = build(certificate, documentos)
        for documento in documentos:
            original = etree.fromstring(documento)
            sig_value = original[-1].findtext(f'{DSIG}SignatureValue')
            assert sig_value.encode() in xml

    def test_modificar_dte_dentro_del_sobre(self, certificate, documentos):
        xml = build(certificate, documentos)
        tampered = xml.replace(b'<Folio>2</Folio>', b'<Folio>3</Folio>', 1)
        results = XmlSigner().validate_xml(tampered)
        assert not results[1].is_valid
        assert not results[2].is_valid  # El SetDTE también cambió.

    def test_receptor_para_intercambio(self, certificate, documentos):
        xml = build(certificate, documentos, rut_receptor='66666666-6')
        assert b'<RutReceptor>66666666-6</RutReceptor>' in xml

    def test_sin_documentos(self, certificate):
        with pytest.raises(EnvelopeError, match='no tiene documentos'):
            DocumentEnvelope(certificate, '2026-10-17').build()

    def test_no_mezcla_emisores(self, certificate, documentos):
        otro = CafFaker(rut='11111111-1', tipo_documento=33).create()
        datos = datos_factura(1)
        datos['Encabezado']['Emisor']['RUTEmisor'] = '11111111-1'
        _, _, xml_otro = emitir(datos, otro, certificate)
        envelope = DocumentEnvelope(certificate, '2026-10-17').add_document(documentos[0])
        with pytest.raises(EnvelopeError, match='mismo emisor'):
            envelope.add_document(xml_otro)

    def test_solo_dte(self, certificate):
        with pytest.raises(EnvelopeError, match='Solo se pueden agregar documentos DTE'):
            DocumentEnvelope(certificate, '2026-10-17').add_document(b'<Otro/>')

    def test_certificado_no_vigente(self, certificate, documentos):
        envelope = DocumentEnvelope(certificate, '2026-10-17').add_document(documentos[0])
        with pytest.raises(EnvelopeError, match='no está vigente'):
            envelope.build('2000-01-01T00:00:00')

    @pytest.mark.skipif(shutil.which('xmllint') is None or shutil.which('openssl') is None,
                        reason='Requiere xmllint y openssl')
    def test_firma_del_sobre_con_xmllint_y_openssl(self, certificate, documentos, tmp_path):
        """Verificación de la firma del SetDTE independiente de lxml."""
        xml = build(certificate, documentos)
        text = xml.decode('iso-8859-1')
        set_dte = text[text.index('<SetDTE'):text.index('</SetDTE>') + len('</SetDTE>')]
        set_dte = set_dte.replace(
            '<SetDTE ',
            '<SetDTE xmlns="http://www.sii.cl/SiiDte" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ', 1
        )
        (tmp_path / 'set.xml').write_text(set_dte, encoding='utf-8')
        c14n = subprocess.run(['xmllint', '--c14n', str(tmp_path / 'set.xml')], capture_output=True, check=True).stdout
        root = etree.fromstring(xml)
        signature = root[-1]
        assert base64.b64encode(hashlib.sha1(c14n).digest()).decode() == signature.findtext(f'.//{DSIG}DigestValue')

        signed_info = text[text.rindex('<SignedInfo'):text.rindex('</SignedInfo>') + len('</SignedInfo>')]
        (tmp_path / 'si.xml').write_text(signed_info, encoding='utf-8')
        (tmp_path / 'pub.pem').write_bytes(certificate.public_key.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ))
        (tmp_path / 'sig.bin').write_bytes(base64.b64decode(''.join(signature.findtext(f'{DSIG}SignatureValue').split())))
        c14n_si = subprocess.run(['xmllint', '--c14n', str(tmp_path / 'si.xml')], capture_output=True, check=True).stdout
        result = subprocess.run(
            ['openssl', 'dgst', '-sha1', '-verify', str(tmp_path / 'pub.pem'), '-signature', str(tmp_path / 'sig.bin')],
            input=c14n_si, capture_output=True,
        )
        assert result.stdout.strip() == b'Verified OK'


@pytest.mark.skipif(_real_certificate() is None, reason='Sin certificado real configurado')
def test_sobre_con_certificado_real(caf33):
    cert = _real_certificate()
    xml_dte = emitir(datos_factura(1), caf33, cert)[2]
    xml = DocumentEnvelope(cert, '2026-10-17').add_document(xml_dte).build()
    assert schema_errors(xml, 'EnvioDTE_v10.xsd') == []
    assert XmlSigner().is_valid_xml(xml)
    assert f'<RutEnvia>{cert.get_id()}</RutEnvia>'.encode() in xml
