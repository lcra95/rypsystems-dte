"""
Tests de la interfaz pública de emisión (rypsystems_dte.emision).
"""

import pytest

from rypsystems_dte.emision import (
    ClienteSii,
    DocumentoEmitido,
    EmisionError,
    anular,
    armar_envio,
    emitir_documento,
)
from rypsystems_dte.firma import SelfSignedCertificate
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.xml.schema import schema_errors

EMISOR = {'RUTEmisor': '76192083-9', 'RznSoc': 'SASCO SpA', 'GiroEmis': 'Servicios', 'Acteco': 726000,
          'DirOrigen': 'Santa Cruz', 'CmnaOrigen': 'Santa Cruz'}
RECEPTOR = {'RUTRecep': '60803000-K', 'RznSocRecep': 'Servicio de Impuestos Internos', 'GiroRecep': 'Gobierno',
            'DirRecep': 'Teatinos 120', 'CmnaRecep': 'Santiago'}
EXTRANJERO = {'RUTRecep': '55555555-5', 'RznSocRecep': 'Northwind Software Inc.', 'Extranjero': {'Nacionalidad': 225},
              'GiroRecep': 'Software', 'DirRecep': '500 Market Street'}


@pytest.fixture(scope='module')
def certificado():
    return SelfSignedCertificate().create()


@pytest.fixture(scope='module')
def cafs():
    return {t: CafFaker(rut=EMISOR['RUTEmisor'], tipo_documento=t, desde=1, hasta=50).create()
            for t in (33, 39, 56, 61, 110, 112)}


def factura(folio=1, tipo=33, **extra):
    return {
        'Encabezado': {'IdDoc': {'TipoDTE': tipo, 'Folio': folio, 'FchEmis': '2026-10-18'}, 'Emisor': dict(EMISOR),
                       'Receptor': dict(RECEPTOR)},
        'Detalle': [{'NmbItem': 'Servicio', 'QtyItem': 2, 'PrcItem': 10000},
                    {'NmbItem': 'Exento', 'QtyItem': 1, 'PrcItem': 5000, 'IndExe': 1, 'DescuentoPct': 10}],
        'DscRcgGlobal': [{'TpoMov': 'D', 'TpoValor': '%', 'ValorDR': 5}],
        **extra,
    }


def test_emitir_y_armar_envio(certificado, cafs):
    doc = emitir_documento(factura(), cafs[33], certificado)
    assert (doc.tipo, doc.folio, doc.receptor, doc.fecha) == (33, 1, '60803000-K', '2026-10-18')
    assert doc.totales['MntNeto'] == 19000 and doc.totales['MntTotal'] == 19000 + 3610 + 4500
    envio = armar_envio([doc], certificado, '2026-10-17', 0)
    assert b'<EnvioDTE' in envio and not ClienteSii.es_envio_boletas(envio)


def test_errores_de_caf_y_folio(certificado, cafs):
    with pytest.raises(EmisionError, match='tipo 61'):
        emitir_documento(factura(), cafs[61], certificado)
    with pytest.raises(EmisionError, match='no está en el CAF'):
        emitir_documento(factura(folio=51), cafs[33], certificado)
    with pytest.raises(EmisionError, match='obligatorios'):
        emitir_documento({'Encabezado': {}}, cafs[33], certificado)


def test_desde_xml(certificado, cafs):
    doc = emitir_documento(factura(folio=2), cafs[33], certificado)
    copia = DocumentoEmitido.desde_xml(doc.xml)
    assert (copia.tipo, copia.folio, copia.emisor, copia.receptor) == (33, 2, '76192083-9', '60803000-K')
    assert copia.totales['MntTotal'] == doc.totales['MntTotal']
    assert len(copia.datos['Detalle']) == 2 and copia.datos['Encabezado']['Emisor']['Acteco'] == '726000'


@pytest.mark.parametrize('desde_xml', [False, True])
def test_anular_factura(certificado, cafs, desde_xml):
    doc = emitir_documento(factura(folio=3), cafs[33], certificado)
    nc = anular(doc.xml if desde_xml else doc, 4 + desde_xml, cafs[61], certificado)
    assert nc.tipo == 61 and nc.totales['MntTotal'] == doc.totales['MntTotal']
    ref = nc.datos['Referencia'][0]
    assert (ref['TpoDocRef'], ref['FolioRef'], ref['CodRef']) == (33, 3, 1)
    assert schema_errors(nc.xml, 'DTE_v10.xsd') == []
    nd = anular(nc, 1, cafs[56], certificado)
    assert nd.tipo == 56 and nd.totales['MntTotal'] == doc.totales['MntTotal']


def test_anular_exportacion(certificado, cafs):
    datos = {
        'Encabezado': {
            'IdDoc': {'TipoDTE': 110, 'Folio': 1, 'FchEmis': '2026-10-18', 'IndServicio': 3},
            'Emisor': dict(EMISOR), 'Receptor': dict(EXTRANJERO),
            'Transporte': {'Aduana': {'CodClauVenta': 6, 'CodViaTransp': 4, 'CodPtoEmbarque': 992,
                                      'CodPtoDesemb': 180, 'CodPaisRecep': 225, 'CodPaisDestin': 225}},
            'Totales': {'TpoMoneda': 'DOLAR USA'},
            'OtraMoneda': {'TpoMoneda': 'PESO CL', 'TpoCambio': 950},
        },
        'Detalle': [{'NmbItem': 'Desarrollo', 'QtyItem': 80, 'UnmdItem': 'HRS', 'PrcItem': 45}],
        'Referencia': [{'TpoDocRef': 812, 'FolioRef': 1, 'RazonRef': 'RESOLUCION SNA'}],
    }
    doc = emitir_documento(datos, cafs[110], certificado)
    nc = anular(doc, 1, cafs[112], certificado)
    assert nc.tipo == 112 and nc.totales['MntTotal'] == doc.totales['MntTotal'] == 3600
    assert [r['TpoDocRef'] for r in nc.datos['Referencia']] == [110, 812]
    assert schema_errors(nc.xml, 'DTE_v10.xsd') == []


def test_guia_no_se_anula_con_nota(certificado, cafs):
    doc = emitir_documento(factura(folio=6), cafs[33], certificado)
    doc.tipo = 52
    with pytest.raises(EmisionError, match='tipo 52'):
        anular(doc, 1, cafs[61], certificado)


def test_boleta(certificado, cafs):
    datos = {'Encabezado': {'IdDoc': {'TipoDTE': 39, 'Folio': 1}, 'Emisor': dict(EMISOR)},
             'Detalle': [{'NmbItem': 'Cafe', 'QtyItem': 2, 'PrcItem': 1190}]}
    doc = emitir_documento(datos, cafs[39], certificado)
    assert doc.es_boleta and doc.receptor == '66666666-6' and doc.totales['MntTotal'] == 2380
    envio = armar_envio([doc], certificado, '2026-10-17')
    assert ClienteSii.es_envio_boletas(envio)
    with pytest.raises(EmisionError):
        armar_envio([doc, emitir_documento(factura(folio=7), cafs[33], certificado)], certificado, '2026-10-17')


class Falso:
    def __init__(self, respuesta):
        self.respuesta = respuesta

    def query_upload_status(self, rut, track_id):
        return self.respuesta


def test_consultar_envio_normaliza_dte_y_boletas(certificado, monkeypatch):
    sii = ClienteSii(certificado)
    monkeypatch.setattr(sii, 'servicio_dte', lambda: Falso(
        {'estado': 'EPR', 'informados': '3', 'aceptados': '2', 'rechazados': '1', 'reparos': '0', 'detalle': []}))
    monkeypatch.setattr(sii, 'servicio_boletas', lambda: Falso(
        {'estado': 'REC', 'estadistica': [{'tipo': 39, 'informados': 5, 'aceptados': 5, 'rechazados': 0,
                                           'reparos': 0}], 'detalle': []}))
    dte = sii.consultar_envio(1, '76192083-9')
    assert dte['final'] and (dte['aceptados'], dte['rechazados']) == (2, 1)
    boletas = sii.consultar_envio(2, '76192083-9', boletas=True)
    assert not boletas['final'] and boletas['aceptados'] == 5
