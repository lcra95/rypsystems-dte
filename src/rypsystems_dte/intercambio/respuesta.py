"""
Respuesta de intercambio (RespuestaDTE, RespuestaEnvioDTE_v10.xsd).

Basado en RespuestaEnvio de LibreDTE clásico. Una respuesta contiene la
recepción de uno o más envíos (RecepcionEnvio) o el resultado de la
aprobación comercial de documentos (ResultadoDTE), nunca ambos.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..firma.digital_certificate import DigitalCertificate
from ..firma.xml_signer import XmlSigner
from ..xml.encoder import XmlEncoder, save_xml
from .envio_recibido import EnvioRecibido, IntercambioError

SII_DTE_NAMESPACE = 'http://www.sii.cl/SiiDte'
XSI_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
RESULTADO_ID = 'LibreDTE_ResultadoEnvio'

ESTADOS_RECEPCION_ENVIO = {
    0: 'Envio Recibido Conforme',
    1: 'Envio Rechazado - Error de Schema',
    2: 'Envio Rechazado - Error de Firma',
    3: 'Envio Rechazado - RUT Receptor No Corresponde',
    90: 'Envio Rechazado - Archivo Repetido',
    91: 'Envio Rechazado - Archivo Ilegible',
    99: 'Envio Rechazado - Otros',
}
ESTADOS_RECEPCION_DTE = {
    0: 'DTE Recibido OK',
    1: 'DTE No Recibido - Error de Firma',
    2: 'DTE No Recibido - Error en RUT Emisor',
    3: 'DTE No Recibido - Error en RUT Receptor',
    4: 'DTE No Recibido - DTE Repetido',
    99: 'DTE No Recibido - Otros',
}
ESTADOS_DTE = {
    0: 'DTE Aceptado OK',
    1: 'DTE Aceptado con Discrepancias',
    2: 'DTE Rechazado',
}


class RespuestaEnvio:
    """
    RespuestaDTE firmada.

    Ejemplo (acuse de recibo del envío):
        respuesta = RespuestaEnvio(rut_responde='78532566-4', rut_recibe='88888888-8')
        respuesta.agregar_recepcion_envio(envio, cod_envio=1)
        xml = respuesta.generar(certificate)

    Ejemplo (aprobación comercial):
        respuesta.agregar_resultado_dte(documento.resumen(), cod_envio=1, estado=0)
    """

    def __init__(
        self,
        rut_responde: str,
        rut_recibe: str,
        id_respuesta: int = 1,
        nombre_contacto: Optional[str] = None,
        fono_contacto: Optional[str] = None,
        mail_contacto: Optional[str] = None,
    ):
        self.rut_responde = rut_responde
        self.rut_recibe = rut_recibe
        self.id_respuesta = int(id_respuesta)
        self.contacto = {
            'NmbContacto': nombre_contacto[:40] if nombre_contacto else False,
            'FonoContacto': fono_contacto[:40] if fono_contacto else False,
            'MailContacto': mail_contacto[:80] if mail_contacto else False,
        }
        self.recepciones: List[Dict[str, Any]] = []
        self.resultados: List[Dict[str, Any]] = []

    def agregar_recepcion_envio(
        self,
        envio: EnvioRecibido,
        cod_envio: int,
        fecha_recepcion: Optional[str] = None,
        estado: Optional[int] = None,
        glosa: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Agrega la recepción de un envío, con el estado de cada uno de sus DTE.

        Si el envío fue rechazado no se informan sus documentos.
        """
        if self.resultados:
            raise IntercambioError('Una respuesta no puede tener recepción de envíos y resultados de DTE.')
        estado = envio.estado if estado is None else int(estado)
        recepcion = {
            'NmbEnvio': envio.nombre,
            'FchRecep': fecha_recepcion or datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'CodEnvio': int(cod_envio),
            'EnvioDTEID': envio.id,
            'Digest': envio.digest or False,
            'RutEmisor': envio.rut_emisor or False,
            'RutReceptor': envio.rut_receptor or False,
            'EstadoRecepEnv': estado,
            'RecepEnvGlosa': (glosa or (envio.glosa if estado == envio.estado else ESTADOS_RECEPCION_ENVIO[estado]))[:256],
            'NroDTE': False,
            'RecepcionDTE': False,
        }
        if estado == 0:
            recepcion['NroDTE'] = len(envio.documentos)
            recepcion['RecepcionDTE'] = [
                {**doc.resumen(), 'EstadoRecepDTE': doc.estado, 'RecepDTEGlosa': doc.glosa[:256]}
                for doc in envio.documentos
            ]
        self.recepciones.append(recepcion)
        return recepcion

    def agregar_resultado_dte(
        self,
        documento: Dict[str, Any],
        cod_envio: int,
        estado: int = 0,
        glosa: Optional[str] = None,
        codigo_rechazo: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Agrega el resultado de la aprobación comercial de un DTE.

        Args:
            documento: TipoDTE, Folio, FchEmis, RUTEmisor, RUTRecep y MntTotal
            estado: 0 aceptado, 1 aceptado con discrepancias, 2 rechazado
            codigo_rechazo: Código (negativo, p. ej. -1) del motivo de rechazo o discrepancia
        """
        if self.recepciones:
            raise IntercambioError('Una respuesta no puede tener recepción de envíos y resultados de DTE.')
        if int(estado) not in ESTADOS_DTE:
            raise IntercambioError(f'Estado de aprobación comercial {estado} no válido.')
        if codigo_rechazo is not None and not -999 <= int(codigo_rechazo) < 0:
            raise IntercambioError('El código de rechazo o discrepancia debe ser un entero negativo.')
        campos = ('TipoDTE', 'Folio', 'FchEmis', 'RUTEmisor', 'RUTRecep', 'MntTotal')
        resultado = {campo: documento[campo] for campo in campos}
        resultado.update({
            'CodEnvio': int(cod_envio),
            'EstadoDTE': int(estado),
            'EstadoDTEGlosa': (glosa or ESTADOS_DTE[int(estado)])[:256],
            'CodRchDsc': int(codigo_rechazo) if codigo_rechazo is not None and int(estado) else False,
        })
        self.resultados.append(resultado)
        return resultado

    def generar(self, certificate: DigitalCertificate, timestamp: Optional[str] = None) -> bytes:
        """Genera el XML de la respuesta firmado."""
        if not self.recepciones and not self.resultados:
            raise IntercambioError('La respuesta no tiene recepciones de envíos ni resultados de DTE.')
        detalle = ('RecepcionEnvio', self.recepciones) if self.recepciones else ('ResultadoDTE', self.resultados)
        data = {
            'RespuestaDTE': {
                '@attributes': {
                    'xmlns': SII_DTE_NAMESPACE,
                    'xmlns:xsi': XSI_NAMESPACE,
                    'xsi:schemaLocation': f'{SII_DTE_NAMESPACE} RespuestaEnvioDTE_v10.xsd',
                    'version': '1.0',
                },
                'Resultado': {
                    '@attributes': {'ID': RESULTADO_ID},
                    'Caratula': {
                        '@attributes': {'version': '1.0'},
                        'RutResponde': self.rut_responde,
                        'RutRecibe': self.rut_recibe,
                        'IdRespuesta': self.id_respuesta,
                        'NroDetalles': len(detalle[1]),
                        **self.contacto,
                        'TmstFirmaResp': timestamp or datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                    },
                    detalle[0]: detalle[1],
                },
            }
        }
        xml = save_xml(XmlEncoder().encode(data))
        return XmlSigner().sign_xml(xml, certificate, RESULTADO_ID, xmlns_xsi=True)
