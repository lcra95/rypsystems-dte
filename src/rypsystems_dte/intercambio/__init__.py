"""
RypSystems DTE - Intercambio de información entre contribuyentes.

- EnvioRecibido: lectura y validación de un EnvioDTE recibido de un proveedor.
- RespuestaEnvio: RespuestaDTE con la recepción del envío (RecepcionEnvio) o
  con la aprobación/rechazo comercial de los documentos (ResultadoDTE).
- EnvioRecibos: acuse de recibo de mercaderías o servicios (Ley 19.983).
"""

from .envio_recibido import DocumentoRecibido, EnvioRecibido, IntercambioError
from .recibos import DECLARACION_RECIBO, EnvioRecibos
from .respuesta import (
    ESTADOS_DTE,
    ESTADOS_RECEPCION_DTE,
    ESTADOS_RECEPCION_ENVIO,
    RespuestaEnvio,
)

__all__ = [
    'DECLARACION_RECIBO', 'DocumentoRecibido', 'ESTADOS_DTE', 'ESTADOS_RECEPCION_DTE', 'ESTADOS_RECEPCION_ENVIO',
    'EnvioRecibido', 'EnvioRecibos', 'IntercambioError', 'RespuestaEnvio',
]
