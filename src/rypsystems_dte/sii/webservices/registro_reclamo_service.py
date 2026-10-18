"""
Registro de aceptación o reclamo de DTE (Ley 20.956).

El receptor de una factura tiene 8 días desde que el SII la recibió para
aceptarla o reclamarla; pasado ese plazo se entiende aceptada. Este servicio
SOAP del SII registra esa acción y permite consultar los eventos de un
documento. Se autentica con el mismo token de los servicios DTEWS (CrSeed y
GetTokenFromSeed), enviado como cookie TOKEN.

Servidores: certificación ws2.sii.cl/WSREGISTRORECLAMODTECERT y producción
ws1.sii.cl/WSREGISTRORECLAMODTE.

Acciones (accionDoc):
- ACD: acepta el contenido del documento.
- RCD: reclama el contenido del documento.
- ERM: otorga el recibo de mercaderías o servicios (Ley 19.983).
- RFP: reclama por falta parcial de mercaderías.
- RFT: reclama por falta total de mercaderías.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from xml.sax.saxutils import escape

import requests

from ...firma.digital_certificate import DigitalCertificate
from .exceptions import SiiAuthenticationError, SiiCommunicationError, SiiValidationError
from .sii_endpoints import SiiEnvironment
from .soap_service import SoapService

logger = logging.getLogger(__name__)

SERVIDORES = {
    SiiEnvironment.CERTIFICACION: 'https://ws2.sii.cl/WSREGISTRORECLAMODTECERT/registroreclamodteservice',
    SiiEnvironment.PRODUCCION: 'https://ws1.sii.cl/WSREGISTRORECLAMODTE/registroreclamodteservice',
}
NAMESPACE = 'http://ws.registroreclamodte.diii.sdi.sii.cl'

ACCIONES = {
    'ACD': 'Acepta contenido del documento',
    'RCD': 'Reclamo al contenido del documento',
    'ERM': 'Otorga recibo de mercaderías o servicios',
    'RFP': 'Reclamo por falta parcial de mercaderías',
    'RFT': 'Reclamo por falta total de mercaderías',
}
RECLAMOS = ('RCD', 'RFP', 'RFT')

# Documentos sobre los que se puede aceptar o reclamar.
TIPOS_DOCUMENTO = (33, 34, 43)


def _local(tag: str) -> str:
    return tag.split('}')[-1]


class RegistroReclamoService:
    """
    Cliente del registro de aceptación o reclamo de DTE.

    Ejemplo:
        service = RegistroReclamoService(SiiEnvironment.CERTIFICACION)
        service.authenticate(certificate)
        service.listar_eventos('76192083-9', 33, 1234)
        service.aceptar('76192083-9', 33, 1234)
    """

    def __init__(self, environment: SiiEnvironment = SiiEnvironment.CERTIFICACION, timeout: int = 30,
                 retry_attempts: int = 3):
        self.environment = environment
        self.url = SERVIDORES[environment]
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.auth = SoapService(environment, timeout=timeout, retry_attempts=retry_attempts)
        self.session = requests.Session()

    def authenticate(self, certificate: DigitalCertificate) -> str:
        """Obtiene (o reutiliza) el token de los servicios DTEWS."""
        return self.auth.authenticate(certificate)

    # ------------------------------------------------------------------
    # Llamada SOAP (RPC/literal)
    # ------------------------------------------------------------------

    @staticmethod
    def _documento(rut_emisor: str, tipo_doc: Union[int, str], folio: Union[int, str]) -> Dict[str, str]:
        numero, dv = SoapService._split_rut(rut_emisor)
        if not str(folio).isdigit() or int(folio) <= 0:
            raise SiiValidationError(f'El folio {folio} no es válido.')
        return {'rutEmisor': numero, 'dvEmisor': dv, 'tipoDoc': str(int(tipo_doc)), 'folio': str(int(folio))}

    def _call(self, function: str, params: Dict[str, str]) -> ET.Element:
        """Llama una operación y entrega el nodo return de la respuesta."""
        if not self.auth.is_authenticated():
            raise SiiAuthenticationError('No hay token de autenticación. Debe autenticarse primero.')
        args = ''.join(f'<{name}>{escape(value)}</{name}>' for name, value in params.items())
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<soapenv:Body><ns1:{function} xmlns:ns1="{NAMESPACE}">{args}</ns1:{function}></soapenv:Body>'
            '</soapenv:Envelope>'
        )
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': '""',
            'Cookie': f'TOKEN={self.auth.auth_token}',
        }
        response = None
        for intento in range(self.retry_attempts):
            try:
                response = self.session.post(self.url, data=body.encode('utf-8'), headers=headers,
                                             timeout=self.timeout)
            except requests.RequestException as e:
                logger.warning(f'Error llamando {function} (intento {intento + 1}): {e}')
                response = None
                continue
            if response.status_code < 500 or b'Fault' in response.content:
                break
        if response is None:
            raise SiiCommunicationError(f'No hubo respuesta del SII en {function}.', endpoint=self.url)

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            raise SiiCommunicationError(f'Respuesta inválida del SII en {function} (HTTP {response.status_code}): {e}',
                                        status_code=response.status_code, endpoint=self.url)
        for node in root.iter():
            if _local(node.tag) == 'Fault':
                mensaje = next((n.text for n in node.iter() if _local(n.tag) in ('message', 'faultstring')), '')
                raise SiiCommunicationError(f'El SII respondió con error en {function}: {(mensaje or "").strip()}',
                                            status_code=response.status_code, endpoint=self.url)
        respuesta = next((n for n in root.iter() if _local(n.tag) == f'{function}Response'), None)
        if respuesta is None or len(respuesta) == 0:
            raise SiiCommunicationError(f'La respuesta del SII no contiene {function}Response.', endpoint=self.url)
        return respuesta[0]

    @staticmethod
    def _respuesta(nodo: ET.Element) -> Dict[str, Any]:
        """Interpreta un respuestaTo: codResp, descResp y listaEventosDoc."""
        def texto(padre: ET.Element, nombre: str) -> Optional[str]:
            hijo = next((n for n in padre if _local(n.tag) == nombre), None)
            return (hijo.text or '').strip() if hijo is not None else None

        codigo = texto(nodo, 'codResp')
        eventos: List[Dict[str, Any]] = []
        for evento in (n for n in nodo if _local(n.tag) == 'listaEventosDoc'):
            rut, dv = texto(evento, 'rutResponsable'), texto(evento, 'dvResponsable')
            eventos.append({
                'codigo': texto(evento, 'codEvento'),
                'descripcion': texto(evento, 'descEvento'),
                'responsable': f'{rut}-{dv}' if rut else None,
                'fecha': texto(evento, 'fechaEvento'),
            })
        return {
            'codigo': int(codigo) if codigo and codigo.lstrip('-').isdigit() else None,
            'descripcion': texto(nodo, 'descResp'),
            'eventos': eventos,
        }

    # ------------------------------------------------------------------
    # Operaciones
    # ------------------------------------------------------------------

    def registrar(self, rut_emisor: str, tipo_doc: Union[int, str], folio: Union[int, str],
                  accion: str) -> Dict[str, Any]:
        """
        Registra la aceptación o el reclamo de un documento recibido.

        Returns:
            {'ok', 'codigo', 'descripcion', 'eventos'}; ok es True solo si el
            SII respondió codResp 0. Otros códigos (p. ej. evento ya
            registrado o plazo vencido) se entregan con la glosa del SII.
        """
        accion = accion.upper()
        if accion not in ACCIONES:
            raise SiiValidationError(f'La acción {accion} no es válida. Opciones: {", ".join(ACCIONES)}.')
        if int(tipo_doc) not in TIPOS_DOCUMENTO:
            raise SiiValidationError(f'No se puede aceptar ni reclamar documentos tipo {tipo_doc}.')
        params = {**self._documento(rut_emisor, tipo_doc, folio), 'accionDoc': accion}
        respuesta = self._respuesta(self._call('ingresarAceptacionReclamoDoc', params))
        respuesta['ok'] = respuesta['codigo'] == 0
        logger.info(f'{accion} T{tipo_doc}F{folio} de {rut_emisor}: {respuesta["codigo"]} {respuesta["descripcion"]}')
        return respuesta

    def aceptar(self, rut_emisor: str, tipo_doc: Union[int, str], folio: Union[int, str],
                recibo_mercaderias: bool = False) -> Dict[str, Any]:
        """Acepta el contenido (ACD) o, con recibo_mercaderias, otorga el recibo (ERM)."""
        return self.registrar(rut_emisor, tipo_doc, folio, 'ERM' if recibo_mercaderias else 'ACD')

    def reclamar(self, rut_emisor: str, tipo_doc: Union[int, str], folio: Union[int, str],
                 accion: str = 'RCD') -> Dict[str, Any]:
        """Reclama el documento: RCD (contenido), RFP o RFT (falta parcial o total de mercaderías)."""
        if accion.upper() not in RECLAMOS:
            raise SiiValidationError(f'{accion} no es un reclamo. Opciones: {", ".join(RECLAMOS)}.')
        return self.registrar(rut_emisor, tipo_doc, folio, accion)

    def listar_eventos(self, rut_emisor: str, tipo_doc: Union[int, str], folio: Union[int, str]) -> Dict[str, Any]:
        """Historial de aceptaciones, reclamos y recibos del documento."""
        return self._respuesta(self._call('listarEventosHistDoc', self._documento(rut_emisor, tipo_doc, folio)))

    def consultar_cedible(self, rut_emisor: str, tipo_doc: Union[int, str], folio: Union[int, str]) -> Dict[str, Any]:
        """Indica si el documento se puede ceder, según su recibo o reclamos."""
        return self._respuesta(self._call('consultarDocDteCedible', self._documento(rut_emisor, tipo_doc, folio)))

    def fecha_recepcion(self, rut_emisor: str, tipo_doc: Union[int, str],
                        folio: Union[int, str]) -> Optional[datetime]:
        """Fecha y hora en que el SII recibió el documento (desde ahí corre el plazo de 8 días)."""
        nodo = self._call('consultarFechaRecepcionSii', self._documento(rut_emisor, tipo_doc, folio))
        texto = (nodo.text or '').strip()
        try:
            return datetime.strptime(texto, '%d-%m-%Y %H:%M:%S')
        except ValueError:
            if texto:
                logger.warning(f'Fecha de recepción no reconocida: {texto!r}')
            return None
