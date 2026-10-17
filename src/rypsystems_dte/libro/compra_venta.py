"""
Información Electrónica de Compras y Ventas (IECV): libro de compras y ventas.

Basado en LibroCompraVenta de LibreDTE clásico (aceptado por el SII) y en el
documento "Formato de Información Electrónica de Compras y Ventas" del SII.
Los nodos se generan en el orden del esquema LibroCV_v10.xsd.

Ejemplo (libro de ventas desde DTE emitidos):

    libro = LibroCompraVenta('VENTA')
    for xml in dtes_emitidos:
        libro.agregar_dte(xml)
    xml = libro.generar(certificado, rut_emisor='76192083-9', periodo='2026-10',
                        fecha_resolucion='2026-10-17', numero_resolucion=0,
                        tipo_libro='ESPECIAL', folio_notificacion=1)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from lxml import etree

from ..dte.normalizer import impuesto_adicional, num, php_empty, php_int, php_round
from ..firma.digital_certificate import DigitalCertificate
from ..firma.xml_signer import XmlSigner
from ..xml.encoder import XmlEncoder, save_xml

SII_DTE_NAMESPACE = 'http://www.sii.cl/SiiDte'
XSI_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
TASA_IVA = 19

# Documentos que no van en el detalle del libro de ventas (se informan solo
# en el resumen: boletas, comprobantes de pago, etc.).
OMITIR_DETALLE_VENTAS = (35, 38, 39, 41, 105, 500, 501, 919, 920, 922, 924)

# Orden de los campos del detalle según LibroCV_v10.xsd.
CAMPOS_DETALLE = (
    'TpoDoc', 'Emisor', 'IndFactCompra', 'NroDoc', 'Anulado', 'Operacion', 'TpoImp', 'TasaImp', 'NumInt',
    'IndServicio', 'IndSinCosto', 'FchDoc', 'CdgSIISucur', 'RUTDoc', 'RznSoc', 'Extranjero', 'TpoDocRef',
    'FolioDocRef', 'MntExe', 'MntNeto', 'MntIVA', 'MntActivoFijo', 'MntIVAActivoFijo', 'IVANoRec',
    'IVAUsoComun', 'IVAFueraPlazo', 'IVAPropio', 'IVATerceros', 'Ley18211', 'OtrosImp', 'MntSinCred',
    'IVARetTotal', 'IVARetParcial', 'CredEC', 'DepEnvase', 'Liquidaciones', 'MntTotal', 'IVANoRetenido',
    'MntNoFact', 'MntPeriodo', 'PsjNac', 'PsjInt', 'TabPuros', 'TabCigarrillos', 'TabElaborado', 'ImpVehiculo',
)

# Orden de los campos de TotalesPeriodo según LibroCV_v10.xsd.
CAMPOS_TOTALES = (
    'TpoDoc', 'TpoImp', 'TotDoc', 'TotAnulado', 'TotOpExe', 'TotMntExe', 'TotMntNeto', 'TotOpIVARec',
    'TotMntIVA', 'TotOpActivoFijo', 'TotMntActivoFijo', 'TotMntIVAActivoFijo', 'TotIVANoRec',
    'TotOpIVAUsoComun', 'TotIVAUsoComun', 'FctProp', 'TotCredIVAUsoComun', 'TotIVAFueraPlazo',
    'TotIVAPropio', 'TotIVATerceros', 'TotLey18211', 'TotOtrosImp', 'TotImpSinCredito', 'TotOpIVARetTotal',
    'TotIVARetTotal', 'TotOpIVARetParcial', 'TotIVARetParcial', 'TotCredEC', 'TotDepEnvase',
    'TotLiquidaciones', 'TotMntTotal', 'TotOpIVANoRetenido', 'TotIVANoRetenido', 'TotMntNoFact',
    'TotMntPeriodo', 'TotPsjNac', 'TotPsjInt', 'TotTabPuros', 'TotTabCigarrillos', 'TotTabElaborado',
    'TotImpVehiculo',
)


class LibroError(ValueError):
    """Error al armar un libro de compras o ventas."""


def _as_list(value: Any) -> List[Any]:
    if value in (None, False):
        return []
    return value if isinstance(value, list) else [value]


class LibroCompraVenta:
    """Libro de compras (TipoOperacion COMPRA) o de ventas (VENTA)."""

    def __init__(self, tipo_operacion: str = 'VENTA'):
        tipo_operacion = tipo_operacion.upper()
        if tipo_operacion not in ('VENTA', 'COMPRA'):
            raise LibroError('El tipo de operación del libro debe ser VENTA o COMPRA.')
        self.tipo_operacion = tipo_operacion
        self.detalles: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Detalle
    # ------------------------------------------------------------------

    def agregar(self, detalle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agrega un documento al libro calculando IVA y total si faltan.

        Campos de entrada (los del detalle del IECV) más:
            FctProp: factor de proporcionalidad del IVA uso común en porcentaje
                (p. ej. 60); el IVA del documento se registra como IVA uso común.

        Returns:
            El detalle normalizado
        """
        d = self._normalizar(dict(detalle))
        self.detalles.append(d)
        return d

    def agregar_dte(self, xml: Union[str, bytes]) -> Dict[str, Any]:
        """
        Agrega al libro un DTE emitido (o recibido) a partir de su XML.

        Equivale a Dte::getResumen() de LibreDTE.
        """
        if isinstance(xml, str):
            xml = xml.encode('iso-8859-1', errors='xmlcharrefreplace')
        root = etree.fromstring(xml)

        def text(path: str) -> Optional[str]:
            nodes = root.xpath(f'string(.//*[local-name()="Encabezado"]/{path})')
            return nodes.strip() or None

        def lname(name: str) -> str:
            return f'*[local-name()="{name}"]'

        tipo = php_int(text(f'{lname("IdDoc")}/{lname("TipoDTE")}'))
        detalle = {
            'TpoDoc': tipo,
            'NroDoc': php_int(text(f'{lname("IdDoc")}/{lname("Folio")}')),
            'TasaImp': 0,
            'FchDoc': text(f'{lname("IdDoc")}/{lname("FchEmis")}'),
            'CdgSIISucur': text(f'{lname("Emisor")}/{lname("CdgSIISucur")}') or False,
            'RUTDoc': text(f'{lname("Receptor")}/{lname("RUTRecep")}'),
            'RznSoc': text(f'{lname("Receptor")}/{lname("RznSocRecep")}') or False,
            'MntExe': False,
            'MntNeto': False,
            'MntIVA': 0,
            'MntTotal': 0,
        }
        for destino, origen in (('TasaImp', 'TasaIVA'), ('MntExe', 'MntExe'), ('MntNeto', 'MntNeto'),
                                ('MntIVA', 'IVA'), ('MntTotal', 'MntTotal')):
            valor = text(f'{lname("Totales")}/{lname(origen)}')
            if not php_empty(valor):
                detalle[destino] = int(php_round(valor)) if tipo not in (110, 111, 112) else num(valor)
        if tipo in (39, 41):
            detalle['TasaImp'] = detalle['TasaImp'] or TASA_IVA
            detalle['MntExe'] = php_int(detalle['MntExe'])
            if not detalle['MntNeto']:
                total = detalle['MntTotal'] - detalle['MntExe']
                neto = int(php_round(total / (1 + detalle['TasaImp'] / 100)))
                detalle['MntNeto'], detalle['MntIVA'] = neto, total - neto
        return self.agregar(detalle)

    def _normalizar(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Traducción de LibroCompraVenta::normalizarDetalle() de LibreDTE."""
        fct_prop = d.pop('FctProp', None)
        base = {campo: False for campo in CAMPOS_DETALLE}
        base['TpoImp'] = 1
        d = {**base, **d}
        if not d['TpoDoc'] or not d['NroDoc']:
            raise LibroError('Cada documento del libro debe tener TpoDoc y NroDoc.')

        if d['Anulado'] == 'A':
            return {'TpoDoc': d['TpoDoc'], 'NroDoc': d['NroDoc'], 'Anulado': 'A'}

        if d['RznSoc']:
            d['RznSoc'] = str(d['RznSoc'])[:50]

        neto_por_tasa = (
            round(php_round(num(d['MntNeto']) * (num(d['TasaImp']) / 100)))
            if d['TasaImp'] and d['MntNeto'] else 0
        )
        iva_no_rec = _as_list(d['IVANoRec'])
        if fct_prop is not None:
            # Compra con IVA uso común: el IVA va en IVAUsoComun, no es recuperable.
            if d['IVAUsoComun'] is False:
                d['IVAUsoComun'] = neto_por_tasa
            if d['MntIVA'] is False:
                d['MntIVA'] = 0
        elif iva_no_rec:
            for inr in iva_no_rec:
                if php_empty(inr.get('MntIVANoRec')):
                    inr['MntIVANoRec'] = neto_por_tasa
            # "Si en un documento no hay IVA recuperable debe venir con cero."
            if d['MntIVA'] is False:
                d['MntIVA'] = 0
        elif not d['MntIVA'] and d['TasaImp'] and d['MntNeto']:
            d['MntIVA'] = neto_por_tasa
        d['IVANoRec'] = [{'CodIVANoRec': i['CodIVANoRec'], 'MntIVANoRec': i['MntIVANoRec']} for i in iva_no_rec] or False

        if d['MntExe'] is False and d['MntNeto'] is False and d['MntTotal'] == 0 and d['MntTotal'] is not False:
            d['MntNeto'] = 0
        if d['MntNeto'] is False and d['MntExe']:
            d['TasaImp'] = TASA_IVA
            d['MntNeto'] = 0
            d['MntIVA'] = 0

        otros = []
        for imp in _as_list(d['OtrosImp']):
            imp = {'CodImp': imp['CodImp'], 'TasaImp': imp.get('TasaImp', False), 'MntImp': imp.get('MntImp')}
            if php_empty(imp['MntImp']) and imp['TasaImp'] and d['MntNeto']:
                imp['MntImp'] = round(php_round(num(d['MntNeto']) * num(imp['TasaImp']) / 100))
            otros.append(imp)
        d['OtrosImp'] = otros or False
        retenido = sum(num(i['MntImp']) for i in otros if impuesto_adicional(i['CodImp'])['tipo'] == 'R')
        if retenido:
            if retenido == num(d['MntIVA']):
                d['IVARetTotal'] = retenido
            else:
                d['IVARetParcial'] = retenido
                d['IVANoRetenido'] = num(d['MntIVA']) - retenido

        if d['MntTotal'] is False:
            total = php_int(d['MntExe']) + php_int(d['MntNeto']) + php_int(d['MntIVA'])
            total += sum(php_int(i['MntIVANoRec']) for i in iva_no_rec)
            total += php_int(d['IVAUsoComun'])
            total -= sum(php_int(i['MntImp']) for i in otros if impuesto_adicional(i['CodImp'])['tipo'] == 'R')
            for campo in ('MntSinCred', 'TabPuros', 'TabCigarrillos', 'TabElaborado', 'ImpVehiculo'):
                total += php_int(d[campo])
            d['MntTotal'] = total

        if d['MntNeto'] is False:
            d['MntNeto'] = d['TasaImp'] = d['MntIVA'] = False
        if not d['CdgSIISucur']:
            d['CdgSIISucur'] = False
        if fct_prop is not None:
            d['_FctProp'] = fct_prop
        return d

    # ------------------------------------------------------------------
    # Resumen
    # ------------------------------------------------------------------

    def get_resumen(self) -> List[Dict[str, Any]]:
        """Totales por tipo de documento (TotalesPeriodo), ordenados por tipo."""
        totales: Dict[int, Dict[str, Any]] = {}
        for d in self.detalles:
            t = totales.setdefault(int(d['TpoDoc']), {
                'TpoDoc': int(d['TpoDoc']), 'TotDoc': 0, 'TotMntExe': 0, 'TotMntNeto': 0, 'TotMntIVA': 0,
                'TotMntTotal': 0,
            })
            t['TotDoc'] += 1
            if d.get('Anulado') == 'A':
                t['TotAnulado'] = t.get('TotAnulado', 0) + 1
                continue
            t['TotMntExe'] += php_int(d['MntExe'])
            t['TotMntNeto'] += php_int(d['MntNeto'])
            t['TotMntIVA'] += php_int(d['MntIVA'])
            t['TotMntTotal'] += php_int(d['MntTotal'])
            for campo, total in (('MntActivoFijo', 'TotMntActivoFijo'), ('MntIVAActivoFijo', 'TotMntIVAActivoFijo'),
                                 ('IVAFueraPlazo', 'TotIVAFueraPlazo'), ('MntSinCred', 'TotImpSinCredito'),
                                 ('ImpVehiculo', 'TotImpVehiculo')):
                if not php_empty(d.get(campo)):
                    t[total] = t.get(total, 0) + php_int(d[campo])
            for inr in _as_list(d.get('IVANoRec')):
                tot = t.setdefault('TotIVANoRec', {})
                item = tot.setdefault(inr['CodIVANoRec'], {
                    'CodIVANoRec': inr['CodIVANoRec'], 'TotOpIVANoRec': 0, 'TotMntIVANoRec': 0,
                })
                item['TotOpIVANoRec'] += 1
                item['TotMntIVANoRec'] += php_int(inr['MntIVANoRec'])
            if '_FctProp' in d:
                t['TotOpIVAUsoComun'] = t.get('TotOpIVAUsoComun', 0) + 1
                t['TotIVAUsoComun'] = t.get('TotIVAUsoComun', 0) + php_int(d['IVAUsoComun'])
                t['FctProp'] = num(d['_FctProp']) / 100
                t['TotCredIVAUsoComun'] = t.get('TotCredIVAUsoComun', 0) + int(
                    php_round(php_int(d['IVAUsoComun']) * (num(d['_FctProp']) / 100))
                )
            for imp in _as_list(d.get('OtrosImp')):
                tot = t.setdefault('TotOtrosImp', {})
                item = tot.setdefault(imp['CodImp'], {'CodImp': imp['CodImp'], 'TotMntImp': 0})
                item['TotMntImp'] += php_int(imp['MntImp'])
            for campo, op, total in (('IVARetTotal', 'TotOpIVARetTotal', 'TotIVARetTotal'),
                                     ('IVARetParcial', 'TotOpIVARetParcial', 'TotIVARetParcial'),
                                     ('IVANoRetenido', 'TotOpIVANoRetenido', 'TotIVANoRetenido')):
                if not php_empty(d.get(campo)):
                    t[op] = t.get(op, 0) + 1
                    t[total] = t.get(total, 0) + php_int(d[campo])

        resumen = []
        for tipo in sorted(totales):
            t = totales[tipo]
            for lista in ('TotIVANoRec', 'TotOtrosImp'):
                if lista in t:
                    t[lista] = list(t[lista].values())
            resumen.append({campo: t[campo] for campo in CAMPOS_TOTALES if campo in t})
        return resumen

    def get_detalle(self) -> List[Dict[str, Any]]:
        """Detalle en el orden del esquema (sin documentos que solo van en el resumen)."""
        detalles = []
        for d in self.detalles:
            if self.tipo_operacion == 'VENTA' and int(d['TpoDoc']) in OMITIR_DETALLE_VENTAS:
                continue
            detalles.append({campo: d[campo] for campo in CAMPOS_DETALLE if campo in d})
        return detalles

    # ------------------------------------------------------------------
    # XML
    # ------------------------------------------------------------------

    def generar(
        self,
        certificate: DigitalCertificate,
        rut_emisor: str,
        periodo: str,
        fecha_resolucion: str,
        numero_resolucion: int = 0,
        tipo_libro: str = 'MENSUAL',
        tipo_envio: str = 'TOTAL',
        folio_notificacion: Optional[int] = None,
        incluir_detalle: bool = True,
        timestamp: Optional[str] = None,
    ) -> bytes:
        """
        Genera el XML del libro firmado.

        Args:
            certificate: Certificado de quien envía
            rut_emisor: RUT del contribuyente dueño del libro
            periodo: Período tributario AAAA-MM
            fecha_resolucion: Fecha de resolución (AAAA-MM-DD)
            numero_resolucion: Número de resolución (0 en certificación)
            tipo_libro: MENSUAL, ESPECIAL o RECTIFICA
            tipo_envio: TOTAL, PARCIAL, FINAL o AJUSTE
            folio_notificacion: Obligatorio para libros ESPECIAL
            incluir_detalle: Incluir el detalle de los documentos
            timestamp: TmstFirma (por defecto ahora)
        """
        if not self.detalles:
            raise LibroError('El libro no tiene documentos.')
        tipo_libro = tipo_libro.upper()
        if tipo_libro == 'ESPECIAL' and folio_notificacion is None:
            raise LibroError('Los libros ESPECIAL requieren el folio de notificación.')
        timestamp = timestamp or datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        libro_id = f'LIBRO_{self.tipo_operacion}_{rut_emisor.replace("-", "")}_{periodo.replace("-", "")}_' \
                   f'{datetime.now().strftime("%Y%m%d%H%M%S")}'

        data = {
            'LibroCompraVenta': {
                '@attributes': {
                    'xmlns': SII_DTE_NAMESPACE,
                    'xmlns:xsi': XSI_NAMESPACE,
                    'xsi:schemaLocation': f'{SII_DTE_NAMESPACE} LibroCV_v10.xsd',
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
                        'TipoOperacion': self.tipo_operacion,
                        'TipoLibro': tipo_libro,
                        'TipoEnvio': tipo_envio.upper(),
                        'FolioNotificacion': folio_notificacion if folio_notificacion is not None else False,
                    },
                    'ResumenPeriodo': {'TotalesPeriodo': self.get_resumen()},
                    'Detalle': self.get_detalle() if incluir_detalle else False,
                    'TmstFirma': timestamp,
                },
            }
        }
        xml = save_xml(XmlEncoder().encode(data))
        return XmlSigner().sign_xml(xml, certificate, libro_id, xmlns_xsi=True)
