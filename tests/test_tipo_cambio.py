"""
Tipo de cambio para exportación: API de la BDE del Banco Central (respuestas
en el formato documentado en si3.bcentral.cl) y valores fijos.
"""

import pytest

from rypsystems_dte import BancoCentral, TipoCambioError, TiposCambioFijos, emitir_documento
from rypsystems_dte.firma import SelfSignedCertificate
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.tipo_cambio import DOLAR_OBSERVADO, completar_tipo_cambio


def obs(fecha, valor, estado='OK'):
    return {'indexDateString': fecha, 'value': valor, 'statusCode': estado}


SERIES = {
    DOLAR_OBSERVADO: [obs('16-10-2026', '951.32'), obs('17-10-2026', 'NaN', 'ND'), obs('18-10-2026', 'NaN', 'ND'),
                      obs('19-10-2026', '948.75')],
    'PARIDAD.EUR': [obs('16-10-2026', '0.8600'), obs('19-10-2026', '0.8550')],
}


class Respuesta:
    def __init__(self, datos):
        self.datos = datos

    def json(self):
        return self.datos


class SesionFalsa:
    def __init__(self):
        self.consultas = []

    def get(self, url, params, timeout):
        self.consultas.append(params)
        if params['function'] == 'SearchSeries':
            return Respuesta({'Codigo': 0, 'Descripcion': 'Success', 'SeriesInfos': [
                {'seriesId': 'F072.CLP.EUR.N.O.D', 'spanishTitle': 'Euro (pesos por euro)', 'englishTitle': 'Euro'},
                {'seriesId': DOLAR_OBSERVADO, 'spanishTitle': 'Dólar observado', 'englishTitle': 'Observed dollar'}]})
        serie = params['timeseries']
        if serie not in SERIES:
            return Respuesta({'Codigo': -50, 'Descripcion': 'Serie no existe', 'Series': {}})
        hasta = params['lastdate']
        filtradas = [o for o in SERIES[serie]
                     if '-'.join(reversed(o['indexDateString'].split('-'))) <= hasta]
        return Respuesta({'Codigo': 0, 'Descripcion': 'Success',
                          'Series': {'seriesId': serie, 'Obs': filtradas}, 'SeriesInfos': []})


@pytest.fixture
def bcch():
    sesion = SesionFalsa()
    return BancoCentral(token='TOKEN', series={'euro': {'paridad': 'PARIDAD.EUR'}}, session=sesion), sesion


def test_dolar_observado_y_fin_de_semana(bcch):
    banco, sesion = bcch
    assert banco.tipo_cambio('DOLAR USA', '2026-10-19') == 948.75
    # Sábado y domingo sin valor: último publicado (viernes 16)
    assert banco.tipo_cambio('dolar usa', '2026-10-18') == 951.32
    consulta = sesion.consultas[0]
    assert consulta['token'] == 'TOKEN' and consulta['timeseries'] == DOLAR_OBSERVADO
    assert (consulta['firstdate'], consulta['lastdate']) == ('2026-10-09', '2026-10-19')
    # Cache por serie y fecha
    banco.tipo_cambio('DOLAR USA', '2026-10-19')
    assert len(sesion.consultas) == 2


def test_paridad_y_errores(bcch):
    banco, _ = bcch
    assert banco.tipo_cambio('EURO', '2026-10-19') == pytest.approx(948.75 / 0.8550)
    with pytest.raises(TipoCambioError, match='buscar_series'):
        banco.tipo_cambio('YEN', '2026-10-19')
    banco.series['LIBRA EST'] = 'NO.EXISTE'
    with pytest.raises(TipoCambioError, match='-50'):
        banco.tipo_cambio('LIBRA EST', '2026-10-19')
    with pytest.raises(TipoCambioError, match='no tiene valores'):
        banco.tipo_cambio('DOLAR USA', '2026-09-01')
    with pytest.raises(TipoCambioError):
        BancoCentral()
    assert [s['seriesId'] for s in banco.buscar_series('euro')] == ['F072.CLP.EUR.N.O.D']


def datos_exportacion(**otra):
    return {
        'Encabezado': {
            'IdDoc': {'TipoDTE': 110, 'Folio': 1, 'FchEmis': '2026-10-18', 'IndServicio': 3},
            'Emisor': {'RUTEmisor': '76192083-9', 'RznSoc': 'SASCO SpA', 'GiroEmis': 'Servicios', 'Acteco': 620900,
                       'DirOrigen': 'Santa Cruz', 'CmnaOrigen': 'Santa Cruz'},
            'Receptor': {'RUTRecep': '55555555-5', 'RznSocRecep': 'Northwind Inc.', 'Extranjero': {'Nacionalidad': 225},
                         'GiroRecep': 'Software', 'DirRecep': 'San Francisco'},
            'Totales': {'TpoMoneda': 'DOLAR USA'},
            **({'OtraMoneda': otra} if otra else {}),
        },
        'Detalle': [{'NmbItem': 'Desarrollo', 'QtyItem': 10, 'PrcItem': 45}],
        'Referencia': [{'TpoDocRef': 812, 'FolioRef': 1, 'RazonRef': 'RESOLUCION SNA'}],
    }


def test_completar_en_exportacion(bcch):
    banco, _ = bcch
    datos = completar_tipo_cambio(datos_exportacion(), banco)
    assert datos['Encabezado']['OtraMoneda'] == {'TpoMoneda': 'PESO CL', 'TpoCambio': 951.32}
    # Un TpoCambio informado se respeta; los documentos nacionales no se tocan
    assert completar_tipo_cambio(datos_exportacion(TpoMoneda='PESO CL', TpoCambio=900), banco)[
        'Encabezado']['OtraMoneda']['TpoCambio'] == 900
    nacional = {'Encabezado': {'IdDoc': {'TipoDTE': 33}, 'Totales': {'TpoMoneda': 'DOLAR USA'}}}
    assert 'OtraMoneda' not in completar_tipo_cambio(nacional, banco)['Encabezado']


def test_emitir_exportacion_con_tipo_de_cambio():
    certificado = SelfSignedCertificate().create()
    caf = CafFaker(rut='76192083-9', tipo_documento=110, desde=1, hasta=10).create()
    doc = emitir_documento(datos_exportacion(), caf, certificado, tipo_cambio=TiposCambioFijos({'DOLAR USA': 950}))
    otra = doc.datos['Encabezado']['OtraMoneda'][0]  # el normalizador la deja como lista
    assert otra['TpoCambio'] == 950 and otra['MntTotOtrMnda'] == 450 * 950
    with pytest.raises(Exception, match='No hay tipo de cambio'):
        emitir_documento(datos_exportacion(), caf, certificado, tipo_cambio=TiposCambioFijos({'EURO': 1}))
