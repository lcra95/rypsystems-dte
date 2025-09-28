"""
Módulo SII - Servicio de Impuestos Internos de Chile

Contiene las utilidades base para interactuar con el SII:
- Ambientes (certificación/producción)
- Validaciones de RUT
- Contribuyentes y entidades
- Configuraciones base
"""

from .base import SiiAmbiente, Contribuyente, PartyIdentifier
from .constants import CodigoDocumento, CategoriaDocumento, OperacionDocumento

__all__ = [
    'SiiAmbiente',
    'Contribuyente',
    'PartyIdentifier',
    'CodigoDocumento',
    'CategoriaDocumento',
    'OperacionDocumento',
]