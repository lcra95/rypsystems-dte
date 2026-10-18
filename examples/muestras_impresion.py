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
    """Último envío con Track ID de cada set y de la simulación: {nombre: (ruta_envio, track_id)}."""
    envios = {}
    archivos = sorted(directorio.glob('set_*_trackid.txt')) + sorted(directorio.glob('simulacion_*_trackid.txt'))
    for trackid in archivos:
        nombre = re.match(r'(set_[^_]+|simulacion)_', trackid.name).group(1)
        envio = trackid.with_name(trackid.name.replace('_trackid.txt', '_envio.xml'))
        if envio.exists():
            envios[nombre] = (envio, trackid.read_text().strip())
    return envios


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--empresa', required=True, type=Path)
    parser.add_argument('--envios', type=Path, default=ROOT / 'output' / 'certificacion')
    parser.add_argument('--salida', type=Path, default=ROOT / 'output' / 'certificacion' / 'muestras')
    parser.add_argument('--logo', type=Path)
    parser.add_argument('--formato', choices=('carta', '80mm'), default='carta',
                        help='Hoja carta o rollo térmico de 80 mm')
    parser.add_argument('--para-sii', action='store_true',
                        help='Carpeta para subir a "Ingreso de Muestras Impresas": un PDF por documento '
                             'y otro por copia cedible, de los sets de prueba (sin boletas) y la simulación')
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
    sufijo = '_80mm' if args.formato == '80mm' else ''
    if args.para_sii:
        para_sii(pdf, ultimos_envios(args.envios), args.salida.parent / 'muestras_sii')
        return
    for nombre, (envio, track_id) in ultimos_envios(args.envios).items():
        xml = envio.read_bytes()
        dtes = etree.fromstring(xml).xpath('//*[local-name()="SetDTE"]/*[local-name()="DTE"]')
        # Un PDF con todos los documentos del envío (con sus copias cedibles)...
        combinado = args.salida / f'{nombre}_envio_{track_id}{sufijo}.pdf'
        combinado.write_bytes(pdf.render_envio(xml))
        print(f'{nombre} (Track ID {track_id}): {len(dtes)} documentos -> {combinado.name}')
        # ... y uno por documento.
        for dte in dtes:
            tipo = dte.xpath('string(.//*[local-name()="IdDoc"]/*[local-name()="TipoDTE"])')
            folio = dte.xpath('string(.//*[local-name()="IdDoc"]/*[local-name()="Folio"])')
            ruta = args.salida / f'{nombre}_T{int(tipo):03d}F{int(folio):09d}{sufijo}.pdf'
            ruta.write_bytes(pdf.render(etree.tostring(dte)))



def para_sii(pdf, envios, salida: Path) -> None:
    """Un PDF por documento original y uno por copia cedible (las boletas se certifican aparte)."""
    salida.mkdir(parents=True, exist_ok=True)
    total = 0
    for nombre, (envio, track_id) in envios.items():
        if nombre == 'set_boleta':
            continue
        dtes = etree.fromstring(envio.read_bytes()).xpath('//*[local-name()="SetDTE"]/*[local-name()="DTE"]')
        archivos = 0
        for dte in dtes:
            tipo = int(dte.xpath('string(.//*[local-name()="IdDoc"]/*[local-name()="TipoDTE"])'))
            folio = int(dte.xpath('string(.//*[local-name()="IdDoc"]/*[local-name()="Folio"])'))
            xml = etree.tostring(dte)
            (salida / f'T{tipo}_F{folio}.pdf').write_bytes(pdf.render(xml, cedible=False))
            archivos += 1
            cedible = pdf.render_cedible(xml)
            if cedible:
                (salida / f'T{tipo}_F{folio}_cedible.pdf').write_bytes(cedible)
                archivos += 1
        total += archivos
        print(f'{nombre} (Track ID {track_id}): {len(dtes)} documentos, {archivos} PDF')
    print(f'Total: {total} PDF en {salida}')


if __name__ == '__main__':
    main()
