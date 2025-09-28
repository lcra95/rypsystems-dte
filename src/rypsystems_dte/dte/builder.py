"""
DTE Builder - Constructor de documentos tributarios electrónicos

Implementación Python de BuilderStrategy de LibreDTE.
Maneja la construcción, normalización, validación y firma de documentos DTE.
"""

from typing import Dict, Any, Optional, Type, List
from abc import ABC, abstractmethod
from datetime import datetime

from ..xml.document import XmlDocument, DocumentBuilder as XmlDocumentBuilder
from ..firma.ted import TEDBuilder
from .document import BaseDocument, DOCUMENT_CLASSES
from .bag import DocumentBag
from ..sii.constants import CodigoDocumento


class DocumentProcessor:
    """
    Procesador de documentos que maneja normalización, sanitización y validación.

    Reproduce la funcionalidad de NormalizerWorker, SanitizerWorker y ValidatorWorker.
    """

    def normalize(self, bag: DocumentBag) -> None:
        """
        Normaliza los datos del documento.

        Args:
            bag: Contenedor del documento a normalizar
        """
        if bag.is_normalized():
            return

        datos = bag.get_datos()

        # Normalización básica de estructura
        self._normalize_structure(datos)
        self._normalize_dates(datos)
        self._normalize_amounts(datos)
        self._normalize_ruts(datos)

        bag.set_datos(datos)
        bag.set_normalized(True)

    def _normalize_structure(self, datos: Dict[str, Any]) -> None:
        """Normaliza la estructura básica del documento."""
        # Asegurar estructura mínima
        if 'Encabezado' not in datos:
            datos['Encabezado'] = {}

        encabezado = datos['Encabezado']

        # Asegurar secciones básicas sin sobrescribir datos existentes
        for seccion in ['IdDoc', 'Emisor', 'Receptor', 'Totales']:
            if seccion not in encabezado:
                encabezado[seccion] = {}

        # Normalizar detalle a lista
        if 'Detalle' in datos:
            detalle = datos['Detalle']
            if not isinstance(detalle, list):
                datos['Detalle'] = [detalle] if detalle else []

    def _normalize_dates(self, datos: Dict[str, Any]) -> None:
        """Normaliza formatos de fecha."""
        id_doc = datos.get('Encabezado', {}).get('IdDoc', {})

        # Normalizar fecha de emisión
        if 'FchEmis' in id_doc:
            fecha = id_doc['FchEmis']
            if isinstance(fecha, datetime):
                id_doc['FchEmis'] = fecha.strftime('%Y-%m-%d')
            elif isinstance(fecha, str) and len(fecha) > 10:
                # Truncar si incluye hora
                id_doc['FchEmis'] = fecha[:10]

    def _normalize_amounts(self, datos: Dict[str, Any]) -> None:
        """Normaliza montos y cantidades."""
        # Normalizar totales
        totales = datos.get('Encabezado', {}).get('Totales', {})
        for key, value in totales.items():
            if key.startswith('Mnt') or key == 'IVA':
                if isinstance(value, str):
                    try:
                        totales[key] = int(float(value))
                    except ValueError:
                        pass

        # Normalizar detalle
        for item in datos.get('Detalle', []):
            for key, value in item.items():
                if key in ['QtyItem', 'PrcItem', 'MontoItem'] and isinstance(value, str):
                    try:
                        if key == 'QtyItem':
                            item[key] = float(value)
                        else:
                            item[key] = int(float(value))
                    except ValueError:
                        pass

    def _normalize_ruts(self, datos: Dict[str, Any]) -> None:
        """Normaliza formato de RUTs."""
        from ..sii.utils import RutValidator

        encabezado = datos.get('Encabezado', {})

        # Normalizar RUT emisor
        emisor = encabezado.get('Emisor', {})
        if 'RUTEmisor' in emisor:
            rut = emisor['RUTEmisor']
            if isinstance(rut, str) and RutValidator.validate(rut):
                emisor['RUTEmisor'] = RutValidator.format(rut)

        # Normalizar RUT receptor
        receptor = encabezado.get('Receptor', {})
        if 'RUTRecep' in receptor:
            rut = receptor['RUTRecep']
            if isinstance(rut, str) and RutValidator.validate(rut):
                receptor['RUTRecep'] = RutValidator.format(rut)

    def sanitize(self, bag: DocumentBag) -> None:
        """
        Sanitiza los datos del documento.

        Args:
            bag: Contenedor del documento a sanitizar
        """
        if bag.is_sanitized():
            return

        datos = bag.get_datos()

        # Sanitización básica
        self._sanitize_strings(datos)
        self._sanitize_numbers(datos)

        bag.set_datos(datos)
        bag.set_sanitized(True)

    def _sanitize_strings(self, datos: Dict[str, Any]) -> None:
        """Sanitiza strings del documento."""
        def clean_string(value: Any) -> Any:
            if isinstance(value, str):
                # Remover caracteres de control
                value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\r\t')
                # Truncar si es muy largo
                return value[:1000].strip()
            elif isinstance(value, dict):
                return {k: clean_string(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [clean_string(item) for item in value]
            return value

        for key, value in datos.items():
            datos[key] = clean_string(value)

    def _sanitize_numbers(self, datos: Dict[str, Any]) -> None:
        """Sanitiza números del documento."""
        # Asegurar que los montos sean enteros
        totales = datos.get('Encabezado', {}).get('Totales', {})
        for key in ['MntExe', 'MntNeto', 'MntTotal', 'IVA']:
            if key in totales and isinstance(totales[key], float):
                totales[key] = round(totales[key])

    def validate(self, bag: DocumentBag) -> List[str]:
        """
        Valida los datos del documento.

        Args:
            bag: Contenedor del documento a validar

        Returns:
            Lista de errores encontrados
        """
        if bag.is_validated():
            return []

        errors = []

        # Validar datos requeridos
        errors.extend(bag.validate_required_data())

        # Validaciones específicas por tipo
        errors.extend(self._validate_by_type(bag))

        if not errors:
            bag.set_validated(True)

        return errors

    def _validate_by_type(self, bag: DocumentBag) -> List[str]:
        """
        Validaciones específicas según tipo de documento.

        Args:
            bag: Contenedor del documento

        Returns:
            Lista de errores específicos del tipo
        """
        errors = []
        tipo = bag.get_tipo_documento()
        datos = bag.get_datos()

        # Validaciones comunes
        if tipo in [CodigoDocumento.FACTURA_AFECTA, CodigoDocumento.BOLETA_AFECTA]:
            # Debe tener IVA
            totales = datos.get('Encabezado', {}).get('Totales', {})
            if not totales.get('IVA'):
                errors.append("Documentos afectos deben incluir IVA")

        # Validar detalle
        detalle = datos.get('Detalle', [])
        if not detalle:
            errors.append("Documento debe tener al menos un item en el detalle")

        return errors


class DTEBuilder:
    """
    Constructor principal de documentos DTE.

    Reproduce la funcionalidad de BuilderStrategy de LibreDTE.
    """

    def __init__(self):
        """Inicializa el constructor DTE."""
        self.processor = DocumentProcessor()
        self.ted_builder = TEDBuilder()
        self.xml_builder = XmlDocumentBuilder()

    def build(self, bag: DocumentBag) -> BaseDocument:
        """
        Construye un documento DTE completo desde un DocumentBag.

        Args:
            bag: Contenedor con datos y opciones del documento

        Returns:
            Documento DTE construido

        Raises:
            ValueError: Si hay errores en los datos
        """
        # 1. Normalizar datos si está habilitado
        normalize = bag.get_normalizer_options().get('normalize', True)
        if normalize:
            self.processor.normalize(bag)
            self.processor.sanitize(bag)

            errors = self.processor.validate(bag)
            if errors:
                raise ValueError(f"Errores de validación: {errors}")

        # 2. Timbrar si hay CAF
        if bag.get_caf():
            self._stamp(bag)

        # 3. Firmar si hay certificado
        if bag.get_certificate():
            self._sign(bag)

        # 4. Crear documento XML
        xml_doc = self._create_xml_document(bag)

        # 5. Crear instancia del documento específico
        return self._create_document_instance(xml_doc, bag.get_tipo_documento())

    def create_from_xml(self, xml_content: str) -> BaseDocument:
        """
        Crea un documento DTE desde contenido XML.

        Args:
            xml_content: Contenido XML del documento

        Returns:
            Documento DTE creado

        Raises:
            ValueError: Si el XML es inválido o no se puede determinar el tipo
        """
        xml_doc = XmlDocument(xml_content)

        # Determinar tipo de documento desde XML
        tipo_dte = xml_doc.query('//Encabezado/IdDoc/TipoDTE')
        if not tipo_dte:
            raise ValueError("No se pudo determinar el tipo de documento desde el XML")

        try:
            codigo = CodigoDocumento(int(tipo_dte))
        except ValueError:
            raise ValueError(f"Tipo de documento no soportado: {tipo_dte}")

        return self._create_document_instance(xml_doc, codigo)

    def _create_xml_document(self, bag: DocumentBag) -> XmlDocument:
        """
        Crea el documento XML desde los datos del bag.

        Args:
            bag: Contenedor con los datos

        Returns:
            Documento XML generado
        """
        # Obtener datos del bag
        datos = bag.get_datos()

        # Asegurar que TipoDTE esté establecido correctamente
        if 'Encabezado' not in datos:
            datos['Encabezado'] = {}
        if 'IdDoc' not in datos['Encabezado']:
            datos['Encabezado']['IdDoc'] = {}

        # Establecer el tipo de documento
        datos['Encabezado']['IdDoc']['TipoDTE'] = bag.get_codigo()

        # El DocumentBuilder.create_dte_document() ya crea la estructura DTE
        # Solo necesitamos pasar los datos del documento directamente
        return self.xml_builder.create_dte_document(datos)

    def _create_document_instance(self, xml_doc: XmlDocument, tipo: CodigoDocumento) -> BaseDocument:
        """
        Crea la instancia específica del documento.

        Args:
            xml_doc: Documento XML
            tipo: Tipo de documento

        Returns:
            Instancia del documento específico

        Raises:
            ValueError: Si el tipo no está soportado
        """
        document_class = DOCUMENT_CLASSES.get(tipo)
        if not document_class:
            raise ValueError(f"Tipo de documento no soportado: {tipo}")

        return document_class(xml_doc)

    def _stamp(self, bag: DocumentBag) -> None:
        """
        Timbra el documento con CAF.

        Args:
            bag: Contenedor del documento
        """
        if bag.is_stamped():
            return

        # TODO: Implementar timbraje real con CAF
        # Por ahora solo marcamos como timbrado
        datos = bag.get_datos()

        # Generar plantilla TED
        ted_template = self._generate_ted_template(bag)

        # Agregar TED a los datos
        datos['TED'] = ted_template['TED']

        bag.set_datos(datos)
        bag.set_stamped(True)

    def _sign(self, bag: DocumentBag) -> None:
        """
        Firma el documento con certificado digital.

        Args:
            bag: Contenedor del documento
        """
        if bag.is_signed():
            return

        # TODO: Implementar firma digital real
        # Por ahora solo marcamos como firmado
        datos = bag.get_datos()

        # Agregar timestamp de firma
        datos['TmstFirma'] = datetime.now().isoformat()

        bag.set_datos(datos)
        bag.set_signed(True)

    def _generate_ted_template(self, bag: DocumentBag) -> Dict[str, Any]:
        """
        Genera la plantilla TED para el documento.

        Args:
            bag: Contenedor del documento

        Returns:
            Plantilla TED generada
        """
        return self.ted_builder.build_ted_from_document_data(bag.get_datos())


# Builder específicos por tipo de documento
class FacturaAfectaBuilder(DTEBuilder):
    """Builder específico para facturas afectas."""

    def __init__(self):
        super().__init__()
        self.tipo_documento = CodigoDocumento.FACTURA_AFECTA


class BoletaAfectaBuilder(DTEBuilder):
    """Builder específico para boletas afectas."""

    def __init__(self):
        super().__init__()
        self.tipo_documento = CodigoDocumento.BOLETA_AFECTA


class NotaCreditoBuilder(DTEBuilder):
    """Builder específico para notas de crédito."""

    def __init__(self):
        super().__init__()
        self.tipo_documento = CodigoDocumento.NOTA_CREDITO


# Mapping de códigos a builders específicos
BUILDER_CLASSES = {
    CodigoDocumento.FACTURA_AFECTA: FacturaAfectaBuilder,
    CodigoDocumento.BOLETA_AFECTA: BoletaAfectaBuilder,
    CodigoDocumento.NOTA_CREDITO: NotaCreditoBuilder,
}