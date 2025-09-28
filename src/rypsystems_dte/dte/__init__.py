"""
RypSystems DTE - Módulo de Documentos Tributarios Electrónicos

Componentes principales para la creación y manejo de documentos DTE.

Componentes:
- Document: Clases base para documentos DTE
- Builder: Constructores para diferentes tipos de documentos
- Factory: Fábrica para crear documentos según tipo
- Bag: Contenedor de datos y opciones de documento
"""

from .document import BaseDocument
from .factory import DTEFactory
from .builder import DTEBuilder
from .bag import DocumentBag

__all__ = ['BaseDocument', 'DTEFactory', 'DTEBuilder', 'DocumentBag']