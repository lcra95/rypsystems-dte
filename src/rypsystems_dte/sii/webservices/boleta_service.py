"""
API REST de boletas electrónicas del SII.

Las boletas (39 y 41) no se envían por DTEUpload sino por la API REST de
boletas, con su propia semilla y token:

- Semilla:  GET  {api}/boleta.electronica.semilla
- Token:    POST {api}/boleta.electronica.token (getToken firmado, application/xml)
- Envío:    POST {envio}/boleta.electronica.envio (multipart, cookie TOKEN)
- Estado del envío: GET {api}/boleta.electronica.envio/{rut}-{dv}-{trackid}
- Estado de una boleta: GET {api}/boleta.electronica/{rut}-{dv}-{tipo}-{folio}/estado

Servidores: certificación apicert.sii.cl (envío en pangal.sii.cl) y
producción api.sii.cl (envío en rahue.sii.cl).
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

import requests

from ...firma.digital_certificate import DigitalCertificate
from ...firma.xml_signer import XmlSigner
from ...xml.encoder import XmlEncoder, save_xml
from .exceptions import SiiAuthenticationError, SiiCommunicationError, SiiValidationError
from .sii_endpoints import SiiEnvironment
from .soap_service import SoapService

logger = logging.getLogger(__name__)

SERVIDORES = {
    SiiEnvironment.CERTIFICACION: {'api': 'https://apicert.sii.cl/recursos/v1',
                                   'envio': 'https://pangal.sii.cl/recursos/v1'},
    SiiEnvironment.PRODUCCION: {'api': 'https://api.sii.cl/recursos/v1',
                                'envio': 'https://rahue.sii.cl/recursos/v1'},
}
USER_AGENT = 'Mozilla/5.0 (compatible; PROG 1.0; RypSystems DTE)'


def _tag(xml: str, tag: str) -> Optional[str]:
    match = re.search(rf'<(?:\w+:)?{tag}>\s*([^<]*?)\s*</(?:\w+:)?{tag}>', xml)
    return match.group(1) if match else None


class BoletaService:
    """
    Cliente de la API REST de boletas electrónicas.

    Ejemplo:
        service = BoletaService(SiiEnvironment.CERTIFICACION)
        service.authenticate(certificate)
        envio = service.upload(certificate.get_id(), '78532566-4', xml_envio_boleta)
        service.query_upload_status('78532566-4', envio['track_id'])
    """

    def __init__(self, environment: SiiEnvironment = SiiEnvironment.CERTIFICACION, timeout: int = 60,
                 retry_attempts: int = 3):
        self.environment = environment
        self.urls = SERVIDORES[environment]
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        last_error: Optional[Exception] = None
        for intento in range(self.retry_attempts):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as e:
                last_error = e
            else:
                # 5xx: el SII suele responder 503 de forma temporal.
                if response.status_code < 500:
                    return response
                last_error = SiiCommunicationError(f'HTTP {response.status_code} en {url}: {response.text[:200]}')
            if intento < self.retry_attempts - 1:
                time.sleep(2 ** intento)
        raise SiiCommunicationError(f'No fue posible comunicarse con {url}: {last_error}')

    def get_seed(self) -> str:
        """Obtiene una semilla de la API de boletas."""
        response = self._request('GET', f'{self.urls["api"]}/boleta.electronica.semilla',
                                 headers={'Accept': 'application/xml'})
        estado, semilla = _tag(response.text, 'ESTADO'), _tag(response.text, 'SEMILLA')
        if response.status_code != 200 or estado != '00' or not semilla:
            raise SiiAuthenticationError(f'No fue posible obtener la semilla (estado {estado}): {response.text[:300]}')
        return semilla

    def get_token(self, signed_seed: Union[str, bytes]) -> str:
        """Canjea el getToken firmado por un token."""
        if isinstance(signed_seed, str):
            signed_seed = signed_seed.encode('iso-8859-1', errors='xmlcharrefreplace')
        response = self._request('POST', f'{self.urls["api"]}/boleta.electronica.token', data=signed_seed,
                                 headers={'Content-Type': 'application/xml', 'Accept': 'application/xml'})
        estado, token = _tag(response.text, 'ESTADO'), _tag(response.text, 'TOKEN')
        if response.status_code != 200 or estado != '00' or not token:
            glosa = _tag(response.text, 'GLOSA')
            raise SiiAuthenticationError(f'No fue posible obtener el token (estado {estado}): {glosa or response.text[:300]}')
        return token

    def authenticate(self, certificate: DigitalCertificate, token_ttl: int = 3000) -> str:
        """Obtiene (o reutiliza mientras esté vigente) el token de la API de boletas."""
        if self.is_authenticated():
            return self.token
        # Mismo getToken firmado que el servicio SOAP (GetTokenFromSeed).
        xml = save_xml(XmlEncoder().encode({'getToken': {'item': {'Semilla': int(self.get_seed())}}}))
        signed = XmlSigner().sign_xml(xml, certificate)
        self.token = self.get_token(signed)
        self.token_expires = datetime.now() + timedelta(seconds=token_ttl)
        return self.token

    def is_authenticated(self) -> bool:
        return bool(self.token) and self.token_expires is not None and datetime.now() < self.token_expires

    def _auth_headers(self) -> Dict[str, str]:
        if not self.is_authenticated():
            raise SiiAuthenticationError('No hay token de la API de boletas. Debe autenticarse primero.')
        return {'Cookie': f'TOKEN={self.token}', 'Accept': 'application/json'}

    @staticmethod
    def _split_rut(rut: str):
        return SoapService._split_rut(rut)

    def _json(self, response: requests.Response) -> Dict[str, Any]:
        if response.status_code == 401:
            self.token = None
            raise SiiAuthenticationError('El SII rechazó el token de la API de boletas (HTTP 401).')
        try:
            return response.json()
        except ValueError as e:
            raise SiiCommunicationError(f'Respuesta no JSON del SII (HTTP {response.status_code}): '
                                        f'{response.text[:300]}') from e

    # ------------------------------------------------------------------
    # Envío y consultas
    # ------------------------------------------------------------------

    def upload(self, rut_sender: str, rut_company: str, xml: Union[str, bytes],
               filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Sube un EnvioBOLETA firmado.

        Returns:
            {'track_id', 'estado', 'fecha_recepcion', 'response'}
        """
        if isinstance(xml, str):
            xml = xml.encode('iso-8859-1', errors='xmlcharrefreplace')
        if b'<EnvioBOLETA' not in xml[:500]:
            raise SiiValidationError('Por la API de boletas solo se puede enviar un EnvioBOLETA.')
        rut_s, dv_s = self._split_rut(rut_sender)
        rut_c, dv_c = self._split_rut(rut_company)
        filename = filename or f'{rut_company}_{datetime.now().strftime("%Y%m%d%H%M%S")}.xml'
        response = self._request(
            'POST', f'{self.urls["envio"]}/boleta.electronica.envio',
            headers=self._auth_headers(),
            data={'rutSender': rut_s, 'dvSender': dv_s, 'rutCompany': rut_c, 'dvCompany': dv_c},
            files={'archivo': (filename, xml, 'application/xml')},
        )
        data = self._json(response)
        track_id = data.get('trackid')
        if response.status_code != 200 or not track_id:
            raise SiiValidationError(f'El SII no recibió el envío de boletas (HTTP {response.status_code}): {data}')
        return {'track_id': int(track_id), 'estado': data.get('estado'),
                'fecha_recepcion': data.get('fecha_recepcion'), 'response': data}

    def query_upload_status(self, rut_company: str, track_id: Union[int, str]) -> Dict[str, Any]:
        """
        Estado de un envío de boletas.

        Returns:
            {'estado', 'estadistica', 'detalle', 'response'}; estadistica con
            informados/aceptados/rechazados/reparos por tipo y detalle con los
            documentos con reparos o rechazados y sus errores.
        """
        rut, dv = self._split_rut(rut_company)
        response = self._request('GET', f'{self.urls["api"]}/boleta.electronica.envio/{rut}-{dv}-{track_id}',
                                 headers=self._auth_headers())
        data = self._json(response)
        if response.status_code != 200:
            raise SiiValidationError(f'No fue posible consultar el envío {track_id} (HTTP {response.status_code}): {data}')
        return {
            'estado': data.get('estado'),
            'estadistica': data.get('estadistica') or [],
            'detalle': data.get('detalle_rep_rech') or [],
            'response': data,
        }

    def query_document_status(self, rut_emisor: str, tipo: int, folio: int, rut_receptor: str, monto: int,
                              fecha_emision: str) -> Dict[str, Any]:
        """Estado de una boleta (fecha_emision AAAA-MM-DD)."""
        rut, dv = self._split_rut(rut_emisor)
        rut_r, dv_r = self._split_rut(rut_receptor)
        fecha = datetime.strptime(fecha_emision, '%Y-%m-%d').strftime('%d-%m-%Y')
        response = self._request(
            'GET', f'{self.urls["api"]}/boleta.electronica/{rut}-{dv}-{int(tipo)}-{int(folio)}/estado',
            headers=self._auth_headers(),
            params={'rut_receptor': rut_r, 'dv_receptor': dv_r, 'monto': int(monto), 'fechaEmision': fecha},
        )
        data = self._json(response)
        if response.status_code != 200:
            raise SiiValidationError(f'No fue posible consultar la boleta {tipo} {folio} '
                                     f'(HTTP {response.status_code}): {data}')
        return data
