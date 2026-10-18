"""
Tipo de cambio para los documentos de exportación (110, 111 y 112).

Los documentos de exportación informan los montos en pesos chilenos en
OtraMoneda (TpoMoneda PESO CL y TpoCambio). Este módulo entrega ese tipo de
cambio para la moneda de la operación y la fecha de emisión:

- BancoCentral: API de la Base de Datos Estadísticos (BDE) del Banco Central
  de Chile, https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx (requiere
  token o usuario y clave de la BDE). Por defecto conoce el dólar observado
  (serie F073.TCO.PRE.Z.D); las demás monedas se configuran con su serie,
  que se puede buscar con buscar_series().
- TiposCambioFijos: valores dados (p. ej. los referenciales de certificación).

Fines de semana y feriados no tienen valor publicado: se usa el último
publicado antes de la fecha (hasta DIAS_ATRAS días).
"""

import threading
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol, Union

import requests

from .errors import RypDteError

URL_BCCH = 'https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx'
DOLAR_OBSERVADO = 'F073.TCO.PRE.Z.D'
DIAS_ATRAS = 10
EXPORTACION = (110, 111, 112)


class TipoCambioError(RypDteError):
    """No fue posible obtener el tipo de cambio."""


class ProveedorTipoCambio(Protocol):
    def tipo_cambio(self, moneda: str, fecha: str) -> float:
        """Pesos chilenos por una unidad de la moneda (glosa de aduana, p. ej. "DOLAR USA") en la fecha AAAA-MM-DD."""


def _clave(moneda: str) -> str:
    return ' '.join(moneda.upper().split())


class TiposCambioFijos:
    """Tipos de cambio dados por moneda (los mismos para cualquier fecha)."""

    def __init__(self, valores: Dict[str, float]):
        self.valores = {_clave(m): float(v) for m, v in valores.items()}

    def tipo_cambio(self, moneda: str, fecha: str) -> float:
        try:
            return self.valores[_clave(moneda)]
        except KeyError:
            raise TipoCambioError(f'No hay tipo de cambio para {moneda}.') from None


class BancoCentral:
    """
    Tipos de cambio de la BDE del Banco Central de Chile.

    Args:
        token: Token de la API (o bien usuario y clave de la BDE).
        series: Serie por moneda (glosa de aduana). Cada valor es el código de
            una serie en pesos por unidad, o {'paridad': codigo} para una serie
            de unidades de la moneda por dólar (se convierte con el dólar observado).

    Ejemplo:
        bcch = BancoCentral(token='...', series={'EURO': 'F072.CLP.EUR.N.O.D'})
        bcch.tipo_cambio('DOLAR USA', '2026-10-19')
    """

    def __init__(self, token: Optional[str] = None, usuario: Optional[str] = None, clave: Optional[str] = None,
                 series: Optional[Dict[str, Union[str, Dict[str, str]]]] = None, timeout: int = 20,
                 session: Optional[requests.Session] = None):
        if not token and not (usuario and clave):
            raise TipoCambioError('El Banco Central requiere token, o usuario y clave de la BDE.')
        self.credenciales = {'token': token} if token else {'user': usuario, 'pass': clave}
        self.series: Dict[str, Union[str, Dict[str, str]]] = {'DOLAR USA': DOLAR_OBSERVADO}
        self.series.update({_clave(m): s for m, s in (series or {}).items()})
        self.timeout = timeout
        self.session = session or requests.Session()
        self._cache: Dict[tuple, float] = {}
        self._lock = threading.Lock()

    def _consultar(self, parametros: Dict[str, str]) -> Dict[str, Any]:
        try:
            respuesta = self.session.get(URL_BCCH, params={**self.credenciales, **parametros}, timeout=self.timeout)
            datos = respuesta.json()
        except (requests.RequestException, ValueError) as e:
            raise TipoCambioError(f'No hubo respuesta válida del Banco Central: {e}') from e
        if str(datos.get('Codigo')) != '0':
            raise TipoCambioError(f'El Banco Central respondió {datos.get("Codigo")}: {datos.get("Descripcion")}')
        return datos

    def valor_serie(self, serie: str, fecha: str) -> float:
        """Último valor publicado de la serie en la fecha o antes."""
        with self._lock:
            if (serie, fecha) in self._cache:
                return self._cache[(serie, fecha)]
        hasta = date.fromisoformat(fecha)
        datos = self._consultar({'function': 'GetSeries', 'timeseries': serie,
                                 'firstdate': (hasta - timedelta(days=DIAS_ATRAS)).isoformat(),
                                 'lastdate': hasta.isoformat()})
        observaciones = []
        for obs in (datos.get('Series') or {}).get('Obs') or []:
            if obs.get('statusCode') != 'OK':
                continue
            try:
                dia = datetime.strptime(obs['indexDateString'], '%d-%m-%Y').date()
                observaciones.append((dia, float(str(obs['value']).replace(',', '.'))))
            except (KeyError, ValueError):
                continue
        observaciones = [o for o in observaciones if o[0] <= hasta]
        if not observaciones:
            raise TipoCambioError(f'El Banco Central no tiene valores de {serie} entre '
                                  f'{(hasta - timedelta(days=DIAS_ATRAS)).isoformat()} y {fecha}.')
        valor = max(observaciones)[1]
        with self._lock:
            self._cache[(serie, fecha)] = valor
        return valor

    def tipo_cambio(self, moneda: str, fecha: str) -> float:
        serie = self.series.get(_clave(moneda))
        if serie is None:
            raise TipoCambioError(f'No hay serie del Banco Central configurada para {moneda}; '
                                  f'búsquela con buscar_series().')
        if isinstance(serie, dict):
            dolar = self.valor_serie(DOLAR_OBSERVADO, fecha)
            return dolar / self.valor_serie(serie['paridad'], fecha)
        return self.valor_serie(serie, fecha)

    def buscar_series(self, texto: str, frecuencia: str = 'DAILY') -> List[Dict[str, Any]]:
        """Series de la BDE cuyo título contiene el texto (p. ej. "euro")."""
        datos = self._consultar({'function': 'SearchSeries', 'frequency': frecuencia})
        texto = texto.lower()
        return [s for s in datos.get('SeriesInfos') or []
                if texto in f'{s.get("spanishTitle", "")} {s.get("englishTitle", "")}'.lower()]


def completar_tipo_cambio(datos: Dict[str, Any], proveedor: ProveedorTipoCambio) -> Dict[str, Any]:
    """
    En un documento de exportación sin TpoCambio, agrega OtraMoneda en pesos con
    el tipo de cambio de la moneda de la operación a la fecha de emisión. Un
    TpoCambio ya informado se respeta.
    """
    encabezado = datos.get('Encabezado') or {}
    id_doc = encabezado.get('IdDoc') or {}
    if int(id_doc.get('TipoDTE') or 0) not in EXPORTACION:
        return datos
    moneda = (encabezado.get('Totales') or {}).get('TpoMoneda')
    otra = encabezado.get('OtraMoneda') or {}
    if not moneda or _clave(moneda) == 'PESO CL' or (otra and otra.get('TpoCambio')):
        return datos
    if otra and _clave(otra.get('TpoMoneda') or 'PESO CL') != 'PESO CL':
        return datos
    fecha = id_doc.get('FchEmis') or date.today().isoformat()
    encabezado['OtraMoneda'] = {**otra, 'TpoMoneda': 'PESO CL',
                                'TpoCambio': round(proveedor.tipo_cambio(moneda, fecha), 4)}
    return datos
