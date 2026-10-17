"""
Tests de validación contra los esquemas XSD oficiales del SII.
"""

import sys
from pathlib import Path

import pytest

from rypsystems_dte.firma import SelfSignedCertificate
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.xml.schema import XmlSchemaError, load_schema, schema_errors, validate_schema

sys.path.insert(0, str(Path(__file__).parent))
from test_dte_emision import OFFICIAL_EXAMPLE, datos_factura, emitir  # noqa: E402


@pytest.mark.parametrize('schema', [
    'DTE_v10.xsd', 'EnvioDTE_v10.xsd', 'EnvioBOLETA_v11.xsd', 'RespuestaEnvioDTE_v10.xsd',
])
def test_esquemas_cargan(schema):
    assert load_schema(schema) is not None


@pytest.mark.skipif(not OFFICIAL_EXAMPLE.is_file(), reason='Requiere repo libredte-php-original')
def test_ejemplo_oficial_cumple_envio_dte():
    validate_schema(OFFICIAL_EXAMPLE.read_bytes(), 'EnvioDTE_v10.xsd')


def test_dte_emitido_cumple_esquema():
    caf = CafFaker(rut='76192083-9', tipo_documento=33).create()
    _, _, xml = emitir(datos_factura(), caf, SelfSignedCertificate().create())
    assert schema_errors(xml, 'DTE_v10.xsd') == []


def test_dte_con_errores_de_esquema():
    from lxml import etree

    caf = CafFaker(rut='76192083-9', tipo_documento=33).create()
    _, _, xml = emitir(datos_factura(), caf, SelfSignedCertificate().create())
    # Orden incorrecto: Receptor después de Totales.
    root = etree.fromstring(xml)
    encabezado = root.find('Documento/Encabezado')
    encabezado.append(encabezado.find('Receptor'))
    with pytest.raises(XmlSchemaError) as e:
        validate_schema(etree.tostring(root), 'DTE_v10.xsd')
    assert 'Receptor' in str(e.value)
