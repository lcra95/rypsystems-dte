"""
Tests contra el ambiente de certificación del SII (maullin.sii.cl).

No se ejecutan por defecto. Requieren red, el certificado real y:
    RYPSYSTEMS_DTE_SII_LIVE=1
    RYPSYSTEMS_DTE_PFX=/ruta/al/certificado.pfx
    (contraseña en ~/.rypsystems-dte/pfx.pass o RYPSYSTEMS_DTE_PFX_PASS_FILE)
"""

import os
import sys
from pathlib import Path

import pytest

from rypsystems_dte.sii.webservices.sii_endpoints import SiiEnvironment
from rypsystems_dte.sii.webservices.soap_service import SoapService

sys.path.insert(0, str(Path(__file__).parent))
from test_dte_emision import _real_certificate  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get('RYPSYSTEMS_DTE_SII_LIVE') != '1', reason='Tests en vivo contra el SII deshabilitados'
)


def test_semilla_maullin():
    assert SoapService(SiiEnvironment.CERTIFICACION).get_seed().isdigit()


@pytest.mark.skipif(_real_certificate() is None, reason='Sin certificado real configurado')
def test_token_maullin():
    service = SoapService(SiiEnvironment.CERTIFICACION)
    token = service.authenticate(_real_certificate())
    assert token and service.is_authenticated()
