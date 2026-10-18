"""
Sobre de envío de documentos (EnvioDTE / EnvioBOLETA).

Traducción de DispatcherWorker y DocumentEnvelope de LibreDTE PHP: arma la
carátula, incorpora los DTE ya firmados (sin modificar sus bytes, para no
invalidar sus firmas) y firma el SetDTE con el certificado de quien envía.
"""

import re
from collections import OrderedDict
from datetime import datetime
from typing import List, Optional, Union

from lxml import etree

from ..firma.digital_certificate import DigitalCertificate
from ..firma.ted import expand_empty_dd_tags
from ..firma.xml_signer import XmlSigner
from ..xml.encoder import XmlEncoder, save_xml
from ..errors import RypDteError

SII_DTE_NAMESPACE = 'http://www.sii.cl/SiiDte'
XSI_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
RUT_SII = '60803000-K'
SET_ID = 'LibreDTE_SetDoc'

_TIPOS_SOBRE = {
    'EnvioDTE': {'schema': 'EnvioDTE_v10.xsd', 'max_tipos': 20, 'max_dte': 2000},
    'EnvioBOLETA': {'schema': 'EnvioBOLETA_v11.xsd', 'max_tipos': 2, 'max_dte': 1000},
}
_BOLETAS = (39, 41)
_DECLARATION_RE = re.compile(rb'^\s*<\?xml[^>]*\?>\s*')


class EnvelopeError(RypDteError):
    """Error al armar o firmar un sobre de envío."""


class DocumentEnvelope:
    """
    Sobre de envío de DTE.

    Ejemplo:
        envelope = DocumentEnvelope(certificate, fecha_resolucion='2026-10-17', numero_resolucion=0)
        envelope.add_document(xml_dte_firmado)
        xml_envio = envelope.build()
    """

    def __init__(
        self,
        certificate: DigitalCertificate,
        fecha_resolucion: str,
        numero_resolucion: int = 0,
        rut_receptor: str = RUT_SII,
        rut_emisor: Optional[str] = None,
        rut_envia: Optional[str] = None,
    ):
        """
        Args:
            certificate: Certificado de quien envía (firma el sobre)
            fecha_resolucion: Fecha de la resolución del SII que autoriza a
                emitir DTE (en certificación, la que indica el SII al postular)
            numero_resolucion: Número de resolución (0 en certificación)
            rut_receptor: Quien recibe el sobre: el SII (60803000-K) o el
                receptor de los documentos en un intercambio
            rut_emisor: RUT del emisor. Por defecto el del primer documento
            rut_envia: RUT de quien envía. Por defecto el del certificado
        """
        self.certificate = certificate
        self.fecha_resolucion = fecha_resolucion
        self.numero_resolucion = int(numero_resolucion)
        self.rut_receptor = rut_receptor
        self.rut_emisor = rut_emisor
        self.rut_envia = rut_envia
        self._documents: List[bytes] = []
        self._tipos: List[int] = []
        self._emisores: List[str] = []

    def add_document(self, xml: Union[str, bytes]) -> 'DocumentEnvelope':
        """
        Agrega un DTE firmado al sobre.

        Raises:
            EnvelopeError: Si el XML no es un DTE o mezcla boletas con otros DTE
        """
        if isinstance(xml, str):
            xml = xml.encode('iso-8859-1', errors='xmlcharrefreplace')
        try:
            root = etree.fromstring(xml)
        except etree.XMLSyntaxError as e:
            raise EnvelopeError(f'El XML del documento no es válido: {e}') from e
        if etree.QName(root).localname != 'DTE':
            raise EnvelopeError('Solo se pueden agregar documentos DTE al sobre.')

        tipo = root.xpath('string(.//*[local-name()="IdDoc"]/*[local-name()="TipoDTE"])')
        emisor = root.xpath('string(.//*[local-name()="Emisor"]/*[local-name()="RUTEmisor"])')
        if not tipo:
            raise EnvelopeError('No fue posible determinar el tipo del documento.')
        tipo = int(tipo)
        if self._tipos and (tipo in _BOLETAS) != (self._tipos[0] in _BOLETAS):
            raise EnvelopeError('No se pueden mezclar boletas con otros DTE en un mismo sobre.')
        if self._emisores and emisor != self._emisores[0]:
            raise EnvelopeError('Todos los documentos del sobre deben ser del mismo emisor.')

        tag = self.get_tag()
        if len(self._documents) >= _TIPOS_SOBRE[tag]['max_dte']:
            raise EnvelopeError(f'No se pueden agregar más de {_TIPOS_SOBRE[tag]["max_dte"]} documentos al sobre.')

        self._documents.append(_DECLARATION_RE.sub(b'', xml).strip())
        self._tipos.append(tipo)
        self._emisores.append(emisor)
        return self

    def get_tag(self) -> str:
        return 'EnvioBOLETA' if self._tipos and self._tipos[0] in _BOLETAS else 'EnvioDTE'

    def get_schema(self) -> str:
        return _TIPOS_SOBRE[self.get_tag()]['schema']

    def get_resumen(self) -> List[dict]:
        """Cantidad de documentos por tipo (SubTotDTE), en orden de aparición."""
        subtotales = OrderedDict()
        for tipo in self._tipos:
            subtotales[tipo] = subtotales.get(tipo, 0) + 1
        return [{'TpoDTE': tipo, 'NroDTE': cantidad} for tipo, cantidad in subtotales.items()]

    def get_caratula(self, timestamp: str) -> dict:
        resumen = self.get_resumen()
        maximo = _TIPOS_SOBRE[self.get_tag()]['max_tipos']
        if len(resumen) > maximo:
            raise EnvelopeError(
                f'Se agregaron más tipos de documentos de los que son permitidos en el sobre ({maximo}).'
            )
        return {
            '@attributes': {'version': '1.0'},
            'RutEmisor': self.rut_emisor or self._emisores[0],
            'RutEnvia': self.rut_envia or self.certificate.get_id(),
            'RutReceptor': self.rut_receptor,
            'FchResol': self.fecha_resolucion,
            'NroResol': self.numero_resolucion,
            'TmstFirmaEnv': timestamp,
            'SubTotDTE': resumen,
        }

    def build(self, timestamp: Optional[str] = None) -> bytes:
        """
        Arma y firma el sobre.

        Args:
            timestamp: Marca de tiempo de la firma (Y-m-dTH:i:s). Por defecto ahora.

        Returns:
            XML del sobre firmado en ISO-8859-1

        Raises:
            EnvelopeError: Si no hay documentos o el certificado no está vigente
        """
        if not self._documents:
            raise EnvelopeError('El sobre no tiene documentos.')

        timestamp = timestamp or datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        certificate = self.certificate
        if not certificate.is_active(timestamp):
            raise EnvelopeError(
                f'El certificado digital de {certificate.get_id()} no está vigente en el tiempo '
                f'{datetime.fromisoformat(timestamp).strftime("%d/%m/%Y %H:%M")}, su rango de vigencia es del '
                f'{datetime.fromisoformat(certificate.get_from()).strftime("%d/%m/%Y %H:%M")} al '
                f'{datetime.fromisoformat(certificate.get_to()).strftime("%d/%m/%Y %H:%M")}.'
            )

        tag = self.get_tag()
        data = {
            tag: {
                '@attributes': {
                    'xmlns': SII_DTE_NAMESPACE,
                    'xmlns:xsi': XSI_NAMESPACE,
                    'xsi:schemaLocation': f'{SII_DTE_NAMESPACE} {self.get_schema()}',
                    'version': '1.0',
                },
                'SetDTE': {
                    '@attributes': {'ID': SET_ID},
                    'Caratula': self.get_caratula(timestamp),
                    'DTE': '',
                },
            }
        }

        # Igual que PHP: se codifica la estructura con un <DTE/> vacío que se
        # reemplaza por los XML de los documentos tal cual fueron firmados.
        base = save_xml(XmlEncoder().encode(data))
        if base.count(b'<DTE/>') != 1:
            raise EnvelopeError('No fue posible ubicar los documentos dentro del sobre.')
        xml = base.replace(b'<DTE/>', b'\n'.join(self._documents))

        return expand_empty_dd_tags(XmlSigner().sign_xml(xml, certificate, SET_ID, xmlns_xsi=True))
