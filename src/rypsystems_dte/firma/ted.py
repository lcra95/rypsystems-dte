"""
TED - Timbre Electrónico DTE

Implementación de la generación y validación del Timbre Electrónico
según la normativa del SII de Chile.

Basado en la implementación PHP original de AbstractDocument::getPlantillaTED()
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import hashlib
import base64

from pydantic import BaseModel, Field, validator

from ..sii.base import Contribuyente
from ..sii.utils import RutValidator
from ..xml.document import XmlDocument
from ..pdf417.generator import TEDGenerator as PDF417TEDGenerator


class TEDData(BaseModel):
    """
    Datos requeridos para generar el TED (Timbre Electrónico).

    Basado en la estructura PHP de getPlantillaTED()
    """
    rut_emisor: str = Field(..., description="RUT del emisor")
    tipo_documento: int = Field(..., description="Código del tipo de documento")
    folio: int = Field(..., description="Folio del documento")
    fecha_emision: str = Field(..., description="Fecha de emisión (YYYY-MM-DD)")
    rut_receptor: str = Field(..., description="RUT del receptor")
    razon_social_receptor: str = Field(..., description="Razón social del receptor")
    monto_total: Union[int, float] = Field(..., description="Monto total del documento")
    primer_item: str = Field("", description="Primer item del detalle")
    caf_data: str = Field("", description="Datos del CAF (Code Authorization File)")
    timestamp_ted: str = Field("", description="Timestamp del TED")

    @validator('rut_emisor', 'rut_receptor')
    def validate_rut(cls, v):
        """Valida formato de RUT"""
        if not RutValidator.validate(v):
            raise ValueError(f"RUT inválido: {v}")
        return RutValidator.format(v)

    @validator('razon_social_receptor', 'primer_item')
    def truncate_text_fields(cls, v):
        """Trunca campos de texto a 40 caracteres como en PHP"""
        if isinstance(v, str):
            return v[:40]
        return v

    @validator('fecha_emision')
    def validate_fecha(cls, v):
        """Valida formato de fecha"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError(f"Formato de fecha inválido: {v}. Use YYYY-MM-DD")


class TEDBuilder:
    """
    Constructor de TED (Timbre Electrónico DTE).

    Reproduce la funcionalidad de AbstractDocument::getPlantillaTED()
    en Python con mejoras de tipo safety y validación.
    """

    def __init__(self):
        """Inicializa el constructor TED."""
        self.pdf417_generator = PDF417TEDGenerator()

    def build_ted_template(self, ted_data: TEDData) -> Dict[str, Any]:
        """
        Construye la plantilla del TED basada en los datos proporcionados.

        Reproduce exactamente la estructura PHP:
        ```php
        return [
            'TED' => [
                '@attributes' => ['version' => '1.0'],
                'DD' => [...],
                'FRMT' => [...]
            ]
        ];
        ```

        Args:
            ted_data: Datos validados para el TED

        Returns:
            Diccionario con la estructura del TED
        """
        return {
            'TED': {
                '@attributes': {
                    'version': '1.0'
                },
                'DD': {
                    'RE': ted_data.rut_emisor,
                    'TD': ted_data.tipo_documento,
                    'F': ted_data.folio,
                    'FE': ted_data.fecha_emision,
                    'RR': ted_data.rut_receptor,
                    'RSR': ted_data.razon_social_receptor,
                    'MNT': ted_data.monto_total,
                    'IT1': ted_data.primer_item,
                    'CAF': ted_data.caf_data,  # Se agregará al timbrar
                    'TSTED': ted_data.timestamp_ted  # Se agregará al timbrar
                },
                'FRMT': {
                    '@attributes': {
                        'algoritmo': 'SHA1withRSA'
                    },
                    '@value': ''  # Se agregará al timbrar
                }
            }
        }

    def build_ted_from_document_data(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Construye TED desde datos estructurados de un documento DTE.

        Args:
            document_data: Datos del documento en formato dict

        Returns:
            Plantilla TED generada
        """
        # Extraer datos del documento
        encabezado = document_data.get('Encabezado', {})
        id_doc = encabezado.get('IdDoc', {})
        emisor = encabezado.get('Emisor', {})
        receptor = encabezado.get('Receptor', {})
        totales = encabezado.get('Totales', {})
        detalle = document_data.get('Detalle', [])

        # Obtener primer item del detalle
        primer_item = ""
        if detalle:
            if isinstance(detalle, list) and len(detalle) > 0:
                primer_item = detalle[0].get('NmbItem', '')
            elif isinstance(detalle, dict):
                primer_item = detalle.get('NmbItem', '')

        # Crear datos TED
        ted_data = TEDData(
            rut_emisor=emisor.get('RUTEmisor', ''),
            tipo_documento=int(id_doc.get('TipoDTE', 0)),
            folio=int(id_doc.get('Folio', 0)),
            fecha_emision=id_doc.get('FchEmis', ''),
            rut_receptor=receptor.get('RUTRecep', ''),
            razon_social_receptor=receptor.get('RznSocRecep', ''),
            monto_total=totales.get('MntTotal', 0),
            primer_item=primer_item
        )

        return self.build_ted_template(ted_data)

    def generate_ted_xml(self, ted_template: Dict[str, Any]) -> str:
        """
        Genera el XML del TED desde la plantilla.

        Args:
            ted_template: Plantilla TED generada

        Returns:
            XML del TED como string
        """
        # Crear XML del TED directamente
        return self._build_ted_xml_from_template(ted_template)

    def _build_ted_xml_from_template(self, ted_template: Dict[str, Any]) -> str:
        """
        Construye XML del TED desde plantilla usando ElementTree.

        Args:
            ted_template: Plantilla TED

        Returns:
            XML del TED formateado
        """
        ted_data = ted_template['TED']

        # Crear elemento raíz TED
        root = ET.Element('TED')
        if '@attributes' in ted_data:
            for attr, value in ted_data['@attributes'].items():
                root.set(attr, str(value))

        # Crear elemento DD
        dd_element = ET.SubElement(root, 'DD')
        dd_data = ted_data.get('DD', {})
        for key, value in dd_data.items():
            if key != '@attributes':
                child = ET.SubElement(dd_element, key)
                child.text = str(value)

        # Crear elemento FRMT
        frmt_element = ET.SubElement(root, 'FRMT')
        frmt_data = ted_data.get('FRMT', {})
        if '@attributes' in frmt_data:
            for attr, value in frmt_data['@attributes'].items():
                frmt_element.set(attr, str(value))
        if '@value' in frmt_data:
            frmt_element.text = str(frmt_data['@value'])

        # Formatear XML con minidom para better formatting
        rough_string = ET.tostring(root, encoding='unicode')
        reparsed = minidom.parseString(rough_string)

        # Crear declaración XML con encoding ISO-8859-1
        xml_declaration = '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
        formatted_xml = reparsed.documentElement.toprettyxml(indent="  ")

        return xml_declaration + formatted_xml

    def generate_ted_canonicalized(self, ted_template: Dict[str, Any]) -> str:
        """
        Genera el TED canonicalizado para usar en PDF417.

        Reproduce la funcionalidad de:
        getXmlDocument()->C14NWithIso88591EncodingFlattened('//TED')

        Args:
            ted_template: Plantilla TED

        Returns:
            TED canonicalizado y aplanado
        """
        # Generar XML del TED
        ted_xml = self.generate_ted_xml(ted_template)

        # Crear documento XML y canonicalizar
        xml_doc = XmlDocument(ted_xml)

        # Primero intentar con xpath específico
        canonicalized = xml_doc.c14n_with_iso88591_encoding_flattened('//TED')

        # Si no funciona el xpath, usar el documento completo
        if not canonicalized:
            canonicalized = xml_doc.c14n_with_iso88591_encoding_flattened()

        return canonicalized or ""

    def generate_ted_barcode(self, ted_template: Dict[str, Any]) -> str:
        """
        Genera el código de barras PDF417 del TED.

        Args:
            ted_template: Plantilla TED

        Returns:
            Data URI del código de barras
        """
        ted_canonicalized = self.generate_ted_canonicalized(ted_template)
        return self.pdf417_generator.generate_ted_barcode(ted_canonicalized)


class TEDValidator:
    """
    Validador de TED (Timbre Electrónico DTE).

    Provee funcionalidades para validar la estructura y datos del TED.
    """

    @staticmethod
    def validate_ted_structure(ted_data: Dict[str, Any]) -> bool:
        """
        Valida la estructura básica del TED.

        Args:
            ted_data: Datos del TED a validar

        Returns:
            True si la estructura es válida
        """
        if not isinstance(ted_data, dict):
            return False

        ted = ted_data.get('TED', {})
        if not ted:
            return False

        # Verificar elementos requeridos
        dd = ted.get('DD', {})
        frmt = ted.get('FRMT', {})

        required_dd_fields = ['RE', 'TD', 'F', 'FE', 'RR', 'RSR', 'MNT']
        for field in required_dd_fields:
            if field not in dd:
                return False

        # Verificar estructura FRMT
        if '@attributes' not in frmt or 'algoritmo' not in frmt['@attributes']:
            return False

        return True

    @staticmethod
    def validate_ted_xml(ted_xml: str) -> bool:
        """
        Valida XML de TED.

        Args:
            ted_xml: XML del TED como string

        Returns:
            True si el XML es válido
        """
        try:
            # Verificar que se puede parsear
            root = ET.fromstring(ted_xml)

            # Verificar elemento raíz
            if root.tag != 'TED':
                return False

            # Verificar elementos requeridos
            dd = root.find('DD')
            frmt = root.find('FRMT')

            if dd is None or frmt is None:
                return False

            # Verificar campos DD requeridos
            required_fields = ['RE', 'TD', 'F', 'FE', 'RR', 'RSR', 'MNT']
            for field in required_fields:
                if dd.find(field) is None:
                    return False

            return True

        except ET.ParseError:
            return False

    @staticmethod
    def extract_ted_data_from_xml(ted_xml: str) -> Optional[TEDData]:
        """
        Extrae datos TEDData desde XML.

        Args:
            ted_xml: XML del TED

        Returns:
            TEDData extraído o None si no es válido
        """
        try:
            root = ET.fromstring(ted_xml)
            dd = root.find('DD')

            if dd is None:
                return None

            # Extraer datos
            data = {
                'rut_emisor': dd.findtext('RE', ''),
                'tipo_documento': int(dd.findtext('TD', '0')),
                'folio': int(dd.findtext('F', '0')),
                'fecha_emision': dd.findtext('FE', ''),
                'rut_receptor': dd.findtext('RR', ''),
                'razon_social_receptor': dd.findtext('RSR', ''),
                'monto_total': float(dd.findtext('MNT', '0')),
                'primer_item': dd.findtext('IT1', ''),
                'caf_data': dd.findtext('CAF', ''),
                'timestamp_ted': dd.findtext('TSTED', '')
            }

            return TEDData(**data)

        except (ET.ParseError, ValueError, TypeError):
            return None

    @staticmethod
    def verify_ted_signature(ted_xml: str, certificate_data: Optional[str] = None) -> bool:
        """
        Verifica la firma digital del TED.

        Args:
            ted_xml: XML del TED con firma
            certificate_data: Datos del certificado (opcional)

        Returns:
            True si la firma es válida

        Note:
            Implementación básica. En producción se requiere validación
            criptográfica real contra certificados del SII.
        """
        try:
            root = ET.fromstring(ted_xml)
            frmt = root.find('FRMT')

            if frmt is None:
                return False

            # Verificar que existe valor de firma
            firma_value = frmt.text or ''
            if not firma_value.strip():
                return False

            # TODO: Implementar validación criptográfica real
            # Por ahora solo verificamos que existe el valor
            return len(firma_value.strip()) > 10

        except ET.ParseError:
            return False


# Funciones de conveniencia
def create_ted_from_document(document_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función de conveniencia para crear TED desde datos de documento.

    Args:
        document_data: Datos del documento DTE

    Returns:
        Plantilla TED generada
    """
    builder = TEDBuilder()
    return builder.build_ted_from_document_data(document_data)


def generate_ted_barcode_from_data(ted_data: TEDData) -> str:
    """
    Función de conveniencia para generar código de barras desde TEDData.

    Args:
        ted_data: Datos del TED

    Returns:
        Data URI del código de barras
    """
    builder = TEDBuilder()
    template = builder.build_ted_template(ted_data)
    return builder.generate_ted_barcode(template)