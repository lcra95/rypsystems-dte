"""
Muestras impresas para la etapa "Documentos impresos" de la certificación:
un PDF por documento (ejemplar tributario) y otro por su copia cedible, de
los DTE del set de pruebas y de la simulación (las boletas se certifican
aparte). Nombres T{tipo}_F{folio}.pdf y T{tipo}_F{folio}_cedible.pdf.
"""

import io
import zipfile
from typing import Dict, Iterable, Union

from lxml import etree

from ..emision import BOLETAS
from ..pdf import DtePdf


def muestras_impresas(dtes: Iterable[Union[bytes, str]], fecha_resolucion: str, numero_resolucion: int = 0,
                      pdf: DtePdf = None) -> Dict[str, bytes]:
    """PDF por nombre de archivo para subir al SII."""
    pdf = pdf or DtePdf({'fecha': fecha_resolucion, 'numero': numero_resolucion})
    archivos: Dict[str, bytes] = {}
    for xml in dtes:
        if isinstance(xml, str):
            xml = xml.encode('iso-8859-1')
        raiz = etree.fromstring(xml)
        tipo = int(raiz.xpath('string(//*[local-name()="IdDoc"]/*[local-name()="TipoDTE"])'))
        folio = int(raiz.xpath('string(//*[local-name()="IdDoc"]/*[local-name()="Folio"])'))
        if tipo in BOLETAS:
            continue
        archivos[f'T{tipo}_F{folio}.pdf'] = pdf.render(xml, cedible=False)
        cedible = pdf.render_cedible(xml)
        if cedible:
            archivos[f'T{tipo}_F{folio}_cedible.pdf'] = cedible
    return archivos


def zip_muestras(archivos: Dict[str, bytes]) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in sorted(archivos.items()):
            zf.writestr(nombre, contenido)
    return salida.getvalue()
