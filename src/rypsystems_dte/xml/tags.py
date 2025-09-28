"""
Mapeo de tags XML a glosas y entidades.

Traducción directa del archivo tag_xml.php de LibreDTE.
Proporciona metadatos sobre las etiquetas XML usadas en documentos DTE.
"""

from typing import Dict, Any, Optional
from enum import Enum


class TagXmlRepository:
    """
    Repositorio de metadatos de tags XML para documentos DTE.

    Traducción de resources/data/repository/tag_xml.php.
    Mapea nombres de tags XML a sus glosas descriptivas y entidades asociadas.
    """

    # Mapeo completo de tags XML (traducción directa del PHP)
    TAG_XML_DATA: Dict[str, Dict[str, Any]] = {
        # Etiquetas de Aduana que tienen datos asociados a sus valores
        'FmaPagExp': {
            'glosa': 'Forma pago exp.',
            'entity': 'AduanaFormaPago',
        },
        'CodModVenta': {
            'glosa': 'Mod. venta',
            'entity': 'AduanaModalidadVenta',
        },
        'CodClauVenta': {
            'glosa': 'Claú. venta',
            'entity': 'AduanaClausulaVenta',
        },
        'CodViaTransp': {
            'glosa': 'Transporte',
            'entity': 'AduanaTransporte',
        },
        'TipoBultos': {
            'glosa': 'Bultos',
            'entity': 'AduanaTipoBulto',
        },
        'CodPaisRecep': {
            'glosa': 'P. receptor',
            'entity': 'AduanaPais',
        },
        'CodPaisDestin': {
            'glosa': 'P. destino',
            'entity': 'AduanaPais',
        },
        'CodPtoEmbarque': {
            'glosa': 'Embarque',
            'entity': 'AduanaPuerto',
        },
        'CodPtoDesemb': {
            'glosa': 'Desembarq.',
            'entity': 'AduanaPuerto',
        },
        'CodUnidMedTara': {
            'glosa': 'U. tara',
            'entity': 'AduanaUnidad',
        },
        'CodUnidPesoBruto': {
            'glosa': 'U. p. bruto',
            'entity': 'AduanaUnidad',
        },
        'CodUnidPesoNeto': {
            'glosa': 'U. p. neto',
            'entity': 'AduanaUnidad',
        },
        'Nacionalidad': {
            'glosa': 'Nacionalidad',
            'entity': 'AduanaPais',
        },

        # Códigos que no tienen un grupo de datos asociados, valores "libres"
        'TotClauVenta': {
            'glosa': 'Total claú.',
        },
        'NombreTransp': {
            'glosa': 'Nomb. trans.',
        },
        'RUTCiaTransp': {
            'glosa': 'RUT trans.',
        },
        'NomCiaTransp': {
            'glosa': 'Comp. trans.',
        },
        'IdAdicTransp': {
            'glosa': 'Trans. Ad.',
        },
        'Booking': {
            'glosa': 'Booking',
        },
        'Operador': {
            'glosa': 'Operador',
        },
        'IdAdicPtoEmb': {
            'glosa': 'Embarq. Ad.',
        },
        'IdAdicPtoDesemb': {
            'glosa': 'Desemb. Ad.',
        },
        'Tara': {
            'glosa': 'Tara',
        },
        'PesoBruto': {
            'glosa': 'Peso bruto',
        },
        'PesoNeto': {
            'glosa': 'Peso neto',
        },
        'TotItems': {
            'glosa': 'Items',
        },
        'TotBultos': {
            'glosa': 'Total bultos',
        },
        'MntFlete': {
            'glosa': 'Flete',
        },
        'MntSeguro': {
            'glosa': 'Seguro',
        },

        # Grupos de códigos no oficiales del SII (ni Aduana), pero útiles
        # para acceder a los datos asociados donde se necesiten
        'pais': {
            'glosa': 'País',
            'entity': 'AduanaPais',
        },
        'puerto': {
            'glosa': 'Puerto',
            'entity': 'AduanaPuerto',
        },
        'unidad': {
            'glosa': 'Unidad',
            'entity': 'AduanaUnidad',
        },
    }

    @classmethod
    def get_tag_info(cls, tag: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información de un tag XML.

        Args:
            tag: Nombre del tag XML

        Returns:
            Diccionario con información del tag o None si no existe
        """
        return cls.TAG_XML_DATA.get(tag)

    @classmethod
    def get_tag_glosa(cls, tag: str) -> Optional[str]:
        """
        Obtiene la glosa descriptiva de un tag XML.

        Args:
            tag: Nombre del tag XML

        Returns:
            Glosa del tag o None si no existe
        """
        info = cls.get_tag_info(tag)
        return info.get('glosa') if info else None

    @classmethod
    def get_tag_entity(cls, tag: str) -> Optional[str]:
        """
        Obtiene la entidad asociada a un tag XML.

        Args:
            tag: Nombre del tag XML

        Returns:
            Nombre de la entidad asociada o None si no existe
        """
        info = cls.get_tag_info(tag)
        return info.get('entity') if info else None

    @classmethod
    def has_entity(cls, tag: str) -> bool:
        """
        Verifica si un tag tiene una entidad asociada.

        Args:
            tag: Nombre del tag XML

        Returns:
            True si tiene entidad asociada, False en caso contrario
        """
        return cls.get_tag_entity(tag) is not None

    @classmethod
    def get_all_tags(cls) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene todos los tags XML disponibles.

        Returns:
            Diccionario completo con todos los tags y su información
        """
        return cls.TAG_XML_DATA.copy()

    @classmethod
    def get_tags_by_entity(cls, entity: str) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene todos los tags asociados a una entidad específica.

        Args:
            entity: Nombre de la entidad

        Returns:
            Diccionario con tags que pertenecen a la entidad
        """
        return {
            tag: info for tag, info in cls.TAG_XML_DATA.items()
            if info.get('entity') == entity
        }

    @classmethod
    def get_aduana_tags(cls) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene todos los tags relacionados con Aduana.

        Returns:
            Diccionario con tags de Aduana
        """
        aduana_tags = {}
        for tag, info in cls.TAG_XML_DATA.items():
            if 'entity' in info and info['entity'].startswith('Aduana'):
                aduana_tags[tag] = info
        return aduana_tags


class DteTagValidator:
    """
    Validador de tags XML para documentos DTE.

    Proporciona validaciones específicas para tags según
    los estándares del SII de Chile.
    """

    # Tags requeridos por tipo de documento
    REQUIRED_TAGS_BY_TYPE = {
        33: [  # Factura Afecta
            'TipoDTE', 'Folio', 'FchEmis', 'RUTEmisor', 'RznSoc',
            'RUTRecep', 'RznSocRecep', 'MntNeto', 'TasaIVA', 'IVA', 'MntTotal'
        ],
        34: [  # Factura Exenta
            'TipoDTE', 'Folio', 'FchEmis', 'RUTEmisor', 'RznSoc',
            'RUTRecep', 'RznSocRecep', 'MntExe', 'MntTotal'
        ],
        39: [  # Boleta Afecta
            'TipoDTE', 'Folio', 'FchEmis', 'RUTEmisor', 'RznSoc',
            'MntNeto', 'TasaIVA', 'IVA', 'MntTotal'
        ],
        52: [  # Guía de Despacho
            'TipoDTE', 'Folio', 'FchEmis', 'RUTEmisor', 'RznSoc',
            'RUTRecep', 'RznSocRecep', 'IndTraslado'
        ],
    }

    # Tags específicos de exportación
    EXPORT_TAGS = [
        'CodModVenta', 'CodClauVenta', 'TotClauVenta', 'CodViaTransp',
        'NombreTransp', 'RUTCiaTransp', 'NomCiaTransp', 'CodPtoEmbarque',
        'IdAdicPtoEmb', 'CodPtoDesemb', 'IdAdicPtoDesemb', 'Tara',
        'CodUnidMedTara', 'PesoBruto', 'CodUnidPesoBruto', 'PesoNeto',
        'CodUnidPesoNeto', 'TotItems', 'TotBultos', 'TipoBultos',
        'MntFlete', 'MntSeguro', 'CodPaisRecep', 'CodPaisDestin'
    ]

    @classmethod
    def validate_required_tags(cls, xml_data: Dict[str, Any], tipo_dte: int) -> Dict[str, Any]:
        """
        Valida que estén presentes los tags requeridos para un tipo de DTE.

        Args:
            xml_data: Datos del XML como diccionario
            tipo_dte: Código del tipo de DTE

        Returns:
            Diccionario con resultado de validación
        """
        required_tags = cls.REQUIRED_TAGS_BY_TYPE.get(tipo_dte, [])
        missing_tags = []

        def find_tag_in_data(data: Any, tag: str) -> bool:
            """Busca un tag recursivamente en los datos."""
            if isinstance(data, dict):
                if tag in data:
                    return True
                for value in data.values():
                    if find_tag_in_data(value, tag):
                        return True
            elif isinstance(data, list):
                for item in data:
                    if find_tag_in_data(item, tag):
                        return True
            return False

        for tag in required_tags:
            if not find_tag_in_data(xml_data, tag):
                missing_tags.append(tag)

        return {
            'valid': len(missing_tags) == 0,
            'missing_tags': missing_tags,
            'required_tags': required_tags,
            'tipo_dte': tipo_dte
        }

    @classmethod
    def is_export_document(cls, xml_data: Dict[str, Any]) -> bool:
        """
        Determina si un documento es de exportación basado en sus tags.

        Args:
            xml_data: Datos del XML como diccionario

        Returns:
            True si es documento de exportación, False en caso contrario
        """
        def find_export_tags(data: Any) -> int:
            """Cuenta tags de exportación encontrados."""
            count = 0
            if isinstance(data, dict):
                for key, value in data.items():
                    if key in cls.EXPORT_TAGS:
                        count += 1
                    count += find_export_tags(value)
            elif isinstance(data, list):
                for item in data:
                    count += find_export_tags(item)
            return count

        # Si tiene 3 o más tags de exportación, probablemente es documento de exportación
        export_tag_count = find_export_tags(xml_data)
        return export_tag_count >= 3

    @classmethod
    def validate_tag_values(cls, tag: str, value: Any) -> Dict[str, Any]:
        """
        Valida el valor de un tag específico.

        Args:
            tag: Nombre del tag
            value: Valor a validar

        Returns:
            Diccionario con resultado de validación
        """
        validation = {
            'tag': tag,
            'value': value,
            'valid': True,
            'errors': []
        }

        # Validaciones específicas por tag
        if tag == 'TipoDTE':
            if not isinstance(value, (int, str)) or int(value) not in [29, 30, 32, 33, 34, 35, 38, 39, 40, 41, 43, 45, 46, 48, 50, 52, 55, 56, 60, 61, 101, 102, 103, 104, 105, 106, 108, 109, 110, 111, 112]:
                validation['valid'] = False
                validation['errors'].append('Tipo de DTE inválido')

        elif tag in ['RUTEmisor', 'RUTRecep', 'RUTCiaTransp']:
            # Validar formato RUT (básico)
            if not isinstance(value, str) or not value:
                validation['valid'] = False
                validation['errors'].append('RUT debe ser string no vacío')

        elif tag == 'FchEmis':
            # Validar formato fecha YYYY-MM-DD (más flexible)
            if not isinstance(value, str) or not value:
                validation['valid'] = False
                validation['errors'].append('Fecha debe ser string no vacío')
            elif len(value) != 10 or value.count('-') != 2:
                validation['valid'] = False
                validation['errors'].append('Fecha debe tener formato YYYY-MM-DD')

        elif tag in ['MntNeto', 'MntExe', 'MntTotal', 'IVA']:
            # Validar montos
            try:
                float(value)
            except (ValueError, TypeError):
                validation['valid'] = False
                validation['errors'].append('Monto debe ser numérico')

        elif tag == 'TasaIVA':
            # Validar tasa IVA
            try:
                tasa = float(value)
                if tasa < 0 or tasa > 100:
                    validation['valid'] = False
                    validation['errors'].append('Tasa IVA debe estar entre 0 y 100')
            except (ValueError, TypeError):
                validation['valid'] = False
                validation['errors'].append('Tasa IVA debe ser numérica')

        return validation