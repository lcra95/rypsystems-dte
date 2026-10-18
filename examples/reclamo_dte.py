#!/usr/bin/env python3
"""
Acepta, reclama o consulta en el SII documentos recibidos (Ley 20.956).

El receptor tiene 8 días desde la recepción del documento en el SII para
aceptarlo o reclamarlo; después se entiende aceptado.

Acciones: eventos, fecha, cedible (consultas) y ACD, ERM, RCD, RFP, RFT
(ver rypsystems_dte.sii.webservices.registro_reclamo_service).

Ejemplos:

    # Consultar el historial de un documento
    PYTHONPATH=src python examples/reclamo_dte.py eventos --emisor 76192083-9 --tipo 33 --folio 1234 \\
        --pfx ~/Downloads/certificado.pfx --pass-file ~/.rypsystems-dte/pfx.pass

    # Aceptar todos los documentos de un EnvioDTE recibido
    PYTHONPATH=src python examples/reclamo_dte.py ACD --envio recibido.xml --pfx ... --pass-file ...

    # Producción
    ... --produccion
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from rypsystems_dte.firma import DigitalCertificate  # noqa: E402
from rypsystems_dte.intercambio import EnvioRecibido  # noqa: E402
from rypsystems_dte.sii.webservices import RegistroReclamoService, SiiEnvironment  # noqa: E402
from rypsystems_dte.sii.webservices.registro_reclamo_service import ACCIONES, TIPOS_DOCUMENTO  # noqa: E402

CONSULTAS = ('eventos', 'fecha', 'cedible')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('accion', choices=CONSULTAS + tuple(ACCIONES))
    parser.add_argument('--emisor', help='RUT del emisor del documento')
    parser.add_argument('--tipo', type=int)
    parser.add_argument('--folio', type=int)
    parser.add_argument('--envio', type=Path, help='EnvioDTE recibido: aplica la acción a todos sus documentos')
    parser.add_argument('--pfx', required=True, type=Path)
    parser.add_argument('--pass-file', required=True, type=Path)
    parser.add_argument('--produccion', action='store_true')
    args = parser.parse_args()

    if args.envio:
        envio = EnvioRecibido(args.envio.read_bytes(), args.envio.name)
        documentos = [(d.rut_emisor, d.tipo, d.folio) for d in envio.documentos]
        if args.accion not in CONSULTAS:
            omitidos = [d for d in documentos if int(d[1]) not in TIPOS_DOCUMENTO]
            for rut, tipo, folio in omitidos:
                print(f'T{tipo} F{folio} de {rut}: se omite, solo se aceptan o reclaman tipos {TIPOS_DOCUMENTO}')
            documentos = [d for d in documentos if d not in omitidos]
    elif args.emisor and args.tipo and args.folio:
        documentos = [(args.emisor, args.tipo, args.folio)]
    else:
        parser.error('Indique --envio o bien --emisor, --tipo y --folio.')

    certificate = DigitalCertificate.from_file(args.pfx.expanduser(), args.pass_file.expanduser().read_text().strip())
    service = RegistroReclamoService(SiiEnvironment.PRODUCCION if args.produccion else SiiEnvironment.CERTIFICACION)
    service.authenticate(certificate)

    errores = 0
    for rut, tipo, folio in documentos:
        documento = f'T{tipo} F{folio} de {rut}'
        if args.accion == 'fecha':
            print(f'{documento}: recibido por el SII el {service.fecha_recepcion(rut, tipo, folio) or "-"}')
            continue
        if args.accion == 'eventos':
            respuesta = service.listar_eventos(rut, tipo, folio)
        elif args.accion == 'cedible':
            respuesta = service.consultar_cedible(rut, tipo, folio)
        else:
            respuesta = service.registrar(rut, tipo, folio, args.accion)
            errores += not respuesta['ok']
        print(f'{documento}: [{respuesta["codigo"]}] {respuesta["descripcion"]}')
        for evento in respuesta['eventos']:
            print(f'    {evento["fecha"]} {evento["codigo"]} {evento["descripcion"]} ({evento["responsable"]})')
    sys.exit(1 if errores else 0)


if __name__ == '__main__':
    main()
