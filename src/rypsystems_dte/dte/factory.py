"""
DTE Factory - Fábrica para crear documentos tributarios electrónicos

Punto de entrada principal para la creación de documentos DTE.
Simplifica la creación y manejo de diferentes tipos de documentos.
"""

from typing import Dict, Any, Optional, Union, Type, List
from datetime import datetime

from .document import BaseDocument, DOCUMENT_CLASSES
from .builder import DTEBuilder, BUILDER_CLASSES
from .bag import DocumentBag, DocumentOptions
from ..sii.constants import CodigoDocumento
from ..sii.base import Contribuyente
from ..xml.document import XmlDocument


class DTEFactory:
    """
    Fábrica principal para crear documentos DTE.

    Proporciona una interfaz simple y unificada para crear diferentes
    tipos de documentos tributarios electrónicos.
    """

    def __init__(self):
        """Inicializa la fábrica DTE."""
        self._default_builder = DTEBuilder()

    def create_document(
        self,
        tipo_documento: Union[CodigoDocumento, int],
        datos: Dict[str, Any],
        options: Optional[DocumentOptions] = None,
        caf_data: Optional[str] = None,
        certificate_data: Optional[str] = None
    ) -> BaseDocument:
        """
        Crea un documento DTE completo.

        Args:
            tipo_documento: Tipo de documento a crear
            datos: Datos del documento
            options: Opciones de procesamiento (opcional)
            caf_data: Datos del CAF para timbraje (opcional)
            certificate_data: Certificado para firma (opcional)

        Returns:
            Documento DTE creado

        Raises:
            ValueError: Si hay errores en los datos o configuración

        Example:
            >>> factory = DTEFactory()
            >>> datos = {
            ...     'Encabezado': {
            ...         'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
            ...         'Emisor': {'RUTEmisor': '76354771-K'},
            ...         'Receptor': {'RUTRecep': '66666666-6', 'RznSocRecep': 'Cliente Test'},
            ...         'Totales': {'MntTotal': 1000}
            ...     },
            ...     'Detalle': [{'NmbItem': 'Producto', 'QtyItem': 1, 'PrcItem': 1000}]
            ... }
            >>> documento = factory.create_document(33, datos)
        """
        # Crear DocumentBag
        bag = DocumentBag(tipo_documento, datos, options)

        # Agregar CAF y certificado si están disponibles
        if caf_data:
            bag.set_caf(caf_data)
        if certificate_data:
            bag.set_certificate(certificate_data)

        # Obtener builder específico o usar el default
        builder = self._get_builder_for_type(bag.get_tipo_documento())

        # Construir documento
        return builder.build(bag)

    def create_from_xml(self, xml_content: str) -> BaseDocument:
        """
        Crea un documento DTE desde contenido XML.

        Args:
            xml_content: Contenido XML del documento

        Returns:
            Documento DTE creado

        Example:
            >>> factory = DTEFactory()
            >>> xml = '''<?xml version="1.0"?>
            ... <DTE><Documento>...</Documento></DTE>'''
            >>> documento = factory.create_from_xml(xml)
        """
        return self._default_builder.create_from_xml(xml_content)

    def create_factura_afecta(
        self,
        emisor: Contribuyente,
        receptor: Contribuyente,
        folio: int,
        fecha_emision: str,
        detalle: List[Dict[str, Any]],
        **kwargs
    ) -> BaseDocument:
        """
        Crea una factura electrónica afecta.

        Args:
            emisor: Contribuyente emisor
            receptor: Contribuyente receptor
            folio: Folio del documento
            fecha_emision: Fecha de emisión (YYYY-MM-DD)
            detalle: Lista de items del detalle
            **kwargs: Parámetros adicionales

        Returns:
            Factura afecta creada

        Example:
            >>> from rypsystems_dte.sii.base import Contribuyente
            >>> emisor = Contribuyente("76354771-K", "Mi Empresa")
            >>> receptor = Contribuyente("66666666-6", "Cliente S.A.")
            >>> detalle = [{'NmbItem': 'Servicio', 'QtyItem': 1, 'PrcItem': 10000}]
            >>> factura = factory.create_factura_afecta(emisor, receptor, 1, '2023-12-01', detalle)
        """
        datos = self._build_factura_data(
            emisor, receptor, folio, fecha_emision, detalle,
            tipo_dte=33, **kwargs
        )

        return self.create_document(CodigoDocumento.FACTURA_AFECTA, datos, **kwargs)

    def create_boleta_afecta(
        self,
        emisor: Contribuyente,
        folio: int,
        fecha_emision: str,
        detalle: List[Dict[str, Any]],
        receptor: Optional[Contribuyente] = None,
        **kwargs
    ) -> BaseDocument:
        """
        Crea una boleta electrónica afecta.

        Args:
            emisor: Contribuyente emisor
            folio: Folio del documento
            fecha_emision: Fecha de emisión (YYYY-MM-DD)
            detalle: Lista de items del detalle
            receptor: Contribuyente receptor (opcional para boletas)
            **kwargs: Parámetros adicionales

        Returns:
            Boleta afecta creada
        """
        datos = self._build_factura_data(
            emisor, receptor, folio, fecha_emision, detalle,
            tipo_dte=39, **kwargs
        )

        return self.create_document(CodigoDocumento.BOLETA_AFECTA, datos, **kwargs)

    def create_nota_credito(
        self,
        emisor: Contribuyente,
        receptor: Contribuyente,
        folio: int,
        fecha_emision: str,
        detalle: List[Dict[str, Any]],
        documento_referencia: Dict[str, Any],
        **kwargs
    ) -> BaseDocument:
        """
        Crea una nota de crédito electrónica.

        Args:
            emisor: Contribuyente emisor
            receptor: Contribuyente receptor
            folio: Folio del documento
            fecha_emision: Fecha de emisión (YYYY-MM-DD)
            detalle: Lista de items del detalle
            documento_referencia: Referencia al documento original
            **kwargs: Parámetros adicionales

        Returns:
            Nota de crédito creada
        """
        datos = self._build_factura_data(
            emisor, receptor, folio, fecha_emision, detalle,
            tipo_dte=61, **kwargs
        )

        # Agregar referencia
        datos['Referencia'] = [documento_referencia]

        return self.create_document(CodigoDocumento.NOTA_CREDITO, datos, **kwargs)

    def _build_factura_data(
        self,
        emisor: Contribuyente,
        receptor: Optional[Contribuyente],
        folio: int,
        fecha_emision: str,
        detalle: List[Dict[str, Any]],
        tipo_dte: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Construye la estructura de datos base para documentos tipo factura.

        Args:
            emisor: Contribuyente emisor
            receptor: Contribuyente receptor (puede ser None)
            folio: Folio del documento
            fecha_emision: Fecha de emisión
            detalle: Lista de items
            tipo_dte: Código del tipo de documento
            **kwargs: Parámetros adicionales

        Returns:
            Estructura de datos del documento
        """
        # Calcular totales desde el detalle
        totales = self._calculate_totales(detalle, tipo_dte)

        # Estructura base
        datos = {
            'Encabezado': {
                'IdDoc': {
                    'TipoDTE': tipo_dte,
                    'Folio': folio,
                    'FchEmis': fecha_emision
                },
                'Emisor': {
                    'RUTEmisor': emisor.get_rut(),
                    'RznSoc': emisor.razon_social
                },
                'Totales': totales
            },
            'Detalle': detalle
        }

        # Agregar receptor si existe
        if receptor:
            datos['Encabezado']['Receptor'] = {
                'RUTRecep': receptor.get_rut(),
                'RznSocRecep': receptor.razon_social
            }

        # Agregar parámetros adicionales
        self._apply_additional_params(datos, kwargs)

        return datos

    def _calculate_totales(self, detalle: List[Dict[str, Any]], tipo_dte: int) -> Dict[str, Any]:
        """
        Calcula los totales del documento desde el detalle.

        Args:
            detalle: Lista de items del detalle
            tipo_dte: Código del tipo de documento

        Returns:
            Diccionario con los totales calculados
        """
        monto_neto = 0
        monto_exento = 0

        for item in detalle:
            cantidad = float(item.get('QtyItem', 1))
            precio = float(item.get('PrcItem', 0))
            monto_item = int(cantidad * precio)

            # Determinar si el item es afecto o exento
            ind_exento = item.get('IndExe', 0)
            if ind_exento:
                monto_exento += monto_item
            else:
                monto_neto += monto_item

        totales = {}

        # Para documentos afectos, calcular IVA
        if tipo_dte in [33, 39, 61]:  # Factura/Boleta afecta, Nota crédito
            if monto_neto != 0:  # Puede ser negativo en notas de crédito
                iva = round(monto_neto * 0.19)
                totales['MntNeto'] = monto_neto
                totales['IVA'] = iva
                totales['MntTotal'] = monto_neto + iva
            if monto_exento > 0:
                totales['MntExe'] = monto_exento
                totales['MntTotal'] = totales.get('MntTotal', 0) + monto_exento
        else:
            # Para documentos exentos o notas
            totales['MntTotal'] = monto_neto + monto_exento
            if monto_exento > 0:
                totales['MntExe'] = monto_exento

        return totales

    def _apply_additional_params(self, datos: Dict[str, Any], params: Dict[str, Any]) -> None:
        """
        Aplica parámetros adicionales a los datos del documento.

        Args:
            datos: Datos del documento a modificar
            params: Parámetros adicionales
        """
        # Filtrar parámetros conocidos que no van en los datos
        known_params = {'options', 'caf_data', 'certificate_data'}
        additional = {k: v for k, v in params.items() if k not in known_params}

        # Aplicar a la estructura según el nombre del parámetro
        for key, value in additional.items():
            if key.startswith('Encabezado.'):
                # Parámetro para encabezado
                nested_key = key[11:]  # Remover 'Encabezado.'
                if '.' in nested_key:
                    section, field = nested_key.split('.', 1)
                    if section not in datos['Encabezado']:
                        datos['Encabezado'][section] = {}
                    datos['Encabezado'][section][field] = value
                else:
                    datos['Encabezado'][nested_key] = value
            else:
                # Parámetro de nivel raíz
                datos[key] = value

    def _get_builder_for_type(self, tipo: CodigoDocumento) -> DTEBuilder:
        """
        Obtiene el builder específico para un tipo de documento.

        Args:
            tipo: Tipo de documento

        Returns:
            Builder específico o builder por defecto
        """
        builder_class = BUILDER_CLASSES.get(tipo)
        if builder_class:
            return builder_class()
        return self._default_builder

    def get_supported_types(self) -> List[CodigoDocumento]:
        """
        Obtiene la lista de tipos de documento soportados.

        Returns:
            Lista de códigos de documento soportados
        """
        return list(DOCUMENT_CLASSES.keys())

    def validate_document_data(
        self,
        tipo_documento: Union[CodigoDocumento, int],
        datos: Dict[str, Any]
    ) -> List[str]:
        """
        Valida los datos de un documento sin crearlo.

        Args:
            tipo_documento: Tipo de documento
            datos: Datos a validar

        Returns:
            Lista de errores encontrados
        """
        bag = DocumentBag(tipo_documento, datos)
        builder = self._get_builder_for_type(bag.get_tipo_documento())
        return builder.processor.validate(bag)


# Instancia global de la fábrica para uso directo
factory = DTEFactory()

# Funciones de conveniencia
def create_factura_afecta(*args, **kwargs) -> BaseDocument:
    """Función de conveniencia para crear factura afecta."""
    return factory.create_factura_afecta(*args, **kwargs)

def create_boleta_afecta(*args, **kwargs) -> BaseDocument:
    """Función de conveniencia para crear boleta afecta."""
    return factory.create_boleta_afecta(*args, **kwargs)

def create_nota_credito(*args, **kwargs) -> BaseDocument:
    """Función de conveniencia para crear nota de crédito."""
    return factory.create_nota_credito(*args, **kwargs)

def create_from_xml(xml_content: str) -> BaseDocument:
    """Función de conveniencia para crear desde XML."""
    return factory.create_from_xml(xml_content)