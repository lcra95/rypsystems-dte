"""
RypSystems DTE - Documentos tributarios electrónicos del SII de Chile.

Traducción a Python de LibreDTE (AGPL-3.0-or-later; ver COPYING y NOTICE).

Uso básico:

    from rypsystems_dte import Caf, ClienteSii, DigitalCertificate, armar_envio, emitir_documento

    certificado = DigitalCertificate.from_file('firma.pfx', 'clave')
    doc = emitir_documento(datos, Caf.from_file('caf33.xml'), certificado)
    envio = armar_envio([doc], certificado, fecha_resolucion='2026-10-17', numero_resolucion=0)
    track_id = ClienteSii(certificado).enviar(envio, doc.emisor)
"""

__version__ = "0.1.0"
__author__ = "RYP AI SYSTEMS SPA"
__description__ = "Documentos tributarios electrónicos (DTE) del SII de Chile"

from .errors import RypDteError
from .sii import SiiAmbiente, Contribuyente, PartyIdentifier
from .sii.webservices import RegistroReclamoService, SiiEnvironment
from .sii.webservices.exceptions import SiiWebServiceException
from .firma import CertificateError, DigitalCertificate
from .identifier import Caf, CafError, CafValidator
from .emision import (
    ClienteSii,
    DocumentoEmitido,
    EmisionError,
    anular,
    armar_envio,
    documento_a_datos,
    emitir_documento,
)
from .intercambio import EnvioRecibido, EnvioRecibos, IntercambioError, RespuestaEnvio
from .pdf import DtePdf, DtePdfTermico

__all__ = [
    # Emisión
    'emitir_documento', 'armar_envio', 'anular', 'documento_a_datos', 'DocumentoEmitido', 'ClienteSii',
    # Firma y folios
    'DigitalCertificate', 'Caf', 'CafValidator',
    # SII
    'SiiEnvironment', 'SiiAmbiente', 'RegistroReclamoService',
    # Intercambio
    'EnvioRecibido', 'RespuestaEnvio', 'EnvioRecibos',
    # PDF
    'DtePdf', 'DtePdfTermico',
    # Contribuyentes
    'Contribuyente', 'PartyIdentifier',
    # Errores
    'RypDteError', 'EmisionError', 'CertificateError', 'CafError', 'IntercambioError', 'SiiWebServiceException',
]
