"""
Codificación de diccionarios a XML compatible con LibreDTE PHP.

Traducción de Derafu\\Xml\\Service\\XmlEncoder y XmlDocument::saveXml()
(versión usada por LibreDTE Core): mismas reglas para atributos, valores,
listas, valores omitidos y escape de textos, con salida en ISO-8859-1.
"""

import re
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Dict, Optional

from lxml import etree

from .canonical import fix_entities

XMLNS_NAMESPACE = 'http://www.w3.org/2000/xmlns/'
XML_NAMESPACE = 'http://www.w3.org/XML/1998/namespace'

_CONTROL_CHARS_RE = re.compile('[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
_PREDEFINED_ENTITIES = (
    ('&amp;', '&'), ('&#38;', '&'),
    ('&lt;', '<'), ('&#60;', '<'),
    ('&gt;', '>'), ('&#62', '>'),
    ('&quot;', '"'), ('&#34;', '"'),
    ('&apos;', "'"), ('&#39;', "'"),
)


class XmlEncoderError(Exception):
    """Error al codificar datos a XML."""


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def sanitize(value: str) -> str:
    """
    Limpia un texto antes de escribirlo en un nodo XML.

    Equivale a XmlHelper::sanitize(): quita caracteres de control inválidos
    en XML 1.0, normaliza CR a LF y decodifica entidades predefinidas (que
    luego el serializador escapa una sola vez). A diferencia de PHP no se
    re-escapa '&', porque lxml escapa el texto al serializar.
    """
    if not value or _is_numeric(value):
        return value
    value = _CONTROL_CHARS_RE.sub('', value).replace('\x0D', '\x0A')
    for entity, char in _PREDEFINED_ENTITIES:
        value = value.replace(entity, char)
    return value


def _skip(value: Any) -> bool:
    """Valores que hacen que el nodo no se genere: None, False y listas o dict vacíos."""
    return value is None or value is False or (isinstance(value, (list, dict)) and len(value) == 0)


def _to_text(value: Any, name: str) -> str:
    if value is True:
        return '1'
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%dT%H:%M:%S')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (str, int, float)):
        if isinstance(value, float) and value.is_integer():
            # PHP convierte 10.0 a "10".
            return str(int(value))
        return str(value)
    raise XmlEncoderError(f'El valor de "{name}" no se puede escribir como texto, se entregó {type(value).__name__}.')


def _is_declaration(name: str) -> bool:
    return name == 'xmlns' or name.startswith('xmlns:')


class XmlEncoder:
    """
    Convierte un diccionario con la estructura de LibreDTE en un documento XML.

    Reglas (iguales a PHP):
    - '@attributes': atributos del nodo (incluye declaraciones xmlns).
    - '@value': texto del nodo cuando también tiene atributos.
    - Una lista genera nodos repetidos con el mismo nombre.
    - None, False, [] y {} no generan el nodo; '' y True generan un nodo vacío
      o con "1" respectivamente.
    - Un etree._Element como valor se inserta tal cual (copia).
    """

    def encode(self, data: Dict[str, Any]) -> etree._ElementTree:
        roots = [k for k, v in data.items() if not k.startswith('@') and not _skip(v)]
        if len(roots) != 1:
            raise XmlEncoderError(
                f'Un documento XML solo puede tener un nodo raíz. Hay {len(roots)}: {", ".join(roots)}.'
            )
        name = roots[0]
        value = data[name]
        if isinstance(value, list):
            raise XmlEncoderError('El nodo raíz no puede ser una lista.')
        root = self._create_element(None, name, value if isinstance(value, dict) else {}, {})
        if isinstance(value, dict):
            self._encode_node(root, value)
        else:
            root.text = sanitize(_to_text(value, name)) or None
        return etree.ElementTree(root)

    # ------------------------------------------------------------------

    def _namespaces(self, node: Dict[str, Any], inherited: Dict[str, str]) -> Dict[str, str]:
        attributes = node.get('@attributes')
        if not isinstance(attributes, dict):
            return inherited
        namespaces = dict(inherited)
        for name, uri in attributes.items():
            if _is_declaration(name) and isinstance(uri, str):
                namespaces[name[6:]] = uri
        return namespaces

    def _create_element(
        self,
        parent: Optional[etree._Element],
        name: str,
        node: Dict[str, Any],
        inherited: Dict[str, str],
    ) -> etree._Element:
        namespaces = self._namespaces(node, inherited)
        # Solo se declaran en el nodo los namespaces que el propio nodo define.
        own = {
            (k[6:] or None): v
            for k, v in (node.get('@attributes') or {}).items()
            if _is_declaration(k) and isinstance(v, str)
        }
        prefix = name.split(':', 1)[0] if ':' in name else ''
        uri = namespaces.get(prefix, '')
        local = name.split(':', 1)[1] if ':' in name else name
        tag = f'{{{uri}}}{local}' if uri else local
        if parent is None:
            element = etree.Element(tag, nsmap=own or None)
        else:
            element = etree.SubElement(parent, tag, nsmap=own or None)
        return element

    def _encode_node(self, element: etree._Element, data: Dict[str, Any]) -> None:
        namespaces = {k or '': v for k, v in element.nsmap.items()}

        if '@value' in data and not _skip(data['@value']):
            element.text = sanitize(_to_text(data['@value'], etree.QName(element).localname))

        for key, value in data.items():
            if key == '@value':
                continue
            if key == '@attributes':
                if isinstance(value, dict):
                    self._add_attributes(element, value, namespaces)
                continue
            if key == '@comment':
                self._add_comments(element, value)
                continue
            if isinstance(value, etree._Element):
                self._import_element(element, value, namespaces)
            elif isinstance(value, (dict, list)):
                if value:
                    self._add_children(element, key, value, namespaces)
            elif not _skip(value):
                child = self._create_element(element, key, {}, namespaces)
                child.text = sanitize(_to_text(value, key)) or None

    def _add_attributes(self, element: etree._Element, attributes: Dict[str, Any], namespaces: Dict[str, str]) -> None:
        for name, value in attributes.items():
            if _is_declaration(name):
                continue  # Ya declarados al crear el elemento.
            if isinstance(value, (list, dict)):
                raise XmlEncoderError(
                    f'El valor del atributo "{name}" del nodo "{element.tag}" no puede ser un arreglo.'
                )
            if _skip(value):
                continue
            text = _to_text(value, f'{element.tag}/@{name}')
            prefix = name.split(':', 1)[0] if ':' in name else ''
            if prefix == 'xml':
                element.set(f'{{{XML_NAMESPACE}}}{name.split(":", 1)[1]}', text)
            elif prefix and prefix in namespaces:
                element.set(f'{{{namespaces[prefix]}}}{name.split(":", 1)[1]}', text)
            else:
                element.set(name, text)

    def _add_children(self, parent: etree._Element, name: str, children: Any, namespaces: Dict[str, str]) -> None:
        items = children if isinstance(children, list) else [children]
        for child in items:
            if _skip(child):
                continue
            if isinstance(child, etree._Element):
                self._import_element(parent, child, namespaces)
            elif isinstance(child, dict):
                element = self._create_element(parent, name, child, namespaces)
                self._encode_node(element, child)
            elif isinstance(child, list):
                raise XmlEncoderError(
                    f'El nodo "{name}" permite listas, pero deben ser listas de nodos.'
                )
            else:
                element = self._create_element(parent, name, {}, namespaces)
                element.text = sanitize(_to_text(child, name)) or None

    def _import_element(self, parent: etree._Element, source: etree._Element, namespaces: Dict[str, str]) -> None:
        """
        Copia un nodo existente bajo parent, como si se hubiese decodificado a
        arreglo y vuelto a codificar en PHP: los nodos sin namespace quedan en
        el namespace por defecto del documento y los textos de solo espacios se
        descartan.
        """
        if not isinstance(source.tag, str):
            return  # Comentarios e instrucciones de procesamiento.
        element = self._create_element(parent, etree.QName(source).localname, {}, namespaces)
        for name, value in source.attrib.items():
            element.set(name, value)
        if source.text and source.text.strip():
            element.text = source.text
        for child in source:
            self._import_element(element, child, namespaces)

    @staticmethod
    def _add_comments(parent: etree._Element, comments: Any) -> None:
        for comment in comments if isinstance(comments, list) else [comments]:
            if _skip(comment):
                continue
            text = _to_text(comment, '@comment')
            if '--' in text or text.endswith('-'):
                raise XmlEncoderError(f'Un comentario no puede tener dos guiones seguidos ni terminar en guion: {text}')
            parent.append(etree.Comment(text))


def save_xml(tree: etree._ElementTree, encoding: str = 'ISO-8859-1', pretty_print: bool = True) -> bytes:
    """
    Serializa un documento XML como XmlDocument::saveXml() de PHP.

    Declaración con comillas dobles, indentación de 2 espacios, el encoding
    indicado (ISO-8859-1 por defecto) y &apos;/&quot; en el texto de los nodos.
    """
    root = tree.getroot() if isinstance(tree, etree._ElementTree) else tree
    if pretty_print:
        root = deepcopy(root)
        etree.indent(root, space='  ')
    body = etree.tostring(root, encoding='unicode')
    body = fix_entities(body)
    declaration = f'<?xml version="1.0" encoding="{encoding}"?>\n'
    return (declaration + body + '\n').encode(encoding, errors='xmlcharrefreplace')
