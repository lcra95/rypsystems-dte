"""
Lectura de los sets de pruebas de certificación que entrega el SII.

Convierte el texto del SII (SIISetDePruebas<RUT>.txt y el set de boletas) a
la estructura de casos que usa la emisión de sets (la misma de los YAML de
examples/sets/):

    {'tipo_set': 'basico', 'numero_atencion': 5136564, 'nombre': 'set_5136564',
     'casos': [{'caso': '5136564-1', 'tipo': 33, 'detalle': [...]},
               {'caso': '5136564-5', 'tipo': 61,
                'referencia': {'caso': '5136564-1', 'CodRef': 2, 'RazonRef': '...'},
                'detalle': [...]}, ...]}

Reglas, según las instrucciones del SII y los sets aceptados:

- Notas: CodRef 1 si la razón anula (mismo detalle del documento), 2 si
  corrige texto (una línea con el primer ítem, sin cantidad ni precio) y 3
  en otro caso. Los ítems de una nota toman del documento referenciado lo que
  el set no indica (cantidad, precio, descuentos, unidad, exención...).
- Set básico: los ítems "EXENTO" llevan IndExe. Set factura exenta: todos.
- Factura de compra: retención total del IVA (código 15) en cada ítem.
- Guías: tipo de traslado (IndTraslado) y de despacho según MOTIVO y TRASLADO POR.
- Liquidaciones: TpoDocLiq según el documento que se liquida (99 anticipos).
- Exportación: códigos de aduana desde las tablas del SII; flete y seguro en
  el encabezado y como recargos globales; OtraMoneda en pesos con el tipo de
  cambio entregado; receptor extranjero genérico (RUT 55555555-5).
"""

import copy
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..errors import RypDteError

_DATA = Path(__file__).resolve().parent.parent / 'resources' / 'data'

# Tipos de cambio referenciales para certificación (en producción se usa el del día).
TIPOS_CAMBIO_CERTIFICACION = {'DOLAR USA': 950, 'EURO': 1050, 'LIBRA EST': 1250, 'FRANCO SZ': 1100,
                              'YEN': 6.5, 'DOLAR CAN': 700, 'DOLAR AUST': 620, 'PESO AR': 1, 'REAL': 175}
RUT_EXTRANJERO = '55555555-5'
PASAPORTE_CERTIFICACION = 'YA1234567'

DOCUMENTOS = {
    'FACTURA ELECTRONICA': 33,
    'FACTURA NO AFECTA O EXENTA ELECTRONICA': 34,
    'FACTURA EXENTA ELECTRONICA': 34,
    'LIQUIDACION FACTURA ELECTRONICA': 43,
    'FACTURA DE COMPRA ELECTRONICA': 46,
    'GUIA DE DESPACHO': 52,
    'GUIA DE DESPACHO ELECTRONICA': 52,
    'NOTA DE DEBITO ELECTRONICA': 56,
    'NOTA DE CREDITO ELECTRONICA': 61,
    'FACTURA DE EXPORTACION ELECTRONICA': 110,
    'NOTA DE DEBITO DE EXPORTACION ELECTRONICA': 111,
    'NOTA DE CREDITO DE EXPORTACION ELECTRONICA': 112,
}
DOCUMENTOS_LIBRO = {
    'FACTURA': 30, 'FACTURA ELECTRONICA': 33, 'FACTURA NO AFECTA O EXENTA ELECTRONICA': 34,
    'FACTURA EXENTA': 32, 'FACTURA DE COMPRA': 45, 'FACTURA DE COMPRA ELECTRONICA': 46,
    'NOTA DE DEBITO': 55, 'NOTA DE DEBITO ELECTRONICA': 56, 'NOTA DE CREDITO': 60,
    'NOTA DE CREDITO ELECTRONICA': 61,
}
COLUMNAS = {
    'CANTIDAD': 'QtyItem', 'PRECIO UNITARIO': 'PrcItem', 'VALOR UNITARIO': 'PrcItem',
    'PRECIO UNITARIO CON IVA': 'PrcItem', 'UNIDAD MEDIDA': 'UnmdItem', 'UNIDAD DE MEDIDA': 'UnmdItem',
    'DESCUENTO ITEM': 'DescuentoPct', 'VALOR LINEA': 'ValorLinea', 'TOTAL LINEA': 'MontoItem',
}
# Tipos de traslado (IndTraslado) según el MOTIVO de la guía.
TRASLADOS = (
    ('VENTA POR EFECTUAR', 2), ('VENTA PARA EXPORTACION', 9), ('TRASLADO PARA EXPORTACION', 8),
    ('CONSIGNACION', 3), ('ENTREGA GRATUITA', 4), ('DEVOLUCION', 7), ('ENTRE BODEGAS', 5),
    ('TRASLADO INTERNO', 5), ('NO CONSTITUYE VENTA', 6), ('OTROS TRASLADOS', 6), ('VENTA', 1),
)
DESPACHOS = (('LOCAL DEL CLIENTE', 2), ('OTRAS INSTALACIONES', 3), ('CLIENTE', 1))
REFERENCIAS_EXPORTACION = (
    ('RESOLUCION SNA', 812), ('PASAPORTE', 813), ('CARTA DE PORTE', 811), ('MIC', 810), ('DTA', 810),
    ('AWB', 809), ('B/L', 808), ('CONOCIMIENTO DE EMBARQUE', 808), ('DUS', 807),
)


class SetPruebasError(RypDteError):
    """El texto del set de pruebas no tiene el formato esperado."""


def _sin_tildes(texto: str) -> str:
    texto = unicodedata.normalize('NFKD', texto.replace('Ñ', 'N').replace('ñ', 'n'))
    return ''.join(c for c in texto if not unicodedata.combining(c))


def _clave(texto: str) -> str:
    """Texto comparable: sin tildes, mayúsculas y espacios simples."""
    return re.sub(r'\s+', ' ', _sin_tildes(texto)).strip().upper()


def _numero(texto: str) -> Union[int, float, str]:
    texto = texto.strip().rstrip('%').lstrip('%')
    if re.fullmatch(r'-?\d+', texto):
        return int(texto)
    if re.fullmatch(r'-?\d+\.\d+', texto):
        return float(texto)
    return texto


def _celdas(linea: str) -> List[str]:
    return [c.strip() for c in re.split(r'\t+|\s{2,}', linea.strip()) if c.strip()]


class _Tablas:
    """Tablas de códigos de aduana del SII (resources/data/aduana_*.json)."""

    def __init__(self):
        def cargar(nombre):
            datos = json.loads((_DATA / f'{nombre}.json').read_text(encoding='utf-8'))
            return {_clave(v['glosa'] if isinstance(v, dict) else v): int(k) for k, v in datos.items()}

        self.tablas = {n: cargar(n) for n in (
            'aduana_moneda', 'aduana_formas_pago', 'formas_pago_exportacion', 'aduana_modalidades_venta',
            'aduana_clausulas_venta', 'aduana_transportes', 'aduana_puertos', 'aduana_unidades',
            'aduana_tipos_bulto', 'aduana_paises')}

    def codigo(self, tabla: str, glosa: str, *alternativas: str) -> int:
        clave = _clave(glosa)
        for nombre in (tabla, *alternativas):
            if clave in self.tablas[nombre]:
                return self.tablas[nombre][clave]
        # Variantes de la glosa: "SIN PAGO" = "S/PAGO"; "MARITIMA, FLUVIAL..." con tildes en la tabla.
        compacto = clave.replace(' ', '').replace('/', '')
        for nombre in (tabla, *alternativas):
            for glosa_tabla, codigo in self.tablas[nombre].items():
                if glosa_tabla.replace(' ', '').replace('/', '') == compacto:
                    return codigo
        raise SetPruebasError(f'No se encontró "{glosa}" en la tabla {tabla} del SII.')


_tablas: Optional[_Tablas] = None


def _tabla() -> _Tablas:
    global _tablas
    if _tablas is None:
        _tablas = _Tablas()
    return _tablas


# ----------------------------------------------------------------------
# Lectura del texto
# ----------------------------------------------------------------------

def _texto(contenido: Union[str, bytes]) -> str:
    if isinstance(contenido, bytes):
        try:
            contenido = contenido.decode('utf-8')
        except UnicodeDecodeError:
            contenido = contenido.decode('iso-8859-1')
    return contenido.replace('\r\n', '\n').replace('\r', '\n')


def leer_set_pruebas(contenido: Union[str, bytes], tipos_cambio: Optional[Dict[str, float]] = None
                     ) -> List[Dict[str, Any]]:
    """
    Lee el archivo de sets de pruebas del SII (todos los sets del contribuyente).

    Args:
        tipos_cambio: Tipo de cambio a pesos por moneda (glosa de aduana) para
            los documentos de exportación; por defecto los referenciales de
            certificación.

    Returns:
        Un diccionario por set, en el orden del archivo.
    """
    texto = _texto(contenido)
    tipos_cambio = {**TIPOS_CAMBIO_CERTIFICACION, **(tipos_cambio or {})}
    sets = []
    for seccion in re.split(r'\n-{40,}\s*\n', texto):  # separador de sets (no el subrayado de títulos)
        cabecera = re.search(r'SET (.+?) - N[UÚ]MERO DE ATENCI[OÓ]N:\s*(\d+)', seccion)
        if not cabecera:
            continue
        nombre, numero = _clave(cabecera.group(1)), int(cabecera.group(2))
        base = {'numero_atencion': numero, 'nombre': f'set_{numero}', 'titulo': f'SET {cabecera.group(1).strip()}'}
        if 'LIBRO DE VENTAS' in nombre:
            sets.append({**base, 'tipo_set': 'libro_ventas', 'folio_notificacion': 1})
        elif 'LIBRO DE COMPRAS' in nombre:
            sets.append({**base, **_libro_compras(seccion)})
        elif 'LIBRO DE GUIAS' in nombre:
            sets.append({**base, **_libro_guias(seccion)})
        else:
            tipo_set = _tipo_set(nombre)
            casos = [_caso(caso, cuerpo, tipo_set) for caso, cuerpo in _casos(seccion)]
            if not casos:
                raise SetPruebasError(f'El set {numero} no tiene casos.')
            _resolver_notas(casos, tipo_set, tipos_cambio)
            sets.append({**base, 'tipo_set': tipo_set, 'casos': casos})
    if not sets:
        raise SetPruebasError('El archivo no contiene sets de pruebas del SII.')
    return sets


def leer_set_boletas(contenido: Union[str, bytes]) -> Dict[str, Any]:
    """Lee el set de pruebas de boleta electrónica (casos CASO-n, precios con IVA)."""
    texto = _texto(contenido)
    casos = []
    for caso, cuerpo in re.findall(r'^(CASO-\d+)\s*\n=+\s*\n(.*?)(?=^CASO-\d+\s*\n=|^={20,}|\Z)', texto,
                                    re.M | re.S):
        items = _tabla_items(cuerpo.split('\n'))
        unidad = re.search(r'unidad de medida en (\w+)', cuerpo, re.I)
        detalle = []
        for item in items:
            if 'EXENTO' in _clave(item['NmbItem']):
                item['IndExe'] = 1
            if unidad:
                item['UnmdItem'] = unidad.group(1)
            detalle.append(item)
        casos.append({'caso': caso, 'tipo': 39, 'detalle': detalle})
    if not casos:
        raise SetPruebasError('El archivo no contiene casos del set de boletas.')
    return {'tipo_set': 'boletas', 'nombre': 'set_boleta', 'titulo': 'SET DE PRUEBA DE BOLETA ELECTRONICA',
            'casos': casos}


def _tipo_set(nombre: str) -> str:
    if 'EXPORTACION' in nombre:
        return 'exportacion'
    for clave, tipo_set in (('GUIA DE DESPACHO', 'guia'), ('FACTURA EXENTA', 'exenta'),
                            ('LIQUIDACION', 'liquidacion'), ('FACTURA DE COMPRA', 'factura_compra'),
                            ('BASICO', 'basico')):
        if clave in nombre:
            return tipo_set
    raise SetPruebasError(f'Set no reconocido: {nombre}')


def _casos(seccion: str):
    return re.findall(r'^CASO (\S+)\s*\n=+\s*\n(.*?)(?=^CASO \S+\s*\n=|\Z)', seccion, re.M | re.S)


def _tabla_items(lineas: List[str], inicio: str = 'ITEM') -> List[Dict[str, Any]]:
    """Filas de la tabla que empieza con una cabecera (ITEM o COMISIONES...)."""
    items, columnas = [], None
    for linea in lineas:
        if columnas is None:
            if _clave(linea).startswith(inicio) and len(_celdas(linea)) >= 2:
                columnas = [COLUMNAS.get(_clave(c), _clave(c)) for c in _celdas(linea)[1:]]
            continue
        if not linea.strip():
            if items:
                break
            continue
        celdas = _celdas(linea)
        item: Dict[str, Any] = {'NmbItem': celdas[0]}
        for columna, valor in zip(columnas, celdas[1:]):
            item[columna] = _numero(valor)
        if 'ValorLinea' in item:
            item['QtyItem'], item['PrcItem'] = 1, item.pop('ValorLinea')
        items.append(item)
    return items


def _caso(caso: str, cuerpo: str, tipo_set: str) -> Dict[str, Any]:
    lineas = cuerpo.split('\n')
    documento = re.search(r'^DOCUMENTO\s+(.+)$', cuerpo, re.M)
    if not documento or _clave(documento.group(1)) not in DOCUMENTOS:
        raise SetPruebasError(f'Caso {caso}: documento no reconocido.')
    resultado: Dict[str, Any] = {'caso': caso, 'tipo': DOCUMENTOS[_clave(documento.group(1))]}
    referencia = re.search(r'^REFERENCIA\s+.*CORRESPONDIENTE A CASO (\S+)', cuerpo, re.M)
    if referencia:
        razon = re.search(r'^RAZON REFERENCIA\s+(.+)$', cuerpo, re.M)
        razon = razon.group(1).strip() if razon else ''
        resultado['referencia'] = {'caso': referencia.group(1), 'CodRef': _cod_ref(razon), 'RazonRef': razon}
    items = _tabla_items(lineas)
    if items:
        resultado['detalle'] = items

    global_ = re.search(r'^DESCUENTO GLOBAL (.+?)\s+(\d+(?:\.\d+)?)%', cuerpo, re.M)
    if global_:
        resultado['descuentos_recargos'] = [{'TpoMov': 'D', 'GlosaDR': f'DESCUENTO GLOBAL {global_.group(1).strip()}',
                                             'TpoValor': '%', 'ValorDR': _numero(global_.group(2))}]
    if tipo_set == 'guia':
        resultado['encabezado'] = {'IdDoc': _guia(cuerpo, caso)}
    if tipo_set == 'liquidacion':
        for item in resultado.get('detalle', []):
            _item_liquidacion(item)
        comisiones = _tabla_items(lineas, 'COMISIONES Y OTROS CARGOS')
        if comisiones:
            resultado['comisiones'] = [{'TipoMovim': 'C', 'Glosa': c['NmbItem'],
                                        'ValComExe' if _clave(c['NmbItem']).startswith('EXENTO') else 'ValComNeto':
                                            c['MontoItem']} for c in comisiones]
    if tipo_set == 'exportacion':
        resultado['_exportacion'] = cuerpo
    for item in resultado.get('detalle', []):
        if tipo_set == 'basico' and 'EXENTO' in _clave(item['NmbItem']):
            item['IndExe'] = 1
        if tipo_set == 'exenta':
            item['IndExe'] = 1
        if tipo_set == 'factura_compra' and resultado['tipo'] == 46:
            item['CodImpAdic'] = 15
    return resultado


def _cod_ref(razon: str) -> int:
    razon = _clave(razon)
    if 'ANULA' in razon:
        return 1
    if 'CORRIGE' in razon:
        return 2
    return 3


def _guia(cuerpo: str, caso: str) -> Dict[str, int]:
    motivo = re.search(r'^MOTIVO:?\s+(.+)$', cuerpo, re.M)
    if not motivo:
        raise SetPruebasError(f'Caso {caso}: la guía no indica el motivo del traslado.')
    motivo = _clave(motivo.group(1))
    id_doc = {'IndTraslado': next((codigo for clave, codigo in TRASLADOS if clave in motivo), 6)}
    traslado = re.search(r'^TRASLADO POR:?\s+(.+)$', cuerpo, re.M)
    if traslado:
        despacho = _clave(traslado.group(1))
        id_doc['TipoDespacho'] = next(codigo for clave, codigo in DESPACHOS if clave in despacho)
    return id_doc


def _item_liquidacion(item: Dict[str, Any]) -> None:
    nombre = _clave(item['NmbItem'])
    electronico = 'ELECTRONIC' in nombre
    if 'ANTICIPO' in nombre:
        tipo = 99
    elif 'LIQUIDACION' in nombre:
        tipo = 43
    elif 'NOTA DE CREDITO' in nombre:
        tipo = 61 if electronico else 60
    elif 'NOTA DE DEBITO' in nombre:
        tipo = 56 if electronico else 55
    elif 'BOLETA' in nombre:
        tipo = 39 if electronico else 35
    elif 'FACTURA' in nombre:
        tipo = 33 if electronico else 30
    else:
        tipo = 99
    nuevo = {'TpoDocLiq': tipo}
    if nombre.startswith('EXENTO'):
        nuevo['IndExe'] = 1
    nuevo.update(item)
    item.clear()
    item.update(nuevo)


# ----------------------------------------------------------------------
# Exportación
# ----------------------------------------------------------------------

def _campos_exportacion(cuerpo: str) -> Dict[str, List[str]]:
    campos: Dict[str, List[str]] = {}
    for clave, valor in re.findall(r'^([A-ZÁÉÍÓÚÑ ()*]+?)\s*(?:\(\*\*\))?:\s+(.+?)\s*$', cuerpo, re.M):
        campos.setdefault(_clave(clave), []).append(valor.strip())
    return campos


def _exportacion(caso: Dict[str, Any], tipos_cambio: Dict[str, float]) -> None:
    cuerpo = caso.pop('_exportacion')
    if caso['tipo'] != 110:
        return
    t = _tabla()
    campos = _campos_exportacion(cuerpo)
    primero = {k: v[0] for k, v in campos.items()}
    id_doc: Dict[str, Any] = {}
    aduana: Dict[str, Any] = {}
    nombres = ' '.join(_clave(i['NmbItem']) for i in caso.get('detalle', []))
    referencias = campos.get('REFERENCIA', [])

    if any(p in nombres for p in ('ALOJAMIENTO', 'HOTEL', 'HABITACION')):
        id_doc['IndServicio'] = 4
    elif any('RESOLUCION SNA' in _clave(r) for r in referencias):
        id_doc['IndServicio'] = 3
    if 'FORMA DE PAGO EXPORTACION' in primero:
        id_doc['FmaPagExp'] = t.codigo('aduana_formas_pago', primero['FORMA DE PAGO EXPORTACION'],
                                       'formas_pago_exportacion')

    def codigo(campo, tabla, destino):
        if campo in primero:
            aduana[destino] = t.codigo(tabla, primero[campo])

    codigo('MODALIDAD DE VENTA', 'aduana_modalidades_venta', 'CodModVenta')
    codigo('CLAUSULA DE VENTA DE EXPORTACION', 'aduana_clausulas_venta', 'CodClauVenta')
    if 'TOTAL CLAUSULA DE VENTA' in primero:
        aduana['TotClauVenta'] = float(primero['TOTAL CLAUSULA DE VENTA'])
    codigo('VIA DE TRANSPORTE', 'aduana_transportes', 'CodViaTransp')
    codigo('PUERTO DE EMBARQUE', 'aduana_puertos', 'CodPtoEmbarque')
    codigo('PUERTO DE DESEMBARQUE', 'aduana_puertos', 'CodPtoDesemb')
    codigo('UNIDAD DE MEDIDA DE TARA', 'aduana_unidades', 'CodUnidMedTara')
    codigo('UNIDAD PESO BRUTO', 'aduana_unidades', 'CodUnidPesoBruto')
    codigo('UNIDAD PESO NETO', 'aduana_unidades', 'CodUnidPesoNeto')
    if 'TOTAL BULTOS' in primero:
        aduana['TotBultos'] = int(primero['TOTAL BULTOS'])
        if 'TIPO DE BULTO' in primero:
            aduana['TipoBultos'] = [{'CodTpoBultos': t.codigo('aduana_tipos_bulto', primero['TIPO DE BULTO']),
                                     'CantBultos': aduana['TotBultos'],
                                     'Marcas': f'CASO {caso["caso"]} 1/{aduana["TotBultos"]}'}]
    flete, seguro = primero.get('FLETE'), primero.get('SEGURO')
    if flete:
        aduana['MntFlete'] = float(flete)
    if seguro:
        aduana['MntSeguro'] = float(seguro)
    pais = primero.get('PAIS RECEPTOR Y PAIS DESTINO')
    nacionalidad = t.codigo('aduana_paises', pais or primero.get('NACIONALIDAD', 'U.S.A.'))
    if pais:
        aduana['CodPaisRecep'] = aduana['CodPaisDestin'] = nacionalidad

    moneda = primero.get('MONEDA DE LA OPERACION', 'DOLAR USA')
    t.codigo('aduana_moneda', moneda)
    if _clave(moneda) not in {_clave(m) for m in tipos_cambio}:
        raise SetPruebasError(f'Caso {caso["caso"]}: falta el tipo de cambio de {moneda}.')
    cambio = next(v for m, v in tipos_cambio.items() if _clave(m) == _clave(moneda))

    encabezado: Dict[str, Any] = {}
    if id_doc:
        encabezado['IdDoc'] = id_doc
    encabezado['Receptor'] = {
        'RUTRecep': RUT_EXTRANJERO, 'RznSocRecep': 'CLIENTE EXTRANJERO', 'Extranjero': {'Nacionalidad': nacionalidad},
        'GiroRecep': 'IMPORTACION', 'DirRecep': pais or primero.get('NACIONALIDAD', 'EXTRANJERO'),
    }
    if aduana:
        encabezado['Transporte'] = {'Aduana': aduana}
    encabezado['Totales'] = {'TpoMoneda': moneda}
    encabezado['OtraMoneda'] = {'TpoMoneda': 'PESO CL', 'TpoCambio': cambio}
    caso['encabezado'] = encabezado

    detalle = caso.get('detalle', [])
    recargo = re.search(r'^%?(\d+)%?\s+RECARGO EN LA LINEA', cuerpo, re.M)
    if recargo:
        for item in detalle:
            item['RecargoPct'] = int(recargo.group(1))
    for linea, porcentaje in re.findall(r'DESCUENTO LINEA # (\d+):\s+(\d+)%', cuerpo):
        detalle[int(linea) - 1]['DescuentoPct'] = int(porcentaje)

    recargos = []
    comision = re.search(r'COMISIONES EN EL EXTRANJERO \(RECARGOS GLOBALES\):\s+(\d+)% DEL TOTAL DE LA CLAUSULA',
                         cuerpo)
    if comision:
        if 'TotClauVenta' not in aduana:
            raise SetPruebasError(f'Caso {caso["caso"]}: comisión sobre la cláusula sin total de la cláusula.')
        recargos.append({'TpoMov': 'R', 'GlosaDR': 'COMISIONES EN EL EXTRANJERO', 'TpoValor': '$',
                         'ValorDR': round(aduana['TotClauVenta'] * int(comision.group(1)) / 100, 2)})
    if flete:
        recargos.append({'TpoMov': 'R', 'GlosaDR': 'FLETE', 'TpoValor': '$', 'ValorDR': float(flete)})
    if seguro:
        recargos.append({'TpoMov': 'R', 'GlosaDR': 'SEGURO', 'TpoValor': '$', 'ValorDR': float(seguro)})
    if recargos:
        caso['descuentos_recargos'] = recargos

    extra = []
    for referencia in referencias:
        tipo = next((c for clave, c in REFERENCIAS_EXPORTACION if clave in _clave(referencia)), None)
        if tipo is None:
            raise SetPruebasError(f'Caso {caso["caso"]}: referencia de exportación no reconocida: {referencia}')
        extra.append({'TpoDocRef': tipo, 'FolioRef': 1, 'RazonRef': referencia})
    if id_doc.get('IndServicio') == 4 and not any(r['TpoDocRef'] == 813 for r in extra):
        # Servicio de hotelería a extranjero: el SII exige el pasaporte como segunda referencia.
        extra.append({'TpoDocRef': 813, 'FolioRef': PASAPORTE_CERTIFICACION, 'RazonRef': 'PASAPORTE'})
    if extra:
        caso['referencias_extra'] = extra


# ----------------------------------------------------------------------
# Notas: detalle desde el documento referenciado
# ----------------------------------------------------------------------

def _resolver_notas(casos: List[Dict[str, Any]], tipo_set: str, tipos_cambio: Dict[str, float]) -> None:
    por_caso = {c['caso']: c for c in casos}
    for caso in casos:
        if tipo_set == 'exportacion':
            _exportacion(caso, tipos_cambio)

    def detalle_de(caso: Dict[str, Any]) -> List[Dict[str, Any]]:
        if caso.get('detalle') == 'copiar':
            return detalle_de(por_caso[caso['referencia']['caso']])
        return caso.get('detalle') or []

    for caso in casos:
        referencia = caso.get('referencia')
        if not referencia:
            continue
        original = por_caso.get(referencia['caso'])
        if original is None:
            raise SetPruebasError(f'Caso {caso["caso"]}: referencia al caso {referencia["caso"]}, que no existe.')
        if tipo_set == 'exportacion' and 'encabezado' in original:
            caso['encabezado'] = copy.deepcopy(original['encabezado'])
        items_original = detalle_de(original)
        if referencia['CodRef'] == 1:
            caso['detalle'] = 'copiar'
        elif referencia['CodRef'] == 2:
            primero = items_original[0]
            caso['detalle'] = [{'NmbItem': primero['NmbItem'],
                                **({'IndExe': primero['IndExe']} if primero.get('IndExe') else {})}]
        elif caso.get('detalle'):
            por_nombre = {_clave(i['NmbItem']): i for i in items_original}
            caso['detalle'] = [{**copy.deepcopy(por_nombre.get(_clave(i['NmbItem']), {})), **i}
                               for i in caso['detalle']]
        else:
            caso['detalle'] = 'copiar'


# ----------------------------------------------------------------------
# Libros
# ----------------------------------------------------------------------

def _libro_compras(seccion: str) -> Dict[str, Any]:
    tabla = re.search(r'={20,}\n.*?\n={20,}\n(.*?)\n={20,}', seccion, re.S)
    if not tabla:
        raise SetPruebasError('No se encontró la tabla del set de libro de compras.')
    documentos = []
    for bloque in re.split(r'\n\s*\n', tabla.group(1).strip('\n')):
        lineas = [l for l in bloque.split('\n') if l.strip()]
        if len(lineas) < 3:
            continue
        encabezado = re.match(r'(.+?)\s+(\d+)\s*$', lineas[0])
        tipo = DOCUMENTOS_LIBRO.get(_clave(encabezado.group(1)))
        if tipo is None:
            raise SetPruebasError(f'Documento no reconocido en el libro de compras: {encabezado.group(1)}')
        documento: Dict[str, Any] = {'TpoDoc': tipo, 'NroDoc': int(encabezado.group(2))}
        montos = re.split(r'\t+', lineas[2].rstrip())
        exento, afecto = (montos[0], montos[1]) if len(montos) > 1 else ('', montos[0])
        if exento.strip():
            documento['MntExe'] = int(exento)
        if afecto.strip():
            documento['MntNeto'] = int(afecto)
        observacion = _clave(lineas[1])
        if 'USO COMUN' in observacion:
            documento['uso_comun'] = True
        if 'ENTREGA GRATUITA' in observacion:
            documento['IVANoRec'] = {'CodIVANoRec': 4}
        if 'RETENCION TOTAL' in observacion:
            documento['OtrosImp'] = {'CodImp': 15, 'TasaImp': 19}
        referencia = re.search(r'(FACTURA(?: ELECTRONICA)?) (\d+)$', observacion)
        if tipo in (55, 56, 60, 61) and referencia:
            documento['TpoDocRef'] = DOCUMENTOS_LIBRO[referencia.group(1)]
            documento['FolioDocRef'] = int(referencia.group(2))
        documento['observacion'] = lineas[1].strip()
        documentos.append(documento)
    factor = re.search(r'FACTOR DE PROPORCIONALIDAD\s+DEL IVA ES DE\s+([\d.,]+)', seccion)
    resultado = {'tipo_set': 'libro_compras', 'folio_notificacion': 2, 'documentos': documentos}
    if factor:
        resultado['factor_proporcionalidad_iva'] = round(float(factor.group(1).replace(',', '.')) * 100)
    return resultado


def _libro_guias(seccion: str) -> Dict[str, Any]:
    casos: Dict[int, Dict[str, Any]] = {}
    for numero, texto in re.findall(r'EL CASO (\d+) CORRESPONDE A UNA (.+)', seccion):
        texto = _clave(texto)
        if 'FACTURO' in texto:
            casos[int(numero)] = {'facturada': True}
        elif 'ANULADA' in texto:
            casos[int(numero)] = {'anulada': True}
    return {'tipo_set': 'libro_guias', 'folio_notificacion': 3, 'casos': casos}
