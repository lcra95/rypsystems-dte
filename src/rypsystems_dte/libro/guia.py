"""
Libro electrónico de guías de despacho.

Basado en LibroGuia de LibreDTE clásico, con los nodos en el orden del
esquema LibroGuia_v10.xsd.

Anulado: 1 = folio anulado (no emitido), 2 = guía anulada (emitida y luego
anulada). TpoOper: tipo de traslado de la guía (IndTraslado); 1 = venta.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

from lxml import etree

from ..dte.normalizer import num, php_empty, php_int, php_round
from ..firma.digital_certificate import DigitalCertificate
from ..firma.xml_signer import XmlSigner
from ..xml.encoder import XmlEncoder, save_xml
from .compra_venta import LibroError, SII_DTE_NAMESPACE, XSI_NAMESPACE

CAMPOS_DETALLE = (
    'Folio', 'Anulado', 'Operacion', 'TpoOper', 'FchDoc', 'RUTDoc', 'RznSoc', 'MntNeto', 'TasaImp', 'IVA',
    'MntTotal', 'MntModificado', 'TpoDocRef', 'FolioDocRef', 'FchDocRef',
)


class LibroGuia:
    """Libro de guías de despacho."""

    def __init__(self):
        self.detalles: List[Dict[str, Any]] = []

    def agregar(self, detalle: Dict[str, Any]) -> Dict[str, Any]:
        """Agrega una guía al libro (traducción de LibroGuia::normalizarDetalle())."""
        base = {campo: False for campo in CAMPOS_DETALLE}
        base.update({'FchDoc': date.today().isoformat(), 'TasaImp': 0, 'IVA': 0})
        d = {**base, **detalle}
        if not d['Folio']:
            raise LibroError('Cada guía del libro debe tener Folio.')
        if d['RznSoc']:
            d['RznSoc'] = str(d['RznSoc'])[:50]
        if not d['IVA'] and d['TasaImp'] and d['MntNeto']:
            d['IVA'] = int(php_round(num(d['MntNeto']) * (num(d['TasaImp']) / 100)))
        if d['MntTotal'] is False:
            d['MntTotal'] = php_int(d['MntNeto']) + php_int(d['IVA'])
        self.detalles.append(d)
        return d

    def agregar_dte(self, xml: Union[str, bytes], **extra: Any) -> Dict[str, Any]:
        """
        Agrega una guía de despacho emitida a partir de su XML.

        Args:
            extra: Campos adicionales del detalle (Anulado, TpoDocRef,
                FolioDocRef, FchDocRef, MntModificado...)
        """
        if isinstance(xml, str):
            xml = xml.encode('iso-8859-1', errors='xmlcharrefreplace')
        root = etree.fromstring(xml)

        def text(*path: str) -> Optional[str]:
            xpath = '/'.join(f'*[local-name()="{p}"]' for p in path)
            value = root.xpath(f'string(.//*[local-name()="Encabezado"]/{xpath})').strip()
            return value or None

        if php_int(text('IdDoc', 'TipoDTE')) != 52:
            raise LibroError('Solo se pueden agregar guías de despacho (tipo 52) al libro de guías.')
        detalle = {
            'Folio': php_int(text('IdDoc', 'Folio')),
            'TpoOper': php_int(text('IdDoc', 'IndTraslado')) or False,
            'FchDoc': text('IdDoc', 'FchEmis'),
            'RUTDoc': text('Receptor', 'RUTRecep') or False,
            'RznSoc': text('Receptor', 'RznSocRecep') or False,
            'MntNeto': php_int(text('Totales', 'MntNeto')) if not php_empty(text('Totales', 'MntNeto')) else False,
            'TasaImp': num(text('Totales', 'TasaIVA')) or 0,
            'IVA': php_int(text('Totales', 'IVA')),
            'MntTotal': php_int(text('Totales', 'MntTotal')),
        }
        detalle.update(extra)
        return self.agregar(detalle)

    def get_resumen(self) -> Dict[str, Any]:
        """ResumenPeriodo (guías de venta, anuladas y traslados por tipo)."""
        resumen = {
            'TotFolAnulado': False, 'TotGuiaAnulada': False, 'TotGuiaVenta': 0, 'TotMntGuiaVta': 0,
            'TotMntModificado': False, 'TotTraslado': {},
        }
        for d in self.detalles:
            if php_int(d['Anulado']) in (1, 2):
                campo = 'TotFolAnulado' if php_int(d['Anulado']) == 1 else 'TotGuiaAnulada'
                resumen[campo] = php_int(resumen[campo]) + 1
            elif php_int(d['TpoOper']) == 1:
                resumen['TotGuiaVenta'] += 1
                resumen['TotMntGuiaVta'] += php_int(d['MntTotal'])
                if not php_empty(d['MntModificado']):
                    resumen['TotMntModificado'] = php_int(resumen['TotMntModificado']) + php_int(d['MntModificado'])
            else:
                item = resumen['TotTraslado'].setdefault(d['TpoOper'], {
                    'TpoTraslado': d['TpoOper'], 'CantGuia': 0, 'MntGuia': 0,
                })
                item['CantGuia'] += 1
                item['MntGuia'] += php_int(d['MntTotal'])
        resumen['TotTraslado'] = list(resumen['TotTraslado'].values()) or False
        return resumen

    def generar(
        self,
        certificate: DigitalCertificate,
        rut_emisor: str,
        periodo: str,
        fecha_resolucion: str,
        numero_resolucion: int = 0,
        folio_notificacion: int = 1,
        tipo_libro: str = 'ESPECIAL',
        tipo_envio: str = 'TOTAL',
        timestamp: Optional[str] = None,
    ) -> bytes:
        """Genera el XML del libro de guías firmado."""
        if not self.detalles:
            raise LibroError('El libro no tiene guías.')
        timestamp = timestamp or datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        libro_id = f'LIBRO_GUIA_{rut_emisor.replace("-", "")}_{periodo.replace("-", "")}_' \
                   f'{datetime.now().strftime("%Y%m%d%H%M%S")}'
        data = {
            'LibroGuia': {
                '@attributes': {
                    'xmlns': SII_DTE_NAMESPACE,
                    'xmlns:xsi': XSI_NAMESPACE,
                    'xsi:schemaLocation': f'{SII_DTE_NAMESPACE} LibroGuia_v10.xsd',
                    'version': '1.0',
                },
                'EnvioLibro': {
                    '@attributes': {'ID': libro_id},
                    'Caratula': {
                        'RutEmisorLibro': rut_emisor,
                        'RutEnvia': certificate.get_id(),
                        'PeriodoTributario': periodo,
                        'FchResol': fecha_resolucion,
                        'NroResol': int(numero_resolucion),
                        'TipoLibro': tipo_libro.upper(),
                        'TipoEnvio': tipo_envio.upper(),
                        'FolioNotificacion': folio_notificacion,
                    },
                    'ResumenPeriodo': self.get_resumen(),
                    'Detalle': [{c: d[c] for c in CAMPOS_DETALLE} for d in self.detalles],
                    'TmstFirma': timestamp,
                },
            }
        }
        xml = save_xml(XmlEncoder().encode(data))
        return XmlSigner().sign_xml(xml, certificate, libro_id, xmlns_xsi=True)
