#!/usr/bin/env python3
"""
Genera (y opcionalmente envía) un set de pruebas de certificación del SII.

Lee los casos del set (examples/sets/*.yaml) y los datos de la empresa
(emisor, receptor, resolución y CAF), emite cada documento con folios
correlativos de los CAF, encadena las referencias entre casos, agrega a cada
documento la referencia al set (TpoDocRef SET, RazonRef "CASO ..."), valida
esquemas, timbres y firmas, y arma un único EnvioDTE firmado.

Ejemplo:

    PYTHONPATH=src python examples/set_pruebas.py \\
        --set examples/sets/set_basico_5136564.yaml \\
        --empresa ../empresa_certificacion.yaml \\
        --pfx ~/Downloads/certificado.pfx --pass-file ~/.rypsystems-dte/pfx.pass

    # Revisados los montos, enviar al SII y consultar el estado:
    ... --enviar --consultar

Los folios usados se registran en <salida>/folios_<RUT>.json después de cada
envío, y por defecto se usa el siguiente folio libre de cada tipo. Para
forzar el primer folio de un tipo use --folio 33=5.
"""

import argparse
import copy
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from rypsystems_dte.dte import DocumentBag, DocumentEnvelope, DTEBuilder  # noqa: E402
from rypsystems_dte.firma import DigitalCertificate, XmlSigner  # noqa: E402
from rypsystems_dte.firma.ted import TEDValidator  # noqa: E402
from rypsystems_dte.identifier import Caf, CafValidator  # noqa: E402
from rypsystems_dte.sii.webservices.sii_endpoints import SiiEnvironment  # noqa: E402
from rypsystems_dte.sii.webservices.soap_service import SoapService  # noqa: E402
from rypsystems_dte.xml.schema import schema_errors  # noqa: E402

NOMBRES = {33: 'Factura', 34: 'Factura exenta', 46: 'Factura compra', 52: 'Guía despacho',
           56: 'Nota débito', 61: 'Nota crédito', 110: 'Factura export.', 111: 'ND export.',
           112: 'NC export.'}


def fail(message: str) -> None:
    print(f'ERROR: {message}')
    sys.exit(1)


def miles(value) -> str:
    if value in (None, False, ''):
        return '-'
    if isinstance(value, float) and not value.is_integer():
        return f'{value:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return f'{int(value):,}'.replace(',', '.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--set', required=True, type=Path, help='YAML con los casos del set')
    parser.add_argument('--empresa', required=True, type=Path, help='YAML con emisor, receptor, resolución y CAF')
    parser.add_argument('--pfx', required=True, type=Path)
    parser.add_argument('--pass-file', required=True, type=Path)
    parser.add_argument('--folio', action='append', default=[], help='Primer folio por tipo, ej: 33=5')
    parser.add_argument('--salida', type=Path, default=ROOT / 'output' / 'certificacion')
    parser.add_argument('--enviar', action='store_true', help='Subir el EnvioDTE al SII (maullin)')
    parser.add_argument('--consultar', action='store_true', help='Consultar el estado del envío')
    args = parser.parse_args()

    set_data = yaml.safe_load(args.set.read_text(encoding='utf-8'))
    empresa = yaml.safe_load(args.empresa.expanduser().read_text(encoding='utf-8'))
    pendientes = [k for k, v in {**empresa['emisor'], 'fecha_resolucion': empresa['fecha_resolucion']}.items()
                  if str(v).strip().upper() == 'COMPLETAR']
    if pendientes:
        fail(f'Complete en {args.empresa} los datos: {", ".join(pendientes)}')

    certificate = DigitalCertificate.from_file(args.pfx.expanduser(), args.pass_file.expanduser().read_text().strip())
    if not certificate.is_active():
        fail(f'El certificado de {certificate.get_id()} no está vigente.')

    # CAF y folios por tipo de documento. El registro local guarda el último
    # folio enviado al SII por tipo, para no repetir folios ya usados.
    tipos = sorted({c['tipo'] for c in set_data['casos']})
    cafs, folios = {}, {}
    inicio = {int(k): int(v) for k, v in (f.split('=') for f in args.folio)}
    registro_path = args.salida / f'folios_{empresa["emisor"]["RUTEmisor"]}.json'
    registro = {int(k): int(v) for k, v in json.loads(registro_path.read_text()).items()} \
        if registro_path.is_file() else {}
    for tipo in tipos:
        path = (empresa.get('caf') or {}).get(tipo)
        if not path or not Path(path).expanduser().is_file():
            fail(f'Falta el CAF del tipo {tipo} en {args.empresa}.')
        caf = CafValidator().validate(Caf.from_file(Path(path).expanduser()))
        if caf.get_tipo_documento() != tipo:
            fail(f'El CAF {path} es del tipo {caf.get_tipo_documento()}, no {tipo}.')
        if caf.get_emisor()['rut'] != empresa['emisor']['RUTEmisor']:
            fail(f'El CAF {path} es de {caf.get_emisor()["rut"]}, no de {empresa["emisor"]["RUTEmisor"]}.')
        if caf.es_falso():
            print(f'AVISO: el CAF del tipo {tipo} es falso (IDK 666); no se podrá enviar al SII.')
        cafs[tipo] = caf
        folios[tipo] = inicio.get(tipo, max(caf.get_folio_desde(), registro.get(tipo, 0) + 1))

    hoy = datetime.now().strftime('%Y-%m-%d')
    emitidos = {}  # caso -> datos del documento emitido
    # "Utilice RUT distintos para las distintas facturas": los documentos
    # originales rotan entre los receptores; las notas usan el del referenciado.
    receptores = empresa.get('receptores') or [empresa['receptor']]
    siguiente_receptor = 0
    envelope = DocumentEnvelope(certificate, empresa['fecha_resolucion'], empresa.get('numero_resolucion', 0))

    print(f'Set {set_data["numero_atencion"]} - emisor {empresa["emisor"]["RUTEmisor"]}, '
          f'envía {certificate.get_id()} {certificate.get_name()}\n')
    print(f'{"Caso":<12} {"Documento":<15} {"Folio":>6} {"Neto":>12} {"Exento":>10} {"IVA":>11} {"Total":>12}  '
          f'{"Receptor":<11} Referencia')

    for caso in set_data['casos']:
        tipo = caso['tipo']
        folio = folios[tipo]
        if not cafs[tipo].en_rango(folio):
            fail(f'No quedan folios del tipo {tipo} en el CAF {cafs[tipo].get_id()}.')
        folios[tipo] += 1

        detalle = caso['detalle']
        ref = caso.get('referencia')
        if detalle == 'copiar':
            detalle = copy.deepcopy(emitidos[ref['caso']]['detalle'])

        referencias = [{
            'TpoDocRef': 'SET', 'FolioRef': folio, 'FchRef': hoy, 'RazonRef': f'CASO {caso["caso"]}',
        }]
        # Otras referencias (DUS, AWB, MIC...) a partir de la línea 2.
        referencias += copy.deepcopy(caso.get('referencias_extra') or [])
        texto_ref = ''
        if ref:
            original = emitidos[ref['caso']]
            receptor = dict(original['receptor'])
        else:
            receptor = dict(receptores[siguiente_receptor % len(receptores)])
            siguiente_receptor += 1
        if ref:
            referencias.append({
                'TpoDocRef': original['tipo'], 'FolioRef': original['folio'], 'FchRef': original['fecha'],
                'CodRef': ref['CodRef'], 'RazonRef': ref['RazonRef'],
            })
            texto_ref = f'{NOMBRES[original["tipo"]]} {original["folio"]} (CodRef {ref["CodRef"]})'

        encabezado = copy.deepcopy(caso.get('encabezado') or {})
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': tipo, 'Folio': folio, 'FchEmis': hoy, **encabezado.pop('IdDoc', {})},
                'Emisor': dict(empresa['emisor']),
                'Receptor': receptor,
                **encabezado,
            },
            'Detalle': copy.deepcopy(detalle),
            'DscRcgGlobal': copy.deepcopy(caso.get('descuentos_recargos') or False),
            'Referencia': referencias,
        }

        bag = DocumentBag(tipo, datos)
        bag.set_caf(cafs[tipo])
        bag.set_certificate(certificate)
        DTEBuilder().build(bag)
        xml = bag.get_xml()

        errors = schema_errors(xml, 'DTE_v10.xsd')
        if errors:
            fail(f'Caso {caso["caso"]}: el DTE no cumple el esquema: {"; ".join(errors[:3])}')
        if not TEDValidator.verify_ted_signature(xml, cafs[tipo]) or not XmlSigner().is_valid_xml(xml):
            fail(f'Caso {caso["caso"]}: timbre o firma inválidos.')

        totales = bag.get_datos()['Encabezado']['Totales']
        rut_recep = bag.get_datos()['Encabezado']['Receptor'].get('RUTRecep')
        print(f'{caso["caso"]:<12} {NOMBRES[tipo]:<15} {folio:>6} {miles(totales.get("MntNeto")):>12} '
              f'{miles(totales.get("MntExe")):>10} {miles(totales.get("IVA")):>11} {miles(totales.get("MntTotal")):>12}  '
              f'{rut_recep:<11} {texto_ref}')

        emitidos[caso['caso']] = {'tipo': tipo, 'folio': folio, 'fecha': hoy, 'detalle': detalle,
                                  'receptor': datos['Encabezado']['Receptor']}
        envelope.add_document(xml)

    envio = envelope.build()
    errors = schema_errors(envio, 'EnvioDTE_v10.xsd')
    if errors:
        fail(f'El EnvioDTE no cumple el esquema: {"; ".join(errors[:3])}')
    results = XmlSigner().validate_xml(envio)
    if not all(r.is_valid for r in results):
        fail('Firmas inválidas en el EnvioDTE: ' + ', '.join(f'{r.reference}: {r.error}' for r in results if not r.is_valid))

    args.salida.mkdir(parents=True, exist_ok=True)
    nombre = f'set_{set_data["numero_atencion"]}_{datetime.now().strftime("%Y%m%d%H%M%S")}'
    salida = args.salida / f'{nombre}_envio.xml'
    salida.write_bytes(envio)
    print(f'\nOK: {len(set_data["casos"])} documentos timbrados y firmados, EnvioDTE válido ({len(results)} firmas).')
    print(f'Guardado en {salida}')
    print('Siguientes folios: ' + ', '.join(f'{t}={f}' for t, f in folios.items()))

    if not args.enviar:
        print('\nNo se envió al SII (revise los montos y use --enviar).')
        return

    if any(caf.es_falso() for caf in cafs.values()):
        fail('No se puede enviar al SII con CAF falsos.')
    service = SoapService(SiiEnvironment.CERTIFICACION)
    service.authenticate(certificate)
    upload = service.upload_dte(certificate.get_id(), empresa['emisor']['RUTEmisor'], envio)
    track_id = upload['track_id']
    # Los folios enviados se consideran usados (aunque el envío se rechace se
    # prefiere no reutilizarlos).
    for tipo, siguiente in folios.items():
        registro[tipo] = max(registro.get(tipo, 0), siguiente - 1)
    registro_path.write_text(json.dumps({str(k): v for k, v in sorted(registro.items())}, indent=1))
    (args.salida / f'{nombre}_trackid.txt').write_text(f'{track_id}\n')
    print(f'\nEnvioDTE recibido por el SII. Track ID: {track_id}')

    if args.consultar:
        for intento in range(12):
            time.sleep(10)
            estado = service.query_upload_status(empresa['emisor']['RUTEmisor'], track_id)
            print(f"  [{intento + 1}] {estado['estado']} - {estado['descripcion'] or estado['glosa']} "
                  f"(aceptados {estado['aceptados']}, rechazados {estado['rechazados']}, reparos {estado['reparos']})")
            # Estados finales: procesado, rechazos o códigos numéricos de error (p. ej. 106).
            if estado['estado'] in ('EPR', 'RSC', 'RFR', 'RCT') or (estado['estado'] or '').lstrip('-').isdigit():
                break


if __name__ == '__main__':
    main()
