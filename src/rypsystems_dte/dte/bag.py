"""
Document Bag - Contenedor de datos y opciones para documentos DTE

Implementación Python de DocumentBag de LibreDTE.
Maneja datos, opciones, certificados y CAF para construcción de documentos.
"""

from typing import Dict, Any, Optional, Union, List
from datetime import datetime

from pydantic import BaseModel, Field

from ..firma.digital_certificate import DigitalCertificate
from ..identifier.caf import Caf
from ..sii.base import Contribuyente
from ..sii.constants import CodigoDocumento


class DocumentOptions(BaseModel):
    """
    Opciones de configuración para el procesamiento de documentos.

    Reproduce las opciones de DocumentBag de LibreDTE.
    """
    builder: Dict[str, Any] = Field(default_factory=dict, description="Opciones del builder")
    normalizer: Dict[str, Any] = Field(default_factory=dict, description="Opciones del normalizador")
    parser: Dict[str, Any] = Field(default_factory=dict, description="Opciones del parser")
    renderer: Dict[str, Any] = Field(default_factory=dict, description="Opciones del renderer")
    sanitizer: Dict[str, Any] = Field(default_factory=dict, description="Opciones del sanitizador")
    validator: Dict[str, Any] = Field(default_factory=dict, description="Opciones del validador")


class DocumentBag:
    """
    Contenedor de datos del documento tributario electrónico.

    Permite "mover" un documento, junto a otros datos asociados, por métodos
    de manera sencilla y extensible.

    Reproduce la funcionalidad de DocumentBag de LibreDTE.
    """

    def __init__(
        self,
        tipo_documento: Union[CodigoDocumento, int],
        datos: Optional[Dict[str, Any]] = None,
        options: Optional[DocumentOptions] = None
    ):
        """
        Constructor del DocumentBag.

        Args:
            tipo_documento: Tipo de documento DTE
            datos: Datos del documento
            options: Opciones de procesamiento
        """
        self._tipo_documento = tipo_documento if isinstance(tipo_documento, CodigoDocumento) else CodigoDocumento(tipo_documento)
        self._input_data: Optional[str] = None
        self._datos = datos or {}
        self._options = options or DocumentOptions()

        # Datos adicionales para procesamiento
        self._caf_data: Optional[Caf] = None
        self._certificate_data: Optional[DigitalCertificate] = None
        self._timbre: Optional[Dict[str, Any]] = None
        self._xml: Optional[bytes] = None
        self._emisor: Optional[Contribuyente] = None
        self._receptor: Optional[Contribuyente] = None

        # Estados de procesamiento
        self._normalized = False
        self._sanitized = False
        self._validated = False
        self._stamped = False
        self._signed = False

    def get_tipo_documento(self) -> CodigoDocumento:
        """
        Obtiene el tipo de documento.

        Returns:
            Enum del tipo de documento
        """
        return self._tipo_documento

    def get_codigo(self) -> int:
        """
        Obtiene el código numérico del tipo de documento.

        Returns:
            Código del tipo de documento
        """
        return self._tipo_documento.value

    def get_input_data(self) -> Optional[str]:
        """
        Obtiene los datos originales de entrada.

        Returns:
            Datos de entrada sin procesar
        """
        return self._input_data

    def set_input_data(self, data: str) -> None:
        """
        Establece los datos originales de entrada.

        Args:
            data: Datos de entrada a procesar
        """
        self._input_data = data

    def get_datos(self) -> Dict[str, Any]:
        """
        Obtiene los datos procesados del documento.

        Returns:
            Datos del documento en formato estándar
        """
        return self._datos

    def set_datos(self, datos: Dict[str, Any]) -> None:
        """
        Establece los datos del documento.

        Args:
            datos: Datos del documento
        """
        self._datos = datos

    def get_options(self) -> DocumentOptions:
        """
        Obtiene las opciones de procesamiento.

        Returns:
            Opciones configuradas
        """
        return self._options

    def set_options(self, options: DocumentOptions) -> None:
        """
        Establece las opciones de procesamiento.

        Args:
            options: Nuevas opciones
        """
        self._options = options

    def get_builder_options(self) -> Dict[str, Any]:
        """
        Obtiene las opciones específicas del builder.

        Returns:
            Opciones del builder
        """
        return self._options.builder

    def get_normalizer_options(self) -> Dict[str, Any]:
        """
        Obtiene las opciones específicas del normalizador.

        Returns:
            Opciones del normalizador
        """
        return self._options.normalizer

    def get_validator_options(self) -> Dict[str, Any]:
        """
        Obtiene las opciones específicas del validador.

        Returns:
            Opciones del validador
        """
        return self._options.validator

    def get_caf(self) -> Optional[Caf]:
        """
        Obtiene el CAF (Código de Autorización de Folios) para timbrar.

        Returns:
            CAF o None
        """
        return self._caf_data

    def set_caf(self, caf: Union[Caf, str, bytes, None]) -> None:
        """
        Establece el CAF con el que se timbrará el documento.

        Args:
            caf: Instancia de Caf o el XML del CAF

        Raises:
            CafError: Si el XML entregado no es un CAF válido
        """
        if caf is None or isinstance(caf, Caf):
            self._caf_data = caf
        else:
            self._caf_data = Caf(caf)

    def get_certificate(self) -> Optional[DigitalCertificate]:
        """
        Obtiene el certificado digital con el que se firmará el documento.

        Returns:
            Certificado o None
        """
        return self._certificate_data

    def set_certificate(self, certificate: Optional[DigitalCertificate]) -> None:
        """
        Establece el certificado digital con el que se firmará el documento.

        Args:
            certificate: Certificado con clave privada (ver DigitalCertificate.from_file())
        """
        if certificate is not None and not isinstance(certificate, DigitalCertificate):
            raise TypeError(
                'El certificado debe ser un DigitalCertificate (cárguelo con DigitalCertificate.from_file()).'
            )
        self._certificate_data = certificate

    def get_timbre(self) -> Optional[Dict[str, Any]]:
        """Timbre (TED) generado al timbrar el documento."""
        return self._timbre

    def set_timbre(self, timbre: Optional[Dict[str, Any]]) -> None:
        self._timbre = timbre

    def get_xml(self) -> Optional[bytes]:
        """XML final del documento (firmado si correspondía)."""
        return self._xml

    def set_xml(self, xml: Optional[bytes]) -> None:
        self._xml = xml

    def get_id(self) -> str:
        """
        ID del nodo Documento, referenciado por la firma.

        Formato de LibreDTE: LibreDTE_{RUT_EMISOR}_T{TIPO:03d}F{FOLIO:09d}
        """
        return 'LibreDTE_%s_T%03dF%09d' % (
            self.get_rut_emisor(),
            self.get_codigo(),
            self.get_folio() or 0,
        )

    def get_emisor(self) -> Optional[Contribuyente]:
        """
        Obtiene el contribuyente emisor.

        Returns:
            Contribuyente emisor o None
        """
        return self._emisor

    def set_emisor(self, emisor: Contribuyente) -> None:
        """
        Establece el contribuyente emisor.

        Args:
            emisor: Contribuyente emisor
        """
        self._emisor = emisor

    def get_receptor(self) -> Optional[Contribuyente]:
        """
        Obtiene el contribuyente receptor.

        Returns:
            Contribuyente receptor o None
        """
        return self._receptor

    def set_receptor(self, receptor: Contribuyente) -> None:
        """
        Establece el contribuyente receptor.

        Args:
            receptor: Contribuyente receptor
        """
        self._receptor = receptor

    # Estados de procesamiento
    def is_normalized(self) -> bool:
        """Verifica si los datos han sido normalizados."""
        return self._normalized

    def set_normalized(self, normalized: bool = True) -> None:
        """Marca los datos como normalizados."""
        self._normalized = normalized

    def is_sanitized(self) -> bool:
        """Verifica si los datos han sido sanitizados."""
        return self._sanitized

    def set_sanitized(self, sanitized: bool = True) -> None:
        """Marca los datos como sanitizados."""
        self._sanitized = sanitized

    def is_validated(self) -> bool:
        """Verifica si los datos han sido validados."""
        return self._validated

    def set_validated(self, validated: bool = True) -> None:
        """Marca los datos como validados."""
        self._validated = validated

    def is_stamped(self) -> bool:
        """Verifica si el documento ha sido timbrado."""
        return self._stamped

    def set_stamped(self, stamped: bool = True) -> None:
        """Marca el documento como timbrado."""
        self._stamped = stamped

    def is_signed(self) -> bool:
        """Verifica si el documento ha sido firmado."""
        return self._signed

    def set_signed(self, signed: bool = True) -> None:
        """Marca el documento como firmado."""
        self._signed = signed

    def get_folio(self) -> Optional[int]:
        """
        Obtiene el folio del documento desde los datos.

        Returns:
            Folio del documento o None
        """
        try:
            return int(self._datos.get('Encabezado', {}).get('IdDoc', {}).get('Folio', 0))
        except (ValueError, TypeError):
            return None

    def get_rut_emisor(self) -> Optional[str]:
        """
        Obtiene el RUT del emisor desde los datos.

        Returns:
            RUT del emisor o None
        """
        return self._datos.get('Encabezado', {}).get('Emisor', {}).get('RUTEmisor')

    def get_rut_receptor(self) -> Optional[str]:
        """
        Obtiene el RUT del receptor desde los datos.

        Returns:
            RUT del receptor o None
        """
        return self._datos.get('Encabezado', {}).get('Receptor', {}).get('RUTRecep')

    def get_monto_total(self) -> Optional[Union[int, float]]:
        """
        Obtiene el monto total desde los datos.

        Returns:
            Monto total o None
        """
        try:
            monto = float(self._datos.get('Encabezado', {}).get('Totales', {}).get('MntTotal', 0))
            return int(monto) if monto == int(monto) else monto
        except (ValueError, TypeError):
            return None

    def validate_required_data(self) -> List[str]:
        """
        Valida que los datos requeridos estén presentes.

        Returns:
            Lista de errores encontrados
        """
        errors = []

        # Validar estructura básica
        if not self._datos:
            errors.append("No hay datos del documento")
            return errors

        encabezado = self._datos.get('Encabezado', {})
        if not encabezado:
            errors.append("Falta sección Encabezado")
            return errors

        # Validar IdDoc
        id_doc = encabezado.get('IdDoc', {})
        if not id_doc:
            errors.append("Falta sección IdDoc")
        else:
            if not id_doc.get('TipoDTE'):
                errors.append("Falta TipoDTE")
            if not id_doc.get('Folio'):
                errors.append("Falta Folio")
            if not id_doc.get('FchEmis'):
                errors.append("Falta FchEmis")

        # Validar Emisor
        emisor = encabezado.get('Emisor', {})
        if not emisor:
            errors.append("Falta sección Emisor")
        else:
            if not emisor.get('RUTEmisor'):
                errors.append("Falta RUTEmisor")

        # Validar Receptor (no obligatorio para todos los tipos)
        receptor = encabezado.get('Receptor', {})
        receptor_con_datos = isinstance(receptor, dict) and any(
            v not in (None, False, '') for v in receptor.values()
        )
        if receptor_con_datos and not receptor.get('RUTRecep'):
            errors.append("RUTRecep inválido en Receptor")

        # Validar Totales
        totales = encabezado.get('Totales', {})
        # MntTotal 0 es válido (p. ej. guía de traslado interno o nota que
        # solo corrige un texto); lo que no puede es faltar.
        mnt_total = totales.get('MntTotal') if totales else None
        if totales and (mnt_total is None or mnt_total is False or mnt_total == ''):
            errors.append("Falta MntTotal en Totales")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el DocumentBag a diccionario para serialización.

        Returns:
            Representación del bag como diccionario
        """
        return {
            'tipo_documento': self._tipo_documento.value,
            'datos': self._datos,
            'options': self._options.dict(),
            'has_caf': self._caf_data is not None,
            'has_certificate': self._certificate_data is not None,
            'states': {
                'normalized': self._normalized,
                'sanitized': self._sanitized,
                'validated': self._validated,
                'stamped': self._stamped,
                'signed': self._signed,
            }
        }

    def __repr__(self) -> str:
        """Representación string del DocumentBag."""
        folio = self.get_folio()
        rut_emisor = self.get_rut_emisor()
        return f"DocumentBag(tipo={self._tipo_documento.name}, folio={folio}, emisor={rut_emisor})"