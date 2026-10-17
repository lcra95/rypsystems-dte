#!/usr/bin/env python3
"""
Genera (y opcionalmente envía) el libro de guías del set de pruebas de
certificación del SII, con las guías del set de guía de despacho aceptado.

Ejemplo:

    PYTHONPATH=src python examples/libro_guias_certificacion.py \\
        --envio output/certificacion/set_5136567_..._envio.xml \\
        --libro examples/sets/libro_guias_5136568.yaml \\
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
from rypsystems_dte.libro import LibroGuia  # noqa: E402
from rypsystems_dte.sii.webservices.sii_endpoints import SiiEnvironment  # noqa: E402
from rypsystems_dte.sii.webservices.soap_service import SoapService  # noqa: E402
from rypsystems_dte.xml.schema import schema_errors  # noqa: E402


def fail(message: str) -> None:
    print(f'ERROR: {message}')
    sys.exit(1)


def miles(value) -> str:
    return f'{int(value):,}'.replace(',', '.') if value not in (None, False, '') else '-'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--envio', required=True, type=Path, help='EnvioDTE del set de guías aceptado por el SII')
    parser.add_argument('--libro', required=True, type=Path, help='YAML del set de libro de guías')
    parser.add_argument('--empresa', required=True, type=Path)
    parser.add_argument('--pfx', required=True, type=Path)
    parser.add_argument('--pass-file', required=True, type=Path)
    parser.add_argument('--salida', type=Path, default=ROOT / 'output' / 'certificacion')
    parser.add_argument('--enviar', action='store_true')
    parser.add_argument('--consultar', action='store_true')
    args = parser.parse_args()

    empresa = yaml.safe_load(args.empresa.expanduser().read_text(encoding='utf-8'))
    rut = empresa['emisor']['RUTEmisor']
    certificate = DigitalCertificate.from_file(args.pfx.expanduser(), args.pass_file.expanduser().read_text().strip())
    set_libro = yaml.safe_load(args.libro.read_text(encoding='utf-8'))
    casos = set_libro.get('casos') or {}

    envio = etree.fromstring(args.envio.read_bytes())
    dtes = envio.xpath('//*[local-name()="SetDTE"]/*[local-name()="DTE"]')
    if not dtes:
        fail(f'{args.envio} no contiene guías.')

    libro = LibroGuia()
    periodos = set()
    for numero, dte in enumerate(dtes, start=1):
        extra = {}
        caso = casos.get(numero) or {}
        if caso.get('anulada'):
            extra['Anulado'] = 2
        if caso.get('facturada'):
            fecha = dte.xpath('string(.//*[local-name()="IdDoc"]/*[local-name()="FchEmis"])')
            extra.update({'FchDocRef': fecha, **caso['facturada']})
        d = libro.agregar_dte(etree.tostring(dte), **extra)
        periodos.add(d['FchDoc'][:7])
        estado = 'anulada' if d['Anulado'] else ('facturada' if d['TpoDocRef'] else '')
        print(f'  Guía {d["Folio"]:>3}  traslado {d["TpoOper"]}  {d["RUTDoc"]:<11} neto {miles(d["MntNeto"]):>10} '
              f'IVA {miles(d["IVA"]):>9} total {miles(d["MntTotal"]):>10}  {estado}')
    if len(periodos) != 1:
        fail(f'Las guías deben ser de un mismo período: {sorted(periodos)}')
    periodo = periodos.pop()

    resumen = libro.get_resumen()
    print(f'\nResumen {periodo}: guías de venta {resumen["TotGuiaVenta"]} por {miles(resumen["TotMntGuiaVta"])}, '
          f'anuladas {resumen["TotGuiaAnulada"] or 0}, traslados '
          + ', '.join(f'tipo {t["TpoTraslado"]}: {t["CantGuia"]}' for t in (resumen['TotTraslado'] or [])))

    xml = libro.generar(certificate, rut, periodo, str(empresa['fecha_resolucion']),
                        empresa.get('numero_resolucion', 0), set_libro.get('folio_notificacion', 3))
    errores = schema_errors(xml, 'LibroGuia_v10.xsd')
    if errores:
        fail(f'El libro no cumple LibroGuia_v10.xsd: {"; ".join(errores[:3])}')
    if not XmlSigner().is_valid_xml(xml):
        fail('La firma del libro no es válida.')
    args.salida.mkdir(parents=True, exist_ok=True)
    ruta = args.salida / f'libro_guias_{periodo}_{datetime.now().strftime("%Y%m%d%H%M%S")}.xml'
    ruta.write_bytes(xml)
    print(f'\nOK: libro válido según LibroGuia_v10.xsd y firmado: {ruta}')

    if not args.enviar:
        print('No se envió al SII (use --enviar).')
        return

    service = SoapService(SiiEnvironment.CERTIFICACION)
    service.authenticate(certificate)
    track_id = service.upload_dte(certificate.get_id(), rut, xml)['track_id']
    ruta.with_suffix('.trackid.txt').write_text(f'{track_id}\n')
    print(f'Libro de guías recibido por el SII. Track ID: {track_id}')
    if args.consultar:
        for intento in range(12):
            time.sleep(10)
            try:
                estado = service.query_upload_status(rut, track_id)
            except Exception as e:  # p. ej. HTTP 503 temporal del SII
                print(f'  [{intento + 1}] {e}')
                continue
            print(f"  [{intento + 1}] {estado['estado']} - {estado['descripcion'] or estado['glosa']}")
            if estado['estado'] not in ('REC', 'SOK', 'LRC', 'LSO', None):
                break


if __name__ == '__main__':
    main()
