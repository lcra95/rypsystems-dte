"""
Tests de carga de certificados digitales (.pfx/.p12/PEM) y firma RSA-SHA1.

Para probar con un certificado real, definir:
    RYPSYSTEMS_DTE_PFX=/ruta/al/certificado.pfx
    RYPSYSTEMS_DTE_PFX_PASS_FILE=/ruta/al/archivo/con/la/contraseña
(por defecto ~/.rypsystems-dte/pfx.pass)
"""

import base64
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from rypsystems_dte.firma import CertificateError, DigitalCertificate, SelfSignedCertificate


@pytest.fixture(scope='module')
def certificate() -> DigitalCertificate:
    return SelfSignedCertificate(rut='11222333-9', name='Daniel Bot').create()


class TestSelfSignedCertificate:

    def test_datos_del_titular(self, certificate):
        assert certificate.get_id() == '11222333-9'
        assert certificate.get_name() == 'Daniel Bot'
        assert certificate.get_email() == 'daniel.bot@example.com'
        assert certificate.get_issuer() == 'RypSystems Test Certificate Authority'
        assert len(certificate.chain) == 1

    def test_vigencia(self, certificate):
        assert certificate.is_active()
        assert not certificate.is_active('2000-01-01')
        assert not certificate.is_active('2999-01-01T00:00:00')
        assert 364 <= certificate.get_expiration_days() <= 365

    def test_modulo_y_exponente(self, certificate):
        assert certificate.get_exponent() == 'AQAB'
        modulus = base64.b64decode(certificate.get_modulus().replace('\n', ''))
        assert int.from_bytes(modulus, 'big') == certificate.public_key.public_numbers().n
        assert all(len(line) <= 64 for line in certificate.get_modulus().splitlines())

    def test_firma_rsa_sha1(self, certificate):
        signature = base64.b64decode(certificate.sign('hola mundo'))
        # Lanza InvalidSignature si no corresponde.
        certificate.public_key.verify(signature, b'hola mundo', padding.PKCS1v15(), hashes.SHA1())


class TestPkcs12:

    def test_roundtrip_pkcs12(self, certificate):
        data = certificate.get_pkcs12('secreto')
        loaded = DigitalCertificate.from_pkcs12(data, 'secreto')
        assert loaded.get_id() == certificate.get_id()
        assert loaded.has_private_key()
        assert len(loaded.chain) == 1

    def test_contrasena_incorrecta(self, certificate):
        data = certificate.get_pkcs12('secreto')
        with pytest.raises(CertificateError):
            DigitalCertificate.from_pkcs12(data, 'otra')

    def test_archivo_inexistente(self):
        with pytest.raises(CertificateError):
            DigitalCertificate.from_file('/no/existe.pfx', 'x')

    @pytest.mark.skipif(shutil.which('openssl') is None, reason='Requiere openssl')
    def test_pkcs12_legacy_rc2(self, certificate, tmp_path):
        """Muchos .pfx emitidos en Chile usan cifrado legado (RC2/3DES)."""
        (tmp_path / 'cert.pem').write_text(certificate.get_certificate_pem())
        (tmp_path / 'key.pem').write_text(certificate.get_private_key_pem())
        result = subprocess.run(
            ['openssl', 'pkcs12', '-export', '-legacy',
             '-in', str(tmp_path / 'cert.pem'), '-inkey', str(tmp_path / 'key.pem'),
             '-out', str(tmp_path / 'legacy.pfx'), '-passout', 'pass:legado'],
            capture_output=True,
        )
        if result.returncode != 0:
            pytest.skip('openssl sin soporte -legacy')
        loaded = DigitalCertificate.from_file(tmp_path / 'legacy.pfx', 'legado')
        assert loaded.get_id() == '11222333-9'

    def test_pem(self, certificate):
        loaded = DigitalCertificate.from_pem(
            certificate.get_certificate_pem(), certificate.get_private_key_pem()
        )
        assert loaded.get_id() == certificate.get_id()
        assert loaded.sign('x') == certificate.sign('x')


def _real_certificate_config():
    pfx = os.environ.get('RYPSYSTEMS_DTE_PFX')
    pass_file = Path(os.environ.get(
        'RYPSYSTEMS_DTE_PFX_PASS_FILE', Path.home() / '.rypsystems-dte' / 'pfx.pass'
    ))
    if not pfx or not Path(pfx).is_file() or not pass_file.is_file():
        return None
    return Path(pfx), pass_file.read_text().strip()


@pytest.mark.skipif(_real_certificate_config() is None, reason='Sin certificado real configurado')
def test_certificado_real():
    path, password = _real_certificate_config()
    cert = DigitalCertificate.from_file(path, password)
    assert cert.has_private_key()
    assert cert.get_id()
    assert cert.is_active()
    signature = base64.b64decode(cert.sign('prueba'))
    cert.public_key.verify(signature, b'prueba', padding.PKCS1v15(), hashes.SHA1())
