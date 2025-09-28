"""
Base Document Classes - Clases base para documentos DTE

Implementación Python de AbstractDocument y DocumentInterface de LibreDTE.
Proporciona funcionalidad base para todos los tipos de documentos DTE.
"""

from typing import Dict, Any, List, Union, Optional
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field

from ..sii.constants import CodigoDocumento
from ..xml.document import XmlDocument
from ..firma.ted import TEDBuilder, TEDData


class BaseDocument(ABC):
    """
    Clase base para documentos tributarios electrónicos.

    Reproduce la funcionalidad de AbstractDocument de LibreDTE.
    Proporciona métodos base para manipular documentos DTE.
    """

    def __init__(self, xml_document: XmlDocument):
        """
        Constructor del documento tributario.

        Args:
            xml_document: Documento XML asociado

        Raises:
            ValueError: Si el tipo de documento no coincide
        """
        self.xml_document = xml_document
        self._datos: Optional[Dict[str, Any]] = None

        # Validar que el código del XML coincida con el esperado
        xml_tipo_dte = self._get_xml_tipo_dte()
        if xml_tipo_dte != self.get_codigo():
            raise ValueError(
                f"El código {xml_tipo_dte} del XmlDocument no corresponde "
                f"con el esperado para {self.__class__.__name__}, "
                f"debería ser código {self.get_codigo()}"
            )

    def __str__(self) -> str:
        """Representación string del documento."""
        return self.get_id()

    @property
    @abstractmethod
    def tipo_documento(self) -> CodigoDocumento:
        """
        Código del tipo de documento tributario.

        Este valor debe estar definido en cada clase que herede de esta.
        """
        pass

    def _get_xml_tipo_dte(self) -> int:
        """Obtiene el tipo DTE desde el XML."""
        return int(self.xml_document.query('//Encabezado/IdDoc/TipoDTE') or 0)

    def get_xml_document(self) -> XmlDocument:
        """
        Entrega el documento XML asociado al DTE.

        Returns:
            Documento XML asociado
        """
        return self.xml_document

    def save_xml(self) -> str:
        """
        Genera el documento XML como string incluyendo encabezado.

        Returns:
            XML del documento con declaración
        """
        return self.xml_document.save_xml()

    def get_xml(self) -> str:
        """
        Genera el documento XML como string sin encabezado.

        Returns:
            XML del documento sin declaración
        """
        # Para compatibilidad, usamos save_xml() pero removemos la declaración
        xml_with_declaration = self.save_xml()
        lines = xml_with_declaration.split('\n')
        # Remover línea de declaración XML
        if lines and lines[0].startswith('<?xml'):
            lines = lines[1:]
        return '\n'.join(lines).strip()

    def get_id(self) -> str:
        """
        Entrega el ID asignado al documento.

        Formato: {RUT_EMISOR}_T{TIPO_DOC:03d}F{FOLIO:09d}

        Returns:
            ID único del documento
        """
        return f"{self.get_rut_emisor()}_T{self.get_codigo():03d}F{self.get_folio():09d}"

    def get_codigo(self) -> int:
        """
        Obtiene el código numérico del documento tributario.

        Returns:
            Código del tipo de documento
        """
        return self.tipo_documento.value

    def get_folio(self) -> int:
        """
        Entrega el folio del documento tributario.

        Returns:
            Folio del documento
        """
        return int(self.xml_document.query('//Encabezado/IdDoc/Folio') or 0)

    def get_tipo_documento(self) -> CodigoDocumento:
        """
        Entrega el tipo de documento (como enum) asociado al DTE.

        Returns:
            Enum del tipo de documento
        """
        return self.tipo_documento

    def get_emisor(self) -> Dict[str, Any]:
        """
        Obtiene el contribuyente emisor del documento.

        Returns:
            Datos del emisor en el DTE
        """
        result = self.xml_document.query('//Encabezado/Emisor')
        return result if isinstance(result, dict) else {}

    def get_rut_emisor(self) -> str:
        """
        Obtiene el RUT del emisor del documento.

        Returns:
            RUT del emisor
        """
        return self.xml_document.query('//Encabezado/Emisor/RUTEmisor') or ''

    def get_receptor(self) -> Dict[str, Any]:
        """
        Obtiene el contribuyente receptor del documento.

        Returns:
            Datos del receptor en el DTE
        """
        result = self.xml_document.query('//Encabezado/Receptor')
        return result if isinstance(result, dict) else {}

    def get_rut_receptor(self) -> str:
        """
        Obtiene el RUT del receptor del documento.

        Returns:
            RUT del receptor
        """
        return self.xml_document.query('//Encabezado/Receptor/RUTRecep') or ''

    def get_razon_social_receptor(self) -> str:
        """
        Obtiene la razón social del receptor del documento.

        Returns:
            Razón social del receptor
        """
        return self.xml_document.query('//Encabezado/Receptor/RznSocRecep') or ''

    def get_fecha_emision(self) -> str:
        """
        Obtiene la fecha de emisión del documento.

        Returns:
            Fecha de emisión (YYYY-MM-DD)
        """
        return self.xml_document.query('//Encabezado/IdDoc/FchEmis') or ''

    def get_totales(self) -> Dict[str, Any]:
        """
        Obtiene los totales del documento.

        Returns:
            Diccionario con los totales
        """
        result = self.xml_document.query('//Encabezado/Totales')
        if isinstance(result, dict):
            # Convertir valores numéricos de string a int/float
            for key, value in result.items():
                if isinstance(value, str) and value.strip():
                    if key.startswith('Mnt') or key == 'IVA':
                        try:
                            # Convertir a float primero, luego a int si no tiene decimales
                            float_val = float(value)
                            result[key] = int(float_val) if float_val == int(float_val) else float_val
                        except ValueError:
                            pass  # Mantener como string si no se puede convertir
            return result
        return {}

    def get_monto_total(self) -> Union[int, float]:
        """
        Obtiene el monto total del documento.

        Returns:
            Monto total como int o float
        """
        monto = float(self.xml_document.query('//Encabezado/Totales/MntTotal') or 0)

        # Verificar si el monto es equivalente a un entero
        if monto == int(monto):
            return int(monto)

        return monto

    def get_moneda(self) -> str:
        """
        Obtiene la moneda del documento.

        Returns:
            Código de moneda (default: 'PESO CL')
        """
        return self.query('//Encabezado/Totales/TpoMoneda') or 'PESO CL'

    def get_detalle(self, index: Optional[int] = None) -> Union[List[Dict], Dict, List]:
        """
        Obtiene el detalle del documento.

        Args:
            index: Índice específico del detalle (opcional)

        Returns:
            Lista de detalles o detalle específico
        """
        detalle = self.xml_document.query('//Detalle')
        if detalle is None:
            return []

        # Normalizar a lista si no lo es
        if not isinstance(detalle, list):
            detalle = [detalle]

        # Convertir valores numéricos de string a tipos apropiados
        for item in detalle:
            if isinstance(item, dict):
                for key, value in item.items():
                    if isinstance(value, str) and value.strip():
                        if key in ['QtyItem', 'PrcItem', 'MontoItem', 'DescuentoMonto']:
                            try:
                                # QtyItem puede ser float, otros generalmente int
                                if key == 'QtyItem':
                                    float_val = float(value)
                                    item[key] = int(float_val) if float_val == int(float_val) else float_val
                                else:
                                    item[key] = int(float(value))
                            except ValueError:
                                pass  # Mantener como string si no se puede convertir

        return detalle[index] if index is not None and index < len(detalle) else detalle

    def get_datos(self) -> Dict[str, Any]:
        """
        Obtiene los datos del documento en formato estandarizado.

        Returns:
            Datos del DTE sin TED ni firma
        """
        if self._datos is None:
            array = self.xml_document.to_array()

            # Extraer datos del documento según estructura
            array = (
                array.get('DTE', {}).get('Documento') or
                array.get('DTE', {}).get('Exportaciones') or
                array.get('DTE', {}).get('Liquidacion') or
                array
            )

            # Remover TED y firma temporal
            if isinstance(array, dict):
                array.pop('TED', None)
                array.pop('TmstFirma', None)

                # Asegurar arrays para campos que pueden ser múltiples
                self._ensure_array_fields(array)

                # Normalizar tipos de datos
                self._normalize_data_types(array)

            self._datos = array

        return self._datos

    def _ensure_array_fields(self, data: Dict[str, Any]) -> None:
        """
        Asegura que ciertos campos sean arrays para consistencia.

        Args:
            data: Datos del documento a normalizar
        """
        array_paths = [
            'Encabezado.Totales.ImptoReten',
            'Detalle',
            'DscRcgGlobal',
            'Referencia',
        ]

        for path in array_paths:
            keys = path.split('.')
            current = data

            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            last_key = keys[-1]
            if last_key in current and not isinstance(current[last_key], list):
                if current[last_key] is not None:
                    current[last_key] = [current[last_key]]
                else:
                    current[last_key] = []

    def _normalize_data_types(self, data: Dict[str, Any]) -> None:
        """
        Normaliza tipos de datos desde strings a tipos apropiados.

        Args:
            data: Datos del documento a normalizar
        """
        # Normalizar Referencia
        if 'Referencia' in data and isinstance(data['Referencia'], list):
            for ref in data['Referencia']:
                if isinstance(ref, dict):
                    for key, value in ref.items():
                        if isinstance(value, str) and value.strip():
                            if key in ['TpoDocRef', 'FolioRef', 'CodRef']:
                                try:
                                    ref[key] = int(value)
                                except ValueError:
                                    pass  # Mantener como string si no se puede convertir

    def get_ted(self) -> Optional[str]:
        """
        Entrega el nodo TED aplanado y listo para ser usado en el PDF417.

        Returns:
            TED canonicalizado o None si no existe
        """
        try:
            return self.xml_document.c14n_with_iso88591_encoding_flattened('//TED')
        except Exception:
            return None

    def get_plantilla_ted(self) -> Dict[str, Any]:
        """
        Entrega un arreglo con una plantilla con la estructura del TED.

        Returns:
            Plantilla TED para completar y firmar
        """
        ted_builder = TEDBuilder()

        # Crear datos TED desde el documento
        ted_data = TEDData(
            rut_emisor=self.get_rut_emisor(),
            tipo_documento=self.get_codigo(),
            folio=self.get_folio(),
            fecha_emision=self.get_fecha_emision(),
            rut_receptor=self.get_rut_receptor(),
            razon_social_receptor=self.get_razon_social_receptor(),
            monto_total=self.get_monto_total(),
            primer_item=self._get_primer_item(),
            caf_data='',  # Se completará al timbrar
            timestamp_ted=''  # Se completará al timbrar
        )

        return ted_builder.build_ted_template(ted_data)

    def _get_primer_item(self) -> str:
        """
        Obtiene el primer item del detalle para el TED.

        Returns:
            Nombre del primer item (truncado a 40 caracteres)
        """
        detalle = self.get_detalle(0)
        if isinstance(detalle, dict):
            primer_item = detalle.get('NmbItem', '')
        elif isinstance(detalle, list) and len(detalle) > 0:
            primer_item = detalle[0].get('NmbItem', '')
        else:
            primer_item = ''

        return primer_item[:40] if primer_item else ''

    def get(self, selector: str) -> Any:
        """
        Obtiene un elemento del DTE utilizando un selector.

        Args:
            selector: Selector del elemento que se desea obtener

        Returns:
            Valor encontrado o None
        """
        # Implementación simple de selector por puntos
        keys = selector.split('.')
        current = self.get_datos()

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def query(self, xpath: str, params: Optional[Dict] = None) -> Any:
        """
        Ejecuta una consulta XPath en el documento XML.

        Args:
            xpath: Consulta XPath
            params: Parámetros para la consulta (opcional)

        Returns:
            Resultado de la consulta
        """
        return self.xml_document.query(xpath, params or {})

    # Métodos de integración SII
    def submit_to_sii(
        self,
        sii_client,
        rut_sender: Optional[str] = None,
        validate_only: bool = False
    ):
        """
        Envía el documento al SII usando el cliente de integración.

        Args:
            sii_client: Cliente SII configurado
            rut_sender: RUT del emisor (opcional, usa el del documento)
            validate_only: Solo validar, no procesar

        Returns:
            Respuesta del SII con resultado del envío

        Raises:
            IntegrationException: Si hay error en el envío
        """
        from ..integration.sii_client import SiiClient
        from ..integration.exceptions import IntegrationException

        if not isinstance(sii_client, SiiClient):
            raise ValueError("sii_client debe ser una instancia de SiiClient")

        try:
            return sii_client.submit_document(
                document=self,
                rut_sender=rut_sender,
                validate_only=validate_only
            )
        except Exception as e:
            raise IntegrationException(f"Error enviando documento {self.get_id()}: {e}")

    def query_sii_status(self, sii_client, track_id: Optional[str] = None):
        """
        Consulta el estado del documento en el SII.

        Args:
            sii_client: Cliente SII configurado
            track_id: ID de seguimiento SII (opcional)

        Returns:
            Respuesta del SII con estado del documento

        Raises:
            IntegrationException: Si hay error en la consulta
        """
        from ..integration.sii_client import SiiClient
        from ..integration.exceptions import IntegrationException

        if not isinstance(sii_client, SiiClient):
            raise ValueError("sii_client debe ser una instancia de SiiClient")

        try:
            if track_id:
                return sii_client.query_document_status(track_ids=[track_id])
            else:
                return sii_client.query_document_status(
                    document_ids=[self.get_id()],
                    folios=[self.get_folio()],
                    document_types=[self.get_codigo()]
                )
        except Exception as e:
            raise IntegrationException(f"Error consultando estado de documento {self.get_id()}: {e}")

    def get_sii_receipt(self, sii_client, track_id: str, receipt_type: str = 'xml') -> Optional[str]:
        """
        Obtiene el acuse de recibo del SII.

        Args:
            sii_client: Cliente SII configurado
            track_id: ID de seguimiento SII
            receipt_type: Tipo de acuse (xml, pdf)

        Returns:
            Contenido del acuse o None si no está disponible

        Raises:
            IntegrationException: Si hay error obteniendo el acuse
        """
        from ..integration.sii_client import SiiClient
        from ..integration.exceptions import IntegrationException

        if not isinstance(sii_client, SiiClient):
            raise ValueError("sii_client debe ser una instancia de SiiClient")

        try:
            return sii_client.get_document_receipt(track_id, receipt_type)
        except Exception as e:
            raise IntegrationException(f"Error obteniendo acuse para documento {self.get_id()}: {e}")


# Clases específicas de documentos DTE
class FacturaAfecta(BaseDocument):
    """Clase que representa una factura electrónica afecta."""

    @property
    def tipo_documento(self) -> CodigoDocumento:
        return CodigoDocumento.FACTURA_AFECTA


class FacturaExenta(BaseDocument):
    """Clase que representa una factura electrónica exenta."""

    @property
    def tipo_documento(self) -> CodigoDocumento:
        return CodigoDocumento.FACTURA_EXENTA


class BoletaAfecta(BaseDocument):
    """Clase que representa una boleta electrónica afecta."""

    @property
    def tipo_documento(self) -> CodigoDocumento:
        return CodigoDocumento.BOLETA_AFECTA


class BoletaExenta(BaseDocument):
    """Clase que representa una boleta electrónica exenta."""

    @property
    def tipo_documento(self) -> CodigoDocumento:
        return CodigoDocumento.BOLETA_EXENTA


class NotaCredito(BaseDocument):
    """Clase que representa una nota de crédito electrónica."""

    @property
    def tipo_documento(self) -> CodigoDocumento:
        return CodigoDocumento.NOTA_CREDITO


class NotaDebito(BaseDocument):
    """Clase que representa una nota de débito electrónica."""

    @property
    def tipo_documento(self) -> CodigoDocumento:
        return CodigoDocumento.NOTA_DEBITO


class GuiaDespacho(BaseDocument):
    """Clase que representa una guía de despacho electrónica."""

    @property
    def tipo_documento(self) -> CodigoDocumento:
        return CodigoDocumento.GUIA_DESPACHO


# Mapping de códigos a clases de documento
DOCUMENT_CLASSES = {
    CodigoDocumento.FACTURA_AFECTA: FacturaAfecta,
    CodigoDocumento.FACTURA_EXENTA: FacturaExenta,
    CodigoDocumento.BOLETA_AFECTA: BoletaAfecta,
    CodigoDocumento.BOLETA_EXENTA: BoletaExenta,
    CodigoDocumento.NOTA_CREDITO: NotaCredito,
    CodigoDocumento.NOTA_DEBITO: NotaDebito,
    CodigoDocumento.GUIA_DESPACHO: GuiaDespacho,
}