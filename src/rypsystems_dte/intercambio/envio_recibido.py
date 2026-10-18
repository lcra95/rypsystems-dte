"""
Lectura y validación de un EnvioDTE recibido en un intercambio.

Determina el estado de recepción del envío y de cada documento según los
códigos de RespuestaEnvioDTE_v10.xsd (EstadoRecepEnv y EstadoRecepDTE).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from lxml import etree

from ..firma.ted import TEDValidator
from ..firma.xml_signer import SignatureError, XmlSigner
from ..xml.canonical import parse, to_bytes
from ..xml.schema import schema_errors
from ..errors import RypDteError


class IntercambioError(RypDteError):
    """Error en el intercambio de información."""


def _text(node: etree._Element, path: str) -> Optional[str]:
    xpath = '/'.join(f'*[local-name()="{p}"]' for p in path.split('/'))
    value = node.xpath(f'string(./{xpath})').strip()
    return value or None


def _normalizar_rut(rut: Optional[str]) -> str:
    return (rut or '').replace('.', '').strip().upper()


@dataclass
class DocumentoRecibido:
    """DTE incluido en un envío recibido, con su estado de recepción."""

    xml: bytes
    tipo: int
    folio: int
    fecha_emision: str
    rut_emisor: str
    rut_receptor: str
    monto_total: int
    estado: int = 0
    glosa: str = 'DTE Recibido OK'
    errores: List[str] = field(default_factory=list)

    def resumen(self) -> Dict[str, Any]:
        """Datos de identificación del DTE (para RecepcionDTE, ResultadoDTE y Recibo)."""
        return {
            'TipoDTE': self.tipo,
            'Folio': self.folio,
            'FchEmis': self.fecha_emision,
            'RUTEmisor': self.rut_emisor,
            'RUTRecep': self.rut_receptor,
            'MntTotal': self.monto_total,
        }


class EnvioRecibido:
    """
    EnvioDTE recibido de un emisor.

    Ejemplo:
        envio = EnvioRecibido(xml, nombre='ENVIO_DTE_123.xml')
        envio.validar(rut_receptor='78532566-4')
        envio.estado, envio.glosa, envio.documentos
    """

    def __init__(self, xml: Union[str, bytes], nombre: str = 'EnvioDTE.xml'):
        self.xml = to_bytes(xml)
        self.nombre = nombre[:80]
        try:
            self.tree = parse(self.xml)
        except etree.XMLSyntaxError as e:
            raise IntercambioError(f'El archivo {nombre} no es un XML válido: {e}') from e
        root = self.tree.getroot()
        if etree.QName(root).localname not in ('EnvioDTE', 'EnvioBOLETA'):
            raise IntercambioError(f'El archivo {nombre} no es un EnvioDTE.')
        sets = root.xpath('./*[local-name()="SetDTE"]')
        if not sets:
            raise IntercambioError(f'El archivo {nombre} no tiene SetDTE.')
        self.set_dte = sets[0]
        caratula = self.set_dte.xpath('./*[local-name()="Caratula"]')[0]
        self.id = self.set_dte.get('ID', '')
        self.rut_emisor = _text(caratula, 'RutEmisor')
        self.rut_envia = _text(caratula, 'RutEnvia')
        self.rut_receptor = _text(caratula, 'RutReceptor')
        self.digest = root.xpath(
            'string(./*[local-name()="Signature"]//*[local-name()="Reference"][@URI=$uri]'
            '/*[local-name()="DigestValue"])', uri=f'#{self.id}',
        ).strip() or None
        self.estado = 0
        self.glosa = 'Envio Recibido Conforme'
        self.errores: List[str] = []
        self._firmas = None
        self.documentos = [self._documento(dte) for dte in self.set_dte.xpath('./*[local-name()="DTE"]')]

    @staticmethod
    def _documento(dte: etree._Element) -> DocumentoRecibido:
        enc = dte.xpath('.//*[local-name()="Encabezado"]')[0]
        return DocumentoRecibido(
            xml=etree.tostring(dte, encoding='ISO-8859-1'),
            tipo=int(_text(enc, 'IdDoc/TipoDTE')),
            folio=int(_text(enc, 'IdDoc/Folio')),
            fecha_emision=_text(enc, 'IdDoc/FchEmis'),
            rut_emisor=_text(enc, 'Emisor/RUTEmisor'),
            rut_receptor=_text(enc, 'Receptor/RUTRecep'),
            monto_total=int(float(_text(enc, 'Totales/MntTotal') or 0)),
        )

    def _firma_valida(self, reference: str) -> bool:
        if self._firmas is None:
            try:
                self._firmas = XmlSigner().validate_xml(self.xml)
            except SignatureError:
                self._firmas = []
        resultados = [r for r in self._firmas if (r.reference or '').lstrip('#') == reference]
        return bool(resultados) and all(r.is_valid for r in resultados)

    @staticmethod
    def _timbre_valido(dte: etree._Element) -> bool:
        from ..pdf.dte_pdf import ted_pdf417  # TED aislado, sin el namespace del sobre
        ted = ted_pdf417(dte)
        return bool(ted) and TEDValidator.verify_ted_signature(ted)

    def validar(self, rut_receptor: str, validar_schema: bool = True,
                validar_timbre: bool = True) -> 'EnvioRecibido':
        """
        Valida el envío y sus documentos y asigna los estados de recepción.

        Args:
            rut_receptor: RUT de quien recibe (el contribuyente que responde)
            validar_schema: Validar contra EnvioDTE_v10.xsd
            validar_timbre: Verificar la firma del TED con la clave del CAF. Los
                documentos del set de intercambio del SII traen un timbre que no
                verifica (se generan con la fecha del día y el receptor).
        """
        rut_receptor = _normalizar_rut(rut_receptor)
        tag = etree.QName(self.tree.getroot()).localname
        if validar_schema:
            schema = 'EnvioDTE_v10.xsd' if tag == 'EnvioDTE' else 'EnvioBOLETA_v11.xsd'
            errores = schema_errors(self.xml, schema)
            if errores:
                self.estado, self.glosa, self.errores = 1, 'Envio Rechazado - Error de Schema', errores
        if self.estado == 0 and not self._firma_valida(self.id):
            self.estado, self.glosa = 2, 'Envio Rechazado - Error de Firma'
        if self.estado == 0 and _normalizar_rut(self.rut_receptor) != rut_receptor:
            self.estado, self.glosa = 3, 'Envio Rechazado - RUT Receptor No Corresponde'

        vistos = set()
        for doc in self.documentos:
            clave = (doc.rut_emisor, doc.tipo, doc.folio)
            dte = parse(doc.xml)
            documento_id = dte.getroot().xpath('string(./*[local-name()="Documento" or '
                                               'local-name()="Exportaciones" or local-name()="Liquidacion"]/@ID)')
            if not self._firma_valida(documento_id):
                doc.estado, doc.glosa = 1, 'DTE No Recibido - Error de Firma'
            elif _normalizar_rut(doc.rut_emisor) != _normalizar_rut(self.rut_emisor):
                doc.estado, doc.glosa = 2, 'DTE No Recibido - Error en RUT Emisor'
            elif _normalizar_rut(doc.rut_receptor) != rut_receptor:
                doc.estado, doc.glosa = 3, 'DTE No Recibido - Error en RUT Receptor'
            elif clave in vistos:
                doc.estado, doc.glosa = 4, 'DTE No Recibido - DTE Repetido'
            elif validar_timbre and not self._timbre_valido(dte.getroot()):
                doc.estado, doc.glosa = 99, 'DTE No Recibido - Timbre electronico no valido'
            vistos.add(clave)
        return self
