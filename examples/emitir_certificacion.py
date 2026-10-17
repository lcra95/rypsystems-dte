#!/usr/bin/env python3
"""
Emisión de un DTE en el ambiente de certificación del SII (maullin).

Genera el DTE timbrado (CAF) y firmado (certificado), lo incluye en un
EnvioDTE firmado, valida esquemas y firmas, guarda los XML y, solo si se
indica --enviar, lo sube al SII y consulta el estado del envío.

Ejemplo:

    PYTHONPATH=src python examples/emitir_certificacion.py \\
        --pfx ~/certificados/mi_certificado.pfx \\
        --pass-file ~/.rypsystems-dte/pfx.pass \\
        --caf ~/caf/33.xml \\
        --datos examples/datos/factura_33.yaml \\
        --fecha-resolucion 2026-10-17 \\
        --salida output/certificacion

    # Igual, pero enviando al SII y consultando el estado:
    ... --enviar --consultar

Los datos del documento se entregan completos (Encabezado con IdDoc,
Emisor, Receptor y Totales calculados, y Detalle), en el orden del esquema
del SII. El folio y el RUT del emisor se toman del CAF si no vienen.
"""

import argparse
import getpass
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from rypsystems_dte.dte import DocumentBag, DocumentEnvelope, DTEBuilder  # noqa: E402
from rypsystems_dte.firma import DigitalCertificate, XmlSigner  # noqa: E402
from rypsystems_dte.firma.ted import TEDValidator  # noqa: E402
from rypsystems_dte.identifier import Caf, CafValidator  # noqa: E402
from rypsystems_dte.sii.webservices.sii_endpoints import SiiEnvironment  # noqa: E402
from rypsystems_dte.sii.webservices.soap_service import SoapService  # noqa: E402
from rypsystems_dte.xml.schema import schema_errors  # noqa: E402


def load_data(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    if path.suffix.lower() in ('.yaml', '.yml'):
        import yaml
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    data.pop('Test', None)
    return data


def check(title: str, ok: bool, detail: str = '') -> None:
    print(f"  {'OK ' if ok else 'ERR'} {title}{(': ' + detail) if detail else ''}")
    if not ok:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pfx', required=True, type=Path, help='Certificado digital .pfx/.p12')
    parser.add_argument('--pass-file', type=Path, help='Archivo con la contraseña del certificado (si no, se pregunta)')
    parser.add_argument('--caf', required=True, type=Path, help='XML del CAF descargado desde el SII')
    parser.add_argument('--datos', required=True, type=Path, help='Datos del DTE (YAML o JSON)')
    parser.add_argument('--fecha-resolucion', required=True, help='Fecha de resolución (AAAA-MM-DD)')
    parser.add_argument('--numero-resolucion', type=int, default=0, help='Número de resolución (0 en certificación)')
    parser.add_argument('--folio', type=int, help='Folio a usar (por defecto el de los datos o el primero del CAF)')
    parser.add_argument('--salida', type=Path, default=ROOT / 'output' / 'certificacion', help='Directorio de salida')
    parser.add_argument('--produccion', action='store_true', help='Usar el ambiente de producción (palena)')
    parser.add_argument('--enviar', action='store_true', help='Subir el EnvioDTE al SII')
    parser.add_argument('--consultar', action='store_true', help='Consultar el estado del envío después de subirlo')
    args = parser.parse_args()

    password = args.pass_file.expanduser().read_text().strip() if args.pass_file else getpass.getpass('Contraseña del certificado: ')

    print('1. Certificado digital')
    certificate = DigitalCertificate.from_file(args.pfx.expanduser(), password)
    check('Certificado cargado', certificate.has_private_key(), f'{certificate.get_id()} {certificate.get_name()}')
    check('Certificado vigente', certificate.is_active(), f'hasta {certificate.get_to()}')

    print('2. CAF')
    caf = Caf.from_file(args.caf.expanduser())
    CafValidator().validate(caf)
    ambiente = caf.get_ambiente()
    check('CAF válido', True, f'{caf.get_id()} emisor {caf.get_emisor()["rut"]} ambiente {ambiente.name if ambiente else "FALSO (IDK 666)"}')
    check('CAF vigente', caf.vigente(), f'vence {caf.get_fecha_vencimiento() or "nunca"}')
    if args.produccion and ambiente is not None and ambiente.name != 'PRODUCCION':
        check('CAF de producción', False, 'el CAF es de certificación')

    print('3. Documento')
    data = load_data(args.datos)
    id_doc = data.setdefault('Encabezado', {}).setdefault('IdDoc', {})
    id_doc['TipoDTE'] = caf.get_tipo_documento()
    if args.folio:
        id_doc['Folio'] = args.folio
    id_doc.setdefault('Folio', caf.get_folio_desde())
    id_doc.setdefault('FchEmis', datetime.now().strftime('%Y-%m-%d'))
    emisor = data['Encabezado'].setdefault('Emisor', {})
    emisor.setdefault('RUTEmisor', caf.get_emisor()['rut'])
    check('Emisor coincide con el CAF', emisor['RUTEmisor'] == caf.get_emisor()['rut'],
          f'{emisor["RUTEmisor"]} / CAF {caf.get_emisor()["rut"]}')

    bag = DocumentBag(caf.get_tipo_documento(), data)
    bag.set_caf(caf)
    bag.set_certificate(certificate)
    DTEBuilder().build(bag)
    dte = bag.get_xml()

    errors = schema_errors(dte, 'DTE_v10.xsd')
    check('DTE cumple DTE_v10.xsd', not errors, '; '.join(errors[:3]))
    check('Timbre (TED) válido', TEDValidator.verify_ted_signature(dte, caf))
    check('Firma del DTE válida', XmlSigner().is_valid_xml(dte), bag.get_id())

    print('4. Sobre EnvioDTE')
    envelope = DocumentEnvelope(certificate, args.fecha_resolucion, args.numero_resolucion)
    envelope.add_document(dte)
    envio = envelope.build()
    errors = schema_errors(envio, 'EnvioDTE_v10.xsd')
    check('EnvioDTE cumple EnvioDTE_v10.xsd', not errors, '; '.join(errors[:3]))
    results = XmlSigner().validate_xml(envio)
    check('Firmas del EnvioDTE válidas', all(r.is_valid for r in results),
          ', '.join(f'{r.reference}: {"ok" if r.is_valid else r.error}' for r in results))

    args.salida.mkdir(parents=True, exist_ok=True)
    nombre = f'{emisor["RUTEmisor"]}_T{caf.get_tipo_documento()}F{id_doc["Folio"]}'
    (args.salida / f'{nombre}_dte.xml').write_bytes(dte)
    (args.salida / f'{nombre}_envio.xml').write_bytes(envio)
    print(f'  XML guardados en {args.salida}/{nombre}_*.xml')

    if not args.enviar:
        print('\nNo se envió al SII (use --enviar para subir el EnvioDTE).')
        return

    print('5. Envío al SII')
    if caf.es_falso():
        check('CAF real', False, 'no se puede enviar al SII un documento timbrado con un CAF falso')
    environment = SiiEnvironment.PRODUCCION if args.produccion else SiiEnvironment.CERTIFICACION
    service = SoapService(environment)
    service.authenticate(certificate)
    check('Autenticado en el SII', service.is_authenticated(), environment.value)
    upload = service.upload_dte(certificate.get_id(), emisor['RUTEmisor'], envio)
    track_id = upload['track_id']
    check('EnvioDTE recibido por el SII', upload['success'], f'Track ID {track_id}')
    (args.salida / f'{nombre}_trackid.txt').write_text(f'{track_id}\n')

    if args.consultar:
        print('6. Estado del envío')
        for intento in range(10):
            time.sleep(10)
            estado = service.query_upload_status(emisor['RUTEmisor'], track_id)
            print(f"  [{intento + 1}] {estado['estado']} - {estado['descripcion'] or estado['glosa']} "
                  f"(aceptados {estado['aceptados']}, rechazados {estado['rechazados']}, reparos {estado['reparos']})")
            if estado['estado'] in ('EPR', 'RSC', 'RFR', 'RCT') or (estado['estado'] or '').startswith('-'):
                break


if __name__ == '__main__':
    main()
