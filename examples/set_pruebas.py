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

Para la etapa de simulación (documentos que representan la operación real de
la empresa) el YAML lleva `referencia_set: false`, y así los documentos no
llevan la referencia SET. Cada caso puede indicar su propio `receptor`.

Los sets de boletas (39 y 41) se arman en un EnvioBOLETA, con la referencia
CodRef SET / RazonRef CASO-n y receptor 66666666-6 por defecto, y se envían por
la API REST de boletas del SII.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from rypsystems_dte import (  # noqa: E402
    Caf, CafValidator, ClienteSii, DigitalCertificate, EmisionError, SiiEnvironment, armar_envio,
)
from rypsystems_dte.certificacion.emision import emitir_set  # noqa: E402
from rypsystems_dte.sii.webservices import BoletaService  # noqa: E402

BOLETAS = (39, 41)
NOMBRES = {39: 'Boleta', 41: 'Boleta exenta', 33: 'Factura', 34: 'Factura exenta', 46: 'Factura compra', 52: 'Guía despacho',
           43: 'Liquidación', 56: 'Nota débito', 61: 'Nota crédito', 110: 'Factura export.', 111: 'ND export.',
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

    nombre_set = set_data.get('nombre') or f'set_{set_data["numero_atencion"]}'
    boletas = all(t in BOLETAS for t in tipos)

    def asignar_folio(tipo):
        folio = folios[tipo]
        if not cafs[tipo].en_rango(folio):
            fail(f'No quedan folios del tipo {tipo} en el CAF {cafs[tipo].get_id()}.')
        folios[tipo] += 1
        return cafs[tipo], folio

    print(f'{nombre_set} - emisor {empresa["emisor"]["RUTEmisor"]}, '
          f'envía {certificate.get_id()} {certificate.get_name()}\n')
    print(f'{"Caso":<12} {"Documento":<15} {"Folio":>6} {"Neto":>12} {"Exento":>10} {"IVA":>11} {"Total":>12}  '
          f'{"Receptor":<11} Referencia')
    try:
        emitidos = emitir_set(set_data, empresa['emisor'], certificate, asignar_folio,
                              receptores=empresa.get('receptores') or [empresa['receptor']])
    except EmisionError as e:
        fail(str(e))
    documentos = []
    for emitido in emitidos:
        documento, ref = emitido.documento, emitido.referencia
        totales = documento.totales
        texto_ref = f'{NOMBRES[ref["tipo"]]} {ref["folio"]} (CodRef {ref["CodRef"]})' if ref else ''
        print(f'{emitido.caso:<12} {NOMBRES[documento.tipo]:<15} {documento.folio:>6} '
              f'{miles(totales.get("MntNeto")):>12} {miles(totales.get("MntExe")):>10} {miles(totales.get("IVA")):>11} '
              f'{miles(totales.get("MntTotal")):>12}  {documento.receptor:<11} {texto_ref}')
        documentos.append(documento)

    try:
        envio = armar_envio(documentos, certificate, empresa['fecha_resolucion'], empresa.get('numero_resolucion', 0))
    except EmisionError as e:
        fail(str(e))

    args.salida.mkdir(parents=True, exist_ok=True)
    nombre = f'{nombre_set}_{datetime.now().strftime("%Y%m%d%H%M%S")}'
    salida = args.salida / f'{nombre}_envio.xml'
    salida.write_bytes(envio)
    print(f'\nOK: {len(set_data["casos"])} documentos timbrados y firmados, sobre válido y firmado.')
    print(f'Guardado en {salida}')
    print('Siguientes folios: ' + ', '.join(f'{t}={f}' for t, f in folios.items()))

    if not args.enviar:
        print('\nNo se envió al SII (revise los montos y use --enviar).')
        return

    if any(caf.es_falso() for caf in cafs.values()):
        fail('No se puede enviar al SII con CAF falsos.')
    if boletas:
        enviar_boletas(args, empresa, certificate, envio, folios, registro, registro_path, nombre)
        return
    sii = ClienteSii(certificate, SiiEnvironment.CERTIFICACION)
    track_id = sii.enviar(envio, empresa['emisor']['RUTEmisor'])
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
            estado = sii.servicio_dte().query_upload_status(empresa['emisor']['RUTEmisor'], track_id)
            print(f"  [{intento + 1}] {estado['estado']} - {estado['descripcion'] or estado['glosa']} "
                  f"(aceptados {estado['aceptados']}, rechazados {estado['rechazados']}, reparos {estado['reparos']})")
            # Estados finales: procesado, rechazos o códigos numéricos de error (p. ej. 106).
            if estado['estado'] in ('EPR', 'RSC', 'RFR', 'RCT') or (estado['estado'] or '').lstrip('-').isdigit():
                informados = sum(int(d.get('informados') or 0) for d in estado.get('detalle') or [])
                if estado['estado'] == 'EPR' and informados < len(set_data['casos']):
                    # El resumen de QueryEstUp lista solo algunos tipos (se vio con 10 tipos en
                    # un envío: informó 5); los demás se revisan con QueryEstDte.
                    tipos_informados = {int(d['tipo_docto']) for d in estado.get('detalle') or []}
                    faltan = sorted({c['tipo'] for c in set_data['casos']} - tipos_informados)
                    print(f'  AVISO: el resumen informa {informados} de {len(set_data["casos"])} documentos; '
                          f'consulte individualmente los tipos {faltan}.')
                break



def registrar_folios(folios, registro, registro_path) -> None:
    """Los folios enviados se consideran usados (aunque el envío se rechace)."""
    for tipo, siguiente in folios.items():
        registro[tipo] = max(registro.get(tipo, 0), siguiente - 1)
    registro_path.write_text(json.dumps({str(k): v for k, v in sorted(registro.items())}, indent=1))


def enviar_boletas(args, empresa, certificate, envio, folios, registro, registro_path, nombre) -> None:
    """Envío por la API REST de boletas y consulta de su estado."""
    rut = empresa['emisor']['RUTEmisor']
    service = BoletaService(SiiEnvironment.CERTIFICACION)
    service.authenticate(certificate)
    upload = service.upload(certificate.get_id(), rut, envio, filename=f'{nombre}.xml')
    track_id = upload['track_id']
    registrar_folios(folios, registro, registro_path)
    (args.salida / f'{nombre}_trackid.txt').write_text(f'{track_id}\n')
    print(f'\nEnvioBOLETA recibido por el SII. Track ID: {track_id} ({upload["estado"]})')
    if not args.consultar:
        return
    for intento in range(18):
        time.sleep(10)
        try:
            estado = service.query_upload_status(rut, track_id)
        except Exception as e:  # p. ej. HTTP 503 temporal del SII
            print(f'  [{intento + 1}] {e}')
            continue
        totales = ', '.join(f"T{e.get('tipo')}: {e.get('aceptados')}/{e.get('informados')} aceptadas, "
                            f"{e.get('rechazados')} rechazadas, {e.get('reparos')} reparos"
                            for e in estado['estadistica'])
        print(f"  [{intento + 1}] {estado['estado']} {totales}")
        for doc in estado['detalle']:
            print(f"    T{doc.get('tipo')} F{doc.get('folio')} {doc.get('estado')} {doc.get('descripcion', '')}")
            for error in doc.get('error') or []:
                print(f"      {error.get('codigo', '')} {error.get('descripcion', '')} {error.get('detalle') or ''}")
        if estado['estado'] not in ('REC', 'SOK', 'CRT', 'FOK', 'PDR', None):
            break


if __name__ == '__main__':
    main()
