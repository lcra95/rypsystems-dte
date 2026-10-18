"""
Tests de la representación impresa (PDF) de DTE.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from rypsystems_dte.firma import SelfSignedCertificate
from rypsystems_dte.identifier import CafFaker
from rypsystems_dte.pdf import DtePdf, pdf417_image, ted_pdf417
from rypsystems_dte.pdf.dte_pdf import fecha, numero, rut

sys.path.insert(0, str(Path(__file__).parent))
from test_dte_emision import datos_factura, emitir  # noqa: E402

RESOLUCION = {'fecha': '2026-10-17', 'numero': 0}


@pytest.fixture(scope='module')
def factura():
    caf = CafFaker(rut='76192083-9', tipo_documento=33).create()
    _, _, xml = emitir(datos_factura(), caf, SelfSignedCertificate().create())
    return xml


def test_formatos():
    assert numero(3353587) == '3.353.587'
    assert numero(121839.12) == '121.839,12'
    assert rut('76192083-9') == '76.192.083-9'
    assert fecha('2026-10-17') == '17/10/2026'


def test_ted_pdf417_sin_namespace(factura):
    ted = ted_pdf417(factura)
    assert ted.startswith(b'<TED version="1.0"><DD><RE>76192083-9</RE>')
    assert b'xmlns' not in ted and b'\n' not in ted


def test_pdf_factura_con_cedible(factura):
    contenido = DtePdf(RESOLUCION).render(factura)
    assert contenido.startswith(b'%PDF')
    sin_cedible = DtePdf(RESOLUCION).render(factura, cedible=False)
    # Factura: original y copia cedible (con acuse de recibo).
    assert contenido.count(b'/Type /Page\n') == 2
    assert sin_cedible.count(b'/Type /Page\n') == 1


@pytest.mark.skipif(shutil.which('pdftoppm') is None, reason='Requiere pdftoppm (poppler)')
def test_pdf417_impreso_es_el_ted(factura, tmp_path):
    zxingcpp = pytest.importorskip('zxingcpp')
    from PIL import Image

    pdf = tmp_path / 'factura.pdf'
    pdf.write_bytes(DtePdf(RESOLUCION).render(factura, cedible=False))
    subprocess.run(['pdftoppm', '-r', '300', '-png', str(pdf), str(tmp_path / 'pagina')], check=True)
    imagen = Image.open(next(tmp_path.glob('pagina*.png')))
    leidos = [r for r in zxingcpp.read_barcodes(imagen) if r.format == zxingcpp.BarcodeFormat.PDF417]
    assert leidos and leidos[0].bytes == ted_pdf417(factura)
    # Tamaño exigido por el SII: 5-9 cm de ancho y 2-4 cm de alto.
    p = leidos[0].position
    ancho = (max(p.top_right.x, p.bottom_right.x) - min(p.top_left.x, p.bottom_left.x)) / 300 * 25.4
    alto = (max(p.bottom_left.y, p.bottom_right.y) - min(p.top_left.y, p.top_right.y)) / 300 * 25.4
    assert 50 <= ancho <= 90 and 20 <= alto <= 40, (ancho, alto)


def test_pdf417_iso_8859_1():
    zxingcpp = pytest.importorskip('zxingcpp')
    datos = '<TED version="1.0"><DD><RSR>Compañía Ñandú</RSR></DD></TED>'.encode('iso-8859-1')
    leidos = zxingcpp.read_barcodes(pdf417_image(datos))
    assert leidos[0].bytes == datos
