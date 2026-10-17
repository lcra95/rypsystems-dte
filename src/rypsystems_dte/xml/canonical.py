"""
Canonicalización XML (C14N) compatible con LibreDTE PHP.

Reproduce DOMNode::C14N() y los métodos C14NEncoded() y
C14NEncodedFlattened() (antes C14NWithIso88591EncodingFlattened()) de
derafu/xml, usados para firmar, timbrar (TED) y validar CAF.
"""

import re
from copy import deepcopy
from typing import Optional, Union

from lxml import etree

_XML_NS = '{http://www.w3.org/XML/1998/namespace}'
_ENCODING_RE = re.compile(rb'encoding\s*=\s*["\']([A-Za-z0-9._-]+)["\']')


def to_bytes(xml: Union[str, bytes]) -> bytes:
    """
    Normaliza un XML a bytes en el encoding de su declaración.

    Si se entrega un str se codifica según el encoding declarado (por defecto
    ISO-8859-1, el usado por el SII).
    """
    if isinstance(xml, bytes):
        return xml
    match = _ENCODING_RE.search(xml[:200].encode('ascii', 'ignore'))
    encoding = match.group(1).decode('ascii') if match else 'ISO-8859-1'
    return xml.encode(encoding, errors='xmlcharrefreplace')


def parse(xml: Union[str, bytes]) -> etree._ElementTree:
    """Parsea un XML conservando los espacios y sin resolver entidades externas."""
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, huge_tree=True)
    return etree.fromstring(to_bytes(xml), parser).getroottree()


def c14n(node: etree._Element) -> bytes:
    """
    C14N inclusiva, sin comentarios, del nodo en el contexto de su documento.

    Equivale a DOMNode::C14N() de PHP. No se usa directamente
    etree.tostring(node, method='c14n') sobre un subárbol porque libxml2,
    vía lxml, emite declaraciones xmlns="" erróneas en los nietos de un nodo
    con namespace por defecto. En su lugar se canonicaliza una copia aislada
    del nodo que declara todos los namespaces que tiene en alcance, que es
    exactamente lo que exige la C14N inclusiva para el nodo superior.
    """
    if node.getparent() is None:
        return etree.tostring(node, method='c14n', exclusive=False, with_comments=False)

    isolated = etree.Element(node.tag, attrib=dict(node.attrib), nsmap=node.nsmap)
    isolated.text = node.text
    for child in node:
        isolated.append(deepcopy(child))
    # Atributos xml:* heredados de los ancestros (C14N inclusiva los incluye).
    for ancestor in node.iterancestors():
        for name, value in ancestor.attrib.items():
            if name.startswith(_XML_NS) and name not in isolated.attrib:
                isolated.set(name, value)

    return etree.tostring(isolated, method='c14n', exclusive=False, with_comments=False)


def fix_entities(xml: str) -> str:
    """
    Escapa comillas simples y dobles en el contenido de los tags.

    Equivale a XmlHelper::fixEntities() de derafu/xml: el SII exige &apos; y
    &quot; en el texto de los nodos, cosa que C14N no hace.
    """
    out = []
    convert = False
    in_attribute = False
    delimiter = None
    i = 0
    n = len(xml)
    while i < n:
        char = xml[i]
        if not convert and char == '=' and i + 1 < n and xml[i + 1] in ('"', "'"):
            in_attribute = True
            delimiter = xml[i + 1]
            out.append(char + delimiter)
            i += 2
            continue
        if in_attribute and char == delimiter:
            in_attribute = False
            delimiter = None
            out.append(char)
            i += 1
            continue
        if char == '>':
            convert = True
        if char == '<':
            convert = False
        if convert and not in_attribute:
            if char == "'":
                char = '&apos;'
            elif char == '"':
                char = '&quot;'
        out.append(char)
        i += 1
    return ''.join(out)


def _select(tree: etree._ElementTree, xpath: Optional[str]) -> etree._Element:
    if not xpath:
        return tree.getroot()
    nodes = tree.xpath(xpath)
    if not nodes or not isinstance(nodes[0], etree._Element):
        raise ValueError(f'No fue posible obtener el nodo con el XPath {xpath}.')
    return nodes[0]


def c14n_encoded(
    xml: Union[str, bytes, etree._ElementTree],
    xpath: Optional[str] = None,
    encoding: Optional[str] = None,
) -> bytes:
    """
    C14N del nodo (o documento) con entidades corregidas, en el encoding del
    documento. Equivale a XmlDocument::C14NEncoded().
    """
    tree = xml if isinstance(xml, etree._ElementTree) else parse(xml)
    data = fix_entities(c14n(_select(tree, xpath)).decode('utf-8'))
    encoding = (encoding or tree.docinfo.encoding or 'UTF-8').upper()
    # Igual que mb_convert_encoding(), los caracteres que no existen en el
    # encoding de destino se reemplazan por '?'.
    return data.encode(encoding, errors='replace')


def c14n_encoded_flattened(
    xml: Union[str, bytes, etree._ElementTree],
    xpath: Optional[str] = None,
    encoding: Optional[str] = None,
) -> bytes:
    """
    Como c14n_encoded() pero sin espacios entre tags.

    Equivale a XmlDocument::C14NEncodedFlattened() (antes
    C14NWithIso88591EncodingFlattened()). Es la representación usada para
    timbrar el DD del TED, generar el PDF417 y validar la firma del CAF.
    """
    return re.sub(rb'>\s+<', b'><', c14n_encoded(xml, xpath, encoding))
