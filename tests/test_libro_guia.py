"""
Tests del libro de guías de despacho.
"""

import pytest

from rypsystems_dte.dte import DocumentBag, DTEBuilder
from rypsystems_dte.firma import SelfSignedCertificate, XmlSigner
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.libro import LibroError, LibroGuia
from rypsystems_dte.xml.schema import schema_errors

EMISOR = {'RUTEmisor': '76192083-9', 'RznSoc': 'SASCO SpA', 'GiroEmis': 'Tecnología', 'Acteco': 726000,
          'DirOrigen': 'Santa Cruz', 'CmnaOrigen': 'Santa Cruz'}
RECEPTOR = {'RUTRecep': '60803000-K', 'RznSocRecep': 'SII', 'GiroRecep': 'Gobierno', 'DirRecep': 'Santiago',
            'CmnaRecep': 'Santiago'}


@pytest.fixture(scope='module')
def certificado():
    return SelfSignedCertificate().create()


@pytest.fixture(scope='module')
def guias(certificado):
    caf = CafFaker(rut='76192083-9', tipo_documento=52).create()
    casos = [
        ({'IndTraslado': 5}, [{'NmbItem': 'ITEM 1', 'QtyItem': 75}]),
        ({'IndTraslado': 1, 'TipoDespacho': 2}, [{'NmbItem': 'ITEM 1', 'QtyItem': 308, 'PrcItem': 6388}]),
        ({'IndTraslado': 1, 'TipoDespacho': 1}, [{'NmbItem': 'ITEM 1', 'QtyItem': 157, 'PrcItem': 1836}]),
    ]
    xmls = []
    for folio, (id_doc, detalle) in enumerate(casos, start=1):
        bag = DocumentBag(52, {
            'Encabezado': {'IdDoc': {'TipoDTE': 52, 'Folio': folio, **id_doc}, 'Emisor': dict(EMISOR),
                           'Receptor': dict(RECEPTOR)},
            'Detalle': detalle,
        })
        bag.set_caf(caf)
        bag.set_certificate(certificado)
        DTEBuilder().build(bag)
        xmls.append(bag.get_xml())
    return xmls


def test_libro_de_guias(guias, certificado):
    libro = LibroGuia()
    traslado = libro.agregar_dte(guias[0])
    assert (traslado['TpoOper'], traslado['RUTDoc'], traslado['MntNeto'], traslado['MntTotal']) == \
        (5, '76192083-9', False, 0)
    venta = libro.agregar_dte(guias[1], TpoDocRef=33, FolioDocRef=5, FchDocRef='2026-10-17')
    assert (venta['MntNeto'], venta['IVA'], venta['MntTotal']) == (1967504, 373826, 2341330)
    anulada = libro.agregar_dte(guias[2], Anulado=2)
    assert anulada['Anulado'] == 2

    resumen = libro.get_resumen()
    assert resumen['TotGuiaVenta'] == 1 and resumen['TotMntGuiaVta'] == 2341330
    assert resumen['TotGuiaAnulada'] == 1
    assert resumen['TotTraslado'] == [{'TpoTraslado': 5, 'CantGuia': 1, 'MntGuia': 0}]

    xml = libro.generar(certificado, '76192083-9', '2026-10', '2026-10-17', 0, folio_notificacion=3)
    assert schema_errors(xml, 'LibroGuia_v10.xsd') == []
    assert XmlSigner().is_valid_xml(xml)


def test_solo_guias(certificado):
    from test_dte_emision import datos_factura, emitir
    _, _, factura = emitir(datos_factura(), CafFaker(rut='76192083-9', tipo_documento=33).create(), certificado)
    with pytest.raises(LibroError, match='tipo 52'):
        LibroGuia().agregar_dte(factura)
