#!/usr/bin/env python3
"""
Etapa de intercambio de información de la certificación del SII.

A partir del EnvioDTE que el SII entrega para el intercambio (descargado desde
la página de certificación), genera los tres archivos que se deben subir:

1. Respuesta de recepción del envío (RespuestaDTE con RecepcionEnvio).
2. Acuse de recibo de mercaderías (EnvioRecibos, Ley 19.983).
3. Resultado de la aprobación comercial (RespuestaDTE con ResultadoDTE).

Ejemplo:

    PYTHONPATH=src python examples/intercambio_certificacion.py \\
        --envio ~/Downloads/ENVIO_DTE_xxxx.xml \\
        --empresa ../empresa_certificacion.yaml \\
        --pfx ~/Downloads/certificado.pfx --pass-file ~/.rypsystems-dte/pfx.pass
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from rypsystems_dte.firma import DigitalCertificate, XmlSigner  # noqa: E402
from rypsystems_dte.intercambio import EnvioRecibido, EnvioRecibos, RespuestaEnvio  # noqa: E402
from rypsystems_dte.xml.schema import schema_errors  # noqa: E402


def fail(message: str) -> None:
    print(f'ERROR: {message}')
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--envio', required=True, type=Path, help='EnvioDTE recibido (del SII)')
    parser.add_argument('--empresa', required=True, type=Path)
    parser.add_argument('--pfx', required=True, type=Path)
    parser.add_argument('--pass-file', required=True, type=Path)
    parser.add_argument('--cod-envio', type=int, default=1, help='Número interno asignado al envío recibido')
    parser.add_argument('--recinto', help='Lugar de recepción de las mercaderías (por defecto, la dirección)')
    parser.add_argument('--contacto', help='Nombre de contacto')
    parser.add_argument('--fono', help='Teléfono de contacto')
    parser.add_argument('--mail', help='Correo de contacto')
    parser.add_argument('--rechazar', default='',
                        help='DTE a rechazar comercialmente, como TIPO:FOLIO separados por coma (ej. 33:12)')
    parser.add_argument('--sin-validar-timbre', action='store_true',
                        help='No verificar el timbre (el set de intercambio del SII trae timbres que no verifican)')
    parser.add_argument('--salida', type=Path, default=ROOT / 'output' / 'certificacion' / 'intercambio')
    args = parser.parse_args()

    empresa = yaml.safe_load(args.empresa.expanduser().read_text(encoding='utf-8'))
    emisor = empresa['emisor']
    rut = emisor['RUTEmisor']
    certificate = DigitalCertificate.from_file(args.pfx.expanduser(), args.pass_file.expanduser().read_text().strip())
    contacto = dict(nombre_contacto=args.contacto, fono_contacto=args.fono, mail_contacto=args.mail)
    recinto = args.recinto or f'{emisor["DirOrigen"]}, {emisor["CmnaOrigen"]}'
    rechazar = {tuple(int(v) for v in item.split(':')) for item in args.rechazar.split(',') if item.strip()}

    envio = EnvioRecibido(args.envio.expanduser().read_bytes(), nombre=args.envio.name).validar(
        rut, validar_timbre=not args.sin_validar_timbre)
    print(f'Envío {envio.nombre} (ID {envio.id}) de {envio.rut_emisor} para {envio.rut_receptor}')
    print(f'  Estado recepción: {envio.estado} - {envio.glosa}')
    for error in envio.errores[:5]:
        print(f'    {error}')
    for doc in envio.documentos:
        print(f'  T{doc.tipo} F{doc.folio} {doc.fecha_emision} {doc.rut_emisor} -> {doc.rut_receptor} '
              f'${doc.monto_total:,}: {doc.estado} - {doc.glosa}'.replace(',', '.'))

    # 1. Recepción del envío.
    recepcion = RespuestaEnvio(rut, envio.rut_emisor, id_respuesta=args.cod_envio, **contacto)
    recepcion.agregar_recepcion_envio(envio, cod_envio=args.cod_envio)
    archivos = {'recepcion_envio': (recepcion.generar(certificate), 'RespuestaEnvioDTE_v10.xsd')}

    recibidos = [doc for doc in envio.documentos if envio.estado == 0 and doc.estado == 0]
    if recibidos:
        # 2. Recibo de mercaderías de los DTE aceptados.
        aceptados = [doc for doc in recibidos if (doc.tipo, doc.folio) not in rechazar]
        if aceptados:
            recibos = EnvioRecibos(rut, envio.rut_emisor, **contacto)
            for doc in aceptados:
                recibos.agregar(doc.resumen(), recinto=recinto, certificate=certificate)
            archivos['recibo_mercaderias'] = (recibos.generar(certificate), 'EnvioRecibos_v10.xsd')

    if envio.estado == 0:
        # 3. Aprobación comercial de cada DTE del envío: los que no se recibieron
        # conforme (p. ej. dirigidos a otro RUT) se informan rechazados.
        resultado = RespuestaEnvio(rut, envio.rut_emisor, id_respuesta=args.cod_envio, **contacto)
        for doc in envio.documentos:
            if doc.estado != 0:
                resultado.agregar_resultado_dte(doc.resumen(), args.cod_envio, estado=2,
                                                glosa='DTE Rechazado - ' + doc.glosa.replace('DTE No Recibido - ', ''), codigo_rechazo=-1)
            elif (doc.tipo, doc.folio) in rechazar:
                resultado.agregar_resultado_dte(doc.resumen(), args.cod_envio, estado=2, codigo_rechazo=-1)
            else:
                resultado.agregar_resultado_dte(doc.resumen(), args.cod_envio, estado=0)
        archivos['resultado_dte'] = (resultado.generar(certificate), 'RespuestaEnvioDTE_v10.xsd')

    args.salida.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime('%Y%m%d%H%M%S')
    print()
    for nombre, (xml, schema) in archivos.items():
        errores = schema_errors(xml, schema)
        if errores:
            fail(f'{nombre} no cumple {schema}: {"; ".join(errores[:3])}')
        if not XmlSigner().is_valid_xml(xml):
            fail(f'La firma de {nombre} no es válida.')
        ruta = args.salida / f'{nombre}_{marca}.xml'
        ruta.write_bytes(xml)
        print(f'OK {nombre}: {ruta}')


if __name__ == '__main__':
    main()
