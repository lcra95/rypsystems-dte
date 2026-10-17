"""
Normalización de datos de documentos tributarios.

Traducción del NormalizerWorker de LibreDTE PHP (estrategias por tipo de
documento, jobs de pre y post normalización y traits de detalle, descuentos
y recargos, impuestos adicionales, IVA y totales, transporte y boletas), más
sanitizeEssentials() del SanitizerWorker.

A partir de datos mínimos (receptor, ítems con cantidad y precio) completa
la estructura del DTE en el orden del esquema del SII y calcula montos por
ítem, neto, exento, IVA, impuestos adicionales y total.

Para mantener exactamente los mismos resultados que PHP se replican sus
semánticas: round() redondea alejándose de cero, false/null/'' suman como 0,
empty('0') es verdadero y los valores False no generan nodos en el XML.

No soportado aún: liquidación factura (43).
"""

import json
from copy import deepcopy
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

Number = Union[int, float]

_RESOURCES = Path(__file__).resolve().parent.parent / 'resources' / 'data'

BOLETAS = (39, 41)
EXPORTACION = (110, 111, 112)
NO_SOPORTADOS = (43,)


class NormalizerError(ValueError):
    """Error al normalizar los datos de un documento."""


# ----------------------------------------------------------------------
# Semánticas de PHP
# ----------------------------------------------------------------------

def php_empty(value: Any) -> bool:
    """empty() de PHP: None, False, 0, 0.0, '', '0', [] y {} son vacíos."""
    if value is None or value is False:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 0
    if isinstance(value, str):
        return value == '' or value == '0'
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def php_bool(value: Any) -> bool:
    """Conversión a booleano de PHP (if ($x))."""
    return not php_empty(value) or value is True


def num(value: Any) -> Number:
    """Valor numérico como en las operaciones aritméticas de PHP (false/null/'' = 0)."""
    if value is None or value is False or value == '':
        return 0
    if value is True:
        return 1
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        return int(text) if text.lstrip('-').isdigit() else float(text)
    except ValueError:
        return 0


def php_int(value: Any) -> int:
    """Cast (int) de PHP: trunca hacia cero."""
    return int(num(value))


def php_round(value: Any, precision: int = 0) -> float:
    """
    round() de PHP: redondea la mitad alejándose de cero y considera el
    valor decimal "visible" (round(1.005, 2) = 1.01). Entrega un float.
    """
    value = num(value)
    quantum = Decimal(1).scaleb(-precision)
    return float(Decimal(repr(float(value))).quantize(quantum, rounding=ROUND_HALF_UP))


def php_eq(value: Any, number: Number) -> bool:
    """Comparación flexible (==) de PHP contra un número."""
    if value is None or value is False:
        return number == 0
    if value is True:
        return number != 0
    try:
        return float(value) == float(number)
    except (TypeError, ValueError):
        return False


def php_str(value: Any) -> str:
    """Conversión a string de PHP (false/null = '')."""
    if value is None or value is False:
        return ''
    if value is True:
        return '1'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def array_merge(defaults: Dict[str, Any], data: Any) -> Dict[str, Any]:
    """
    array_merge() de PHP con claves string: el orden es el de defaults, los
    valores de data reemplazan y sus claves nuevas se agregan al final.
    """
    result = dict(defaults)
    if isinstance(data, dict):
        result.update(data)
    return result


def array_replace_recursive(base: Any, replacement: Any) -> Any:
    """
    array_replace_recursive() de PHP: reemplaza recursivamente manteniendo
    el orden de las claves de base y agregando al final las nuevas.
    """
    if isinstance(base, list) and isinstance(replacement, list):
        result = list(base)
        for i, value in enumerate(replacement):
            if i < len(result):
                result[i] = array_replace_recursive(result[i], value)
            else:
                result.append(deepcopy(value))
        return result
    if not isinstance(base, dict) or not isinstance(replacement, dict):
        return deepcopy(replacement)
    result = dict(base)
    for key, value in replacement.items():
        if key in result and isinstance(result[key], (dict, list)) and isinstance(value, (dict, list)):
            result[key] = array_replace_recursive(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def as_list(value: Any) -> List[Any]:
    """Equivale a: if (!isset($x[0])) $x = [$x];"""
    return value if isinstance(value, list) else [value]


def utils_round(amount: Any, currency: Any = None, decimals: int = 4) -> Number:
    """Utils::round(): pesos chilenos a entero, otras monedas con decimales."""
    if not currency or currency == 'PESO CL':
        return int(php_round(amount))
    return php_round(amount, decimals)


def calcular_neto_iva(total: Any, tasa: Any) -> List[Number]:
    """Utils::calcularNetoIVA(): separa un monto bruto en neto e IVA."""
    if tasa is False or tasa == 0 or tasa is None:
        return [0, 0]
    neto = php_round(num(total) / (1 + (num(tasa) / 100)))
    return [neto, num(total) - neto]


def _today() -> str:
    return date.today().isoformat()


def _date_from_timestamp(value: Any) -> Any:
    # Compatibilidad (no está en PHP): objetos fecha y fechas con hora.
    if isinstance(value, (date, datetime)):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, str) and len(value) > 10 and value[10] in 'T ' and value[:4].isdigit():
        return value[:10]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value).strftime('%Y-%m-%d')
    if isinstance(value, str) and value.strip().isdigit() and len(value.strip()) > 8:
        return datetime.fromtimestamp(int(value)).strftime('%Y-%m-%d')
    return value


# ----------------------------------------------------------------------
# Datos de referencia
# ----------------------------------------------------------------------

_IMPUESTOS: Optional[Dict[int, Dict[str, Any]]] = None


def impuesto_adicional(codigo: Any) -> Dict[str, Any]:
    """Impuesto adicional (A) o retención (R) por su código."""
    global _IMPUESTOS
    if _IMPUESTOS is None:
        raw = json.loads((_RESOURCES / 'impuestos_adicionales_retenciones.json').read_text(encoding='utf-8'))
        _IMPUESTOS = {int(k): v for k, v in raw.items()}
    try:
        return _IMPUESTOS[int(num(codigo))]
    except KeyError:
        raise NormalizerError(f'No existe el impuesto adicional o retención con código {codigo}.')


def default_tasa_iva(codigo: int) -> Union[int, bool]:
    return 19 if codigo not in (34, 41, 110, 111, 112) else False


def requiere_tpo_tran_venta(codigo: int) -> bool:
    return codigo not in (39, 41, 110, 111, 112)


def default_ind_servicio(codigo: int) -> Union[int, bool]:
    return 3 if codigo in BOLETAS else False


# ----------------------------------------------------------------------
# Normalizador
# ----------------------------------------------------------------------

ProviderFn = Callable[[Dict[str, Any]], Dict[str, Any]]


class DocumentNormalizer:
    """
    Normalizador de datos de DTE.

    Ejemplo:
        datos = DocumentNormalizer().normalize({
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1},
                'Emisor': {...},
                'Receptor': {...},
            },
            'Detalle': [{'NmbItem': 'Producto', 'QtyItem': 2, 'PrcItem': 1000}],
        })
        datos['Encabezado']['Totales']  # MntNeto 2000, IVA 380, MntTotal 2380

    Igual que en PHP, los totales se calculan desde el detalle: si además se
    entregan MntNeto o MntExe, los montos del detalle se suman a ellos. Para
    entregar un documento con todo ya calculado, desactive la normalización
    (opción del builder normalize=False).

    Los proveedores opcionales de emisor y receptor completan datos faltantes
    (equivalen a EmisorProvider y ReceptorProvider). Reciben los datos del
    nodo y entregan un diccionario con las claves: razon_social, giro,
    telefono, email, actividad_economica, direccion, comuna, codigo_sucursal
    y vendedor (emisor) o razon_social, giro, telefono, email, direccion y
    comuna (receptor).
    """

    def __init__(
        self,
        emisor_provider: Optional[ProviderFn] = None,
        receptor_provider: Optional[ProviderFn] = None,
    ):
        self.emisor_provider = emisor_provider
        self.receptor_provider = receptor_provider

    def normalize(self, datos: Dict[str, Any], codigo: Optional[int] = None) -> Dict[str, Any]:
        """
        Normaliza los datos de un documento. No modifica el diccionario entregado.

        Args:
            datos: Datos del documento (Encabezado, Detalle, ...)
            codigo: Tipo de documento. Por defecto Encabezado/IdDoc/TipoDTE.

        Returns:
            Datos normalizados (los valores False no generan nodos en el XML)

        Raises:
            NormalizerError: Si el tipo no está soportado o faltan datos esenciales
        """
        data = deepcopy(datos)
        if codigo is None:
            codigo = php_int(((data.get('Encabezado') or {}).get('IdDoc') or {}).get('TipoDTE'))
        codigo = int(codigo)
        if codigo in NO_SOPORTADOS:
            raise NormalizerError(f'La normalización del documento tipo {codigo} aún no está soportada.')
        if codigo not in (33, 34, 39, 41, 46, 52, 56, 61, 110, 111, 112):
            raise NormalizerError(f'El tipo de documento {codigo} no es válido.')
        data.pop('Test', None)
        self._compat_input(data)

        data = self._pre_normalization(data, codigo)
        data = self._normalize_document(data, codigo)
        data = self._post_normalization(data)
        return data

    @staticmethod
    def _compat_input(data: Dict[str, Any]) -> None:
        """
        Conversiones de compatibilidad con la API Python anterior (no están en
        PHP y no cambian sus resultados): números entregados como texto en
        cantidades y precios del detalle, y RUT sin guion.
        """
        from ..sii.utils import RutValidator

        for d in as_list(data.get('Detalle') or []):
            if not isinstance(d, dict):
                continue
            for tag in ('QtyItem', 'PrcItem'):
                value = d.get(tag)
                if isinstance(value, str) and _is_numeric(value):
                    number = float(value)
                    d[tag] = number if tag == 'QtyItem' or not number.is_integer() else int(number)
        encabezado = data.get('Encabezado') or {}
        for nodo, tag in (('Emisor', 'RUTEmisor'), ('Receptor', 'RUTRecep')):
            rut = (encabezado.get(nodo) or {}).get(tag)
            if isinstance(rut, (str, int)) and rut and RutValidator.validate(rut):
                encabezado[nodo][tag] = RutValidator.format(rut)

    # ------------------------------------------------------------------
    # NormalizeDataPreDocumentNormalizationJob
    # ------------------------------------------------------------------

    def _pre_normalization(self, data: Dict[str, Any], codigo: int) -> Dict[str, Any]:
        data = array_replace_recursive({
            'Encabezado': {
                'IdDoc': {
                    'TipoDTE': False,
                    'Folio': False,
                    'FchEmis': _today(),
                    'IndNoRebaja': False,
                    'TipoDespacho': False,
                    'IndTraslado': False,
                    'TpoImpresion': False,
                    'IndServicio': default_ind_servicio(codigo),
                    'MntBruto': False,
                    'TpoTranCompra': False,
                    'TpoTranVenta': False,
                    'FmaPago': False,
                    'FmaPagExp': False,
                    'MntCancel': False,
                    'SaldoInsol': False,
                    'FchCancel': False,
                    'MntPagos': False,
                    'PeriodoDesde': False,
                    'PeriodoHasta': False,
                    'MedioPago': False,
                    'TpoCtaPago': False,
                    'NumCtaPago': False,
                    'BcoPago': False,
                    'TermPagoCdg': False,
                    'TermPagoGlosa': False,
                    'TermPagoDias': False,
                    'FchVenc': False,
                },
                'Emisor': {
                    'RUTEmisor': False,
                    'RznSoc': False,
                    'GiroEmis': False,
                    'Telefono': False,
                    'CorreoEmisor': False,
                    'Acteco': False,
                    'GuiaExport': False,
                    'Sucursal': False,
                    'CdgSIISucur': False,
                    'DirOrigen': False,
                    'CmnaOrigen': False,
                    'CiudadOrigen': False,
                    'CdgVendedor': False,
                    'IdAdicEmisor': False,
                },
                'Receptor': {
                    'RUTRecep': False,
                    'CdgIntRecep': False,
                    'RznSocRecep': False,
                    'Extranjero': False,
                    'GiroRecep': False,
                    'Contacto': False,
                    'CorreoRecep': False,
                    'DirRecep': False,
                    'CmnaRecep': False,
                    'CiudadRecep': False,
                    'DirPostal': False,
                    'CmnaPostal': False,
                    'CiudadPostal': False,
                },
                'Totales': {
                    'TpoMoneda': False,
                },
            },
            'Detalle': False,
            'SubTotInfo': False,
            'DscRcgGlobal': False,
            'Referencia': False,
            'Comisiones': False,
        }, data)

        id_doc = data['Encabezado']['IdDoc']
        for tag in ('FchEmis', 'FchCancel', 'FchVenc'):
            id_doc[tag] = _date_from_timestamp(id_doc[tag])

        if not php_empty(data['DscRcgGlobal']):
            data['DscRcgGlobal'] = [
                array_merge({'NroLinDR': i}, dr) for i, dr in enumerate(as_list(data['DscRcgGlobal']), start=1)
            ]

        if not php_empty(data['Referencia']):
            referencias = []
            for i, r in enumerate(as_list(data['Referencia']), start=1):
                r = array_merge({
                    'NroLinRef': i,
                    'TpoDocRef': False,
                    'IndGlobal': False,
                    'FolioRef': False,
                    'RUTOtr': False,
                    'FchRef': _today(),
                    'CodRef': False,
                    'RazonRef': False,
                }, r)
                r['FchRef'] = _date_from_timestamp(r['FchRef'])
                referencias.append(r)
            data['Referencia'] = referencias

        if requiere_tpo_tran_venta(codigo) and php_empty(id_doc['TpoTranVenta']):
            id_doc['TpoTranVenta'] = 1

        self._normalize_emisor(data)
        self._normalize_receptor(data)
        return data

    def _normalize_emisor(self, data: Dict[str, Any]) -> None:
        emisor = data['Encabezado']['Emisor']
        provided = self.emisor_provider(dict(emisor)) if self.emisor_provider else {}
        for tag, key in (
            ('RznSoc', 'razon_social'), ('GiroEmis', 'giro'), ('Telefono', 'telefono'),
            ('CorreoEmisor', 'email'), ('Acteco', 'actividad_economica'), ('DirOrigen', 'direccion'),
            ('CmnaOrigen', 'comuna'), ('CdgSIISucur', 'codigo_sucursal'), ('CdgVendedor', 'vendedor'),
        ):
            emisor[tag] = emisor.get(tag) if php_bool(emisor.get(tag)) else (provided.get(key) or False)

    def _normalize_receptor(self, data: Dict[str, Any]) -> None:
        receptor = data['Encabezado']['Receptor']
        provided = self.receptor_provider(dict(receptor)) if self.receptor_provider else {}
        for tag, key in (
            ('RznSocRecep', 'razon_social'), ('GiroRecep', 'giro'), ('Contacto', 'telefono'),
            ('CorreoRecep', 'email'), ('DirRecep', 'direccion'), ('CmnaRecep', 'comuna'),
        ):
            receptor[tag] = receptor.get(tag) if php_bool(receptor.get(tag)) else (provided.get(key) or False)

    # ------------------------------------------------------------------
    # Jobs por tipo de documento
    # ------------------------------------------------------------------

    def _normalize_document(self, data: Dict[str, Any], codigo: int) -> Dict[str, Any]:
        tasa = default_tasa_iva(codigo)

        if codigo == 33:
            data = array_replace_recursive({'Encabezado': {
                'IdDoc': False, 'Emisor': False, 'RUTMandante': False, 'Receptor': False,
                'RUTSolicita': False, 'Transporte': False,
                'Totales': {
                    'MntNeto': 0, 'MntExe': False, 'TasaIVA': tasa, 'IVA': 0, 'ImptoReten': False,
                    'CredEC': False, 'MntTotal': 0,
                },
                'OtraMoneda': False,
            }}, data)
            self._detalle(data, codigo)
            self._descuentos_recargos(data, codigo)
            self._impuesto_adicional_retencion(data)
            self._iva_mnt_total(data, codigo)
            self._transporte(data)

        elif codigo == 34:
            data = array_replace_recursive({'Encabezado': {
                'IdDoc': False, 'Emisor': False, 'Receptor': False, 'RUTSolicita': False,
                'Totales': {'MntExe': 0, 'MntTotal': 0},
            }}, data)
            self._detalle(data, codigo)
            self._descuentos_recargos(data, codigo)
            self._iva_mnt_total(data, codigo)

        elif codigo in (56, 61):
            data = array_replace_recursive({'Encabezado': {
                'IdDoc': False, 'Emisor': False, 'Receptor': False, 'RUTSolicita': False,
                'Totales': {
                    'MntNeto': 0, 'MntExe': 0, 'TasaIVA': tasa, 'IVA': False, 'ImptoReten': False,
                    'IVANoRet': False, 'CredEC': False, 'MntTotal': 0,
                },
            }}, data)
            self._detalle(data, codigo)
            self._descuentos_recargos(data, codigo)
            self._impuesto_adicional_retencion(data)
            self._iva_mnt_total(data, codigo)
            totales = data['Encabezado']['Totales']
            if not php_bool(totales['MntNeto']):
                totales['MntNeto'] = 0
                totales['TasaIVA'] = False

        elif codigo == 52:
            data = array_replace_recursive({'Encabezado': {
                'IdDoc': False, 'Emisor': False, 'Receptor': False, 'RUTSolicita': False, 'Transporte': False,
                'Totales': {
                    'MntNeto': 0, 'MntExe': False, 'TasaIVA': tasa, 'IVA': 0, 'ImptoReten': False,
                    'CredEC': False, 'MntTotal': 0,
                },
            }}, data)
            self._guia_traslado_interno(data)
            self._detalle(data, codigo)
            self._descuentos_recargos(data, codigo)
            self._impuesto_adicional_retencion(data)
            self._iva_mnt_total(data, codigo)
            self._transporte(data)

        elif codigo == 46:
            data = array_replace_recursive({'Encabezado': {
                'IdDoc': False, 'Emisor': False, 'Receptor': False, 'RUTSolicita': False,
                'Totales': {
                    'MntNeto': 0, 'MntExe': False, 'TasaIVA': tasa, 'IVA': 0, 'ImptoReten': False,
                    'IVANoRet': False, 'MntTotal': 0,
                },
            }}, data)
            self._detalle(data, codigo)
            self._descuentos_recargos(data, codigo)
            self._impuesto_adicional_retencion(data)
            self._iva_mnt_total(data, codigo)

        elif codigo == 39:
            data = array_replace_recursive({'Encabezado': {
                'IdDoc': False,
                'Emisor': {'RUTEmisor': False, 'RznSocEmisor': False, 'GiroEmisor': False},
                'Receptor': False,
                'Totales': {'MntNeto': False, 'MntExe': False, 'IVA': False, 'MntTotal': 0},
            }}, data)
            self._boletas(data)
            self._detalle(data, codigo)
            self._descuentos_recargos(data, codigo)
            self._iva_mnt_total(data, codigo)

        elif codigo == 41:
            data = array_replace_recursive({'Encabezado': {
                'IdDoc': False,
                'Emisor': {'RUTEmisor': False, 'RznSocEmisor': False, 'GiroEmisor': False},
                'Receptor': False,
                'Totales': {'MntExe': 0, 'MntTotal': 0},
            }}, data)
            self._boletas(data)
            self._detalle(data, codigo)
            self._descuentos_recargos(data, codigo)
            self._iva_mnt_total(data, codigo)

        elif codigo in EXPORTACION:
            data = array_replace_recursive({'Encabezado': {
                'IdDoc': False, 'Emisor': False, 'Receptor': False,
                'Transporte': {
                    'Patente': False, 'RUTTrans': False, 'Chofer': False, 'DirDest': False, 'CmnaDest': False,
                    'CiudadDest': False,
                    'Aduana': {
                        'CodModVenta': False, 'CodClauVenta': False, 'TotClauVenta': False, 'CodViaTransp': False,
                        'NombreTransp': False, 'RUTCiaTransp': False, 'NomCiaTransp': False, 'IdAdicTransp': False,
                        'Booking': False, 'Operador': False, 'CodPtoEmbarque': False, 'IdAdicPtoEmb': False,
                        'CodPtoDesemb': False, 'IdAdicPtoDesemb': False, 'Tara': False, 'CodUnidMedTara': False,
                        'PesoBruto': False, 'CodUnidPesoBruto': False, 'PesoNeto': False, 'CodUnidPesoNeto': False,
                        'TotItems': False, 'TotBultos': False, 'TipoBultos': False, 'MntFlete': False,
                        'MntSeguro': False, 'CodPaisRecep': False, 'CodPaisDestin': False,
                    },
                },
                'Totales': {'TpoMoneda': None, 'MntExe': 0, 'MntTotal': 0},
            }}, data)
            self._detalle(data, codigo)
            self._descuentos_recargos(data, codigo)
            self._impuesto_adicional_retencion(data)
            self._iva_mnt_total(data, codigo)
            self._exportacion(data)

        return data

    @staticmethod
    def _exportacion(data: Dict[str, Any]) -> None:
        """NormalizeExportacionTrait."""
        encabezado = data['Encabezado']
        aduana = encabezado['Transporte']['Aduana']
        id_doc = encabezado['IdDoc']
        ind_servicio = id_doc.get('IndServicio')
        if php_empty(aduana.get('CodModVenta')) and (
            ind_servicio is None or ind_servicio is False or php_int(ind_servicio) not in (3, 4, 5)
        ):
            aduana['CodModVenta'] = 1
        encabezado['Receptor']['CmnaRecep'] = False
        if not php_empty(id_doc.get('FmaPago')):
            formas = {3: 21}
            if php_int(id_doc['FmaPago']) in formas:
                id_doc['FmaPagExp'] = formas[php_int(id_doc['FmaPago'])]
            id_doc['FmaPago'] = False
        if not php_empty(id_doc.get('FmaPagExp')) and php_eq(id_doc['FmaPagExp'], 21) \
                and not php_empty(encabezado.get('OtraMoneda')):
            encabezado['OtraMoneda'] = as_list(encabezado['OtraMoneda'])
            for otra in encabezado['OtraMoneda']:
                if otra.get('TpoMoneda') == 'PESO CL':
                    otra['TpoCambio'] = 0

    @staticmethod
    def _guia_traslado_interno(data: Dict[str, Any]) -> None:
        """Guía con IndTraslado 5 (traslado interno): el receptor es el emisor."""
        encabezado = data['Encabezado']
        if not php_eq(encabezado['IdDoc'].get('IndTraslado'), 5):
            return
        receptor, emisor = encabezado.get('Receptor'), encabezado['Emisor']
        if not receptor or receptor.get('RUTRecep') != emisor.get('RUTEmisor'):
            receptor = {}
            for tag_emisor, tag_receptor in (
                ('RUTEmisor', 'RUTRecep'), ('RznSoc', 'RznSocRecep'), ('GiroEmis', 'GiroRecep'),
                ('Telefono', 'Contacto'), ('CorreoEmisor', 'CorreoRecep'), ('DirOrigen', 'DirRecep'),
                ('CmnaOrigen', 'CmnaRecep'),
            ):
                if not php_empty(emisor.get(tag_emisor)):
                    receptor[tag_receptor] = emisor[tag_emisor]
            if not php_empty(receptor.get('GiroRecep')):
                receptor['GiroRecep'] = php_str(receptor['GiroRecep'])[:40]
            encabezado['Receptor'] = receptor

    # ------------------------------------------------------------------
    # NormalizeDetalleTrait
    # ------------------------------------------------------------------

    def _detalle(self, data: Dict[str, Any], codigo: int) -> None:
        totales = data['Encabezado']['Totales']
        moneda = totales.get('TpoMoneda')
        sumar_monto_nf = totales.get('MontoNF', False) is False
        es_boleta = codigo in BOLETAS

        detalles = []
        for item, d in enumerate(as_list(data['Detalle']), start=1):
            d = array_merge({
                'NroLinDet': item, 'CdgItem': False, 'IndExe': False, 'Retenedor': False,
                'NmbItem': False, 'DscItem': False, 'QtyRef': False, 'UnmdRef': False, 'PrcRef': False,
                'QtyItem': False, 'Subcantidad': False, 'FchElabor': False, 'FchVencim': False,
                'UnmdItem': False, 'PrcItem': False, 'DescuentoPct': False, 'DescuentoMonto': False,
                'RecargoPct': False, 'RecargoMonto': False, 'CodImpAdic': False, 'MontoItem': False,
            }, d)
            d['NmbItem'] = php_str(d['NmbItem'])[:80]
            if not php_empty(d['DscItem']):
                d['DscItem'] = php_str(d['DscItem'])[:1000]
            if codigo in EXPORTACION:
                d['IndExe'] = 1

            if isinstance(d['CdgItem'], dict):
                d['CdgItem'] = array_merge({'TpoCodigo': False, 'VlrCodigo': False}, d['CdgItem'])
                if d['Retenedor'] is False and d['CdgItem']['TpoCodigo'] == 'CPCS':
                    d['Retenedor'] = True
            if d['Retenedor'] is not False:
                if not isinstance(d['Retenedor'], dict):
                    d['Retenedor'] = {'IndAgente': 'R'}
                d['Retenedor'] = array_merge({
                    'IndAgente': 'R', 'MntBaseFaena': False, 'MntMargComer': False, 'PrcConsFinal': False,
                }, d['Retenedor'])
            if d['CdgItem'] is not False and not isinstance(d['CdgItem'], (dict, list)):
                agente = d['Retenedor'].get('IndAgente') if isinstance(d['Retenedor'], dict) else None
                d['CdgItem'] = {
                    'TpoCodigo': 'INT1' if php_empty(agente) else 'CPCS',
                    'VlrCodigo': d['CdgItem'],
                }

            if php_bool(d['PrcItem']):
                if not php_bool(d['QtyItem']):
                    d['QtyItem'] = 1
                if php_empty(d['MontoItem']):
                    monto = utils_round(float(num(d['QtyItem'])) * float(num(d['PrcItem'])), moneda)
                    if php_bool(d['DescuentoPct']):
                        d['DescuentoMonto'] = php_round(monto * float(num(d['DescuentoPct'])) / 100)
                    monto -= num(d['DescuentoMonto'])
                    if php_bool(d['RecargoPct']):
                        d['RecargoMonto'] = php_round(monto * float(num(d['RecargoPct'])) / 100)
                    monto += num(d['RecargoMonto'])
                    d['MontoItem'] = utils_round(monto, moneda)
            elif php_empty(d['MontoItem']):
                d['MontoItem'] = 0

            if php_bool(d['MontoItem']):
                monto = num(d['MontoItem'])
                exento = not php_empty(d['IndExe'])
                if exento and php_eq(d['IndExe'], 1):
                    totales['MntExe'] = num(totales.get('MntExe')) + monto
                    if es_boleta:
                        totales['MntTotal'] = num(totales.get('MntTotal')) + monto
                elif exento and php_eq(d['IndExe'], 2):
                    if sumar_monto_nf:
                        totales['MontoNF'] = num(totales.get('MontoNF')) + monto
                elif not exento:
                    if es_boleta:
                        totales['MntTotal'] = num(totales.get('MntTotal')) + monto
                    else:
                        totales['MntNeto'] = num(totales.get('MntNeto')) + monto

            detalles.append(d)
        data['Detalle'] = detalles

    # ------------------------------------------------------------------
    # NormalizeDescuentosRecargosTrait
    # ------------------------------------------------------------------

    def _descuentos_recargos(self, data: Dict[str, Any], codigo: int) -> None:
        if php_empty(data.get('DscRcgGlobal')):
            return
        totales = data['Encabezado']['Totales']
        moneda = totales.get('TpoMoneda')
        tipo_dte = php_int(data['Encabezado']['IdDoc'].get('TipoDTE'))

        resultado = []
        for dr in as_list(data['DscRcgGlobal']):
            dr = array_merge({
                'NroLinDR': False, 'TpoMov': False, 'GlosaDR': False, 'TpoValor': False,
                'ValorDR': False, 'ValorDROtrMnda': False, 'IndExeDR': False,
            }, dr)
            resultado.append(dr)
            if codigo in EXPORTACION:
                dr['IndExeDR'] = 1
            if dr.get('IndExeDR') is None or dr['IndExeDR'] is False:
                monto = 'MntTotal' if tipo_dte == 39 else 'MntNeto'
            else:
                monto = 'MntExe' if php_eq(dr['IndExeDR'], 1) else 'MontoNF'
            if php_empty(totales.get(monto)):
                continue
            if dr['TpoValor'] == '$':
                dr['ValorDR'] = utils_round(dr['ValorDR'], moneda, 2)
            if dr['TpoValor'] == '%':
                valor = utils_round((num(dr['ValorDR']) / 100) * num(totales[monto]), moneda)
            else:
                valor = num(dr['ValorDR'])
            if dr['TpoMov'] == 'D':
                totales[monto] = num(totales[monto]) - valor
            elif dr['TpoMov'] == 'R':
                totales[monto] = num(totales[monto]) + valor
            totales[monto] = utils_round(totales[monto], moneda)
            if tipo_dte == 41 and dr.get('IndExeDR') is not None and php_eq(dr['IndExeDR'], 1):
                totales['MntTotal'] = totales['MntExe']
        data['DscRcgGlobal'] = resultado

    # ------------------------------------------------------------------
    # NormalizeImpuestoAdicionalRetencionTrait
    # ------------------------------------------------------------------

    def _impuesto_adicional_retencion(self, data: Dict[str, Any]) -> None:
        totales = data['Encabezado']['Totales']
        montos: Dict[Any, Number] = {}
        for d in data['Detalle']:
            if not php_empty(d.get('CodImpAdic')):
                montos[d['CodImpAdic']] = num(montos.get(d['CodImpAdic'])) + num(d['MontoItem'])

        if montos:
            if not isinstance(totales.get('ImptoReten'), (list, dict)):
                totales['ImptoReten'] = []
            else:
                totales['ImptoReten'] = as_list(totales['ImptoReten'])

        for codigo, neto in montos.items():
            impuestos = totales['ImptoReten']
            index = next(
                (i for i, imp in enumerate(impuestos) if php_eq(imp.get('TipoImp'), num(codigo))),
                None,
            )
            if index is None:
                impuestos.append({'TipoImp': codigo})
                index = len(impuestos) - 1
            impuesto = array_merge({
                'TipoImp': codigo,
                'TasaImp': impuesto_adicional(codigo)['tasa'],
                'MontoImp': None,
            }, impuestos[index])
            if impuesto['MontoImp'] is None:
                impuesto['MontoImp'] = php_round(neto * num(impuesto['TasaImp']) / 100)
            impuestos[index] = impuesto

        if isinstance(totales.get('ImptoReten'), (list, dict)):
            codigos = [num(c) for c in montos]
            impuestos = [imp for imp in as_list(totales['ImptoReten']) if num(imp.get('TipoImp')) in codigos]
            # sort() de PHP sobre arreglos con las mismas claves: por sus valores en orden.
            impuestos.sort(key=lambda imp: tuple(num(v) if not isinstance(v, str) else v for v in imp.values()))
            totales['ImptoReten'] = impuestos

    # ------------------------------------------------------------------
    # NormalizeIvaMntTotalTrait
    # ------------------------------------------------------------------

    def _iva_mnt_total(self, data: Dict[str, Any], codigo: int) -> None:
        totales = data['Encabezado']['Totales']
        id_doc = data['Encabezado']['IdDoc']

        if codigo in BOLETAS and (php_empty(id_doc.get('IndMntNeto')) or not php_eq(id_doc.get('IndMntNeto'), 2)):
            total = php_int(totales.get('MntTotal')) - php_int(totales.get('MntExe'))
            if total and (php_empty(totales.get('MntNeto')) or php_empty(totales.get('IVA'))):
                tasa = totales['TasaIVA'] if totales.get('TasaIVA') is not None else default_tasa_iva(codigo)
                totales['MntNeto'], totales['IVA'] = calcular_neto_iva(total, tasa)

        if not php_empty(totales.get('MntNeto')):
            if php_eq(id_doc.get('MntBruto'), 1):
                totales['MntNeto'], totales['IVA'] = calcular_neto_iva(totales['MntNeto'], totales.get('TasaIVA'))
            elif php_empty(totales.get('IVA')) and not php_empty(totales.get('TasaIVA')):
                totales['IVA'] = php_round(num(totales['MntNeto']) * (num(totales['TasaIVA']) / 100))
            if php_empty(totales.get('MntTotal')):
                totales['MntTotal'] = num(totales['MntNeto'])
                if not php_empty(totales.get('IVA')):
                    totales['MntTotal'] += num(totales['IVA'])
                if not php_empty(totales.get('MntExe')):
                    totales['MntTotal'] += num(totales['MntExe'])
        elif not php_bool(totales.get('MntTotal')) and not php_empty(totales.get('MntExe')):
            totales['MntTotal'] = totales['MntExe']

        if _is_numeric(totales.get('IVA')):
            totales['IVA'] = php_int(totales['IVA'])

        if not php_empty(totales.get('ImptoReten')):
            for impuesto in as_list(totales['ImptoReten']):
                tipo = impuesto_adicional(impuesto['TipoImp'])['tipo']
                if tipo == 'R':
                    totales['MntTotal'] = num(totales['MntTotal']) - num(impuesto.get('MontoImp'))
                    if not php_eq(impuesto.get('MontoImp'), num(totales.get('IVA'))):
                        totales['IVANoRet'] = num(totales.get('IVA')) - num(impuesto.get('MontoImp'))
                elif tipo == 'A' and impuesto.get('MontoImp') is not None:
                    totales['MntTotal'] = num(totales['MntTotal']) + num(impuesto['MontoImp'])

        # Nota: en PHP el ajuste por CredEC verifica method_exists($this,
        # 'getDefaultCredEC') sobre el job, que no lo tiene, por lo que nunca
        # se aplica. Se mantiene el mismo comportamiento.

        if php_int(id_doc.get('TipoDTE')) not in BOLETAS:
            if not php_empty(totales.get('MntTotal')) and not php_empty(totales.get('MontoNF')):
                totales['MontoPeriodo'] = num(totales['MntTotal']) + num(totales['MontoNF'])

        if _is_numeric(totales.get('MntTotal')) and codigo not in EXPORTACION:
            totales['MntTotal'] = php_int(totales['MntTotal'])

    # ------------------------------------------------------------------
    # NormalizeTransporteTrait y NormalizeBoletasTrait
    # ------------------------------------------------------------------

    @staticmethod
    def _transporte(data: Dict[str, Any]) -> None:
        if not php_empty(data['Encabezado'].get('Transporte')):
            data['Encabezado']['Transporte'] = array_merge({
                'Patente': False, 'RUTTrans': False, 'Chofer': False, 'DirDest': False,
                'CmnaDest': False, 'CiudadDest': False, 'Aduana': False,
            }, data['Encabezado']['Transporte'])

    @staticmethod
    def _boletas(data: Dict[str, Any]) -> None:
        encabezado = data['Encabezado']
        emisor, receptor, id_doc = encabezado['Emisor'], encabezado['Receptor'], encabezado['IdDoc']
        if php_bool(emisor.get('RznSoc')):
            emisor['RznSocEmisor'] = emisor['RznSoc']
            emisor['RznSoc'] = False
        if php_bool(emisor.get('GiroEmis')):
            emisor['GiroEmisor'] = emisor['GiroEmis']
            emisor['GiroEmis'] = False
        for tag in ('Acteco', 'Telefono', 'CorreoEmisor', 'CdgVendedor'):
            emisor[tag] = False
        receptor['GiroRecep'] = False
        if not php_empty(receptor.get('CorreoRecep')):
            if data['Referencia'] is False:
                data['Referencia'] = []
            data['Referencia'] = as_list(data['Referencia'])
            data['Referencia'].append({
                'NroLinRef': len(data['Referencia']) + 1 if data['Referencia'] else 1,
                'RazonRef': f"Email receptor: {receptor['CorreoRecep']}"[:90],
            })
        receptor['CorreoRecep'] = False
        for tag in ('FmaPago', 'FchCancel', 'MedioPago', 'TpoCtaPago', 'NumCtaPago', 'BcoPago',
                    'TermPagoGlosa', 'TpoTranCompra', 'TpoTranVenta'):
            id_doc[tag] = False
        encabezado['RUTSolicita'] = False
        encabezado['Transporte'] = False
        if not php_empty(data['Referencia']):
            data['Referencia'] = [{k: v for k, v in r.items() if k != 'FchRef'} for r in as_list(data['Referencia'])]

    # ------------------------------------------------------------------
    # NormalizeDataPostDocumentNormalizationJob
    # ------------------------------------------------------------------

    def _post_normalization(self, data: Dict[str, Any]) -> Dict[str, Any]:
        id_doc = data['Encabezado']['IdDoc']
        totales = data['Encabezado']['Totales']

        if isinstance(id_doc.get('MntPagos'), (dict, list)):
            pagos = []
            for pago in as_list(id_doc['MntPagos']):
                pago = array_merge({'FchPago': None, 'MntPago': None, 'GlosaPagos': False}, pago)
                if pago['MntPago'] is None:
                    pago['MntPago'] = totales['MntTotal']
                pagos.append(pago)
            id_doc['MntPagos'] = pagos

        if not php_empty(data['Encabezado'].get('OtraMoneda')):
            monedas = []
            for otra in as_list(data['Encabezado']['OtraMoneda']):
                otra = array_merge({
                    'TpoMoneda': False, 'TpoCambio': False, 'MntNetoOtrMnda': False, 'MntExeOtrMnda': False,
                    'MntFaeCarneOtrMnda': False, 'MntMargComOtrMnda': False, 'IVAOtrMnda': False,
                    'ImpRetOtrMnda': False, 'IVANoRetOtrMnda': False, 'MntTotOtrMnda': False,
                }, otra)
                monedas.append(otra)
                if otra.get('TpoCambio') is None:
                    continue
                for monto in ('MntNeto', 'MntExe', 'IVA', 'IVANoRet'):
                    if php_empty(otra.get(f'{monto}OtrMnda')) and not php_empty(totales.get(monto)):
                        otra[f'{monto}OtrMnda'] = php_round(num(totales[monto]) * num(otra['TpoCambio']), 4)
                for tag in ('MntFaeCarneOtrMnda', 'MntMargComOtrMnda', 'ImpRetOtrMnda'):
                    if php_empty(otra[tag]):
                        otra[tag] = False
                if php_empty(otra['MntTotOtrMnda']):
                    otra['MntTotOtrMnda'] = 0
                    for tag in ('MntNetoOtrMnda', 'MntExeOtrMnda', 'MntFaeCarneOtrMnda',
                                'MntMargComOtrMnda', 'IVAOtrMnda', 'IVANoRetOtrMnda'):
                        if not php_empty(otra[tag]):
                            otra['MntTotOtrMnda'] += num(otra[tag])
                    if otra['TpoMoneda'] == 'PESO CL':
                        otra['MntTotOtrMnda'] = php_round(otra['MntTotOtrMnda'], 0)
                if php_eq(otra['TpoCambio'], 0):
                    otra['TpoCambio'] = False
            data['Encabezado']['OtraMoneda'] = monedas

        data.pop('LibreDTE', None)
        return data

    # ------------------------------------------------------------------
    # AbstractSanitizerStrategy::sanitizeEssentials()
    # ------------------------------------------------------------------

    @staticmethod
    def sanitize(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitización esencial posterior a normalizar (formato de RUT, Acteco
        de 6 dígitos y largo máximo de los datos del receptor).

        Raises:
            NormalizerError: Si falta el folio
        """
        from ..sii.utils import RutValidator

        encabezado = data.get('Encabezado') or {}
        if 'IdDoc' in encabezado and encabezado['IdDoc'].get('Folio') is None:
            raise NormalizerError('Es obligatorio indicar el folio del documento.')
        for nodo, tag in (('Emisor', 'RUTEmisor'), ('Receptor', 'RUTRecep')):
            rut = (encabezado.get(nodo) or {}).get(tag)
            if rut:
                encabezado[nodo][tag] = RutValidator.format(rut)
        acteco = (encabezado.get('Emisor') or {}).get('Acteco')
        if not php_empty(acteco) and len(php_str(acteco)) == 5:
            encabezado['Emisor']['Acteco'] = '0' + php_str(acteco)
        receptor = encabezado.get('Receptor') or {}
        for tag, largo in (('RznSocRecep', 100), ('GiroRecep', 40), ('Contacto', 80),
                           ('CorreoRecep', 80), ('DirRecep', 70), ('CmnaRecep', 20)):
            if not php_empty(receptor.get(tag)):
                receptor[tag] = php_str(receptor[tag])[:largo]
        return data


def _is_numeric(value: Any) -> bool:
    """is_numeric() de PHP."""
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value).strip())
        return True
    except ValueError:
        return False
