"""
Tests del libro de compras y ventas (IECV).
"""

import sys
from pathlib import Path

import pytest
import yaml

from rypsystems_dte.firma import SelfSignedCertificate, XmlSigner
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.libro import LibroCompraVenta, LibroError
from rypsystems_dte.xml.schema import schema_errors

sys.path.insert(0, str(Path(__file__).parent))
from test_dte_emision import datos_factura, emitir  # noqa: E402

SET_COMPRAS = Path(__file__).resolve().parents[1] / 'examples' / 'sets' / 'libro_compras_5136566.yaml'


@pytest.fixture(scope='module')
def certificado():
    return SelfSignedCertificate(rut='11222333-9').create()


def libro_compras():
    datos = yaml.safe_load(SET_COMPRAS.read_text(encoding='utf-8'))
    libro = LibroCompraVenta('COMPRA')
    for doc in datos['documentos']:
        doc = dict(doc)
        if doc.pop('uso_comun', False):
            doc['FctProp'] = datos['factor_proporcionalidad_iva']
        libro.agregar({'TasaImp': 19, 'FchDoc': '2026-10-01', 'RUTDoc': '78885550-8', **doc})
    return libro


class TestLibroCompras:

    def test_detalle_casos_especiales(self):
        detalles = {d['NroDoc']: d for d in libro_compras().detalles}
        # Factura del giro: IVA = neto * 19 %
        assert (detalles[234]['MntIVA'], detalles[234]['MntTotal']) == (12210, 76471)
        # Exento + afecto
        assert (detalles[32]['MntIVA'], detalles[32]['MntTotal']) == (2504, 26930)
        # IVA uso común: no recuperable (MntIVA 0) y va en IVAUsoComun
        assert (detalles[781]['MntIVA'], detalles[781]['IVAUsoComun'], detalles[781]['MntTotal']) == (0, 5758, 36061)
        # Entrega gratuita: IVA no recuperable código 4
        assert detalles[67]['MntIVA'] == 0
        assert detalles[67]['IVANoRec'] == [{'CodIVANoRec': 4, 'MntIVANoRec': 2444}]
        assert detalles[67]['MntTotal'] == 15306
        # Factura de compra con retención total
        assert (detalles[9]['MntIVA'], detalles[9]['IVARetTotal'], detalles[9]['MntTotal']) == (2089, 2089, 10996)
        assert detalles[9]['OtrosImp'] == [{'CodImp': 15, 'TasaImp': 19, 'MntImp': 2089}]

    def test_resumen(self):
        resumen = {t['TpoDoc']: t for t in libro_compras().get_resumen()}
        assert list(resumen) == [30, 33, 46, 60]
        assert resumen[30]['TotIVAUsoComun'] == 5758
        assert resumen[30]['FctProp'] == 0.6
        assert resumen[30]['TotCredIVAUsoComun'] == 3455
        assert resumen[33]['TotIVANoRec'] == [{'CodIVANoRec': 4, 'TotOpIVANoRec': 1, 'TotMntIVANoRec': 2444}]
        assert (resumen[46]['TotOpIVARetTotal'], resumen[46]['TotIVARetTotal']) == (1, 2089)
        assert (resumen[60]['TotDoc'], resumen[60]['TotMntNeto'], resumen[60]['TotMntTotal']) == (2, 13633, 16223)

    def test_xml_valido_y_firmado(self, certificado):
        xml = libro_compras().generar(certificado, '76192083-9', '2026-10', '2026-10-17', 0,
                                      tipo_libro='ESPECIAL', folio_notificacion=2)
        assert schema_errors(xml, 'LibroCV_v10.xsd') == []
        assert XmlSigner().is_valid_xml(xml)
        assert b'<FolioNotificacion>2</FolioNotificacion>' in xml
        assert b'<SignedInfo xmlns="http://www.w3.org/2000/09/xmldsig#" xmlns:xsi=' in xml


class TestLibroVentas:

    def test_desde_dte_emitidos(self, certificado):
        caf = CafFaker(rut='76192083-9', tipo_documento=33).create()
        libro = LibroCompraVenta('VENTA')
        for folio in (1, 2):
            _, _, xml = emitir(datos_factura(folio), caf, certificado)
            libro.agregar_dte(xml)
        resumen = libro.get_resumen()
        assert resumen == [{'TpoDoc': 33, 'TotDoc': 2, 'TotMntExe': 0, 'TotMntNeto': 2000,
                            'TotMntIVA': 380, 'TotMntTotal': 2380}]
        detalle = libro.get_detalle()[0]
        assert (detalle['NroDoc'], detalle['RUTDoc'], detalle['TasaImp']) == (1, '60803000-K', 19)
        xml = libro.generar(certificado, '76192083-9', '2026-10', '2026-10-17', 0,
                            tipo_libro='ESPECIAL', folio_notificacion=1)
        assert schema_errors(xml, 'LibroCV_v10.xsd') == []
        assert XmlSigner().is_valid_xml(xml)

    def test_documento_anulado(self):
        libro = LibroCompraVenta('VENTA')
        libro.agregar({'TpoDoc': 33, 'NroDoc': 5, 'Anulado': 'A'})
        assert libro.get_resumen()[0]['TotAnulado'] == 1

    def test_errores(self, certificado):
        with pytest.raises(LibroError):
            LibroCompraVenta('OTRA')
        with pytest.raises(LibroError, match='no tiene documentos'):
            LibroCompraVenta('VENTA').generar(certificado, '76192083-9', '2026-10', '2026-10-17')
        libro = LibroCompraVenta('VENTA')
        libro.agregar({'TpoDoc': 33, 'NroDoc': 1, 'MntNeto': 100, 'TasaImp': 19})
        with pytest.raises(LibroError, match='folio de notificación'):
            libro.generar(certificado, '76192083-9', '2026-10', '2026-10-17', tipo_libro='ESPECIAL')
