"""
Tests del intercambio de información: RespuestaDTE (RecepcionEnvio y
ResultadoDTE) y EnvioRecibos.
"""

import sys
from pathlib import Path

import pytest
from lxml import etree

from rypsystems_dte.dte.envelope import DocumentEnvelope
from rypsystems_dte.firma import SelfSignedCertificate, XmlSigner
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.intercambio import EnvioRecibido, EnvioRecibos, IntercambioError, RespuestaEnvio
from rypsystems_dte.xml.schema import schema_errors

sys.path.insert(0, str(Path(__file__).parent))
from test_dte_emision import datos_factura, emitir  # noqa: E402

EMISOR = '76192083-9'


@pytest.fixture(scope='module')
def certificado():
    return SelfSignedCertificate().create()


@pytest.fixture(scope='module')
def envio_xml(certificado):
    caf = CafFaker(rut=EMISOR, tipo_documento=33, desde=1, hasta=10).create()
    datos = datos_factura()
    receptor = datos['Encabezado']['Receptor']['RUTRecep']
    sobre = DocumentEnvelope(certificado, '2026-10-17', 0, rut_receptor=receptor)
    for folio in (1, 2):
        datos['Encabezado']['IdDoc']['Folio'] = folio
        sobre.add_document(emitir(datos, caf, certificado)[2])
    return sobre.build(), receptor


def recibido(envio_xml, rut=None):
    xml, receptor = envio_xml
    return EnvioRecibido(xml, nombre='ENVIO_DTE_1.xml').validar(rut or receptor)


def test_envio_recibido_conforme(envio_xml):
    envio = recibido(envio_xml)
    assert envio.estado == 0, envio.glosa
    assert envio.rut_emisor == EMISOR and envio.id == 'LibreDTE_SetDoc' and envio.digest
    assert [(d.tipo, d.folio, d.estado) for d in envio.documentos] == [(33, 1, 0), (33, 2, 0)]


def test_envio_rut_receptor_no_corresponde(envio_xml):
    envio = recibido(envio_xml, '11111111-1')
    assert envio.estado == 3
    assert all(d.estado == 3 for d in envio.documentos)


def test_envio_firma_alterada(envio_xml):
    xml, receptor = envio_xml
    alterado = xml.replace(b'<RutEnvia>', b'<RutEnvia>', 1).replace(b'<FchResol>2026-10-17', b'<FchResol>2026-10-18')
    envio = EnvioRecibido(alterado).validar(receptor)
    assert envio.estado == 2


def test_no_es_envio():
    with pytest.raises(IntercambioError):
        EnvioRecibido(b'<?xml version="1.0"?><Otro/>')


def test_respuesta_recepcion_envio(envio_xml, certificado):
    envio = recibido(envio_xml)
    respuesta = RespuestaEnvio(envio.rut_receptor, envio.rut_emisor, nombre_contacto='Contacto')
    respuesta.agregar_recepcion_envio(envio, cod_envio=1)
    xml = respuesta.generar(certificado)
    assert schema_errors(xml, 'RespuestaEnvioDTE_v10.xsd') == []
    assert XmlSigner().is_valid_xml(xml)
    root = etree.fromstring(xml)
    assert root.xpath('string(//*[local-name()="NroDTE"])') == '2'
    assert root.xpath('count(//*[local-name()="RecepcionDTE"])') == 2


def test_respuesta_resultado_dte(envio_xml, certificado):
    envio = recibido(envio_xml)
    respuesta = RespuestaEnvio(envio.rut_receptor, envio.rut_emisor)
    respuesta.agregar_resultado_dte(envio.documentos[0].resumen(), cod_envio=1, estado=0)
    respuesta.agregar_resultado_dte(envio.documentos[1].resumen(), cod_envio=1, estado=2,
                                    glosa='DTE Rechazado - Precio no corresponde', codigo_rechazo=-1)
    xml = respuesta.generar(certificado)
    assert schema_errors(xml, 'RespuestaEnvioDTE_v10.xsd') == []
    assert XmlSigner().is_valid_xml(xml)
    with pytest.raises(IntercambioError):
        respuesta.agregar_recepcion_envio(envio, cod_envio=1)


def test_envio_recibos(envio_xml, certificado):
    envio = recibido(envio_xml)
    recibos = EnvioRecibos(envio.rut_receptor, envio.rut_emisor)
    for doc in envio.documentos:
        recibos.agregar(doc.resumen(), recinto='Oficina central', certificate=certificado)
    xml = recibos.generar(certificado)
    assert schema_errors(xml, 'EnvioRecibos_v10.xsd') == []
    resultados = XmlSigner().validate_xml(xml)
    assert len(resultados) == 3 and all(r.is_valid for r in resultados), [r.error for r in resultados]
