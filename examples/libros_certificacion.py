#!/usr/bin/env python3
"""
Genera (y opcionalmente envía) los libros de ventas y compras del set de
pruebas de certificación del SII.

Según las "Instrucciones para la construcción de documentos tributarios
electrónicos con los datos del set de pruebas" del SII:

- Libro de ventas: con los documentos del set reportado para revisión, del
  período tributario de esos documentos. Tipo ESPECIAL, envío TOTAL, folio de
  notificación 1.
- Libro de compras: con los documentos del set de libro de compras, mismo
  período. Tipo ESPECIAL, envío TOTAL, folio de notificación 2.

Ejemplo:

    PYTHONPATH=src python examples/libros_certificacion.py \\
        --envio output/certificacion/set_5136564_..._envio.xml \\
        --compras examples/sets/libro_compras_5136566.yaml \\
        --empresa ../empresa_certificacion.yaml \\
        --pfx ~/Downloads/certificado.pfx --pass-file ~/.rypsystems-dte/pfx.pass

    ... --enviar --consultar
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from rypsystems_dte.firma import DigitalCertificate, XmlSigner  # noqa: E402
from rypsystems_dte.libro import LibroCompraVenta  # noqa: E402
from rypsystems_dte.sii.webservices.sii_endpoints import SiiEnvironment  # noqa: E402
from rypsystems_dte.sii.webservices.soap_service import SoapService  # noqa: E402
from rypsystems_dte.xml.schema import schema_errors  # noqa: E402


def fail(message: str) -> None:
    print(f'ERROR: {message}')
    sys.exit(1)


def miles(value) -> str:
    return f'{int(value):,}'.replace(',', '.') if value not in (None, False, '') else '-'


def imprimir_resumen(titulo: str, libro: LibroCompraVenta) -> None:
    print(f'\n{titulo}')
    print(f'  {"Tipo":>4} {"Docs":>4} {"Exento":>10} {"Neto":>12} {"IVA":>10} {"Total":>12}  Otros')
    for t in libro.get_resumen():
        otros = []
        if t.get('TotIVAUsoComun'):
            otros.append(f'IVA uso común {miles(t["TotIVAUsoComun"])} (FctProp {t["FctProp"]}, crédito {miles(t["TotCredIVAUsoComun"])})')
        for inr in t.get('TotIVANoRec', []):
            otros.append(f'IVA no recuperable cód. {inr["CodIVANoRec"]}: {miles(inr["TotMntIVANoRec"])}')
        if t.get('TotIVARetTotal'):
            otros.append(f'IVA retenido total {miles(t["TotIVARetTotal"])}')
        print(f'  {t["TpoDoc"]:>4} {t["TotDoc"]:>4} {miles(t["TotMntExe"]):>10} {miles(t["TotMntNeto"]):>12} '
              f'{miles(t["TotMntIVA"]):>10} {miles(t["TotMntTotal"]):>12}  {"; ".join(otros)}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--envio', required=True, type=Path, help='EnvioDTE del set aceptado por el SII')
    parser.add_argument('--compras', required=True, type=Path, help='YAML del set de libro de compras')
    parser.add_argument('--empresa', required=True, type=Path)
    parser.add_argument('--pfx', required=True, type=Path)
    parser.add_argument('--pass-file', required=True, type=Path)
    parser.add_argument('--proveedor-rut', default='78885550-8', help='RUT válido para los proveedores')
    parser.add_argument('--proveedor-razon', default='Proveedor de Prueba Limitada')
    parser.add_argument('--salida', type=Path, default=ROOT / 'output' / 'certificacion')
    parser.add_argument('--libros', default='ventas,compras',
                        help='Libros a generar y enviar, separados por coma (ventas, compras)')
    parser.add_argument('--enviar', action='store_true')
    parser.add_argument('--consultar', action='store_true')
    args = parser.parse_args()

    empresa = yaml.safe_load(args.empresa.expanduser().read_text(encoding='utf-8'))
    rut = empresa['emisor']['RUTEmisor']
    certificate = DigitalCertificate.from_file(args.pfx.expanduser(), args.pass_file.expanduser().read_text().strip())

    # Libro de ventas: los DTE tal como fueron enviados (y aceptados) al SII.
    envio = etree.fromstring(args.envio.read_bytes())
    dtes = envio.xpath('//*[local-name()="SetDTE"]/*[local-name()="DTE"]')
    if not dtes:
        fail(f'{args.envio} no contiene DTE.')
    ventas = LibroCompraVenta('VENTA')
    fechas = set()
    for dte in dtes:
        detalle = ventas.agregar_dte(etree.tostring(dte))
        fechas.add(detalle['FchDoc'][:7])
    if len(fechas) != 1:
        fail(f'Los documentos del set deben ser de un mismo período tributario: {sorted(fechas)}')
    periodo = fechas.pop()

    # Libro de compras: documentos del set, en el mismo período.
    set_compras = yaml.safe_load(args.compras.read_text(encoding='utf-8'))
    compras = LibroCompraVenta('COMPRA')
    for i, doc in enumerate(set_compras['documentos'], start=1):
        doc = dict(doc)
        if doc.pop('uso_comun', False):
            doc['FctProp'] = set_compras['factor_proporcionalidad_iva']
        compras.agregar({
            'TasaImp': 19,
            'FchDoc': f'{periodo}-{min(i, 28):02d}',
            'RUTDoc': args.proveedor_rut,
            'RznSoc': args.proveedor_razon,
            **doc,
        })

    comun = dict(certificate=certificate, rut_emisor=rut, periodo=periodo,
                 fecha_resolucion=str(empresa['fecha_resolucion']),
                 numero_resolucion=empresa.get('numero_resolucion', 0), tipo_libro='ESPECIAL', tipo_envio='TOTAL')
    elegidos = {nombre.strip() for nombre in args.libros.split(',')}
    libros = {}
    if 'ventas' in elegidos:
        libros['ventas'] = ventas.generar(folio_notificacion=1, **comun)
    if 'compras' in elegidos:
        libros['compras'] = compras.generar(folio_notificacion=set_compras.get('folio_notificacion', 2), **comun)

    print(f'Libros del período {periodo} - {rut}, envía {certificate.get_id()}')
    imprimir_resumen(f'LIBRO DE VENTAS ({len(dtes)} documentos del set)', ventas)
    imprimir_resumen(f'LIBRO DE COMPRAS (set {set_compras["numero_atencion"]})', compras)

    args.salida.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime('%Y%m%d%H%M%S')
    rutas = {}
    for nombre, xml in libros.items():
        errores = schema_errors(xml, 'LibroCV_v10.xsd')
        if errores:
            fail(f'El libro de {nombre} no cumple LibroCV_v10.xsd: {"; ".join(errores[:3])}')
        if not XmlSigner().is_valid_xml(xml):
            fail(f'La firma del libro de {nombre} no es válida.')
        rutas[nombre] = args.salida / f'libro_{nombre}_{periodo}_{marca}.xml'
        rutas[nombre].write_bytes(xml)
    print('\nOK: libros válidos según LibroCV_v10.xsd y firmados.')
    for nombre, ruta in rutas.items():
        print(f'  {nombre}: {ruta}')

    if not args.enviar:
        print('\nNo se enviaron al SII (use --enviar).')
        return

    service = SoapService(SiiEnvironment.CERTIFICACION)
    service.authenticate(certificate)
    for nombre, xml in libros.items():
        upload = service.upload_dte(certificate.get_id(), rut, xml)
        track_id = upload['track_id']
        rutas[nombre].with_suffix('.trackid.txt').write_text(f'{track_id}\n')
        print(f'\nLibro de {nombre} recibido por el SII. Track ID: {track_id}')
        if args.consultar:
            for intento in range(12):
                time.sleep(10)
                try:
                    estado = service.query_upload_status(rut, track_id)
                except Exception as e:  # p. ej. HTTP 503 temporal del SII
                    print(f'  [{intento + 1}] {e}')
                    continue
                print(f"  [{intento + 1}] {estado['estado']} - {estado['descripcion'] or estado['glosa']}")
                # Estados intermedios de libros: LRC (recibido), LSO (esquema correcto).
                if estado['estado'] not in ('REC', 'SOK', 'CRT', 'FOK', 'PDR', 'LRC', 'LSO', None):
                    break


if __name__ == '__main__':
    main()
