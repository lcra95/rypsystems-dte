"""
RypSystems DTE - Librería para documentos tributarios electrónicos Chile
Traducción de LibreDTE Core a Python

Esta librería mantiene EXACTAMENTE la misma funcionalidad y salidas que
la versión PHP original de LibreDTE Core.
"""

__version__ = "1.0.0"
__author__ = "RypSystems"
__description__ = "Librería Python para documentos tributarios electrónicos (DTE) del SII de Chile"

# Importaciones principales
from .sii import SiiAmbiente, Contribuyente, PartyIdentifier

__all__ = [
    'SiiAmbiente',
    'Contribuyente',
    'PartyIdentifier',
]