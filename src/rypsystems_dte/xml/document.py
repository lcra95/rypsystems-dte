"""
Módulo de manipulación de documentos XML para DTE.

Traducción de la funcionalidad XML de LibreDTE manteniendo
compatibilidad exacta con la versión PHP original.
"""

import base64
from typing import Any, Dict, List, Optional, Union
from xml.etree import ElementTree as ET
from xml.dom import minidom
import uuid

from pydantic import BaseModel, Field


class XmlDocument:
    r"""
    Manejador de documentos XML que mantiene compatibilidad con XmlDocumentInterface de PHP.

    Equivale a Derafu\Xml\Contract\XmlDocumentInterface.
    Proporciona funcionalidad para consultar, manipular y generar XML
    conforme a los estándares del SII de Chile.
    """

    def __init__(self, xml_content: Union[str, ET.Element] = None):
        """
        Constructor del documento XML.

        Args:
            xml_content: Contenido XML como string o Element
        """
        if xml_content is None:
            # Crear documento vacío
            self.root = ET.Element("root")
        elif isinstance(xml_content, str):
            # Parsear string XML
            try:
                self.root = ET.fromstring(xml_content)
            except ET.ParseError as e:
                raise ValueError(f"XML inválido: {e}")
        elif isinstance(xml_content, ET.Element):
            self.root = xml_content
        else:
            raise TypeError("xml_content debe ser string o ET.Element")

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
        try:
            if xpath:
                elements = self.root.findall('.' + xpath if xpath.startswith('//') else xpath)
                if not elements:
                    return None
                element = elements[0]
            else:
                element = self.root

            # Generar XML canonicalizado
            xml_str = ET.tostring(element, encoding='unicode', method='xml')

            # Remover espacios entre tags pero preservar espacios en atributos y contenido
            import re
            # Solo remover espacios entre > y <
            flattened = re.sub(r'>\s+<', '><', xml_str.strip())

            return flattened

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

        elif isinstance(data, list):
            # Si es lista en el nivel raíz, crear múltiples elementos
            for item in data:
                DocumentBuilder._build_generic_element(parent, tag, item)
            return elem

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