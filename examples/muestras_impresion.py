#!/usr/bin/env python3
"""
Genera las muestras de impresión (PDF) de los sets de certificación.

Para cada set toma el último EnvioDTE enviado al SII (el que tiene Track ID)
y genera un PDF por documento, con su copia cedible cuando corresponde.

Ejemplo:

    PYTHONPATH=src python examples/muestras_impresion.py --empresa ../empresa_certificacion.yaml
"""

import argparse
import re
import sys
from pathlib import Path

import yaml
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from rypsystems_dte.pdf import DtePdf, DtePdfTermico  # noqa: E402


def ultimos_envios(directorio: Path):
    """Último envío con Track ID de cada set: {numero_atencion: ruta_envio}."""
    envios = {}
    for trackid in sorted(directorio.glob('set_*_trackid.txt')):
        numero = re.match(r'set_([^_]+)_', trackid.name).group(1)
        envio = trackid.with_name(trackid.name.replace('_trackid.txt', '_envio.xml'))
        if envio.exists():
            envios[numero] = envio
    return envios


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--empresa', required=True, type=Path)
    parser.add_argument('--envios', type=Path, default=ROOT / 'output' / 'certificacion')
    parser.add_argument('--salida', type=Path, default=ROOT / 'output' / 'certificacion' / 'muestras')
    parser.add_argument('--logo', type=Path)
    parser.add_argument('--formato', choices=('carta', '80mm'), default='carta',
                        help='Hoja carta o rollo térmico de 80 mm')
    parser.add_argument('--sin-timbre-boletas', action='store_true',
                        help='No imprimir el timbre en boletas (opcional desde 2026)')
    args = parser.parse_args()

    empresa = yaml.safe_load(args.empresa.expanduser().read_text(encoding='utf-8'))
    clase = DtePdfTermico if args.formato == '80mm' else DtePdf
    opciones = {'timbre_boletas': not args.sin_timbre_boletas} if args.formato == '80mm' else {}
    pdf = clase(
        **opciones,
        resolucion={'fecha': str(empresa['fecha_resolucion']), 'numero': empresa.get('numero_resolucion', 0)},
        logo=str(args.logo) if args.logo else None,
    )
    args.salida.mkdir(parents=True, exist_ok=True)
    for numero, envio in ultimos_envios(args.envios).items():
        root = etree.fromstring(envio.read_bytes())
        dtes = root.xpath('//*[local-name()="SetDTE"]/*[local-name()="DTE"]')
        print(f'Set {numero} ({envio.name}): {len(dtes)} documentos')
        for dte in dtes:
            tipo = dte.xpath('string(.//*[local-name()="IdDoc"]/*[local-name()="TipoDTE"])')
            folio = dte.xpath('string(.//*[local-name()="IdDoc"]/*[local-name()="Folio"])')
            sufijo = '_80mm' if args.formato == '80mm' else ''
            ruta = args.salida / f'set_{numero}_T{int(tipo):03d}F{int(folio):09d}{sufijo}.pdf'
            ruta.write_bytes(pdf.render(etree.tostring(dte)))
            print(f'  {ruta}')


if __name__ == '__main__':
    main()
