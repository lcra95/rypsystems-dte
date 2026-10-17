"""
Módulo de manipulación de documentos XML para DTE.

Traducción de la funcionalidad XML de LibreDTE manteniendo
compatibilidad exacta con la versión PHP original.
"""

import base64
from typing import Any, Dict, List, Optional, Union
from xml.etree import ElementTree as ET
from xml.dom import minidom
import re
import uuid

from pydantic import BaseModel, Field

from .canonical import c14n_encoded_flattened, to_bytes


def _strip_namespaces(element: ET.Element) -> ET.Element:
    """Quita los namespaces de los tags para poder consultar con XPath simples."""
    for node in element.iter():
        if isinstance(node.tag, str) and node.tag.startswith('{'):
            node.tag = node.tag.split('}', 1)[1]
    return element


def _local_name_xpath(xpath: str) -> str:
    """
    Convierte un XPath simple (//TED, /DTE/Documento/TED) en uno que ignora
    namespaces, para consultar documentos con xmlns por defecto.
    """
    def step(name: str) -> str:
        if not name or name in ('*', '.', '..') or name.startswith('@') or '(' in name or '[' in name:
            return name
        return f"*[local-name()='{name}']"
    parts = re.split(r'(/+)', xpath)
    return ''.join(p if p.startswith('/') else step(p) for p in parts)


class XmlDocument:
    r"""
    Manejador de documentos XML que mantiene compatibilidad con XmlDocumentInterface de PHP.

    Equivale a Derafu\Xml\Contract\XmlDocumentInterface.
    Proporciona funcionalidad para consultar, manipular y generar XML
    conforme a los estándares del SII de Chile.
    """

    def __init__(self, xml_content: Union[str, bytes, ET.Element] = None):
        """
        Constructor del documento XML.

        Args:
            xml_content: Contenido XML como string, bytes o Element. Si se
                entrega como string o bytes se conserva el contenido exacto
                (necesario para no invalidar firmas al volver a serializar).
        """
        self._raw: Optional[bytes] = None

        if xml_content is None:
            # Crear documento vacío
            self.root = ET.Element("root")
        elif isinstance(xml_content, (str, bytes)):
            raw = to_bytes(xml_content)
            try:
                self.root = _strip_namespaces(ET.fromstring(raw))
            except ET.ParseError as e:
                raise ValueError(f"XML inválido: {e}")
            self._raw = raw
        elif isinstance(xml_content, ET.Element):
            self.root = xml_content
        else:
            raise TypeError("xml_content debe ser string, bytes o ET.Element")

    def get_xml_bytes(self) -> bytes:
        """
        XML del documento en bytes, en su encoding original.

        Si el documento se creó desde un XML (por ejemplo, uno firmado) se
        entrega exactamente ese contenido.
        """
        if self._raw is not None:
            return self._raw
        return self.save_xml().encode('iso-8859-1', errors='xmlcharrefreplace')

    def query(self, xpath: str, params: Optional[Dict[str, Any]] = None) -> Union[str, List[Dict], None]:
        """
        Ejecuta una consulta XPath en el documento XML.

        Equivale al método query() de XmlDocumentInterface en PHP.

        Args:
            xpath: Expresión XPath a evaluar
            params: Parámetros opcionales (no usado en esta implementación)

        Returns:
            Resultado de la consulta: string, lista de diccionarios o None

        Examples:
            >>> doc.query('//Encabezado/IdDoc/TipoDTE')
            "33"
            >>> doc.query('//Detalle')
            [{'NmbItem': 'Producto 1', 'QtyItem': '10'}]
        """
        try:
            # Convertir XPath relativo a absoluto si es necesario
            if xpath.startswith('//'):
                # XPath global - buscar en todo el documento
                elements = self.root.findall('.' + xpath)
            else:
                # XPath relativo al root
                elements = self.root.findall(xpath)

            if not elements:
                return None

            # Si es un solo elemento, analizar su contenido
            if len(elements) == 1:
                element = elements[0]

                # Si tiene solo texto y no tiene hijos ni atributos, retornar texto
                if (element.text is not None and
                    element.text.strip() and
                    len(element) == 0 and
                    not element.attrib):
                    return element.text.strip()

                # En cualquier otro caso, retornar como diccionario
                return self._element_to_dict(element)

            # Múltiples elementos, retornar como lista
            return [self._element_to_dict(elem) for elem in elements]

        except Exception:
            return None

    def _element_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """
        Convierte un elemento XML a diccionario.

        Args:
            element: Elemento XML a convertir

        Returns:
            Diccionario con la representación del elemento
        """
        result = {}

        # Agregar atributos si existen
        if element.attrib:
            result['@attributes'] = element.attrib

        # Agregar texto si existe
        if element.text and element.text.strip():
            if len(element) == 0:  # No tiene hijos
                return element.text.strip()
            else:  # Tiene hijos y texto
                result['@value'] = element.text.strip()

        # Procesar elementos hijos
        for child in element:
            child_data = self._element_to_dict(child)

            if child.tag in result:
                # Si ya existe, convertir a lista
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data

        return result

    def to_array(self) -> Dict[str, Any]:
        """
        Convierte el documento XML completo a un diccionario/array.

        Equivale al método toArray() de XmlDocumentInterface en PHP.

        Returns:
            Diccionario con la representación completa del XML
        """
        return {self.root.tag: self._element_to_dict(self.root)}

    def save_xml(self) -> str:
        """
        Genera la representación XML del documento.

        Equivale al método saveXml() de XmlDocumentInterface en PHP.

        Returns:
            String con el XML formateado
        """
        # Si el documento viene de un XML se entrega tal cual, para no alterar
        # firmas ni timbres.
        if self._raw is not None and self._raw.lstrip().startswith(b'<?xml'):
            match = re.search(rb'encoding\s*=\s*["\']([A-Za-z0-9._-]+)', self._raw[:200])
            encoding = match.group(1).decode('ascii') if match else 'UTF-8'
            return self._raw.decode(encoding).strip()

        # Crear declaración XML con encoding ISO-8859-1 para compatibilidad SII
        xml_str = ET.tostring(self.root, encoding='unicode', method='xml')

        # Formatear con minidom para mejor legibilidad
        dom = minidom.parseString(xml_str)
        formatted = dom.toprettyxml(indent="  ", encoding=None)

        # Remover líneas vacías extra y ajustar declaración XML
        lines = [line for line in formatted.split('\n') if line.strip()]
        if lines and lines[0].startswith('<?xml'):
            lines[0] = '<?xml version="1.0" encoding="ISO-8859-1"?>'

        return '\n'.join(lines)

    def get_xml(self) -> str:
        """
        Alias para save_xml() manteniendo compatibilidad.

        Returns:
            String con el XML formateado
        """
        return self.save_xml()

    def c14n_with_iso88591_encoding_flattened(self, xpath: str = None) -> Optional[str]:
        """
        Canonicalización C14N con encoding ISO-8859-1 aplanado.

        Equivale al método C14NWithIso88591EncodingFlattened() de PHP.
        Usado para generar el TED (Timbre Electrónico).

        Args:
            xpath: XPath del elemento a canonicalizar

        Returns:
            String canonicalizado o None si no se encuentra
        """
        if self._raw is not None:
            try:
                return c14n_encoded_flattened(self._raw, _local_name_xpath(xpath) if xpath else None).decode('iso-8859-1')
            except ValueError:
                return None

        try:
            if xpath:
                elements = self.root.findall('.' + xpath if xpath.startswith('//') else xpath)
                if not elements:
                    return None
                element = elements[0]
            else:
                element = self.root

            xml_str = ET.tostring(element, encoding='unicode', method='xml')
            return c14n_encoded_flattened(xml_str.encode('utf-8'), None, 'ISO-8859-1').decode('iso-8859-1')

        except Exception:
            return None


class DocumentBuilder:
    """
    Constructor de documentos XML para DTE.

    Proporciona métodos para construir documentos XML
    siguiendo los estándares del SII de Chile.
    """

    @staticmethod
    def create_dte_document(datos: Dict[str, Any]) -> XmlDocument:
        """
        Crea un documento DTE desde datos estructurados.

        Args:
            datos: Diccionario con los datos del DTE

        Returns:
            XmlDocument con el DTE generado
        """
        # Crear elemento root DTE
        dte_root = ET.Element("DTE")
        dte_root.set("version", "1.0")

        # Crear elemento Documento
        documento = ET.SubElement(dte_root, "Documento")

        # Agregar ID al documento si se proporciona
        if 'ID' in datos:
            documento.set("ID", datos['ID'])

        # Construir Encabezado
        if 'Encabezado' in datos:
            DocumentBuilder._build_encabezado(documento, datos['Encabezado'])

        # Construir Detalle(s)
        if 'Detalle' in datos:
            DocumentBuilder._build_detalle(documento, datos['Detalle'])

        # Construir otros elementos según tipo de documento
        for key in ['DscRcgGlobal', 'Referencia', 'Comisiones']:
            if key in datos:
                DocumentBuilder._build_generic_element(documento, key, datos[key])

        return XmlDocument(dte_root)

    @staticmethod
    def _build_encabezado(parent: ET.Element, encabezado: Dict[str, Any]) -> None:
        """Construye el elemento Encabezado."""
        enc_elem = ET.SubElement(parent, "Encabezado")

        # IdDoc
        if 'IdDoc' in encabezado:
            DocumentBuilder._build_generic_element(enc_elem, 'IdDoc', encabezado['IdDoc'])

        # Emisor
        if 'Emisor' in encabezado:
            DocumentBuilder._build_generic_element(enc_elem, 'Emisor', encabezado['Emisor'])

        # Receptor
        if 'Receptor' in encabezado:
            DocumentBuilder._build_generic_element(enc_elem, 'Receptor', encabezado['Receptor'])

        # Totales
        if 'Totales' in encabezado:
            DocumentBuilder._build_generic_element(enc_elem, 'Totales', encabezado['Totales'])

    @staticmethod
    def _build_detalle(parent: ET.Element, detalle: Union[Dict, List[Dict]]) -> None:
        """Construye elemento(s) Detalle."""
        if isinstance(detalle, dict):
            detalle = [detalle]

        for item in detalle:
            DocumentBuilder._build_generic_element(parent, 'Detalle', item)

    @staticmethod
    def _build_generic_element(parent: ET.Element, tag: str, data: Any) -> ET.Element:
        """Construye un elemento XML genérico desde datos."""
        if isinstance(data, list):
            # Si es lista en el nivel raíz, crear múltiples elementos
            # No crear elemento vacío inicial
            last_elem = None
            for item in data:
                last_elem = DocumentBuilder._build_generic_element(parent, tag, item)
            return last_elem or ET.SubElement(parent, tag)  # Fallback para lista vacía

        # Crear elemento para datos no-lista
        elem = ET.SubElement(parent, tag)

        if isinstance(data, dict):
            # Manejar atributos
            if '@attributes' in data:
                for attr_name, attr_value in data['@attributes'].items():
                    elem.set(attr_name, str(attr_value))

            # Manejar valor directo
            if '@value' in data:
                elem.text = str(data['@value'])

            # Manejar elementos hijos
            for key, value in data.items():
                if key not in ['@attributes', '@value']:
                    if isinstance(value, list):
                        for item in value:
                            DocumentBuilder._build_generic_element(elem, key, item)
                    else:
                        DocumentBuilder._build_generic_element(elem, key, value)

        else:
            # Valor simple
            elem.text = str(data)

        return elem


class Document(BaseModel):
    r"""
    Clase que representa un documento que se enviará en un sobre.

    Traducción de Exchange\Support\Document de PHP.
    Contiene el documento y los metadatos de dicho documento.
    """

    content: str = Field(default="", description="Contenido del documento (típicamente XML)")
    attachments: List[Any] = Field(default_factory=list, description="Archivos adjuntos")
    document_type: str = Field(default="B2B", description="Tipo de documento")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos del documento")

    def get_id(self) -> str:
        """
        Obtiene el ID del documento.

        Si no existe, genera uno nuevo automáticamente.

        Returns:
            ID único del documento
        """
        if 'id' not in self.metadata:
            self.metadata['id'] = str(uuid.uuid4())

        return self.metadata['id']

    def get_content(self) -> str:
        """
        Obtiene el contenido del documento.

        Returns:
            Contenido del documento
        """
        return self.content

    def get_content_size(self) -> int:
        """
        Obtiene el tamaño del contenido en bytes.

        Returns:
            Tamaño del contenido
        """
        return len(self.content.encode('utf-8'))

    def add_attachment(self, attachment: Any) -> 'Document':
        """
        Agrega un archivo adjunto al documento.

        Args:
            attachment: Archivo adjunto a agregar

        Returns:
            Instancia del documento para encadenamiento
        """
        self.attachments.append(attachment)
        return self

    def get_attachments(self) -> List[Any]:
        """
        Obtiene los archivos adjuntos.

        Returns:
            Lista de archivos adjuntos
        """
        return self.attachments

    def set_metadata(self, metadata: Dict[str, Any]) -> 'Document':
        """
        Establece los metadatos del documento.

        Args:
            metadata: Diccionario con metadatos

        Returns:
            Instancia del documento para encadenamiento
        """
        self.metadata = metadata
        return self

    def add_metadata(self, key: str, value: Any) -> 'Document':
        """
        Agrega un metadato al documento.

        Args:
            key: Clave del metadato
            value: Valor del metadato

        Returns:
            Instancia del documento para encadenamiento
        """
        self.metadata[key] = value
        return self

    def get_metadata(self) -> Dict[str, Any]:
        """
        Obtiene los metadatos del documento.

        Returns:
            Diccionario con metadatos
        """
        return self.metadata

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el documento a diccionario.

        Returns:
            Diccionario con la representación del documento
        """
        return {
            'id': self.get_id(),
            'content': self.content,
            'content_size': self.get_content_size(),
            'attachments': self.attachments,
            'document_type': self.document_type,
            'metadata': self.metadata,
        }

    def to_json_serializable(self) -> Dict[str, Any]:
        """
        Convierte el documento a formato serializable en JSON.

        Codifica el contenido en base64 para serialización segura.

        Returns:
            Diccionario serializable en JSON
        """
        data = self.to_dict()
        data['content'] = base64.b64encode(data['content'].encode('utf-8')).decode('ascii')
        return data