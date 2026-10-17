"""
Tests del normalizador de documentos (traducción del NormalizerWorker de PHP).

Usa como referencia los casos YAML de LibreDTE PHP
(tests/fixtures/yaml/documentos_ok): cada uno trae datos mínimos y, en
Test.ExpectedValues, los montos que calcula PHP.
"""

from pathlib import Path

import pytest
import yaml

from rypsystems_dte.dte import DocumentBag, DTEBuilder
from rypsystems_dte.dte.normalizer import (
    DocumentNormalizer,
    NormalizerError,
    array_merge,
    array_replace_recursive,
    calcular_neto_iva,
    php_empty,
    php_round,
    utils_round,
)
from rypsystems_dte.firma import SelfSignedCertificate, XmlSigner
from rypsystems_dte.firma.ted import TEDValidator
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.xml.schema import schema_errors

FIXTURES = Path(__file__).resolve().parents[2] / 'libredte-php-original' / 'tests' / 'fixtures' / 'yaml' / 'documentos_ok'
CASOS = sorted(FIXTURES.glob('*/*.yaml')) if FIXTURES.is_dir() else []
NO_SOPORTADOS = (43,)


class TestSemanticaPhp:

    @pytest.mark.parametrize('valor, precision, esperado', [
        (2.5, 0, 3), (-2.5, 0, -3), (3.5, 0, 4), (1.005, 2, 1.01), (0.285, 2, 0.29), (5984.99, 0, 5985),
    ])
    def test_round_alejandose_de_cero(self, valor, precision, esperado):
        assert php_round(valor, precision) == esperado

    @pytest.mark.parametrize('valor, vacio', [
        (None, True), (False, True), (0, True), (0.0, True), ('', True), ('0', True), ([], True),
        ({}, True), (1, False), ('a', False), ('0.0', False), ([0], False), (True, False),
    ])
    def test_empty(self, valor, vacio):
        assert php_empty(valor) is vacio

    def test_array_replace_recursive_conserva_orden_de_la_plantilla(self):
        plantilla = {'A': False, 'B': {'x': 1, 'y': 2}, 'C': False}
        datos = {'C': 3, 'Z': 9, 'B': {'y': 20, 'w': 0}}
        resultado = array_replace_recursive(plantilla, datos)
        assert list(resultado) == ['A', 'B', 'C', 'Z']
        assert list(resultado['B'].items()) == [('x', 1), ('y', 20), ('w', 0)]
        assert plantilla['B'] == {'x': 1, 'y': 2}  # no se modifica

    def test_array_merge(self):
        assert list(array_merge({'a': 1, 'b': 2}, {'c': 3, 'a': 9}).items()) == [('a', 9), ('b', 2), ('c', 3)]

    def test_utils_round_y_neto_iva(self):
        assert utils_round(10.5) == 11 and isinstance(utils_round(10.5), int)
        assert utils_round(10.12345, 'DOLAR USA') == 10.1235
        assert calcular_neto_iva(1190, 19) == [1000, 190]
        assert calcular_neto_iva(1190, False) == [0, 0]


class TestNormalizador:

    def datos(self, **detalle):
        return {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1},
                'Emisor': {'RUTEmisor': '76192083-9', 'RznSoc': 'SASCO SpA', 'GiroEmis': 'Tecnología',
                           'Acteco': 726000, 'DirOrigen': 'Santa Cruz', 'CmnaOrigen': 'Santa Cruz'},
                'Receptor': {'RUTRecep': '60803000-K', 'RznSocRecep': 'SII', 'GiroRecep': 'Gobierno',
                             'DirRecep': 'Santiago', 'CmnaRecep': 'Santiago'},
            },
            'Detalle': [{'NmbItem': 'Producto', 'QtyItem': 3, 'PrcItem': 1000, **detalle}],
        }

    def test_factura_simple(self):
        datos = DocumentNormalizer().normalize(self.datos())
        totales = datos['Encabezado']['Totales']
        assert (totales['MntNeto'], totales['IVA'], totales['MntTotal']) == (3000, 570, 3570)
        assert datos['Detalle'][0]['NroLinDet'] == 1
        assert datos['Detalle'][0]['MontoItem'] == 3000
        assert datos['Encabezado']['IdDoc']['TpoTranVenta'] == 1
        assert datos['Encabezado']['IdDoc']['FchEmis']  # fecha por defecto

    def test_no_modifica_los_datos_de_entrada(self):
        datos = self.datos()
        DocumentNormalizer().normalize(datos)
        assert 'Totales' not in datos['Encabezado']

    def test_descuento_por_porcentaje(self):
        datos = DocumentNormalizer().normalize(self.datos(DescuentoPct=10))
        assert datos['Detalle'][0]['DescuentoMonto'] == 300
        assert datos['Detalle'][0]['MontoItem'] == 2700
        assert datos['Encabezado']['Totales']['MntTotal'] == 3213

    def test_item_exento(self):
        datos = DocumentNormalizer().normalize(self.datos(IndExe=1))
        totales = datos['Encabezado']['Totales']
        assert totales['MntExe'] == 3000 and totales['MntTotal'] == 3000

    def test_proveedores_de_emisor_y_receptor(self):
        datos = self.datos()
        del datos['Encabezado']['Receptor']['GiroRecep']
        normalizer = DocumentNormalizer(
            emisor_provider=lambda emisor: {'telefono': '+56 2 1234 5678'},
            receptor_provider=lambda receptor: {'giro': 'Servicios públicos', 'giro_invalido': 'x'},
        )
        normalizado = normalizer.normalize(datos)
        assert normalizado['Encabezado']['Emisor']['Telefono'] == '+56 2 1234 5678'
        assert normalizado['Encabezado']['Receptor']['GiroRecep'] == 'Servicios públicos'
        assert normalizado['Encabezado']['Emisor']['RznSoc'] == 'SASCO SpA'  # no se reemplaza

    def test_tipo_no_soportado(self):
        with pytest.raises(NormalizerError, match='aún no está soportada'):
            DocumentNormalizer().normalize(self.datos(), 43)

    def test_sanitize(self):
        datos = DocumentNormalizer().normalize(self.datos())
        datos['Encabezado']['Emisor']['Acteco'] = 12345
        datos['Encabezado']['Receptor']['GiroRecep'] = 'G' * 60
        datos = DocumentNormalizer.sanitize(datos)
        assert datos['Encabezado']['Emisor']['Acteco'] == '012345'
        assert len(datos['Encabezado']['Receptor']['GiroRecep']) == 40


def _valores(datos, esperado, ruta=()):
    """Compara recursivamente los valores esperados (numéricos o texto)."""
    errores = []
    for clave, valor in esperado.items():
        actual = datos.get(clave) if isinstance(datos, dict) else None
        if isinstance(valor, dict):
            errores += _valores(actual or {}, valor, ruta + (clave,))
        elif isinstance(valor, list):
            for i, item in enumerate(valor):
                actual_i = actual[i] if isinstance(actual, list) and i < len(actual) else {}
                errores += _valores(actual_i, item, ruta + (clave, str(i)))
        else:
            try:
                igual = float(actual) == float(valor)
            except (TypeError, ValueError):
                igual = str(actual) == str(valor)
            if not igual:
                errores.append(f'{"/".join(ruta + (clave,))}: {actual!r} (esperado {valor!r})')
    return errores


@pytest.fixture(scope='module')
def certificado():
    return SelfSignedCertificate().create()


@pytest.mark.skipif(not CASOS, reason='Requiere repo libredte-php-original')
@pytest.mark.parametrize('archivo', CASOS, ids=[c.name for c in CASOS])
def test_casos_libredte_php(archivo, certificado):
    datos = yaml.safe_load(archivo.read_text(encoding='utf-8'))
    esperado = (datos.pop('Test', None) or {}).get('ExpectedValues', {})
    tipo = int(datos['Encabezado']['IdDoc']['TipoDTE'])
    if tipo in NO_SOPORTADOS:
        pytest.skip(f'Normalización de documentos tipo {tipo} aún no traducida')

    if tipo in (39, 41):
        # Las boletas se validan dentro de EnvioBOLETA (no implementado).
        normalizado = DocumentNormalizer().normalize(datos)
        assert _valores(normalizado, esperado) == []
        return

    bag = DocumentBag(tipo, datos)
    bag.set_caf(CafFaker(rut=datos['Encabezado']['Emisor']['RUTEmisor'], tipo_documento=tipo,
                         desde=1, hasta=99999).create())
    bag.set_certificate(certificado)
    DTEBuilder().build(bag)
    xml = bag.get_xml()

    assert _valores(bag.get_datos(), esperado) == []
    assert schema_errors(xml, 'DTE_v10.xsd') == []
    assert XmlSigner().is_valid_xml(xml)
    assert TEDValidator.verify_ted_signature(xml, bag.get_caf())
