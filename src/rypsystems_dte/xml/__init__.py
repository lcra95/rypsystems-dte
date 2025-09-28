"""
Módulo XML - Manipulación y generación de XML

Utilidades para:
- Generación de XML conforme a estándares SII
- Validación de estructura
- Manipulación de documentos XML
"""

from .document import XmlDocument, DocumentBuilder, Document
from .tags import TagXmlRepository, DteTagValidator

__all__ = [
    'XmlDocument',
    'DocumentBuilder',
    'Document',
    'TagXmlRepository',
    'DteTagValidator',
]