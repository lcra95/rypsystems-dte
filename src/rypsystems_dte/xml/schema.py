"""
Validación de documentos XML contra los esquemas XSD oficiales del SII.

Equivale a XmlValidator de derafu/xml y a los validateSchema() de
ValidatorWorker y DispatcherWorker de LibreDTE PHP.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Union

from lxml import etree

from .canonical import parse

SCHEMAS_PATH = Path(__file__).resolve().parent.parent / 'resources' / 'schemas'


class XmlSchemaError(Exception):
    """El XML no cumple con el esquema XSD."""

    def __init__(self, schema: str, errors: List[str]):
        self.schema = schema
        self.errors = errors
        detail = '\n'.join(f'  - {e}' for e in errors[:20])
        more = f'\n  ... y {len(errors) - 20} errores más' if len(errors) > 20 else ''
        super().__init__(f'El XML no es válido según el esquema {schema}:\n{detail}{more}')


@lru_cache(maxsize=None)
def load_schema(name: str) -> etree.XMLSchema:
    """Carga (y guarda en caché) un esquema XSD de resources/schemas."""
    path = SCHEMAS_PATH / name
    if not path.is_file():
        raise FileNotFoundError(f'No existe el esquema XSD {name} en {SCHEMAS_PATH}.')
    return etree.XMLSchema(etree.parse(str(path)))


SII_DTE_NAMESPACE = 'http://www.sii.cl/SiiDte'


def _with_namespace(tree: etree._ElementTree, namespace: str) -> etree._ElementTree:
    """
    Copia del documento con los nodos sin namespace en el namespace indicado.

    Los DTE se generan sin xmlns (como LibreDTE clásico) y lo heredan del
    EnvioDTE; para validarlos solos contra DTE_v10.xsd se les asigna el
    namespace del SII en una copia, sin alterar el XML firmado.
    """
    root = etree.fromstring(etree.tostring(tree))
    for node in root.iter():
        if isinstance(node.tag, str) and not node.tag.startswith('{'):
            node.tag = f'{{{namespace}}}{node.tag}'
    etree.cleanup_namespaces(root)
    return etree.fromstring(etree.tostring(root)).getroottree()


def schema_errors(xml: Union[str, bytes, etree._ElementTree], schema: str) -> List[str]:
    """Errores de validación del XML contra el esquema (lista vacía si es válido)."""
    tree = xml if isinstance(xml, etree._ElementTree) else parse(xml)
    if schema == 'DTE_v10.xsd' and etree.QName(tree.getroot()).namespace is None:
        tree = _with_namespace(tree, SII_DTE_NAMESPACE)
    validator = load_schema(schema)
    if validator.validate(tree):
        return []
    return [f'Línea {e.line}: {e.message}' for e in validator.error_log]


def validate_schema(xml: Union[str, bytes, etree._ElementTree], schema: str) -> None:
    """
    Valida el XML contra el esquema.

    Raises:
        XmlSchemaError: Si el XML no cumple con el esquema
    """
    errors = schema_errors(xml, schema)
    if errors:
        raise XmlSchemaError(schema, errors)
