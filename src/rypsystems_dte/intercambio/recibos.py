"""
Acuse de recibo de mercaderías o servicios (EnvioRecibos_v10.xsd).

Basado en EnvioRecibos de LibreDTE clásico: cada Recibo se firma por separado
(nodo DocumentoRecibo) y luego se firma el SetRecibos que los contiene.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..firma.digital_certificate import DigitalCertificate
from ..firma.xml_signer import XmlSigner
from ..xml.encoder import XmlEncoder, save_xml
from .envio_recibido import IntercambioError
from .respuesta import SII_DTE_NAMESPACE, XSI_NAMESPACE

SET_ID = 'LibreDTE_SetDteRecibidos'
DECLARACION_RECIBO = (
    'El acuse de recibo que se declara en este acto, de acuerdo a lo dispuesto en la letra b) del Art. 4, '
    'y la letra c) del Art. 5 de la Ley 19.983, acredita que la entrega de mercaderias o servicio(s) '
    'prestado(s) ha(n) sido recibido(s).'
)
_DECLARATION_RE = re.compile(rb'^\s*<\?xml[^>]*\?>\s*')


class EnvioRecibos:
    """
    Envío de recibos de mercaderías.

    Ejemplo:
        recibos = EnvioRecibos(rut_responde='78532566-4', rut_recibe='88888888-8')
        recibos.agregar(documento.resumen(), recinto='Oficina central', certificate=certificate)
        xml = recibos.generar(certificate)
    """

    def __init__(
        self,
        rut_responde: str,
        rut_recibe: str,
        nombre_contacto: Optional[str] = None,
        fono_contacto: Optional[str] = None,
        mail_contacto: Optional[str] = None,
    ):
        self.rut_responde = rut_responde
        self.rut_recibe = rut_recibe
        self.contacto = {
            'NmbContacto': nombre_contacto[:40] if nombre_contacto else False,
            'FonoContacto': fono_contacto[:40] if fono_contacto else False,
            'MailContacto': mail_contacto[:80] if mail_contacto else False,
        }
        self.recibos: List[bytes] = []

    def agregar(
        self,
        documento: Dict[str, Any],
        recinto: str,
        certificate: DigitalCertificate,
        timestamp: Optional[str] = None,
    ) -> bytes:
        """
        Agrega (y firma) el recibo de un documento.

        Args:
            documento: TipoDTE (o TipoDoc), Folio, FchEmis, RUTEmisor, RUTRecep y MntTotal
            recinto: Lugar donde se recibieron las mercaderías o servicios
            certificate: Certificado de quien firma el recibo (RutFirma)
        """
        if not recinto:
            raise IntercambioError('El recibo debe indicar el recinto donde se recibieron las mercaderías.')
        tipo = documento.get('TipoDoc', documento.get('TipoDTE'))
        recibo_id = f'LibreDTE_T{tipo}F{documento["Folio"]}'
        data = {
            'Recibo': {
                '@attributes': {
                    'xmlns': SII_DTE_NAMESPACE,
                    'xmlns:xsi': XSI_NAMESPACE,
                    'xsi:schemaLocation': f'{SII_DTE_NAMESPACE} Recibos_v10.xsd',
                    'version': '1.0',
                },
                'DocumentoRecibo': {
                    '@attributes': {'ID': recibo_id},
                    'TipoDoc': tipo,
                    'Folio': documento['Folio'],
                    'FchEmis': documento['FchEmis'],
                    'RUTEmisor': documento['RUTEmisor'],
                    'RUTRecep': documento['RUTRecep'],
                    'MntTotal': documento['MntTotal'],
                    'Recinto': recinto[:80],
                    'RutFirma': certificate.get_id(),
                    'Declaracion': DECLARACION_RECIBO,
                    'TmstFirmaRecibo': timestamp or datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                },
            }
        }
        xml = save_xml(XmlEncoder().encode(data))
        recibo = XmlSigner().sign_xml(xml, certificate, recibo_id, xmlns_xsi=True)
        self.recibos.append(_DECLARATION_RE.sub(b'', recibo).strip())
        return recibo

    def generar(self, certificate: DigitalCertificate, timestamp: Optional[str] = None) -> bytes:
        """Genera el XML del envío de recibos firmado."""
        if not self.recibos:
            raise IntercambioError('El envío no tiene recibos.')
        data = {
            'EnvioRecibos': {
                '@attributes': {
                    'xmlns': SII_DTE_NAMESPACE,
                    'xmlns:xsi': XSI_NAMESPACE,
                    'xsi:schemaLocation': f'{SII_DTE_NAMESPACE} EnvioRecibos_v10.xsd',
                    'version': '1.0',
                },
                'SetRecibos': {
                    '@attributes': {'ID': SET_ID},
                    'Caratula': {
                        '@attributes': {'version': '1.0'},
                        'RutResponde': self.rut_responde,
                        'RutRecibe': self.rut_recibe,
                        **self.contacto,
                        'TmstFirmaEnv': timestamp or datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                    },
                    'Recibo': '',
                },
            }
        }
        base = save_xml(XmlEncoder().encode(data))
        if base.count(b'<Recibo/>') != 1:
            raise IntercambioError('No fue posible ubicar los recibos dentro del envío.')
        xml = base.replace(b'<Recibo/>', b'\n'.join(self.recibos))
        return XmlSigner().sign_xml(xml, certificate, SET_ID, xmlns_xsi=True)
