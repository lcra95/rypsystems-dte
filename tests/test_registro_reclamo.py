"""
Tests del registro de aceptación o reclamo de DTE (Ley 20.956), con
respuestas tomadas del servicio de certificación del SII.
"""

from datetime import datetime, timedelta

import pytest

from rypsystems_dte.sii.webservices import RegistroReclamoService, SiiEnvironment
from rypsystems_dte.sii.webservices.exceptions import (
    SiiAuthenticationError,
    SiiCommunicationError,
    SiiValidationError,
)


def sobre(function, contenido):
    return (
        '<?xml version="1.0" encoding="UTF-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><ns2:{function}Response xmlns:ns2="http://ws.registroreclamodte.diii.sdi.sii.cl">'
        f'{contenido}</ns2:{function}Response></soap:Body></soap:Envelope>'
    ).encode()


RESPUESTAS = {
    'ingresarAceptacionReclamoDoc': sobre('ingresarAceptacionReclamoDoc',
                                          '<return><codResp>0</codResp><descResp>Accion Completada OK</descResp>'
                                          '</return>'),
    'listarEventosHistDoc': sobre('listarEventosHistDoc',
                                  '<return><codResp>15</codResp><descResp>Listado de eventos del documento</descResp>'
                                  '<listaEventosDoc><codEvento>ACD</codEvento><descEvento>Acepta Contenido del '
                                  'Documento</descEvento><rutResponsable>78532566</rutResponsable><dvResponsable>4'
                                  '</dvResponsable><fechaEvento>18-10-2026 10:15:00</fechaEvento></listaEventosDoc>'
                                  '</return>'),
    'consultarFechaRecepcionSii': sobre('consultarFechaRecepcionSii', '<return>17-10-2026 23:06:22</return>'),
    'consultarDocDteCedible': sobre('consultarDocDteCedible',
                                    '<return><codResp>22</codResp><descResp>No existe registro de reclamo o de '
                                    'recepcion de mercaderia o servicios</descResp></return>'),
}


class Respuesta:
    def __init__(self, content, status_code=200):
        self.content, self.status_code = content, status_code


@pytest.fixture
def servicio(monkeypatch):
    service = RegistroReclamoService(SiiEnvironment.CERTIFICACION, retry_attempts=1)
    service.auth.auth_token = 'ABCDEFGHIJKLM'
    service.auth.token_expiry = datetime.now() + timedelta(hours=1)
    llamadas = []

    def post(url, data, headers, timeout):
        llamadas.append((url, data.decode(), headers))
        funcion = next(f for f in RESPUESTAS if f'<ns1:{f} ' in data.decode())
        return Respuesta(RESPUESTAS[funcion])

    monkeypatch.setattr(service.session, 'post', post)
    service.llamadas = llamadas
    return service


def test_aceptar(servicio):
    respuesta = servicio.aceptar('76192083-9', 33, 1234)
    assert respuesta['ok'] and respuesta['codigo'] == 0
    url, body, headers = servicio.llamadas[-1]
    assert url == 'https://ws2.sii.cl/WSREGISTRORECLAMODTECERT/registroreclamodteservice'
    assert headers['Cookie'] == 'TOKEN=ABCDEFGHIJKLM'
    assert ('<rutEmisor>76192083</rutEmisor><dvEmisor>9</dvEmisor><tipoDoc>33</tipoDoc><folio>1234</folio>'
            '<accionDoc>ACD</accionDoc>') in body


def test_recibo_y_reclamos(servicio):
    servicio.aceptar('76192083-9', 34, 5, recibo_mercaderias=True)
    assert '<accionDoc>ERM</accionDoc>' in servicio.llamadas[-1][1]
    servicio.reclamar('76192083-9', 33, 5, 'rft')
    assert '<accionDoc>RFT</accionDoc>' in servicio.llamadas[-1][1]
    with pytest.raises(SiiValidationError):
        servicio.reclamar('76192083-9', 33, 5, 'ACD')
    with pytest.raises(SiiValidationError):
        servicio.registrar('76192083-9', 33, 5, 'XXX')
    with pytest.raises(SiiValidationError):
        servicio.aceptar('76192083-9', 52, 5)
    with pytest.raises(SiiValidationError):
        servicio.aceptar('76192083-0', 33, 5)


def test_consultas(servicio):
    eventos = servicio.listar_eventos('78532566-4', 33, 20)
    assert eventos['codigo'] == 15
    assert eventos['eventos'] == [{'codigo': 'ACD', 'descripcion': 'Acepta Contenido del Documento',
                                   'responsable': '78532566-4', 'fecha': '18-10-2026 10:15:00'}]
    assert servicio.fecha_recepcion('78532566-4', 33, 20) == datetime(2026, 10, 17, 23, 6, 22)
    cedible = servicio.consultar_cedible('78532566-4', 33, 20)
    assert cedible['codigo'] == 22 and cedible['eventos'] == []


def test_requiere_token():
    service = RegistroReclamoService(SiiEnvironment.PRODUCCION)
    assert service.url == 'https://ws1.sii.cl/WSREGISTRORECLAMODTE/registroreclamodteservice'
    with pytest.raises(SiiAuthenticationError):
        service.listar_eventos('78532566-4', 33, 20)


def test_fault(servicio, monkeypatch):
    fault = (b'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><soap:Fault>'
             b'<faultcode>soap:Server</faultcode><faultstring>Token invalido</faultstring></soap:Fault>'
             b'</soap:Body></soap:Envelope>')
    monkeypatch.setattr(servicio.session, 'post', lambda *a, **k: Respuesta(fault, 500))
    with pytest.raises(SiiCommunicationError, match='Token invalido'):
        servicio.listar_eventos('78532566-4', 33, 20)
