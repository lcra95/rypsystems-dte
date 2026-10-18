"""
Libros del set de pruebas de certificación, según las instrucciones del SII:

- Libro de ventas: con los documentos del set básico (o del de factura exenta),
  tipo ESPECIAL, envío TOTAL, folio de notificación 1.
- Libro de compras: con los documentos del set de libro de compras, en el
  mismo período, folio de notificación 2.
- Libro de guías: con las guías del set de guía de despacho, folio 3; el set
  indica qué guía se facturó y cuál se anuló.

Cada función entrega el XML firmado y validado contra su esquema.
"""

from typing import Any, Dict, Iterable, Optional, Union

from lxml import etree

from ..emision import EmisionError
from ..firma import DigitalCertificate, XmlSigner
from ..libro import LibroCompraVenta, LibroGuia
from ..xml.schema import schema_errors

PROVEEDOR_CERTIFICACION = {'RUTDoc': '78885550-8', 'RznSoc': 'Proveedor de Prueba Limitada'}


def _periodo(fechas: Iterable[str]) -> str:
    periodos = {f[:7] for f in fechas}
    if len(periodos) != 1:
        raise EmisionError(f'Los documentos deben ser de un mismo período tributario: {sorted(periodos)}')
    return periodos.pop()


def _validar(xml: bytes, esquema: str) -> bytes:
    errores = schema_errors(xml, esquema)
    if errores:
        raise EmisionError(f'El libro no cumple {esquema}: {"; ".join(errores[:3])}')
    if not XmlSigner().is_valid_xml(xml):
        raise EmisionError('La firma del libro no es válida.')
    return xml


def _comun(certificado, rut_emisor, periodo, fecha_resolucion, numero_resolucion):
    return dict(certificate=certificado, rut_emisor=rut_emisor, periodo=periodo,
                fecha_resolucion=str(fecha_resolucion), numero_resolucion=numero_resolucion,
                tipo_libro='ESPECIAL', tipo_envio='TOTAL')


def libro_ventas(dtes: Iterable[bytes], certificado: DigitalCertificate, rut_emisor: str, fecha_resolucion: str,
                 numero_resolucion: int = 0, folio_notificacion: int = 1) -> bytes:
    libro = LibroCompraVenta('VENTA')
    fechas = [libro.agregar_dte(xml)['FchDoc'] for xml in dtes]
    if not fechas:
        raise EmisionError('El libro de ventas no tiene documentos.')
    xml = libro.generar(folio_notificacion=folio_notificacion,
                        **_comun(certificado, rut_emisor, _periodo(fechas), fecha_resolucion, numero_resolucion))
    return _validar(xml, 'LibroCV_v10.xsd')


def libro_compras(set_compras: Dict[str, Any], periodo: str, certificado: DigitalCertificate, rut_emisor: str,
                  fecha_resolucion: str, numero_resolucion: int = 0,
                  proveedor: Optional[Dict[str, str]] = None) -> bytes:
    """
    Args:
        set_compras: Set de libro de compras (leer_set_pruebas o YAML).
        periodo: AAAA-MM, el de los documentos del libro de ventas.
        proveedor: RUTDoc y RznSoc de los proveedores (un RUT válido).
    """
    libro = LibroCompraVenta('COMPRA')
    proveedor = proveedor or PROVEEDOR_CERTIFICACION
    for i, documento in enumerate(set_compras['documentos'], start=1):
        documento = {k: v for k, v in documento.items() if k != 'observacion'}
        if documento.pop('uso_comun', False):
            documento['FctProp'] = set_compras['factor_proporcionalidad_iva']
        libro.agregar({'TasaImp': 19, 'FchDoc': f'{periodo}-{min(i, 28):02d}', **proveedor, **documento})
    xml = libro.generar(folio_notificacion=set_compras.get('folio_notificacion', 2),
                        **_comun(certificado, rut_emisor, periodo, fecha_resolucion, numero_resolucion))
    return _validar(xml, 'LibroCV_v10.xsd')


def libro_guias(guias: Iterable[bytes], set_guias: Dict[str, Any], certificado: DigitalCertificate, rut_emisor: str,
                fecha_resolucion: str, numero_resolucion: int = 0,
                factura: Optional[Dict[str, Any]] = None) -> bytes:
    """
    Args:
        guias: XML de las guías del set de guía de despacho, en el orden de sus casos.
        set_guias: Set de libro de guías: casos {n: {'facturada': ...} | {'anulada': True}}.
        factura: {'TpoDocRef', 'FolioDocRef'} de la factura que facturó la guía
            (si el set lo trae como True).
    """
    libro = LibroGuia()
    casos = set_guias.get('casos') or {}
    fechas = []
    for numero, xml in enumerate(guias, start=1):
        if isinstance(xml, str):
            xml = xml.encode('iso-8859-1')
        caso = casos.get(numero) or casos.get(str(numero)) or {}
        extra: Dict[str, Union[int, str]] = {}
        if caso.get('anulada'):
            extra['Anulado'] = 2
        if caso.get('facturada'):
            referencia = caso['facturada'] if isinstance(caso['facturada'], dict) else factura
            if not referencia:
                raise EmisionError(f'Indique la factura que facturó la guía del caso {numero}.')
            fecha = etree.fromstring(xml).xpath('string(//*[local-name()="IdDoc"]/*[local-name()="FchEmis"])')
            extra.update({'FchDocRef': fecha, **referencia})
        fechas.append(libro.agregar_dte(xml, **extra)['FchDoc'])
    if not fechas:
        raise EmisionError('El libro de guías no tiene guías.')
    xml = libro.generar(certificado, rut_emisor, _periodo(fechas), str(fecha_resolucion), numero_resolucion,
                        set_guias.get('folio_notificacion', 3))
    return _validar(xml, 'LibroGuia_v10.xsd')
