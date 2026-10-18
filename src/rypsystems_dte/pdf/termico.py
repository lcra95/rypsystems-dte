"""
Representación impresa de DTE en papel térmico (rollo de 80 mm).

Pensado para boletas en el punto de venta, aunque sirve para cualquier DTE
(facturas con su copia cedible incluida). Cada documento es una página del
ancho del rollo y del alto de su contenido, en blanco y negro.

Contenido: emisor, recuadro con RUT, tipo y folio, unidad del SII, fecha y
receptor (si está identificado), referencias, detalle, descuentos o recargos
globales, totales (en boletas el total con el IVA incluido) y el timbre
electrónico en PDF417 con la resolución y "Verifique documento".

Desde el 1 de enero de 2026 el SII no exige imprimir el timbre en la
representación impresa de la boleta (sigue siendo obligatorio en el XML), por
lo que en boletas se puede omitir con `timbre_boletas=False`.
"""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from lxml import etree
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from .dte_pdf import (
    ACUSE_RECIBO,
    BOLETAS,
    CODIGOS_REFERENCIA,
    FORMAS_PAGO,
    SIN_ACUSE_RECIBO,
    TIPOS_DOCUMENTO,
    DtePdf,
    _as_list,
    _local,
    _to_dict,
    fecha,
    numero,
    pdf417_image,
    rut,
    ted_pdf417,
)

ANCHO_PAPEL = 80 * mm
MARGEN_X = 4 * mm
MARGEN_Y = 5 * mm
ANCHO_TIMBRE = 62 * mm  # El SII exige entre 5 y 9 cm de ancho y entre 2 y 4 cm de alto.


def _estilo(nombre: str, size: float = 7.5, bold: bool = False, align: int = 0, leading: float = None):
    return ParagraphStyle(nombre, fontName='Helvetica-Bold' if bold else 'Helvetica', fontSize=size,
                          leading=leading or size * 1.25, alignment=align)


NORMAL = _estilo('normal')
CENTRO = _estilo('centro', align=1)
TITULO = _estilo('titulo', 10, True, 1)
NEGRITA = _estilo('negrita', bold=True)
PEQUENO = _estilo('pequeno', 6.5, align=4)


def _esc(value: Any) -> str:
    return str(value if value not in (None, False) else '').replace('&', '&amp;').replace('<', '&lt;')


class DtePdfTermico(DtePdf):
    """
    Representación impresa en rollo térmico de 80 mm.

    Ejemplo:
        pdf = DtePdfTermico(resolucion={'fecha': '2026-10-17', 'numero': 0})
        contenido = pdf.render(xml_boleta)
    """

    def __init__(self, resolucion: Dict[str, Any], logo: Optional[Union[str, Path]] = None,
                 web_verificacion: str = 'www.sii.cl', sucursal_sii: Optional[str] = None,
                 ancho_papel: float = ANCHO_PAPEL, timbre_boletas: bool = True):
        """
        Args:
            ancho_papel: Ancho del rollo (por defecto 80 mm; el área impresa es 8 mm menor)
            timbre_boletas: Imprimir el timbre PDF417 en las boletas (39 y 41)
        """
        super().__init__(resolucion, logo, web_verificacion, sucursal_sii)
        self.ancho_papel = ancho_papel
        self.ancho = ancho_papel - 2 * MARGEN_X
        self.timbre_boletas = timbre_boletas

    def _render_dtes(self, dtes: List[etree._Element], cedible: bool) -> bytes:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(self.ancho_papel, 100 * mm))
        c.setTitle('Documentos tributarios electrónicos')
        for dte in dtes:
            documento = next(child for child in dte if isinstance(child.tag, str) and _local(child) != 'Signature')
            datos = _to_dict(documento)
            tipo = int(datos['Encabezado']['IdDoc']['TipoDTE'])
            timbre = ted_pdf417(dte) if self.timbre_boletas or tipo not in BOLETAS else None
            self._dibujar(c, self._contenido(datos, timbre, None))
            if cedible and tipo not in SIN_ACUSE_RECIBO:
                copia = 'CEDIBLE CON SU FACTURA' if tipo == 52 else 'CEDIBLE'
                self._dibujar(c, self._contenido(datos, timbre, copia))
        c.save()
        return buffer.getvalue()

    def _dibujar(self, c: canvas.Canvas, bloques: list) -> None:
        """Una página del alto exacto del contenido."""
        medidas = [b.wrap(self.ancho, 2000 * mm) for b in bloques]
        alto = sum(h for _, h in medidas) + 2 * MARGEN_Y
        c.setPageSize((self.ancho_papel, alto))
        y = alto - MARGEN_Y
        for bloque, (w, h) in zip(bloques, medidas):
            y -= h
            # Centrado horizontal (recuadro del folio, timbre y logo).
            bloque.drawOn(c, MARGEN_X + max(0, self.ancho - w) / 2, y)
        c.showPage()

    # ------------------------------------------------------------------

    def _linea(self) -> Table:
        tabla = Table([['']], colWidths=[self.ancho], rowHeights=[2 * mm])
        tabla.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.black, None, (1, 1))]))
        return tabla

    def _filas(self, filas, anchos=None, negrita_ultima=False, derecha=(1,)) -> Table:
        anchos = anchos or (self.ancho * 0.55, self.ancho * 0.45)
        tabla = Table([[Paragraph(_esc(a), NORMAL) if not isinstance(a, Paragraph) else a,
                        Paragraph(_esc(b), _estilo('d', align=2)) if 1 in derecha else Paragraph(_esc(b), NORMAL)]
                       for a, b in filas], colWidths=anchos)
        estilo = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                  ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                  ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5)]
        tabla.setStyle(TableStyle(estilo))
        return tabla

    def _contenido(self, datos: Dict[str, Any], timbre: Optional[bytes], copia: Optional[str]) -> list:
        enc = datos['Encabezado']
        id_doc, emisor, receptor = enc['IdDoc'], enc.get('Emisor', {}), enc.get('Receptor') or {}
        if not isinstance(receptor, dict):
            receptor = {}
        tipo = int(id_doc['TipoDTE'])
        decimales = 2 if tipo in (110, 111, 112) else None
        bloques: list = []

        # Emisor.
        if self.logo and self.logo.is_file():
            logo = Image(str(self.logo))
            escala = min(50 * mm / logo.imageWidth, 20 * mm / logo.imageHeight)
            logo.drawWidth, logo.drawHeight = logo.imageWidth * escala, logo.imageHeight * escala
            bloques += [logo, Spacer(1, 2 * mm)]
        bloques.append(Paragraph(_esc(emisor.get('RznSoc') or emisor.get('RznSocEmisor')), TITULO))
        giro = emisor.get('GiroEmis') or emisor.get('GiroEmisor')
        if giro:
            bloques.append(Paragraph(_esc(giro), CENTRO))
        direccion = ', '.join(v for v in (emisor.get('DirOrigen'), emisor.get('CmnaOrigen'),
                                          emisor.get('CiudadOrigen')) if v)
        if direccion:
            bloques.append(Paragraph(_esc(direccion), CENTRO))
        contacto = ' - '.join(v for v in (emisor.get('Telefono'), emisor.get('CorreoEmisor')) if v)
        if contacto:
            bloques.append(Paragraph(_esc(contacto), CENTRO))
        bloques.append(Spacer(1, 2 * mm))

        # Recuadro RUT / tipo / folio.
        recuadro = Table([[Paragraph(t, _estilo('folio', 9.5, True, 1))] for t in (
            f'R.U.T.: {rut(emisor.get("RUTEmisor", ""))}', TIPOS_DOCUMENTO.get(tipo, f'DOCUMENTO {tipo}'),
            f'N° {id_doc.get("Folio")}')], colWidths=[self.ancho - 6 * mm])
        recuadro.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black),
                                      ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
        bloques.append(recuadro)
        bloques.append(Paragraph(f'<b>S.I.I. - {_esc(self._direccion_regional(emisor.get("CmnaOrigen", "")))}</b>',
                                 _estilo('sii', 8, align=1, leading=12)))
        bloques.append(Spacer(1, 1.5 * mm))

        # Fecha y receptor.
        filas = [('Fecha emisión', fecha(id_doc.get('FchEmis', '')))]
        if id_doc.get('FchVenc'):
            filas.append(('Vencimiento', fecha(id_doc['FchVenc'])))
        if id_doc.get('FmaPago'):
            filas.append(('Forma de pago', FORMAS_PAGO.get(int(id_doc['FmaPago']), id_doc['FmaPago'])))
        bloques.append(self._filas(filas))
        if receptor.get('RznSocRecep'):
            bloques.append(self._linea())
            filas = [(Paragraph('<b>Señor(es)</b>', NORMAL), receptor['RznSocRecep']),
                     (Paragraph('<b>R.U.T.</b>', NORMAL), rut(receptor.get('RUTRecep', '')))]
            if receptor.get('GiroRecep'):
                filas.append((Paragraph('<b>Giro</b>', NORMAL), receptor['GiroRecep']))
            direccion = ', '.join(v for v in (receptor.get('DirRecep'), receptor.get('CmnaRecep')) if v)
            if direccion:
                filas.append((Paragraph('<b>Dirección</b>', NORMAL), direccion))
            bloques.append(self._filas(filas, (18 * mm, self.ancho - 18 * mm), derecha=()))

        # Referencias.
        refs = _as_list(datos.get('Referencia'))
        if refs:
            bloques.append(self._linea())
            for r in refs:
                tipo_ref = r.get('TpoDocRef')
                texto = []
                if tipo_ref:
                    nombre = TIPOS_DOCUMENTO.get(int(tipo_ref) if str(tipo_ref).isdigit() else tipo_ref, tipo_ref)
                    texto.append(f'{nombre} N° {r.get("FolioRef", "")}'
                                 + (f' del {fecha(r["FchRef"])}' if r.get('FchRef') else ''))
                razon = r.get('RazonRef', '')
                if r.get('CodRef'):
                    codigo = int(r['CodRef']) if str(r['CodRef']).isdigit() else r['CodRef']
                    razon = f'{CODIGOS_REFERENCIA.get(codigo, codigo)}: {razon}'.strip(': ')
                if razon:
                    texto.append(razon)
                bloques.append(Paragraph('<b>Ref.:</b> ' + _esc(' - '.join(texto)), NORMAL))

        # Detalle: nombre del ítem y, debajo, cantidad x precio = monto.
        bloques.append(self._linea())
        for d in _as_list(datos.get('Detalle')):
            nombre = _esc(d.get('NmbItem', ''))
            if d.get('IndExe') == '1' and tipo not in (34, 41, 110, 111, 112):
                nombre += ' (EXENTO)'
            bloques.append(Paragraph(f'<b>{nombre}</b>', NORMAL))
            if d.get('DscItem'):
                bloques.append(Paragraph(_esc(d['DscItem']), _estilo('dsc', 6.5)))
            cantidad = ''
            if d.get('QtyItem'):
                precio = numero(d.get('PrcItem'), decimales if '.' in str(d.get('PrcItem', '')) else None)
                cantidad = f"{numero(d['QtyItem'])} {d.get('UnmdItem', '')} x {precio}".replace('  ', ' ')
            bloques.append(self._filas([(cantidad, numero(d.get('MontoItem'), decimales))]))
            if d.get('DescuentoMonto'):
                pct = f" {numero(d['DescuentoPct'])}%" if d.get('DescuentoPct') else ''
                bloques.append(self._filas([(f'  Descuento{pct}', f"-{numero(d['DescuentoMonto'])}")]))
            if d.get('RecargoMonto'):
                pct = f" {numero(d['RecargoPct'])}%" if d.get('RecargoPct') else ''
                bloques.append(self._filas([(f'  Recargo{pct}', f"+{numero(d['RecargoMonto'])}")]))

        globales = _as_list(datos.get('DscRcgGlobal'))
        if globales:
            bloques.append(self._linea())
            for g in globales:
                signo = '-' if g.get('TpoMov') == 'D' else '+'
                valor = f"{signo}{numero(g.get('ValorDR'))}{'%' if g.get('TpoValor') == '%' else ''}"
                bloques.append(self._filas([(g.get('GlosaDR') or ('Descuento' if signo == '-' else 'Recargo'), valor)]))

        # Totales.
        bloques.append(self._linea())
        bloques.append(self._totales(enc.get('Totales', {}), tipo, decimales))

        # Timbre y leyendas.
        bloques.append(Spacer(1, 3 * mm))
        anio = str(self.resolucion.get('fecha', ''))[:4]
        if timbre:
            bloques += [self._imagen_timbre(timbre), Spacer(1, 1.5 * mm),
                        Paragraph('<b>Timbre Electrónico SII</b>', CENTRO)]
        bloques.append(Paragraph(f"Res. {self.resolucion.get('numero', 0)} de {anio} - "
                                 f'Verifique documento: {_esc(self.web_verificacion)}', CENTRO))

        if copia:
            bloques += [Spacer(1, 3 * mm), self._linea(), Paragraph('<b>ACUSE DE RECIBO</b>', CENTRO)]
            bloques.append(self._filas([(f'{e}:', '_' * 30) for e in ('Nombre', 'R.U.T.', 'Fecha', 'Recinto', 'Firma')],
                                       (14 * mm, self.ancho - 14 * mm)))
            bloques += [Spacer(1, 1 * mm), Paragraph(ACUSE_RECIBO, PEQUENO), Spacer(1, 2 * mm),
                        Paragraph(f'<b>{copia}</b>', _estilo('copia', 11, True, 1))]
        return bloques

    def _totales(self, totales: Dict[str, Any], tipo: int, decimales) -> Table:
        filas = []
        if totales.get('TpoMoneda'):
            filas.append(('Moneda', totales['TpoMoneda']))
        if tipo in BOLETAS:
            if totales.get('MntExe'):
                filas.append(('Exento', numero(totales['MntExe'])))
        else:
            if totales.get('MntNeto'):
                filas.append(('Neto', numero(totales['MntNeto'], decimales)))
            if totales.get('MntExe'):
                filas.append(('Exento', numero(totales['MntExe'], decimales)))
            if totales.get('IVA'):
                filas.append((f"IVA ({numero(totales.get('TasaIVA'))}%)", numero(totales['IVA'])))
            for imp in _as_list(totales.get('ImptoReten')):
                filas.append((f"Impuesto {imp.get('TipoImp')} ({numero(imp.get('TasaImp'))}%)",
                              numero(imp.get('MontoImp'))))
        filas.append(('TOTAL', numero(totales.get('MntTotal'), decimales)))
        if tipo in BOLETAS and totales.get('IVA'):
            filas.append(('IVA incluido', numero(totales['IVA'])))
        celdas = []
        for etiqueta, valor in filas:
            if etiqueta == 'TOTAL':  # Total destacado.
                celdas.append([Paragraph('<b>TOTAL</b>', _estilo('tt', 10)),
                               Paragraph(f'<b>{_esc(valor)}</b>', _estilo('tv', 10, align=2))])
            else:
                celdas.append([Paragraph(_esc(etiqueta), NORMAL), Paragraph(_esc(valor), _estilo('t', align=2))])
        tabla = Table(celdas, colWidths=(self.ancho * 0.55, self.ancho * 0.45))
        tabla.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
        ]))
        return tabla

    def _imagen_timbre(self, timbre: bytes) -> Image:
        columnas = 10
        imagen = pdf417_image(timbre, columnas)
        while ANCHO_TIMBRE * imagen.height / imagen.width > 40 * mm and columnas < 30:
            columnas += 2
            imagen = pdf417_image(timbre, columnas)
        png = io.BytesIO()
        imagen.save(png, format='PNG')
        png.seek(0)
        return Image(png, width=ANCHO_TIMBRE, height=ANCHO_TIMBRE * imagen.height / imagen.width)
