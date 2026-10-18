"""
Tests de boletas electrónicas: emisión (EnvioBOLETA), PDF y API REST del SII
(con respuestas simuladas).
"""

import pytest

from rypsystems_dte.dte import DocumentBag, DocumentEnvelope, DTEBuilder
from rypsystems_dte.firma import SelfSignedCertificate, XmlSigner
from rypsystems_dte.firma.ted import TEDValidator
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.pdf import DtePdf
from rypsystems_dte.sii.webservices import BoletaService, SiiEnvironment
from rypsystems_dte.sii.webservices.exceptions import SiiAuthenticationError, SiiValidationError
from rypsystems_dte.xml.schema import schema_errors

EMISOR = {'RUTEmisor': '76192083-9', 'RznSoc': 'SASCO SpA', 'GiroEmis': 'Servicios', 'Acteco': 726000,
          'DirOrigen': 'Santa Cruz', 'CmnaOrigen': 'Santa Cruz'}


@pytest.fixture(scope='module')
def certificado():
    return SelfSignedCertificate().create()


def boleta(folio, detalle, caf, certificado, tipo=39):
    datos = {
        'Encabezado': {'IdDoc': {'TipoDTE': tipo, 'Folio': folio}, 'Emisor': dict(EMISOR)},
        'Detalle': detalle,
        'Referencia': [{'CodRef': 'SET', 'RazonRef': f'CASO-{folio}'}],
    }
    bag = DocumentBag(tipo, datos)
    bag.set_caf(caf)
    bag.set_certificate(certificado)
    DTEBuilder().build(bag)
    return bag


@pytest.fixture(scope='module')
def boletas(certificado):
    caf = CafFaker(rut=EMISOR['RUTEmisor'], tipo_documento=39, desde=1, hasta=10).create()
    return [
        boleta(1, [{'NmbItem': 'Cambio de aceite', 'QtyItem': 1, 'PrcItem': 19900},
                   {'NmbItem': 'Alineacion y balanceo', 'QtyItem': 1, 'PrcItem': 9900}], caf, certificado),
        boleta(2, [{'NmbItem': 'item afecto 1', 'QtyItem': 8, 'PrcItem': 1590},
                   {'NmbItem': 'item exento 2', 'QtyItem': 2, 'PrcItem': 1000, 'IndExe': 1}], caf, certificado),
        boleta(3, [{'NmbItem': 'Arroz', 'QtyItem': 5, 'UnmdItem': 'Kg', 'PrcItem': 700}], caf, certificado),
    ]


def test_totales_con_iva_incluido(boletas):
    totales = [b.get_datos()['Encabezado']['Totales'] for b in boletas]
    assert (totales[0]['MntNeto'], totales[0]['IVA'], totales[0]['MntTotal']) == (25042, 4758, 29800)
    assert (totales[1]['MntNeto'], totales[1]['MntExe'], totales[1]['IVA'], totales[1]['MntTotal']) == \
        (10689, 2000, 2031, 14720)
    assert boletas[0].get_datos()['Encabezado']['Receptor']['RUTRecep'] == '66666666-6'


def test_envio_boleta(boletas, certificado):
    sobre = DocumentEnvelope(certificado, '2026-10-17', 0)
    for b in boletas:
        assert TEDValidator.verify_ted_signature(b.get_xml(), b.get_caf())
        sobre.add_document(b.get_xml())
    assert sobre.get_tag() == 'EnvioBOLETA'
    xml = sobre.build()
    assert schema_errors(xml, 'EnvioBOLETA_v11.xsd') == []
    assert XmlSigner().is_valid_xml(xml)
    assert b'<RznSocEmisor>SASCO SpA</RznSocEmisor>' in xml and b'<Acteco>' not in xml
    assert b'<CodRef>SET</CodRef>' in xml and b'<UnmdItem>Kg</UnmdItem>' in xml


def test_pdf_boleta(boletas):
    pdf = DtePdf({'fecha': '2026-10-17', 'numero': 0}).render(boletas[1].get_xml())
    # Boleta: sin copia cedible.
    assert pdf.count(b'/Type /Page\n') == 1


class Respuesta:
    def __init__(self, status_code=200, text='', data=None):
        self.status_code, self.text, self._data = status_code, text, data

    def json(self):
        if self._data is None:
            raise ValueError('no json')
        return self._data


SEMILLA = ('<?xml version="1.0" encoding="UTF-8"?><SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema">'
           '<SII:RESP_BODY><SEMILLA>012345678901</SEMILLA></SII:RESP_BODY>'
           '<SII:RESP_HDR><ESTADO>00</ESTADO></SII:RESP_HDR></SII:RESPUESTA>')
TOKEN = ('<?xml version="1.0" encoding="UTF-8"?><SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema">'
         '<SII:RESP_BODY><TOKEN>ABCDEFGHIJKLM</TOKEN></SII:RESP_BODY>'
         '<SII:RESP_HDR><ESTADO>00</ESTADO><GLOSA>Token Creado</GLOSA></SII:RESP_HDR></SII:RESPUESTA>')


@pytest.fixture
def servicio(monkeypatch):
    service = BoletaService(SiiEnvironment.CERTIFICACION, retry_attempts=1)
    llamadas = []

    def request(method, url, **kwargs):
        llamadas.append((method, url, kwargs))
        if url.endswith('boleta.electronica.semilla'):
            return Respuesta(text=SEMILLA)
        if url.endswith('boleta.electronica.token'):
            assert b'<Semilla>12345678901</Semilla>' in kwargs['data']
            return Respuesta(text=TOKEN)
        if url.endswith('boleta.electronica.envio'):
            return Respuesta(data={'rut_emisor': '76192083-9', 'trackid': 9876, 'estado': 'REC',
                                   'fecha_recepcion': '2026-10-17 22:00:00'})
        if '/boleta.electronica.envio/76192083-9-9876' in url:
            return Respuesta(data={'estado': 'EPR', 'estadistica': [
                {'tipo': 39, 'informados': 3, 'aceptados': 3, 'rechazados': 0, 'reparos': 0}],
                'detalle_rep_rech': []})
        if '/boleta.electronica/76192083-9-39-1/estado' in url:
            return Respuesta(data={'codigo': 'DOK', 'descripcion': 'Documento Recibido por el SII'})
        return Respuesta(status_code=404, text='no encontrado')

    monkeypatch.setattr(service.session, 'request', request)
    service.llamadas = llamadas
    return service


def test_autenticacion_y_envio(servicio, certificado):
    assert servicio.authenticate(certificado) == 'ABCDEFGHIJKLM'
    envio = servicio.upload('11222333-9', '76192083-9', b'<?xml version="1.0"?>\n<EnvioBOLETA/>')
    assert envio['track_id'] == 9876 and envio['estado'] == 'REC'
    _, url, kwargs = servicio.llamadas[-1]
    assert url == 'https://pangal.sii.cl/recursos/v1/boleta.electronica.envio'
    assert kwargs['headers']['Cookie'] == 'TOKEN=ABCDEFGHIJKLM'
    assert kwargs['data'] == {'rutSender': '11222333', 'dvSender': '9', 'rutCompany': '76192083', 'dvCompany': '9'}
    estado = servicio.query_upload_status('76192083-9', 9876)
    assert estado['estado'] == 'EPR' and estado['estadistica'][0]['aceptados'] == 3
    doc = servicio.query_document_status('76192083-9', 39, 1, '66666666-6', 29800, '2026-10-17')
    assert doc['codigo'] == 'DOK'
    assert servicio.llamadas[-1][2]['params']['fechaEmision'] == '17-10-2026'


def test_envio_requiere_token_y_envio_boleta(servicio, certificado):
    with pytest.raises(SiiAuthenticationError):
        servicio.upload('11222333-9', '76192083-9', b'<EnvioBOLETA/>')
    servicio.authenticate(certificado)
    with pytest.raises(SiiValidationError):
        servicio.upload('11222333-9', '76192083-9', b'<EnvioDTE/>')


def test_timbre_verificable_sobre_el_texto_del_xml(boletas, certificado):
    """El SII verifica el DD tal cual viene en el XML (reparo 510 con <RSR/>)."""
    import base64
    import re

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    sobre = DocumentEnvelope(certificado, '2026-10-17', 0)
    for b in boletas:
        sobre.add_document(b.get_xml())
    xml = sobre.build()
    assert b'<RSR/>' not in xml and xml.count(b'<RSR></RSR>') == len(boletas)
    assert XmlSigner().is_valid_xml(xml)
    for b, dd, frmt in zip(boletas, re.findall(rb'<DD>.*?</DD>', xml, re.S),
                           re.findall(rb'<FRMT[^>]*>([^<]*)</FRMT>', xml)):
        texto = re.sub(rb'>\s+<', b'><', dd)
        b.get_caf().get_public_key().verify(base64.b64decode(frmt), texto, padding.PKCS1v15(), hashes.SHA1())
