"""
Constantes y enums del SII de Chile.

Traducción directa de los enums y constantes PHP de LibreDTE:
- CodigoDocumento
- CategoriaDocumento
- OperacionDocumento
- TagXmlDocumento
- TipoSobre
"""

from enum import Enum, IntEnum
from typing import Dict, Any


class CategoriaDocumento(Enum):
    """
    Categorías de documentos según SII.

    Equivale a CategoriaDocumento enum en PHP.
    """
    TRIBUTARIO = "tributario"
    INFORMATIVO = "informativo"
    REFERENCIA = "referencia"


class OperacionDocumento(Enum):
    """
    Tipos de operación de documentos.

    Equivale a OperacionDocumento enum en PHP.
    """
    SUMA = "suma"
    RESTA = "resta"


class TagXmlDocumento(Enum):
    """
    Tags XML para diferentes tipos de documentos.

    Equivale a TagXmlDocumento enum en PHP.
    """
    DOCUMENTO = "Documento"
    LIQUIDACION = "Liquidacion"
    EXPORTACIONES = "Exportaciones"


class TipoSobre(Enum):
    """
    Tipos de sobre para envío de documentos.

    Equivale a TipoSobre enum en PHP.
    """
    ENVIO_DTE = "EnvioDTE"
    ENVIO_BOLETA = "EnvioBOLETA"


class CodigoDocumento(IntEnum):
    """
    Códigos oficiales de documentos tributarios según SII.

    Equivale a CodigoDocumento enum en PHP.
    """
    # Facturas
    FACTURA_AFECTA = 33
    FACTURA_EXENTA = 34
    FACTURA_COMPRA = 46
    FACTURA_EXPORTACION = 110

    # Boletas
    BOLETA_AFECTA = 39
    BOLETA_EXENTA = 41

    # Notas
    NOTA_DEBITO = 56
    NOTA_CREDITO = 61
    NOTA_DEBITO_EXPORTACION = 111
    NOTA_CREDITO_EXPORTACION = 112

    # Otros
    GUIA_DESPACHO = 52
    LIQUIDACION_FACTURA = 43

    def get_nombre(self) -> str:
        """Obtiene el nombre completo del documento."""
        return DOCUMENTOS_SII[self.value]["nombre"]

    def get_nombre_corto(self) -> str:
        """Obtiene el nombre corto del documento."""
        return DOCUMENTOS_SII[self.value].get("nombre_corto", self.get_nombre())

    def get_alias(self) -> str:
        """Obtiene el alias del documento."""
        return DOCUMENTOS_SII[self.value].get("alias", str(self.value))

    def get_interface(self) -> str:
        """Obtiene la interfaz del documento."""
        return DOCUMENTOS_SII[self.value].get("interface", "default")


# Diccionario completo de tipos de documento
# Traducción directa del array PHP en tipos_documento.php
DOCUMENTOS_SII: Dict[int, Dict[str, Any]] = {
    # Documentos tributarios oficiales del SII
    29: {
        "nombre": "Factura de inicio",
    },
    30: {
        "nombre": "Factura",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
    },
    32: {
        "nombre": "Factura de venta bienes y servicios no afectos o exentos de IVA",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
    },
    CodigoDocumento.FACTURA_AFECTA.value: {
        "nombre": "Factura electrónica",
        "nombre_corto": "Factura",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
        "cedible": True,
        "tag_xml": TagXmlDocumento.DOCUMENTO,
        "disponible": True,
        "alias": "FE",
        "interface": "factura",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    CodigoDocumento.FACTURA_EXENTA.value: {
        "nombre": "Factura no afecta o exenta electrónica",
        "nombre_corto": "Factura exenta",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
        "cedible": True,
        "tag_xml": TagXmlDocumento.DOCUMENTO,
        "disponible": True,
        "alias": "FEE",
        "interface": "factura_exenta",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    35: {
        "nombre": "Boleta",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": False,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
    },
    38: {
        "nombre": "Boleta exenta",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": False,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
    },
    CodigoDocumento.BOLETA_AFECTA.value: {
        "nombre": "Boleta electrónica",
        "nombre_corto": "Boleta",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": False,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
        "tag_xml": TagXmlDocumento.DOCUMENTO,
        "disponible": True,
        "alias": "BE",
        "interface": "boleta",
        "tipo_sobre": TipoSobre.ENVIO_BOLETA,
    },
    40: {
        "nombre": "Liquidación factura",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": True,
        "venta": True,
    },
    CodigoDocumento.BOLETA_EXENTA.value: {
        "nombre": "Boleta exenta electrónica",
        "nombre_corto": "Boleta exenta",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": False,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
        "tag_xml": TagXmlDocumento.DOCUMENTO,
        "disponible": True,
        "alias": "BEE",
        "interface": "boleta_exenta",
        "tipo_sobre": TipoSobre.ENVIO_BOLETA,
    },
    CodigoDocumento.LIQUIDACION_FACTURA.value: {
        "nombre": "Liquidación factura electrónica",
        "nombre_corto": "Liquidación",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": True,
        "venta": True,
        "cedible": True,
        "tag_xml": TagXmlDocumento.LIQUIDACION,
        "disponible": False,  # No soportado actualmente en LibreDTE
        "alias": "LF",
        "interface": "liquidacion",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    45: {
        "nombre": "Factura de compra",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.RESTA,
    },
    CodigoDocumento.FACTURA_COMPRA.value: {
        "nombre": "Factura de compra electrónica",
        "nombre_corto": "Factura compra",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.RESTA,
        "cedible": True,
        "tag_xml": TagXmlDocumento.DOCUMENTO,
        "disponible": True,
        "alias": "FC",
        "interface": "factura_compra",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    48: {
        "nombre": "Comprobante de pago electrónico",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": False,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
    },
    50: {
        "nombre": "Guía de despacho",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": False,
        "venta": False,
    },
    CodigoDocumento.GUIA_DESPACHO.value: {
        "nombre": "Guía de despacho electrónica",
        "nombre_corto": "Guía despacho",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": False,
        "venta": False,
        "cedible": True,
        "tag_xml": TagXmlDocumento.DOCUMENTO,
        "disponible": True,
        "alias": "GD",
        "interface": "guia_despacho",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    55: {
        "nombre": "Nota de débito",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
    },
    CodigoDocumento.NOTA_DEBITO.value: {
        "nombre": "Nota de débito electrónica",
        "nombre_corto": "Nota débito",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
        "tag_xml": TagXmlDocumento.DOCUMENTO,
        "disponible": True,
        "alias": "ND",
        "interface": "nota_debito",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    60: {
        "nombre": "Nota de crédito",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.RESTA,
    },
    CodigoDocumento.NOTA_CREDITO.value: {
        "nombre": "Nota de crédito electrónica",
        "nombre_corto": "Nota crédito",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.RESTA,
        "tag_xml": TagXmlDocumento.DOCUMENTO,
        "disponible": True,
        "alias": "NC",
        "interface": "nota_credito",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    101: {
        "nombre": "Factura de exportación",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
    },
    104: {
        "nombre": "Nota de débito de exportación",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
    },
    106: {
        "nombre": "Nota de crédito de exportación",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": False,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.RESTA,
    },
    CodigoDocumento.FACTURA_EXPORTACION.value: {
        "nombre": "Factura de exportación electrónica",
        "nombre_corto": "Factura exportación",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
        "tag_xml": TagXmlDocumento.EXPORTACIONES,
        "disponible": True,
        "alias": "FEX",
        "interface": "factura_exportacion",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    CodigoDocumento.NOTA_DEBITO_EXPORTACION.value: {
        "nombre": "Nota de débito de exportación electrónica",
        "nombre_corto": "Nota débito exportación",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.SUMA,
        "tag_xml": TagXmlDocumento.EXPORTACIONES,
        "disponible": True,
        "alias": "NDEX",
        "interface": "nota_debito_exportacion",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    CodigoDocumento.NOTA_CREDITO_EXPORTACION.value: {
        "nombre": "Nota de crédito de exportación electrónica",
        "nombre_corto": "Nota crédito exportación",
        "categoria": CategoriaDocumento.TRIBUTARIO,
        "electronico": True,
        "enviar": True,
        "compra": True,
        "venta": True,
        "operacion": OperacionDocumento.RESTA,
        "tag_xml": TagXmlDocumento.EXPORTACIONES,
        "disponible": True,
        "alias": "NCEX",
        "interface": "nota_credito_exportacion",
        "tipo_sobre": TipoSobre.ENVIO_DTE,
    },
    # Documentos informativos oficiales del SII
    801: {
        "nombre": "Orden de compra",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    802: {
        "nombre": "Nota de pedido",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    803: {
        "nombre": "Contrato",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    804: {
        "nombre": "Resolución",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    805: {
        "nombre": "Procedo ChileCompra",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    806: {
        "nombre": "Ficha ChileCompra",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    807: {
        "nombre": "DUS",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    808: {
        "nombre": "Conocimiento de embarque (B/L)",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    809: {
        "nombre": "AWB",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    810: {
        "nombre": "Manifiesto internacional (MIC)",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    811: {
        "nombre": "Carta de porte",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    812: {
        "nombre": "Resolución SNA",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    813: {
        "nombre": "Pasaporte",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    814: {
        "nombre": "Certificado de depósito Bolsa Prod. Chile",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
    815: {
        "nombre": "Vale de prenda Bolsa Prod. Chile",
        "categoria": CategoriaDocumento.INFORMATIVO,
    },
}


def get_documento_info(codigo: int) -> Dict[str, Any]:
    """
    Obtiene información completa de un tipo de documento.

    Args:
        codigo: Código del documento según SII

    Returns:
        Diccionario con información del documento

    Raises:
        KeyError: Si el código no existe
    """
    if codigo not in DOCUMENTOS_SII:
        raise KeyError(f"Código de documento {codigo} no encontrado")

    return DOCUMENTOS_SII[codigo]


def es_documento_electronico(codigo: int) -> bool:
    """
    Verifica si un documento es electrónico.

    Args:
        codigo: Código del documento

    Returns:
        True si es electrónico, False en caso contrario
    """
    info = get_documento_info(codigo)
    return info.get("electronico", False)


def es_documento_cedible(codigo: int) -> bool:
    """
    Verifica si un documento es cedible.

    Args:
        codigo: Código del documento

    Returns:
        True si es cedible, False en caso contrario
    """
    info = get_documento_info(codigo)
    return info.get("cedible", False)