"""
Interfaz pública de emisión de DTE.

Reúne en pocas funciones el flujo completo, sin archivos ni estado global (el
folio, el CAF y el certificado los entrega quien llama), para usarse desde un
servicio con varias empresas y concurrencia:

    doc = emitir_documento(datos, caf, certificado)       # normaliza, timbra, firma y valida
    envio = armar_envio([doc], certificado, '2026-10-17', 0)
    sii = ClienteSii(certificado, SiiEnvironment.CERTIFICACION)
    track_id = sii.enviar(envio, '78532566-4')
    sii.consultar_envio(track_id, '78532566-4', boletas=doc.es_boleta)

    nc = anular(doc, folio=15, caf=caf_61, certificado=certificado)

Las boletas (39 y 41) se arman en un EnvioBOLETA y se envían por la API REST
de boletas; el resto en un EnvioDTE por DTEUpload. ClienteSii elige el
servicio según el sobre.
"""

import copy
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Union

from lxml import etree

from .dte import DocumentBag, DocumentEnvelope, DTEBuilder
from .errors import RypDteError
from .tipo_cambio import ProveedorTipoCambio, TipoCambioError, completar_tipo_cambio
from .firma import DigitalCertificate, XmlSigner
from .firma.ted import TEDValidator
from .identifier import Caf
from .sii.webservices.boleta_service import BoletaService
from .sii.webservices.sii_endpoints import SiiEnvironment
from .sii.webservices.soap_service import SoapService
from .xml.schema import schema_errors

BOLETAS = (39, 41)

# Documento que anula a cada tipo (CodRef 1).
DOCUMENTO_ANULACION = {
    33: 61, 34: 61, 39: 61, 41: 61, 43: 61, 46: 61, 56: 61,
    61: 56,
    110: 112, 111: 112,
    112: 111,
}

# Estados finales de un envío: procesado o rechazado (los códigos numéricos
# negativos o positivos de QueryEstUp también son errores finales).
ESTADOS_FINALES = ('EPR', 'RSC', 'RFR', 'RCT', 'RCH', 'RPT', 'RCS', 'RLV')

# Nodos del documento que pueden repetirse (se leen siempre como lista).
_LISTAS = {'Detalle', 'Referencia', 'DscRcgGlobal', 'Comisiones', 'ImptoReten', 'CdgItem', 'SubDscto',
           'SubRecargo', 'Subcantidad', 'OtrosImp'}
# Campos de texto que no se convierten a número aunque lo parezcan.
_TEXTO = {'RUTEmisor', 'RUTRecep', 'RUTSolicita', 'RUTTrans', 'RUTChofer', 'CdgSIISucur', 'Acteco', 'VlrCodigo',
          'Telefono', 'Contacto', 'FolioRef', 'IdAdicEmisor', 'NumId', 'Patente', 'CodAdicSucur'}


class EmisionError(RypDteError):
    """El documento no se pudo emitir (datos, CAF, folio, esquema, timbre o firma)."""


@dataclass
class DocumentoEmitido:
    """DTE timbrado y firmado."""

    tipo: int
    folio: int
    xml: bytes
    datos: Dict[str, Any] = field(repr=False)

    @property
    def es_boleta(self) -> bool:
        return self.tipo in BOLETAS

    @property
    def fecha(self) -> str:
        return self.datos['Encabezado']['IdDoc']['FchEmis']

    @property
    def emisor(self) -> str:
        return self.datos['Encabezado']['Emisor']['RUTEmisor']

    @property
    def receptor(self) -> Optional[str]:
        return (self.datos['Encabezado'].get('Receptor') or {}).get('RUTRecep')

    @property
    def totales(self) -> Dict[str, Any]:
        return self.datos['Encabezado']['Totales']

    @classmethod
    def desde_xml(cls, xml: Union[str, bytes]) -> 'DocumentoEmitido':
        """Reconstruye el documento desde el XML firmado de un DTE."""
        if isinstance(xml, str):
            xml = xml.encode('iso-8859-1', errors='xmlcharrefreplace')
        datos = documento_a_datos(xml)
        id_doc = datos['Encabezado']['IdDoc']
        return cls(int(id_doc['TipoDTE']), int(id_doc['Folio']), xml, datos)


def _valor(nombre: str, texto: str) -> Any:
    if nombre in _TEXTO or not re.fullmatch(r'-?(0|[1-9]\d*)(\.\d+)?', texto):
        return texto
    return float(texto) if '.' in texto else int(texto)


def _nodo_a_dict(nodo: etree._Element) -> Any:
    hijos = [h for h in nodo if isinstance(h.tag, str)]
    if not hijos:
        return _valor(etree.QName(nodo).localname, (nodo.text or '').strip())
    resultado: Dict[str, Any] = {}
    for hijo in hijos:
        nombre = etree.QName(hijo).localname
        valor = _nodo_a_dict(hijo)
        if nombre in _LISTAS:
            resultado.setdefault(nombre, []).append(valor)
        elif nombre in resultado:
            if not isinstance(resultado[nombre], list):
                resultado[nombre] = [resultado[nombre]]
            resultado[nombre].append(valor)
        else:
            resultado[nombre] = valor
    return resultado


def documento_a_datos(xml: bytes) -> Dict[str, Any]:
    """Datos (Encabezado, Detalle, Referencia...) del nodo Documento de un DTE, sin TED ni firma."""
    root = etree.fromstring(xml)
    documento = root.xpath('//*[local-name()="Documento" or local-name()="Exportaciones" or '
                           'local-name()="Liquidacion"]')
    if not documento:
        raise EmisionError('El XML no contiene un DTE.')
    datos = _nodo_a_dict(documento[0])
    for nodo in ('TED', 'TmstFirma'):
        datos.pop(nodo, None)
    return datos


def emitir_documento(datos: Dict[str, Any], caf: Caf, certificado: DigitalCertificate, *,
                     validar: bool = True, tipo_cambio: Optional[ProveedorTipoCambio] = None) -> DocumentoEmitido:
    """
    Normaliza, timbra y firma un documento.

    Args:
        datos: Encabezado (con IdDoc.TipoDTE e IdDoc.Folio), Detalle y, si
            corresponde, Referencia, DscRcgGlobal, Comisiones... en el formato
            del normalizador. Los totales se calculan desde el detalle.
        caf: CAF del tipo del documento que contiene el folio.
        certificado: Certificado con el que se firma el DTE.
        validar: Valida esquema (DTE_v10; las boletas se validan dentro del
            EnvioBOLETA), timbre y firma.
        tipo_cambio: Proveedor del tipo de cambio (rypsystems_dte.tipo_cambio)
            para los documentos de exportación que no traen TpoCambio.

    Raises:
        EmisionError
    """
    try:
        id_doc = datos['Encabezado']['IdDoc']
        tipo, folio = int(id_doc['TipoDTE']), int(id_doc['Folio'])
        rut_emisor = datos['Encabezado']['Emisor']['RUTEmisor']
    except (KeyError, TypeError, ValueError) as e:
        raise EmisionError(f'Faltan datos obligatorios del documento: {e}') from e
    if caf.get_tipo_documento() != tipo:
        raise EmisionError(f'El CAF es del tipo {caf.get_tipo_documento()} y el documento es del tipo {tipo}.')
    if caf.get_emisor()['rut'] != rut_emisor:
        raise EmisionError(f'El CAF es de {caf.get_emisor()["rut"]} y el emisor es {rut_emisor}.')
    if not caf.en_rango(folio):
        raise EmisionError(f'El folio {folio} no está en el CAF ({caf.get_folio_desde()} a {caf.get_folio_hasta()}).')

    datos = copy.deepcopy(datos)
    datos['Encabezado']['IdDoc'].setdefault('FchEmis', date.today().isoformat())
    if tipo_cambio is not None:
        try:
            completar_tipo_cambio(datos, tipo_cambio)
        except TipoCambioError as e:
            raise EmisionError(f'T{tipo} F{folio}: {e}') from e
    bag = DocumentBag(tipo, datos)
    bag.set_caf(caf)
    bag.set_certificate(certificado)
    try:
        DTEBuilder().build(bag)
    except Exception as e:
        raise EmisionError(f'No fue posible generar el documento T{tipo} F{folio}: {e}') from e
    xml = bag.get_xml()

    if validar:
        errores = [] if tipo in BOLETAS else schema_errors(xml, 'DTE_v10.xsd')
        if errores:
            raise EmisionError(f'T{tipo} F{folio} no cumple el esquema: {"; ".join(errores[:3])}')
        if not TEDValidator.verify_ted_signature(xml, caf):
            raise EmisionError(f'T{tipo} F{folio}: el timbre no es válido.')
        if not XmlSigner().is_valid_xml(xml):
            raise EmisionError(f'T{tipo} F{folio}: la firma no es válida.')
    return DocumentoEmitido(tipo, folio, xml, bag.get_datos())


def armar_envio(documentos: Iterable[Union[DocumentoEmitido, bytes]], certificado: DigitalCertificate,
                fecha_resolucion: str, numero_resolucion: int = 0, *, validar: bool = True) -> bytes:
    """
    Arma y firma el sobre (EnvioDTE, o EnvioBOLETA si son boletas) para el SII.

    Raises:
        EmisionError
    """
    sobre = DocumentEnvelope(certificado, str(fecha_resolucion), numero_resolucion)
    try:
        for documento in documentos:
            sobre.add_document(documento.xml if isinstance(documento, DocumentoEmitido) else documento)
        envio = sobre.build()
    except Exception as e:
        raise EmisionError(f'No fue posible armar el envío: {e}') from e
    if validar:
        errores = schema_errors(envio, sobre.get_schema())
        if errores:
            raise EmisionError(f'El {sobre.get_tag()} no cumple el esquema: {"; ".join(errores[:3])}')
        invalidas = [r for r in XmlSigner().validate_xml(envio) if not r.is_valid]
        if invalidas:
            raise EmisionError('Firmas inválidas en el envío: ' + ', '.join(f'{r.reference}: {r.error}'
                                                                           for r in invalidas))
    return envio


def anular(original: Union[DocumentoEmitido, bytes], folio: int, caf: Caf, certificado: DigitalCertificate, *,
           razon: str = 'ANULA DOCUMENTO', fecha: Optional[str] = None) -> DocumentoEmitido:
    """
    Emite el documento que anula a otro (CodRef 1): nota de crédito para
    facturas, boletas y notas de débito; nota de débito para notas de crédito
    (y sus equivalentes de exportación). Copia receptor, detalle, descuentos y
    datos de exportación del original para que los montos coincidan.

    Raises:
        EmisionError: Si el tipo no se anula con una nota (p. ej. guías de despacho)
    """
    if not isinstance(original, DocumentoEmitido):
        original = DocumentoEmitido.desde_xml(original)
    tipo = DOCUMENTO_ANULACION.get(original.tipo)
    if not tipo:
        raise EmisionError(f'Los documentos tipo {original.tipo} no se anulan con una nota de crédito o débito.')

    encabezado = copy.deepcopy(original.datos['Encabezado'])
    encabezado.pop('Totales', None)
    id_original = encabezado.pop('IdDoc')
    id_doc = {'TipoDTE': tipo, 'Folio': int(folio), 'FchEmis': fecha or date.today().isoformat()}
    for campo in ('IndServicio', 'IndMntNeto', 'FmaPagExp', 'TpoTranVenta', 'TpoTranCompra'):
        if id_original.get(campo) not in (None, ''):
            id_doc[campo] = id_original[campo]
    encabezado['IdDoc'] = id_doc
    if encabezado.get('Totales') is None and original.totales.get('TpoMoneda'):
        encabezado['Totales'] = {'TpoMoneda': original.totales['TpoMoneda']}
    if isinstance(encabezado.get('OtraMoneda'), dict):
        encabezado['OtraMoneda'] = {k: v for k, v in encabezado['OtraMoneda'].items()
                                    if k in ('TpoMoneda', 'TpoCambio')}

    detalle = []
    for item in copy.deepcopy(original.datos.get('Detalle') or []):
        for calculado in ('NroLinDet', 'MontoItem'):
            item.pop(calculado, None)
        detalle.append(item)
    if not detalle:
        raise EmisionError('El documento original no tiene detalle.')

    datos = {
        'Encabezado': encabezado,
        'Detalle': detalle,
        'DscRcgGlobal': copy.deepcopy(original.datos.get('DscRcgGlobal')) or False,
        'Referencia': [{
            'TpoDocRef': original.tipo, 'FolioRef': original.folio, 'FchRef': original.fecha,
            'CodRef': 1, 'RazonRef': razon,
        }],
    }
    for item in datos['DscRcgGlobal'] or []:
        item.pop('NroLinDR', None)
    if tipo in (111, 112):
        # Las notas de exportación repiten las referencias aduaneras del
        # original (p. ej. 812 resolución SNA en exportación de servicios).
        for ref in original.datos.get('Referencia') or []:
            if str(ref.get('TpoDocRef', '')).isdigit() and int(ref['TpoDocRef']) >= 800:
                datos['Referencia'].append({k: v for k, v in ref.items() if k != 'NroLinRef'})
    return emitir_documento(datos, caf, certificado)


class ClienteSii:
    """
    Comunicación con el SII para un certificado y ambiente: autentica (y
    reutiliza el token) en DTEUpload y en la API de boletas, envía y consulta.
    """

    def __init__(self, certificado: DigitalCertificate,
                 ambiente: SiiEnvironment = SiiEnvironment.CERTIFICACION, timeout: int = 60):
        self.certificado = certificado
        self.ambiente = ambiente
        self.timeout = timeout
        self._dte: Optional[SoapService] = None
        self._boletas: Optional[BoletaService] = None

    def servicio_dte(self) -> SoapService:
        if self._dte is None:
            self._dte = SoapService(self.ambiente, timeout=self.timeout)
        self._dte.authenticate(self.certificado)
        return self._dte

    def servicio_boletas(self) -> BoletaService:
        if self._boletas is None:
            self._boletas = BoletaService(self.ambiente, timeout=self.timeout)
        self._boletas.authenticate(self.certificado)
        return self._boletas

    @staticmethod
    def es_envio_boletas(envio: bytes) -> bool:
        return etree.QName(etree.fromstring(envio)).localname == 'EnvioBOLETA'

    def enviar(self, envio: bytes, rut_empresa: str) -> int:
        """Sube el sobre al SII y entrega el Track ID."""
        if self.es_envio_boletas(envio):
            respuesta = self.servicio_boletas().upload(self.certificado.get_id(), rut_empresa, envio)
        else:
            respuesta = self.servicio_dte().upload_dte(self.certificado.get_id(), rut_empresa, envio)
        return int(respuesta['track_id'])

    def consultar_envio(self, track_id: Union[int, str], rut_empresa: str, *, boletas: bool = False) -> Dict[str, Any]:
        """
        Estado de un envío, igual para DTE y boletas.

        Returns:
            {'estado', 'final', 'informados', 'aceptados', 'rechazados',
            'reparos', 'detalle', 'respuesta'}; final indica que el SII ya
            terminó de procesar el envío (aceptado o rechazado).
        """
        if boletas:
            r = self.servicio_boletas().query_upload_status(rut_empresa, track_id)
            totales = {k: sum(int(e.get(k) or 0) for e in r['estadistica'])
                       for k in ('informados', 'aceptados', 'rechazados', 'reparos')}
            detalle = r['detalle']
        else:
            r = self.servicio_dte().query_upload_status(rut_empresa, track_id)
            totales = {k: int(r.get(k) or 0) for k in ('informados', 'aceptados', 'rechazados', 'reparos')}
            detalle = r.get('detalle') or []
        estado = r.get('estado')
        final = estado in ESTADOS_FINALES or bool(re.fullmatch(r'-?\d+', estado or ''))
        return {'estado': estado, 'final': final, **totales, 'detalle': detalle, 'respuesta': r}

    def consultar_documento(self, documento: DocumentoEmitido) -> Dict[str, Any]:
        """Estado de un documento en el SII (QueryEstDte o la API de boletas)."""
        receptor = documento.receptor or '66666666-6'
        monto = int(documento.totales.get('MntTotal') or 0)
        if documento.es_boleta:
            return self.servicio_boletas().query_document_status(
                documento.emisor, documento.tipo, documento.folio, receptor, monto, documento.fecha)
        return self.servicio_dte().query_document_status(
            self.certificado.get_id(), documento.emisor, documento.tipo, documento.folio,
            fecha_emision=documento.fecha, monto=monto, rut_receptor=receptor)
