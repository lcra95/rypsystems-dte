"""
Representación impresa (PDF) de documentos tributarios electrónicos.

Basado en la representación de LibreDTE clásico (lib/Sii/Dte/PDF/Dte.php) y en
las exigencias del SII para la muestra impresa:

- Recuadro con RUT del emisor, nombre del documento y folio, más la unidad
  del SII ("S.I.I. - <dirección regional>").
- Timbre electrónico en PDF417 (nivel de seguridad 5) con el TED del DTE,
  bajo la leyenda "Timbre Electrónico SII", la resolución y
  "Verifique documento: www.sii.cl".
- Copia cedible con acuse de recibo (Ley 19.983) para los documentos que lo
  requieren; en guías de despacho "CEDIBLE CON SU FACTURA".
"""

import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pdf417gen
from lxml import etree
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from ..xml.canonical import c14n_encoded_flattened
from ..xml.encoder import XmlEncoder

_DATA = Path(__file__).resolve().parent.parent / 'resources' / 'data'

TIPOS_DOCUMENTO = {
    30: 'FACTURA', 32: 'FACTURA DE VENTA BIENES Y SERVICIOS NO AFECTOS O EXENTOS DE IVA',
    33: 'FACTURA ELECTRÓNICA', 34: 'FACTURA NO AFECTA O EXENTA ELECTRÓNICA', 35: 'BOLETA',
    38: 'BOLETA EXENTA', 39: 'BOLETA ELECTRÓNICA', 41: 'BOLETA NO AFECTA O EXENTA ELECTRÓNICA',
    43: 'LIQUIDACIÓN FACTURA ELECTRÓNICA', 45: 'FACTURA DE COMPRA', 46: 'FACTURA DE COMPRA ELECTRÓNICA',
    50: 'GUÍA DE DESPACHO', 52: 'GUÍA DE DESPACHO ELECTRÓNICA', 55: 'NOTA DE DÉBITO',
    56: 'NOTA DE DÉBITO ELECTRÓNICA', 60: 'NOTA DE CRÉDITO', 61: 'NOTA DE CRÉDITO ELECTRÓNICA',
    110: 'FACTURA DE EXPORTACIÓN ELECTRÓNICA', 111: 'NOTA DE DÉBITO DE EXPORTACIÓN ELECTRÓNICA',
    112: 'NOTA DE CRÉDITO DE EXPORTACIÓN ELECTRÓNICA',
    801: 'ORDEN DE COMPRA', 802: 'NOTA DE PEDIDO', 803: 'CONTRATO', 804: 'RESOLUCIÓN', 807: 'DUS',
    808: 'B/L', 809: 'AWB', 810: 'MIC/DTA', 811: 'CARTA DE PORTE', 812: 'RESOLUCIÓN SNA', 813: 'PASAPORTE',
    'SET': 'SET DE PRUEBAS',
}
# Abreviaturas del tipo de documento liquidado (detalle de liquidaciones).
TIPOS_LIQUIDADOS = {
    30: 'Factura', 32: 'Fact. exenta', 33: 'Fact. elec.', 34: 'Fact. ex. elec.', 35: 'Boleta',
    38: 'Boleta exenta', 39: 'Boleta elec.', 41: 'Bol. ex. elec.', 43: 'Liq. fact. elec.',
    55: 'N. débito', 56: 'N. débito elec.', 60: 'N. crédito', 61: 'N. crédito elec.', 99: 'Otros',
}
CODIGOS_REFERENCIA = {1: 'Anula documento', 2: 'Corrige texto', 3: 'Corrige montos'}
TRASLADOS = {
    1: 'Operación constituye venta', 2: 'Ventas por efectuar', 3: 'Consignaciones', 4: 'Entrega gratuita',
    5: 'Traslado interno', 6: 'Otros traslados no venta', 7: 'Guía de devolución',
    8: 'Traslado para exportación', 9: 'Venta para exportación',
}
FORMAS_PAGO = {1: 'Contado', 2: 'Crédito', 3: 'Sin costo (entrega gratuita)'}
# Documentos sin acuse de recibo ni copia cedible (boletas, notas y exportación).
SIN_ACUSE_RECIBO = (39, 41, 56, 61, 110, 111, 112)
ACUSE_RECIBO = (
    'El acuse de recibo que se declara en este acto, de acuerdo a lo dispuesto en la letra b) del Art. 4°, '
    'y la letra c) del Art. 5° de la Ley 19.983, acredita que la entrega de mercaderías o servicio(s) '
    'prestado(s) ha(n) sido recibido(s).'
)

COLOR_FOLIO = colors.HexColor('#ff0000')
COLOR_FOLIO_GUIA = colors.HexColor('#00ac8c')
MARGEN = 10 * mm


def _local(node: etree._Element) -> str:
    return etree.QName(node).localname


def _to_dict(node: etree._Element) -> Any:
    """Nodo XML a diccionario (sin namespaces); los nodos repetidos van en listas."""
    children = [c for c in node if isinstance(c.tag, str)]
    if not children:
        return (node.text or '').strip()
    result: Dict[str, Any] = {}
    for child in children:
        key = _local(child)
        value = _to_dict(child)
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value
    return result


def _as_list(value: Any) -> List[Any]:
    if value in (None, '', {}):
        return []
    return value if isinstance(value, list) else [value]


def numero(value: Any, decimales: Optional[int] = None) -> str:
    """Número con separador de miles '.' y decimales ','."""
    if value in (None, ''):
        return ''
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimales is None:
        decimales = 0 if n.is_integer() else 2
    texto = f'{n:,.{decimales}f}'
    return texto.replace(',', '_').replace('.', ',').replace('_', '.')


def rut(value: str) -> str:
    """RUT con puntos: 76192083-9 -> 76.192.083-9."""
    if not value or '-' not in value:
        return value or ''
    cuerpo, dv = value.split('-', 1)
    return f'{numero(int(cuerpo))}-{dv}' if cuerpo.isdigit() else value


def fecha(value: str) -> str:
    """AAAA-MM-DD -> DD/MM/AAAA."""
    if value and len(value) >= 10 and value[4] == '-':
        return f'{value[8:10]}/{value[5:7]}/{value[:4]}'
    return value or ''


def ted_pdf417(dte: Union[bytes, etree._Element]) -> Optional[bytes]:
    """
    Datos del timbre para el PDF417: el TED canonicalizado, aplanado y en
    ISO-8859-1, sin namespace (igual que al timbrar).
    """
    root = etree.fromstring(dte) if isinstance(dte, bytes) else dte
    teds = root.xpath('.//*[local-name()="TED"]')
    if not teds:
        return None
    # Se reimporta el TED (sin namespaces) dentro de un nodo contenedor.
    tree = XmlEncoder().encode({'Contenedor': {'TED': teds[0]}})
    return c14n_encoded_flattened(tree, '/Contenedor/TED', 'ISO-8859-1')


def pdf417_image(data: bytes, columns: int = 12):
    """Imagen PDF417 (nivel de seguridad 5) para el timbre."""
    # Un PDF417 admite hasta 90 filas: si los datos no caben se agregan columnas.
    while True:
        try:
            codes = pdf417gen.encode(data, columns=columns, security_level=5)
            break
        except ValueError:
            if columns >= 30:
                raise
            columns += 1
    return pdf417gen.render_image(codes, scale=3, ratio=3, padding=0)


class DtePdf:
    """
    Genera la representación impresa en hoja carta de uno o varios DTE.

    Ejemplo:
        pdf = DtePdf(resolucion={'fecha': '2026-10-17', 'numero': 0})
        contenido = pdf.render(xml_dte)              # original y copia cedible
        contenido = pdf.render_envio(xml_envio_dte)  # todos los DTE del sobre
    """

    def __init__(
        self,
        resolucion: Dict[str, Any],
        logo: Optional[Union[str, Path]] = None,
        web_verificacion: str = 'www.sii.cl',
        sucursal_sii: Optional[str] = None,
    ):
        """
        Args:
            resolucion: {'fecha': 'AAAA-MM-DD', 'numero': int} de la autorización del SII
            logo: Imagen opcional del emisor
            web_verificacion: Sitio de verificación del timbre
            sucursal_sii: Unidad del SII; por defecto la dirección regional de la comuna del emisor
        """
        self.resolucion = resolucion
        self.logo = Path(logo) if logo else None
        self.web_verificacion = web_verificacion
        self.sucursal_sii = sucursal_sii
        self._comunas = None

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def render(self, xml: Union[str, bytes], cedible: bool = True) -> bytes:
        """PDF de un DTE (más su copia cedible si corresponde)."""
        if isinstance(xml, str):
            xml = xml.encode('iso-8859-1', errors='xmlcharrefreplace')
        root = etree.fromstring(xml)
        dtes = [root] if _local(root) == 'DTE' else root.xpath('.//*[local-name()="DTE"]')
        return self._render_dtes(dtes, cedible)

    def render_envio(self, xml: Union[str, bytes], cedible: bool = True) -> bytes:
        """PDF con todos los DTE de un EnvioDTE."""
        return self.render(xml, cedible)

    # ------------------------------------------------------------------

    def _render_dtes(self, dtes: List[etree._Element], cedible: bool) -> bytes:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setTitle('Documentos tributarios electrónicos')
        for dte in dtes:
            documento = next(child for child in dte if isinstance(child.tag, str) and _local(child) != 'Signature')
            datos = _to_dict(documento)
            tipo = int(datos['Encabezado']['IdDoc']['TipoDTE'])
            timbre = ted_pdf417(dte)
            self._pagina(c, datos, timbre, copia=None)
            if cedible and tipo not in SIN_ACUSE_RECIBO:
                self._pagina(c, datos, timbre, copia='CEDIBLE CON SU FACTURA' if tipo == 52 else 'CEDIBLE')
        c.save()
        return buffer.getvalue()

    def _direccion_regional(self, comuna: str) -> str:
        if self.sucursal_sii:
            return self.sucursal_sii
        if self._comunas is None:
            self._comunas = json.loads((_DATA / 'comunas.json').read_text(encoding='utf-8'))
        import unicodedata
        clave = unicodedata.normalize('NFKD', comuna or '').encode('ascii', 'ignore').decode().upper().strip()
        return (self._comunas.get(clave) or {}).get('direccion_regional', clave)

    # ------------------------------------------------------------------
    # Página
    # ------------------------------------------------------------------

    def _pagina(self, c: canvas.Canvas, datos: Dict[str, Any], timbre: Optional[bytes], copia: Optional[str]):
        ancho, alto = letter
        enc = datos['Encabezado']
        id_doc, emisor, receptor = enc['IdDoc'], enc.get('Emisor', {}), enc.get('Receptor', {})
        tipo = int(id_doc['TipoDTE'])
        exportacion = tipo in (110, 111, 112)
        decimales = 2 if exportacion else 0

        y = alto - MARGEN
        y_folio = self._folio(c, emisor.get('RUTEmisor', ''), tipo, id_doc.get('Folio'),
                              emisor.get('CmnaOrigen', ''), ancho - MARGEN - 75 * mm, y, 75 * mm)
        y_emisor = self._emisor(c, emisor, MARGEN, y, ancho - 2 * MARGEN - 80 * mm)
        y = min(y_folio, y_emisor) - 4 * mm

        y = self._receptor(c, id_doc, receptor, enc, MARGEN, y, ancho - 2 * MARGEN)
        y = self._traslado(c, id_doc, enc.get('Transporte'), MARGEN, y, ancho - 2 * MARGEN, exportacion)
        y = self._referencias(c, datos.get('Referencia'), MARGEN, y, ancho - 2 * MARGEN)
        y = self._detalle(c, datos, MARGEN, y, ancho - 2 * MARGEN, decimales)
        y = self._descuentos_recargos(c, datos.get('DscRcgGlobal'), MARGEN, y, ancho - 2 * MARGEN, decimales)
        y = self._comisiones(c, datos.get('Comisiones'), MARGEN, y, ancho - 2 * MARGEN)

        # Totales bajo el contenido, a la derecha; el pie (timbre, acuse y
        # leyenda cedible) ocupa la parte inferior de la página.
        # Pie en tres columnas: timbre (izquierda), acuse de recibo (centro) y
        # totales (derecha). Los totales van bajo el contenido y pueden bajar
        # hasta la leyenda cedible; el timbre y el acuse ocupan el pie.
        ancho_totales = 65 * mm
        tabla_totales = self._tabla_totales(enc.get('Totales', {}), enc.get('OtraMoneda'), ancho_totales, decimales)
        _, h_totales = tabla_totales.wrap(ancho_totales, 200 * mm)
        y_totales = min(y, MARGEN + 75 * mm + h_totales)
        if y_totales - h_totales < MARGEN + 8 * mm or y < MARGEN + 62 * mm and y - h_totales < MARGEN + 8 * mm:
            c.showPage()
            y_totales = alto - MARGEN
        tabla_totales.drawOn(c, ancho - MARGEN - ancho_totales, y_totales - h_totales)
        if y < MARGEN + 62 * mm:
            # El contenido llegó al pie: timbre y acuse en una página nueva.
            c.showPage()
        self._timbre(c, timbre, MARGEN, MARGEN, 70 * mm)
        if copia:
            self._acuse_recibo(c, MARGEN + 74 * mm, MARGEN, 52 * mm)
            c.setFont('Helvetica-Bold', 12)
            c.drawRightString(ancho - MARGEN, MARGEN, copia)
        c.showPage()

    # ------------------------------------------------------------------
    # Secciones
    # ------------------------------------------------------------------

    def _folio(self, c, rut_emisor, tipo, folio, comuna, x, y, w) -> float:
        color = COLOR_FOLIO_GUIA if tipo == 52 else COLOR_FOLIO
        nombre = TIPOS_DOCUMENTO.get(tipo, f'DOCUMENTO {tipo}')
        estilo = ParagraphStyle('folio', fontName='Helvetica-Bold', fontSize=12, leading=14,
                                alignment=1, textColor=color)
        lineas = [f'R.U.T.: {rut(rut_emisor)}', nombre, f'N° {folio}']
        bloques = [Paragraph(t, estilo) for t in lineas]
        alto_total = sum(p.wrap(w - 6 * mm, 100 * mm)[1] for p in bloques) + 8 * mm
        c.setStrokeColor(color)
        c.setLineWidth(1.5)
        c.rect(x, y - alto_total, w, alto_total)
        cursor = y - 4 * mm
        for p in bloques:
            _, h = p.wrap(w - 6 * mm, 100 * mm)
            p.drawOn(c, x + 3 * mm, cursor - h)
            cursor -= h
        c.setFillColor(color)
        c.setFont('Helvetica-Bold', 10)
        c.drawCentredString(x + w / 2, y - alto_total - 5 * mm, f'S.I.I. - {self._direccion_regional(comuna)}')
        c.setFillColor(colors.black)
        c.setStrokeColor(colors.black)
        return y - alto_total - 7 * mm

    def _emisor(self, c, emisor, x, y, w) -> float:
        if self.logo and self.logo.is_file():
            c.drawImage(ImageReader(str(self.logo)), x, y - 20 * mm, 30 * mm, 20 * mm,
                        preserveAspectRatio=True, mask='auto')
            x += 33 * mm
            w -= 33 * mm
        razon = emisor.get('RznSoc') or emisor.get('RznSocEmisor', '')
        giro = emisor.get('GiroEmis') or emisor.get('GiroEmisor', '')
        estilo = ParagraphStyle('emisor', fontName='Helvetica', fontSize=9, leading=11)
        titulo = ParagraphStyle('emisor_t', fontName='Helvetica-Bold', fontSize=13, leading=15)
        lineas = [Paragraph(razon, titulo), Paragraph(giro, estilo)]
        direccion = ', '.join(v for v in (emisor.get('DirOrigen'), emisor.get('CmnaOrigen'),
                                          emisor.get('CiudadOrigen')) if v)
        if direccion:
            lineas.append(Paragraph(direccion, estilo))
        contacto = ' - '.join(v for v in (emisor.get('Telefono'), emisor.get('CorreoEmisor')) if v)
        if contacto:
            lineas.append(Paragraph(contacto, estilo))
        cursor = y
        for p in lineas:
            _, h = p.wrap(w, 50 * mm)
            p.drawOn(c, x, cursor - h)
            cursor -= h + 1
        return cursor

    def _receptor(self, c, id_doc, receptor, enc, x, y, w) -> float:
        extranjero = receptor.get('Extranjero') or {}
        filas = [
            ('Señor(es)', receptor.get('RznSocRecep', ''), 'Fecha emisión', fecha(id_doc.get('FchEmis', ''))),
            ('R.U.T.', rut(receptor.get('RUTRecep', '')), 'Vencimiento', fecha(id_doc.get('FchVenc', ''))),
            ('Giro', receptor.get('GiroRecep', ''), 'Forma de pago',
             FORMAS_PAGO.get(int(id_doc['FmaPago']), id_doc['FmaPago']) if id_doc.get('FmaPago') else ''),
            ('Dirección', ', '.join(v for v in (receptor.get('DirRecep'), receptor.get('CmnaRecep'),
                                                receptor.get('CiudadRecep')) if v), '', ''),
        ]
        if isinstance(extranjero, dict) and extranjero.get('Nacionalidad'):
            filas.append(('País', self._aduana('aduana_paises', extranjero.get('Nacionalidad')),
                          'Id. extranjero', extranjero.get('NumId', '')))
        if receptor.get('Contacto') or receptor.get('CorreoRecep'):
            filas.append(('Contacto', receptor.get('Contacto', ''), 'Correo', receptor.get('CorreoRecep', '')))
        return self._tabla_datos(c, filas, x, y, w, (22 * mm, w - 22 * mm - 58 * mm, 28 * mm, 30 * mm), caja=True)

    def _aduana(self, tabla: str, codigo: Any) -> str:
        """Código de aduana con su glosa, p. ej. '504 (ITALIA)'."""
        if codigo in (None, ''):
            return ''
        cache = self.__dict__.setdefault('_tablas', {})
        if tabla not in cache:
            ruta = _DATA / f'{tabla}.json'
            cache[tabla] = json.loads(ruta.read_text(encoding='utf-8')) if ruta.is_file() else {}
        glosa = cache[tabla].get(str(int(codigo)) if str(codigo).isdigit() else str(codigo))
        if isinstance(glosa, dict):
            glosa = glosa.get('glosa')
        return f'{codigo} ({glosa})' if glosa else str(codigo)

    def _traslado(self, c, id_doc, transporte, x, y, w, exportacion) -> float:
        filas = []
        if id_doc.get('IndTraslado'):
            filas.append(('Traslado', TRASLADOS.get(int(id_doc['IndTraslado']), id_doc['IndTraslado']), '', ''))
        if isinstance(transporte, dict):
            destino = ', '.join(v for v in (transporte.get('DirDest'), transporte.get('CmnaDest'),
                                            transporte.get('CiudadDest')) if v)
            if destino or transporte.get('Patente'):
                filas.append(('Destino', destino, 'Patente', transporte.get('Patente', '')))
            aduana = transporte.get('Aduana') if exportacion else None
            if isinstance(aduana, dict):
                filas.append(('Cláusula venta', self._aduana('aduana_clausulas_venta', aduana.get('CodClauVenta')), 'Total cláusula',
                              numero(aduana.get('TotClauVenta'), 2) if aduana.get('TotClauVenta') else ''))
                filas.append(('Vía transporte', self._aduana('aduana_transportes', aduana.get('CodViaTransp')),
                              'Modalidad venta', self._aduana('aduana_modalidades_venta', aduana.get('CodModVenta'))))
                filas.append(('Puerto embarque', self._aduana('aduana_puertos', aduana.get('CodPtoEmbarque')),
                              'Puerto desembarque', self._aduana('aduana_puertos', aduana.get('CodPtoDesemb'))))
                filas.append(('País receptor', self._aduana('aduana_paises', aduana.get('CodPaisRecep')),
                              'País destino', self._aduana('aduana_paises', aduana.get('CodPaisDestin'))))
                if aduana.get('MntFlete') or aduana.get('MntSeguro'):
                    filas.append(('Flete', numero(aduana.get('MntFlete'), 2), 'Seguro', numero(aduana.get('MntSeguro'), 2)))
                for bulto in _as_list(aduana.get('TipoBultos')):
                    filas.append(('Bultos', f"{bulto.get('CantBultos', '')} x {self._aduana('aduana_tipos_bulto', bulto.get('CodTpoBultos'))}",
                                  'Marcas', bulto.get('Marcas', '')))
        if not filas:
            return y
        return self._tabla_datos(c, filas, x, y, w, (30 * mm, w - 30 * mm - 72 * mm, 34 * mm, 38 * mm))

    def _referencias(self, c, referencias, x, y, w) -> float:
        refs = _as_list(referencias)
        if not refs:
            return y
        filas = [['Tipo documento', 'Folio', 'Fecha', 'Razón de referencia']]
        for r in refs:
            tipo = r.get('TpoDocRef', '')
            tipo_nombre = TIPOS_DOCUMENTO.get(int(tipo) if str(tipo).isdigit() else tipo, tipo)
            razon = r.get('RazonRef', '')
            if r.get('CodRef'):
                razon = f"{CODIGOS_REFERENCIA.get(int(r['CodRef']), r['CodRef'])}: {razon}".strip(': ')
            filas.append([tipo_nombre, r.get('FolioRef', ''), fecha(r.get('FchRef', '')), razon])
        return self._tabla(c, filas, x, y, w, (60 * mm, 25 * mm, 22 * mm, w - 107 * mm))

    def _detalle(self, c, datos, x, y, w, decimales) -> float:
        tipo = int(datos['Encabezado']['IdDoc']['TipoDTE'])
        filas = [['Código', 'Descripción', 'Cantidad', 'Unidad', 'P. unitario', 'Dscto/Rcgo', 'Total']]
        for d in _as_list(datos.get('Detalle')):
            codigos = _as_list(d.get('CdgItem'))
            codigo = codigos[0].get('VlrCodigo', '') if codigos and isinstance(codigos[0], dict) else ''
            if tipo == 43 and d.get('TpoDocLiq'):
                codigo = TIPOS_LIQUIDADOS.get(int(d['TpoDocLiq']), d['TpoDocLiq'])
            descripcion = d.get('NmbItem', '')
            if d.get('DscItem'):
                descripcion += f"<br/><font size=7>{d['DscItem']}</font>"
            if d.get('IndExe') == '1' and tipo not in (34, 41, 110, 111, 112):
                descripcion += ' <font size=7>(EXENTO)</font>'
            ajuste = ''
            if d.get('DescuentoMonto'):
                ajuste = f"-{numero(d['DescuentoMonto'])}" + (f" ({numero(d['DescuentoPct'])}%)" if d.get('DescuentoPct') else '')
            if d.get('RecargoMonto'):
                ajuste = f"+{numero(d['RecargoMonto'])}" + (f" ({numero(d['RecargoPct'])}%)" if d.get('RecargoPct') else '')
            filas.append([codigo, descripcion, numero(d.get('QtyItem')), d.get('UnmdItem', ''),
                          numero(d.get('PrcItem'), decimales if d.get('PrcItem') and '.' in str(d.get('PrcItem')) else None),
                          ajuste, numero(d.get('MontoItem'), decimales)])
        return self._tabla(c, filas, x, y, w,
                           (22 * mm, w - 22 * mm - 115 * mm, 20 * mm, 15 * mm, 25 * mm, 25 * mm, 30 * mm),
                           numericas=(2, 4, 5, 6))

    def _descuentos_recargos(self, c, dr, x, y, w, decimales) -> float:
        lineas = _as_list(dr)
        if not lineas:
            return y
        filas = [['Descuentos y recargos globales', 'Valor']]
        for d in lineas:
            signo = '-' if d.get('TpoMov') == 'D' else '+'
            valor = f"{numero(d.get('ValorDR'))}%" if d.get('TpoValor') == '%' else numero(d.get('ValorDR'), decimales)
            glosa = d.get('GlosaDR') or ('Descuento' if signo == '-' else 'Recargo')
            filas.append([glosa, f'{signo}{valor}'])
        return self._tabla(c, filas, x, y, w, (w - 40 * mm, 40 * mm), numericas=(1,))

    def _comisiones(self, c, comisiones, x, y, w) -> float:
        lineas = _as_list(comisiones)
        if not lineas:
            return y
        filas = [['Comisiones y otros cargos', 'Neto', 'Exento', 'IVA']]
        for d in lineas:
            filas.append([d.get('Glosa', ''), numero(d.get('ValComNeto')), numero(d.get('ValComExe')),
                          numero(d.get('ValComIVA'))])
        return self._tabla(c, filas, x, y, w, (w - 90 * mm, 30 * mm, 30 * mm, 30 * mm), numericas=(1, 2, 3))

    def _tabla_totales(self, totales, otra_moneda, w, decimales) -> Table:
        moneda = totales.get('TpoMoneda')
        filas = []
        if moneda:
            filas.append(('Moneda', moneda))
        etiquetas = (('MntNeto', 'Neto'), ('MntExe', 'Exento'), ('IVA', f"IVA ({numero(totales.get('TasaIVA'))}%)"))
        for campo, etiqueta in etiquetas:
            if totales.get(campo) not in (None, ''):
                filas.append((etiqueta, numero(totales[campo], decimales)))
        for imp in _as_list(totales.get('ImptoReten')):
            filas.append((f"Impuesto {imp.get('TipoImp')} ({numero(imp.get('TasaImp'))}%)", numero(imp.get('MontoImp'))))
        comisiones = totales.get('Comisiones')
        if isinstance(comisiones, dict):
            filas.append(('Comisiones neto', numero(comisiones.get('ValComNeto'))))
            filas.append(('IVA comisiones', numero(comisiones.get('ValComIVA'))))
        filas.append(('TOTAL', numero(totales.get('MntTotal'), decimales)))
        for otra in _as_list(otra_moneda):
            filas.append((f"Total {otra.get('TpoMoneda', '')}", numero(otra.get('MntTotOtrMnda'))))
            if otra.get('TpoCambio'):
                filas.append(('Tipo de cambio', numero(otra.get('TpoCambio'))))
        tabla = Table([list(f) for f in filas], colWidths=(w * 0.55, w * 0.45))
        estilo = [
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ]
        total = next(i for i, f in enumerate(filas) if f[0] == 'TOTAL')
        estilo += [('FONT', (0, total), (-1, total), 'Helvetica-Bold', 10),
                   ('LINEABOVE', (0, total), (-1, total), 0.5, colors.black)]
        tabla.setStyle(TableStyle(estilo))
        return tabla

    def _timbre(self, c, timbre, x, y, w):
        if not timbre:
            return
        columnas = 12
        imagen = pdf417_image(timbre, columnas)
        proporcion = imagen.height / imagen.width
        # El SII exige entre 2 y 4 cm de alto y entre 5 y 9 cm de ancho.
        while w * proporcion > 40 * mm and columnas < 30:
            columnas += 2
            imagen = pdf417_image(timbre, columnas)
            proporcion = imagen.height / imagen.width
        alto = w * proporcion
        y_barra = y + 14 * mm
        c.drawImage(ImageReader(imagen), x, y_barra, w, alto)
        c.setFont('Helvetica-Bold', 8)
        centro = x + w / 2
        c.drawCentredString(centro, y + 10 * mm, 'Timbre Electrónico SII')
        anio = str(self.resolucion.get('fecha', ''))[:4]
        c.drawCentredString(centro, y + 6 * mm, f"Resolución {self.resolucion.get('numero', 0)} de {anio}")
        c.drawCentredString(centro, y + 2 * mm, f'Verifique documento: {self.web_verificacion}')

    def _acuse_recibo(self, c, x, y, w):
        h = 56 * mm
        c.setLineWidth(0.5)
        c.rect(x, y, w, h)
        c.setFont('Helvetica-Bold', 10)
        c.drawCentredString(x + w / 2, y + h - 5 * mm, 'Acuse de recibo')
        c.setFont('Helvetica-Bold', 8)
        cursor = y + h - 12 * mm
        for etiqueta in ('Nombre', 'R.U.T.', 'Fecha', 'Recinto', 'Firma'):
            c.drawString(x + 2 * mm, cursor, etiqueta)
            c.line(x + 18 * mm, cursor - 1, x + w - 2 * mm, cursor - 1)
            cursor -= 6 * mm
        estilo = ParagraphStyle('acuse', fontName='Helvetica', fontSize=6, leading=7, alignment=4)
        p = Paragraph(ACUSE_RECIBO, estilo)
        _, ph = p.wrap(w - 4 * mm, 20 * mm)
        p.drawOn(c, x + 2 * mm, y + 2 * mm)

    # ------------------------------------------------------------------
    # Utilidades de tablas
    # ------------------------------------------------------------------

    def _tabla_datos(self, c, filas, x, y, w, anchos, caja=False) -> float:
        estilo_valor = ParagraphStyle('valor', fontName='Helvetica', fontSize=8.5, leading=10)
        data = [[Paragraph(f'<b>{a}</b>', estilo_valor) if a else '', Paragraph(str(b), estilo_valor),
                 Paragraph(f'<b>{cc}</b>', estilo_valor) if cc else '', Paragraph(str(d), estilo_valor)]
                for a, b, cc, d in filas]
        tabla = Table(data, colWidths=anchos)
        estilo = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 1),
                  ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]
        if caja:
            estilo.append(('BOX', (0, 0), (-1, -1), 0.5, colors.black))
        tabla.setStyle(TableStyle(estilo))
        _, h = tabla.wrap(w, 300 * mm)
        tabla.drawOn(c, x, y - h)
        return y - h - 3 * mm

    def _tabla(self, c, filas, x, y, w, anchos, numericas=()) -> float:
        estilo_celda = ParagraphStyle('celda', fontName='Helvetica', fontSize=8, leading=9.5)
        data = [filas[0]] + [[Paragraph(str(v), estilo_celda) if i not in numericas else str(v)
                              for i, v in enumerate(f)] for f in filas[1:]]
        tabla = Table(data, colWidths=anchos, repeatRows=1)
        estilo = [
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.black),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]
        for col in numericas:
            estilo.append(('ALIGN', (col, 0), (col, -1), 'RIGHT'))
        tabla.setStyle(TableStyle(estilo))
        _, h = tabla.wrap(w, 300 * mm)
        if y - h < MARGEN + 60 * mm:
            # Tabla larga: se divide en páginas, dejando espacio para el pie.
            partes = tabla.split(w, y - MARGEN - 60 * mm)
            for i, parte in enumerate(partes):
                _, ph = parte.wrap(w, 300 * mm)
                parte.drawOn(c, x, y - ph)
                y -= ph
                if i < len(partes) - 1:
                    c.showPage()
                    y = letter[1] - MARGEN
            return y - 3 * mm
        tabla.drawOn(c, x, y - h)
        return y - h - 3 * mm
