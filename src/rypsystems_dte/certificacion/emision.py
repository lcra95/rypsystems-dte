"""
Emisión de los documentos de un set de pruebas (o de la simulación).

Arma cada caso con los datos del emisor, encadena las referencias entre
casos y agrega la referencia al set que exige el SII:
- DTE: primera línea TpoDocRef SET, RazonRef "CASO <número>".
- Boletas: CodRef SET, RazonRef "CASO-n".

"Utilice RUT distintos para las distintas facturas": los documentos
originales rotan entre los receptores entregados; las notas usan el
receptor del documento que referencian.
"""

import copy
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from ..emision import BOLETAS, DocumentoEmitido, EmisionError, emitir_documento
from ..firma import DigitalCertificate
from ..identifier import Caf

RECEPTOR_BOLETA = {'RUTRecep': '66666666-6'}


@dataclass
class CasoEmitido:
    caso: str
    documento: DocumentoEmitido
    referencia: Optional[Dict[str, Any]] = None  # {'caso', 'tipo', 'folio', 'CodRef'} del documento referenciado


def emitir_set(set_datos: Dict[str, Any], emisor: Dict[str, Any], certificado: DigitalCertificate,
               asignar_folio: Callable[[int], Tuple[Caf, int]], receptores: Iterable[Dict[str, Any]] = (),
               fecha: Optional[str] = None) -> List[CasoEmitido]:
    """
    Emite todos los casos de un set, en orden.

    Args:
        set_datos: Set leído con leer_set_pruebas() o un YAML de examples/sets/
            (casos, y opcionalmente referencia_set: false para la simulación).
        emisor: Nodo Emisor (con RUTEmisor).
        asignar_folio: Entrega (CAF, folio) del tipo pedido; quien llama
            controla qué folios se usan.
        receptores: Receptores que rotan en los documentos originales (no
            se usan en boletas ni en casos que traen su propio receptor).

    Raises:
        EmisionError: indicando el caso que falló.
    """
    casos = set_datos['casos']
    fecha = fecha or date.today().isoformat()
    referencia_set = set_datos.get('referencia_set', True)
    tipos = {c['tipo'] for c in casos}
    boletas = tipos <= set(BOLETAS)
    if not boletas and tipos & set(BOLETAS):
        raise EmisionError('Un set no puede mezclar boletas con otros documentos.')
    receptores = [dict(r) for r in receptores]
    if not boletas and not receptores and not all(c.get('receptor') or c.get('referencia') or
                                                  (c.get('encabezado') or {}).get('Receptor') for c in casos):
        raise EmisionError('Falta al menos un receptor para los documentos del set.')

    emitidos: Dict[str, Dict[str, Any]] = {}
    resultado: List[CasoEmitido] = []
    siguiente_receptor = 0
    for caso in casos:
        tipo = caso['tipo']
        caf, folio = asignar_folio(tipo)
        ref = caso.get('referencia')
        detalle = caso.get('detalle')
        if detalle == 'copiar':
            detalle = copy.deepcopy(emitidos[ref['caso']]['detalle'])

        if referencia_set and boletas:
            referencias = [{'CodRef': 'SET', 'RazonRef': caso['caso']}]
        elif referencia_set:
            referencias = [{'TpoDocRef': 'SET', 'FolioRef': folio, 'FchRef': fecha, 'RazonRef': f'CASO {caso["caso"]}'}]
        else:
            referencias = []
        referencias += copy.deepcopy(caso.get('referencias_extra') or [])

        encabezado = copy.deepcopy(caso.get('encabezado') or {})
        if ref:
            if ref['caso'] not in emitidos:
                raise EmisionError(f'Caso {caso["caso"]}: referencia al caso {ref["caso"]}, que no se emitió antes.')
            original = emitidos[ref['caso']]
            receptor = dict(original['receptor'])
            # El documento referenciado va antes de las otras referencias (SNA, DUS...).
            referencias.insert(1 if referencia_set and not boletas else 0, {
                'TpoDocRef': original['tipo'], 'FolioRef': original['folio'], 'FchRef': original['fecha'],
                'CodRef': ref['CodRef'], 'RazonRef': ref['RazonRef'],
            })
        elif caso.get('receptor'):
            receptor = dict(caso['receptor'])
        elif boletas:
            receptor = dict(RECEPTOR_BOLETA)
        else:
            # También avanza cuando el encabezado trae su receptor (exportación),
            # para que la rotación no dependa de los datos de cada caso.
            receptor = dict(receptores[siguiente_receptor % len(receptores)]) if receptores else {}
            siguiente_receptor += 1
        if encabezado.get('Receptor') and not ref:
            receptor = dict(encabezado['Receptor'])
        encabezado.pop('Receptor', None)

        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': tipo, 'Folio': folio, 'FchEmis': fecha, **encabezado.pop('IdDoc', {})},
                'Emisor': dict(emisor),
                'Receptor': receptor,
                **encabezado,
            },
            'Detalle': copy.deepcopy(detalle),
            'DscRcgGlobal': copy.deepcopy(caso.get('descuentos_recargos') or False),
            'Referencia': referencias or False,
            'Comisiones': copy.deepcopy(caso.get('comisiones') or False),
        }
        try:
            documento = emitir_documento(datos, caf, certificado)
        except EmisionError as e:
            raise EmisionError(f'Caso {caso["caso"]}: {e}') from e
        emitidos[caso['caso']] = {'tipo': tipo, 'folio': folio, 'fecha': fecha, 'detalle': detalle,
                                  'receptor': datos['Encabezado']['Receptor']}
        resultado.append(CasoEmitido(caso['caso'], documento, {
            'caso': ref['caso'], 'tipo': emitidos[ref['caso']]['tipo'], 'folio': emitidos[ref['caso']]['folio'],
            'CodRef': ref['CodRef']} if ref else None))
    return resultado
