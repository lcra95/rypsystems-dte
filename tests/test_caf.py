"""
Tests del componente Identifier (CAF).

Para probar con un CAF real, definir RYPSYSTEMS_DTE_CAF=/ruta/al/caf.xml.
"""

import base64
import os
import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree

from rypsystems_dte.firma import SelfSignedCertificate
from rypsystems_dte.identifier import Caf, CafError, CafFaker, CafValidator
from rypsystems_dte.sii.base import SiiAmbiente
from rypsystems_dte.xml.canonical import c14n_encoded_flattened


@pytest.fixture(scope='module')
def caf() -> Caf:
    return CafFaker(rut='76192083-9', razon_social='SASCO SpA', tipo_documento=33, desde=1, hasta=100).create()


class TestCaf:

    def test_datos(self, caf):
        assert caf.get_id() == 'CAF33D1H100'
        assert caf.get_emisor() == {'rut': '76192083-9', 'razon_social': 'SASCO SpA'}
        assert caf.get_tipo_documento() == 33
        assert caf.get_cantidad_folios() == 100
        assert caf.get_idk() == Caf.IDK_FAKE
        assert caf.es_falso()
        assert caf.get_ambiente() is None

    def test_rango(self, caf):
        assert caf.en_rango(1) and caf.en_rango(100)
        assert not caf.en_rango(0) and not caf.en_rango(101)

    def test_vigencia_factura_vence_a_los_180_dias(self):
        fa = date(2026, 1, 1)
        caf = CafFaker(tipo_documento=33, fecha_autorizacion=fa.isoformat()).create()
        assert caf.vence()
        assert caf.get_fecha_vencimiento() == (fa + timedelta(days=180)).isoformat()
        assert caf.vigente('2026-06-29')
        assert not caf.vigente('2026-06-30')
        assert not caf.vigente('2026-06-30T00:00:00')

    def test_boleta_no_vence(self):
        caf = CafFaker(tipo_documento=39, fecha_autorizacion='2000-01-01').create()
        assert not caf.vence()
        assert caf.get_fecha_vencimiento() is None
        assert caf.vigente()

    def test_claves(self, caf):
        signature = caf.get_private_key().sign(b'x', padding.PKCS1v15(), hashes.SHA1())
        caf.get_public_key().verify(signature, b'x', padding.PKCS1v15(), hashes.SHA1())

    def test_pem_en_una_linea(self, caf):
        """Algunos CAF traen la clave privada en una sola línea."""
        xml = caf.get_xml()
        root = etree.fromstring(xml)
        rsask = root.find('RSASK')
        rsask.text = rsask.text.replace('\n', '')
        one_line = Caf(etree.tostring(root, xml_declaration=True, encoding='ISO-8859-1'))
        assert one_line.get_private_key().private_numbers() == caf.get_private_key().private_numbers()

    def test_xml_invalido(self):
        with pytest.raises(CafError):
            Caf(b'<otro/>')
        with pytest.raises(CafError):
            Caf(b'<AUTORIZACION><CAF>')

    def test_rango_invalido(self):
        with pytest.raises(CafError):
            CafFaker(desde=10, hasta=1)


class TestCafValidator:

    def test_caf_falso_es_valido(self, caf):
        assert CafValidator().validate(caf) is caf

    def test_claves_que_no_corresponden(self, caf):
        other = CafFaker().create()
        root = etree.fromstring(caf.get_xml())
        root.find('RSAPUBK').text = etree.fromstring(other.get_xml()).find('RSAPUBK').text
        with pytest.raises(CafError, match='no corresponden'):
            CafValidator().validate(Caf(etree.tostring(root)))

    @pytest.fixture
    def sii_like(self, tmp_path):
        """CAF con IDK 100 firmado por un 'SII' de prueba."""
        sii = SelfSignedCertificate(rut='60803000-K', name='SII Prueba').create()
        (tmp_path / '100.cer').write_text(sii.get_certificate_pem())
        root = etree.fromstring(CafFaker(razon_social='Compañía "Ñandú"').create().get_xml())
        root.find('CAF/DA/IDK').text = '100'
        tree = root.getroottree()
        da = c14n_encoded_flattened(etree.fromstring(etree.tostring(tree, encoding='ISO-8859-1')).getroottree(),
                                    '/AUTORIZACION/CAF/DA', 'ISO-8859-1')
        root.find('CAF/FRMA').text = sii.sign(da)
        return tmp_path, etree.tostring(root, xml_declaration=True, encoding='ISO-8859-1')

    def test_firma_sii_valida(self, sii_like):
        path, xml = sii_like
        caf = Caf(xml)
        assert caf.get_ambiente() == SiiAmbiente.CERTIFICACION
        CafValidator(path).validate(caf)

    def test_firma_sii_invalida(self, sii_like):
        path, xml = sii_like
        tampered = xml.replace(b'<H>100</H>', b'<H>999</H>')
        with pytest.raises(CafError, match='no está autorizado por el SII'):
            CafValidator(path).validate(Caf(tampered))

    def test_certificados_sii_incluidos(self):
        validator = CafValidator()
        assert validator._sii_public_key(Caf.IDK_CERTIFICACION) is not None
        assert validator._sii_public_key(Caf.IDK_PRODUCCION) is not None


@pytest.mark.skipif(not os.environ.get('RYPSYSTEMS_DTE_CAF'), reason='Sin CAF real configurado')
def test_caf_real():
    caf = Caf.from_file(os.environ['RYPSYSTEMS_DTE_CAF'])
    CafValidator().validate(caf)
    assert caf.get_ambiente() is not None
