"""
El parser del set de pruebas del SII reproduce los sets que el SII aceptó
(examples/sets/*.yaml, escritos a mano para RYP AI SYSTEMS).

En exportación se ignoran los datos inventados del receptor extranjero
(salvo su nacionalidad) y las marcas de los bultos.
"""

import copy
from pathlib import Path

import pytest
import yaml

from rypsystems_dte.certificacion import SetPruebasError, leer_set_boletas, leer_set_pruebas

RAIZ = Path(__file__).resolve().parents[1]
FIXTURES = RAIZ / 'tests' / 'fixtures' / 'sii'
SETS = RAIZ / 'examples' / 'sets'
YAML_POR_SET = {
    5136564: 'set_basico_5136564.yaml', 5136567: 'set_guia_despacho_5136567.yaml',
    5136569: 'set_factura_exenta_5136569.yaml', 5136570: 'set_exportacion_1_5136570.yaml',
    5136571: 'set_exportacion_2_5136571.yaml', 5136572: 'set_liquidacion_5136572.yaml',
    5136573: 'set_factura_compra_5136573.yaml',
}


@pytest.fixture(scope='module')
def sets():
    return {s['numero_atencion']: s for s in leer_set_pruebas((FIXTURES / 'SIISetDePruebas785325664.txt').read_bytes())}


def comparable(caso):
    caso = copy.deepcopy(caso)
    receptor = (caso.get('encabezado') or {}).get('Receptor')
    if receptor and receptor.get('RUTRecep') == '55555555-5':
        caso['encabezado']['Receptor'] = {'Extranjero': receptor['Extranjero']}
    for bulto in ((caso.get('encabezado') or {}).get('Transporte') or {}).get('Aduana', {}).get('TipoBultos', []):
        bulto.pop('Marcas', None)
    return caso


def test_lee_todos_los_sets(sets):
    assert [(n, s['tipo_set']) for n, s in sets.items()] == [
        (5136564, 'basico'), (5136565, 'libro_ventas'), (5136566, 'libro_compras'), (5136567, 'guia'),
        (5136568, 'libro_guias'), (5136569, 'exenta'), (5136570, 'exportacion'), (5136571, 'exportacion'),
        (5136572, 'liquidacion'), (5136573, 'factura_compra')]


@pytest.mark.parametrize('numero', sorted(YAML_POR_SET))
def test_reproduce_set_aceptado(sets, numero):
    esperado = yaml.safe_load((SETS / YAML_POR_SET[numero]).read_text(encoding='utf-8'))
    obtenido = sets[numero]
    assert [c['caso'] for c in obtenido['casos']] == [c['caso'] for c in esperado['casos']]
    for caso_obtenido, caso_esperado in zip(obtenido['casos'], esperado['casos']):
        assert comparable(caso_obtenido) == comparable(caso_esperado), caso_esperado['caso']


def test_libro_de_compras(sets):
    esperado = yaml.safe_load((SETS / 'libro_compras_5136566.yaml').read_text(encoding='utf-8'))
    obtenido = sets[5136566]
    assert obtenido['factor_proporcionalidad_iva'] == esperado['factor_proporcionalidad_iva'] == 60
    assert obtenido['folio_notificacion'] == esperado['folio_notificacion']
    assert [{k: v for k, v in d.items() if k != 'observacion'} for d in obtenido['documentos']] == \
        esperado['documentos']


def test_libro_de_guias(sets):
    assert sets[5136568]['casos'] == {2: {'facturada': True}, 3: {'anulada': True}}
    assert sets[5136565]['folio_notificacion'] == 1


def test_set_de_boletas():
    esperado = yaml.safe_load((SETS / 'set_boleta.yaml').read_text(encoding='utf-8'))
    obtenido = leer_set_boletas((FIXTURES / 'set_prueba_boleta.txt').read_bytes())
    assert obtenido['casos'] == esperado['casos']


def test_tipo_de_cambio_y_errores():
    texto = (FIXTURES / 'SIISetDePruebas785325664.txt').read_bytes()
    sets = {s['numero_atencion']: s for s in leer_set_pruebas(texto, tipos_cambio={'LIBRA EST': 1301.5})}
    assert sets[5136570]['casos'][0]['encabezado']['OtraMoneda']['TpoCambio'] == 1301.5
    with pytest.raises(SetPruebasError):
        leer_set_pruebas('no es un set')
    with pytest.raises(SetPruebasError):
        leer_set_boletas('tampoco')
