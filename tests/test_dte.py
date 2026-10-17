"""
Tests para el módulo DTE (Documentos Tributarios Electrónicos)

Verificación completa de la funcionalidad de creación y manejo de documentos DTE.
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from rypsystems_dte.dte import DTEFactory, DTEBuilder, DocumentBag, BaseDocument
from rypsystems_dte.dte.document import FacturaAfecta, BoletaAfecta, NotaCredito
from rypsystems_dte.dte.bag import DocumentOptions
from rypsystems_dte.dte.builder import DocumentProcessor
from rypsystems_dte.sii.constants import CodigoDocumento
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.xml.document import XmlDocument
from rypsystems_dte.firma.ted import TEDValidator
from rypsystems_dte.identifier import CafError, CafFaker


class TestDocumentBag:
    """Tests para la clase DocumentBag"""

    def test_document_bag_creation(self):
        """Test creación básica de DocumentBag"""
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '76354771-K'},
                'Totales': {'MntTotal': 1000}
            }
        }

        bag = DocumentBag(CodigoDocumento.FACTURA_AFECTA, datos)

        assert bag.get_tipo_documento() == CodigoDocumento.FACTURA_AFECTA
        assert bag.get_codigo() == 33
        assert bag.get_datos() == datos
        assert not bag.is_normalized()
        assert not bag.is_validated()

    def test_document_bag_with_options(self):
        """Test DocumentBag con opciones personalizadas"""
        options = DocumentOptions(
            normalizer={'normalize': False},
            validator={'strict': True}
        )

        bag = DocumentBag(33, {}, options)

        assert bag.get_normalizer_options()['normalize'] is False
        assert bag.get_validator_options()['strict'] is True

    def test_document_bag_data_extraction(self):
        """Test extracción de datos específicos del DocumentBag"""
        datos = {
            'Encabezado': {
                'IdDoc': {'Folio': 123},
                'Emisor': {'RUTEmisor': '11111111-1'},
                'Receptor': {'RUTRecep': '22222222-2'},
                'Totales': {'MntTotal': 5000}
            }
        }

        bag = DocumentBag(33, datos)

        assert bag.get_folio() == 123
        assert bag.get_rut_emisor() == '11111111-1'
        assert bag.get_rut_receptor() == '22222222-2'
        assert bag.get_monto_total() == 5000

    def test_document_bag_validation(self):
        """Test validación de datos requeridos"""
        # Datos incompletos
        datos_incomplete = {
            'Encabezado': {
                'Emisor': {'RUTEmisor': '11111111-1'}
                # Faltan IdDoc, Totales, etc.
            }
        }

        bag = DocumentBag(33, datos_incomplete)
        errors = bag.validate_required_data()

        assert len(errors) > 0
        assert "Falta sección IdDoc" in errors

        # Datos completos
        datos_complete = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '11111111-1'},
                'Totales': {'MntTotal': 1000}
            },
            'Detalle': [{'NmbItem': 'Test'}]
        }

        bag_complete = DocumentBag(33, datos_complete)
        errors_complete = bag_complete.validate_required_data()

        assert len(errors_complete) == 0

    def test_document_bag_states(self):
        """Test manejo de estados de procesamiento"""
        bag = DocumentBag(33, {})

        # Estados iniciales
        assert not bag.is_normalized()
        assert not bag.is_sanitized()
        assert not bag.is_validated()
        assert not bag.is_stamped()
        assert not bag.is_signed()

        # Cambiar estados
        bag.set_normalized(True)
        bag.set_validated(True)
        bag.set_stamped(True)

        assert bag.is_normalized()
        assert bag.is_validated()
        assert bag.is_stamped()
        assert not bag.is_sanitized()  # No cambiado
        assert not bag.is_signed()    # No cambiado


class TestDocumentProcessor:
    """Tests para la clase DocumentProcessor"""

    def setup_method(self):
        """Setup para cada test"""
        self.processor = DocumentProcessor()

    def test_normalize_structure(self):
        """Test normalización de estructura básica"""
        datos = {'other': 'data'}  # Sin estructura base

        bag = DocumentBag(33, datos)
        self.processor.normalize(bag)

        normalized_data = bag.get_datos()
        assert 'Encabezado' in normalized_data
        assert 'IdDoc' in normalized_data['Encabezado']
        assert 'Emisor' in normalized_data['Encabezado']
        assert 'Receptor' in normalized_data['Encabezado']
        assert 'Totales' in normalized_data['Encabezado']
        assert bag.is_normalized()

    def test_normalize_dates(self):
        """Test normalización de fechas"""
        datos = {
            'Encabezado': {
                'IdDoc': {'FchEmis': '2023-12-01T10:30:00'}  # Con hora
            }
        }

        bag = DocumentBag(33, datos)
        self.processor.normalize(bag)

        fecha = bag.get_datos()['Encabezado']['IdDoc']['FchEmis']
        assert fecha == '2023-12-01'  # Solo fecha

    def test_normalize_amounts(self):
        """Test normalización de montos"""
        datos = {
            'Encabezado': {
                'Totales': {
                    'MntTotal': '1000.50',  # String
                    'IVA': '190.0'          # String
                }
            },
            'Detalle': [
                {'PrcItem': '500.75', 'QtyItem': '2.0'}
            ]
        }

        bag = DocumentBag(33, datos)
        self.processor.normalize(bag)

        normalized = bag.get_datos()
        totales = normalized['Encabezado']['Totales']
        detalle = normalized['Detalle'][0]

        assert totales['MntTotal'] == 1000  # Convertido a int
        assert totales['IVA'] == 190
        assert detalle['PrcItem'] == 500
        assert detalle['QtyItem'] == 2.0  # Cantidad como float

    def test_normalize_ruts(self):
        """Test normalización de RUTs"""
        datos = {
            'Encabezado': {
                'Emisor': {'RUTEmisor': '11111111-1'},  # Ya formateado
                'Receptor': {'RUTRecep': '111111111'}   # Sin formato
            }
        }

        bag = DocumentBag(33, datos)
        self.processor.normalize(bag)

        normalized = bag.get_datos()
        emisor = normalized['Encabezado']['Emisor']
        receptor = normalized['Encabezado']['Receptor']

        assert emisor['RUTEmisor'] == '11111111-1'
        assert receptor['RUTRecep'] == '11111111-1'  # Formateado

    def test_sanitize_strings(self):
        """Test sanitización de strings"""
        datos = {
            'Encabezado': {
                'Emisor': {
                    'RznSoc': 'Empresa\x00Test\x01'  # Con caracteres de control
                }
            }
        }

        bag = DocumentBag(33, datos)
        self.processor.sanitize(bag)

        sanitized = bag.get_datos()
        razon_social = sanitized['Encabezado']['Emisor']['RznSoc']

        assert '\x00' not in razon_social
        assert '\x01' not in razon_social
        assert razon_social == 'EmpresaTest'
        assert bag.is_sanitized()

    def test_validate_by_type(self):
        """Test validaciones específicas por tipo"""
        # Factura afecta sin IVA
        datos_sin_iva = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '11111111-1'},
                'Totales': {'MntTotal': 1000}  # Sin IVA
            },
            'Detalle': [{'NmbItem': 'Test'}]
        }

        bag = DocumentBag(CodigoDocumento.FACTURA_AFECTA, datos_sin_iva)
        errors = self.processor.validate(bag)

        assert any('IVA' in error for error in errors)

        # Documento sin detalle
        datos_sin_detalle = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '11111111-1'},
                'Totales': {'MntTotal': 1000, 'IVA': 190}
            }
            # Sin Detalle
        }

        bag_sin_detalle = DocumentBag(33, datos_sin_detalle)
        errors_detalle = self.processor.validate(bag_sin_detalle)

        assert any('detalle' in error.lower() for error in errors_detalle)


class TestDTEBuilder:
    """Tests para la clase DTEBuilder"""

    def setup_method(self):
        """Setup para cada test"""
        self.builder = DTEBuilder()

    def test_build_complete_document(self):
        """Test construcción completa de documento"""
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '76354771-K', 'RznSoc': 'Mi Empresa'},
                'Receptor': {'RUTRecep': '66666666-6', 'RznSocRecep': 'Cliente'},
                'Totales': {'MntNeto': 1000, 'IVA': 190, 'MntTotal': 1190}
            },
            'Detalle': [
                {'NmbItem': 'Producto Test', 'QtyItem': 1, 'PrcItem': 1000}
            ]
        }

        bag = DocumentBag(CodigoDocumento.FACTURA_AFECTA, datos)
        documento = self.builder.build(bag)

        assert isinstance(documento, FacturaAfecta)
        assert documento.get_codigo() == 33
        assert documento.get_folio() == 1
        assert documento.get_monto_total() == 1190
        assert documento.get_rut_emisor() == '76354771-K'

    def test_create_from_xml(self):
        """Test creación desde XML"""
        xml_content = '''<?xml version="1.0" encoding="ISO-8859-1"?>
        <DTE version="1.0">
            <Documento>
                <Encabezado>
                    <IdDoc>
                        <TipoDTE>33</TipoDTE>
                        <Folio>123</Folio>
                        <FchEmis>2023-12-01</FchEmis>
                    </IdDoc>
                    <Emisor>
                        <RUTEmisor>76354771-K</RUTEmisor>
                        <RznSoc>Test Company</RznSoc>
                    </Emisor>
                    <Totales>
                        <MntTotal>1000</MntTotal>
                    </Totales>
                </Encabezado>
                <Detalle>
                    <NmbItem>Test Item</NmbItem>
                </Detalle>
            </Documento>
        </DTE>'''

        documento = self.builder.create_from_xml(xml_content)

        assert isinstance(documento, FacturaAfecta)
        assert documento.get_folio() == 123
        assert documento.get_rut_emisor() == '76354771-K'

    def test_build_with_ted(self):
        """Test construcción con TED"""
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '76354771-K'},
                'Receptor': {'RUTRecep': '66666666-6', 'RznSocRecep': 'Cliente'},
                'Totales': {'MntNeto': 840, 'IVA': 160, 'MntTotal': 1000}
            },
            'Detalle': [{'NmbItem': 'Test'}]
        }

        bag = DocumentBag(33, datos)
        caf = CafFaker(rut='76354771-K', tipo_documento=33, desde=1, hasta=10).create()
        bag.set_caf(caf)

        documento = self.builder.build(bag)

        # Verificar que tiene TED
        plantilla_ted = documento.get_plantilla_ted()
        assert 'TED' in plantilla_ted
        assert plantilla_ted['TED']['DD']['F'] == 1
        assert plantilla_ted['TED']['DD']['RE'] == '76354771-K'

        # El TED del XML está timbrado con la clave del CAF
        xml = documento.get_xml_document().get_xml_bytes()
        assert b'<FRMT algoritmo="SHA1withRSA">' in xml
        assert TEDValidator.verify_ted_signature(xml, caf)
        assert not TEDValidator.verify_ted_signature(xml.replace(b'<MNT>1000</MNT>', b'<MNT>1001</MNT>'), caf)

    def test_build_rechaza_caf_invalido(self):
        """Un texto que no es CAF no se acepta"""
        bag = DocumentBag(33, {})
        with pytest.raises(CafError):
            bag.set_caf('fake_caf_data')


class TestBaseDocument:
    """Tests para la clase BaseDocument"""

    def test_document_basic_functionality(self):
        """Test funcionalidad básica del documento"""
        xml_content = '''<?xml version="1.0"?>
        <DTE>
            <Documento>
                <Encabezado>
                    <IdDoc>
                        <TipoDTE>33</TipoDTE>
                        <Folio>1001</Folio>
                        <FchEmis>2023-12-01</FchEmis>
                    </IdDoc>
                    <Emisor>
                        <RUTEmisor>76354771-K</RUTEmisor>
                        <RznSoc>Mi Empresa</RznSoc>
                    </Emisor>
                    <Receptor>
                        <RUTRecep>66666666-6</RUTRecep>
                        <RznSocRecep>Cliente Test S.A.</RznSocRecep>
                    </Receptor>
                    <Totales>
                        <MntNeto>1000</MntNeto>
                        <IVA>190</IVA>
                        <MntTotal>1190</MntTotal>
                    </Totales>
                </Encabezado>
                <Detalle>
                    <NmbItem>Producto de prueba</NmbItem>
                    <QtyItem>1</QtyItem>
                    <PrcItem>1000</PrcItem>
                </Detalle>
            </Documento>
        </DTE>'''

        xml_doc = XmlDocument(xml_content)
        documento = FacturaAfecta(xml_doc)

        # Tests básicos
        assert documento.get_codigo() == 33
        assert documento.get_folio() == 1001
        assert str(documento) == "76354771-K_T033F000001001"
        assert documento.get_id() == "76354771-K_T033F000001001"

        # Tests de datos
        assert documento.get_rut_emisor() == "76354771-K"
        assert documento.get_rut_receptor() == "66666666-6"
        assert documento.get_razon_social_receptor() == "Cliente Test S.A."
        assert documento.get_fecha_emision() == "2023-12-01"
        assert documento.get_monto_total() == 1190

        # Tests de estructura
        emisor = documento.get_emisor()
        assert emisor['RUTEmisor'] == '76354771-K'
        assert emisor['RznSoc'] == 'Mi Empresa'

        receptor = documento.get_receptor()
        assert receptor['RUTRecep'] == '66666666-6'

        totales = documento.get_totales()
        assert totales['MntTotal'] == 1190
        assert totales['IVA'] == 190

        # Test detalle
        detalle = documento.get_detalle()
        assert len(detalle) == 1
        assert detalle[0]['NmbItem'] == 'Producto de prueba'

        # Test detalle específico
        primer_item = documento.get_detalle(0)
        assert primer_item['QtyItem'] == 1

    def test_document_validation_error(self):
        """Test error de validación de tipo de documento"""
        xml_content = '''<?xml version="1.0"?>
        <DTE>
            <Documento>
                <Encabezado>
                    <IdDoc>
                        <TipoDTE>39</TipoDTE>
                    </IdDoc>
                </Encabezado>
            </Documento>
        </DTE>'''

        xml_doc = XmlDocument(xml_content)

        # Intentar crear factura afecta con XML de boleta
        with pytest.raises(ValueError, match="código 39.*no corresponde.*33"):
            FacturaAfecta(xml_doc)

    def test_document_ted_functionality(self):
        """Test funcionalidad TED del documento"""
        xml_content = '''<?xml version="1.0"?>
        <DTE>
            <Documento>
                <Encabezado>
                    <IdDoc>
                        <TipoDTE>33</TipoDTE>
                        <Folio>1</Folio>
                        <FchEmis>2023-12-01</FchEmis>
                    </IdDoc>
                    <Emisor>
                        <RUTEmisor>76354771-K</RUTEmisor>
                    </Emisor>
                    <Receptor>
                        <RUTRecep>66666666-6</RUTRecep>
                        <RznSocRecep>Cliente</RznSocRecep>
                    </Receptor>
                    <Totales>
                        <MntTotal>1000</MntTotal>
                    </Totales>
                </Encabezado>
                <Detalle>
                    <NmbItem>Producto Test</NmbItem>
                </Detalle>
            </Documento>
        </DTE>'''

        xml_doc = XmlDocument(xml_content)
        documento = FacturaAfecta(xml_doc)

        # Test plantilla TED
        plantilla_ted = documento.get_plantilla_ted()

        assert 'TED' in plantilla_ted
        ted = plantilla_ted['TED']

        assert ted['@attributes']['version'] == '1.0'
        assert ted['DD']['RE'] == '76354771-K'
        assert ted['DD']['TD'] == 33
        assert ted['DD']['F'] == 1
        assert ted['DD']['FE'] == '2023-12-01'
        assert ted['DD']['RR'] == '66666666-6'
        assert ted['DD']['RSR'] == 'Cliente'
        assert ted['DD']['MNT'] == 1000
        assert ted['DD']['IT1'] == 'Producto Test'


class TestDTEFactory:
    """Tests para la clase DTEFactory"""

    def setup_method(self):
        """Setup para cada test"""
        self.factory = DTEFactory()

    def test_create_document_basic(self):
        """Test creación básica de documento"""
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '76354771-K'},
                'Totales': {'MntNeto': 1000, 'IVA': 190, 'MntTotal': 1190}
            },
            'Detalle': [{'NmbItem': 'Test', 'QtyItem': 1, 'PrcItem': 1000}]
        }

        documento = self.factory.create_document(CodigoDocumento.FACTURA_AFECTA, datos)

        assert isinstance(documento, FacturaAfecta)
        assert documento.get_monto_total() == 1190

    def test_create_factura_afecta(self):
        """Test creación de factura afecta con helper"""
        emisor = Contribuyente("76354771-K", "Mi Empresa")
        receptor = Contribuyente("66666666-6", "Cliente S.A.")
        detalle = [
            {'NmbItem': 'Producto 1', 'QtyItem': 1, 'PrcItem': 1000},
            {'NmbItem': 'Producto 2', 'QtyItem': 2, 'PrcItem': 500}
        ]

        factura = self.factory.create_factura_afecta(
            emisor=emisor,
            receptor=receptor,
            folio=1001,
            fecha_emision='2023-12-01',
            detalle=detalle
        )

        assert isinstance(factura, FacturaAfecta)
        assert factura.get_folio() == 1001
        assert factura.get_rut_emisor() == "76354771-K"
        assert factura.get_rut_receptor() == "66666666-6"

        # Verificar cálculo de totales
        assert factura.get_monto_total() == 2380  # (1000 + 1000) * 1.19

        # Verificar detalle
        detalle_doc = factura.get_detalle()
        assert len(detalle_doc) == 2
        assert detalle_doc[0]['NmbItem'] == 'Producto 1'

    def test_create_boleta_afecta(self):
        """Test creación de boleta afecta"""
        emisor = Contribuyente("76354771-K", "Mi Empresa")
        detalle = [{'NmbItem': 'Servicio', 'QtyItem': 1, 'PrcItem': 5000}]

        boleta = self.factory.create_boleta_afecta(
            emisor=emisor,
            folio=2001,
            fecha_emision='2023-12-01',
            detalle=detalle
        )

        assert isinstance(boleta, BoletaAfecta)
        assert boleta.get_codigo() == 39
        assert boleta.get_folio() == 2001
        assert boleta.get_monto_total() == 5950  # 5000 * 1.19

    def test_create_nota_credito(self):
        """Test creación de nota de crédito"""
        emisor = Contribuyente("76354771-K", "Mi Empresa")
        receptor = Contribuyente("66666666-6", "Cliente S.A.")
        detalle = [{'NmbItem': 'Descuento', 'QtyItem': 1, 'PrcItem': -1000}]
        referencia = {
            'TpoDocRef': 33,
            'FolioRef': 1001,
            'FchRef': '2023-11-01',
            'CodRef': 1,
            'RazonRef': 'Descuento por error'
        }

        nota = self.factory.create_nota_credito(
            emisor=emisor,
            receptor=receptor,
            folio=3001,
            fecha_emision='2023-12-01',
            detalle=detalle,
            documento_referencia=referencia
        )

        assert isinstance(nota, NotaCredito)
        assert nota.get_codigo() == 61
        assert nota.get_folio() == 3001

        # Verificar referencia
        datos = nota.get_datos()
        assert 'Referencia' in datos
        assert datos['Referencia'][0]['FolioRef'] == 1001

    def test_factory_supported_types(self):
        """Test tipos de documento soportados"""
        tipos = self.factory.get_supported_types()

        assert CodigoDocumento.FACTURA_AFECTA in tipos
        assert CodigoDocumento.BOLETA_AFECTA in tipos
        assert CodigoDocumento.NOTA_CREDITO in tipos
        assert len(tipos) >= 3

    def test_factory_validation(self):
        """Test validación de datos sin crear documento"""
        # Datos inválidos
        datos_invalidos = {
            'Encabezado': {
                'Emisor': {}  # Sin RUT
            }
        }

        errors = self.factory.validate_document_data(33, datos_invalidos)
        assert len(errors) > 0

        # Datos válidos
        datos_validos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '76354771-K'},
                'Totales': {'MntNeto': 1000, 'IVA': 190, 'MntTotal': 1190}
            },
            'Detalle': [{'NmbItem': 'Test'}]
        }

        errors_validos = self.factory.validate_document_data(33, datos_validos)
        assert len(errors_validos) == 0


class TestIntegration:
    """Tests de integración del módulo DTE completo"""

    def test_end_to_end_workflow(self):
        """Test workflow completo end-to-end"""
        factory = DTEFactory()

        # 1. Crear contribuyentes
        emisor = Contribuyente("76354771-K", "Mi Empresa Limitada", "Servicios informáticos")
        receptor = Contribuyente("66666666-6", "Cliente de Prueba S.A.", "Comercio general")

        # 2. Crear detalle del documento
        detalle = [
            {
                'NmbItem': 'Servicio de desarrollo software',
                'DscItem': 'Desarrollo de aplicación web personalizada',
                'QtyItem': 1,
                'PrcItem': 100000
            },
            {
                'NmbItem': 'Hosting mensual',
                'DscItem': 'Hosting y mantenimiento servidor',
                'QtyItem': 12,
                'PrcItem': 5000
            }
        ]

        # 3. Crear documento
        factura = factory.create_factura_afecta(
            emisor=emisor,
            receptor=receptor,
            folio=1001,
            fecha_emision='2023-12-01',
            detalle=detalle
        )

        # 4. Verificar documento creado
        assert isinstance(factura, FacturaAfecta)
        assert factura.get_id() == "76354771-K_T033F000001001"
        assert factura.get_monto_total() == 190400  # (100000 + 60000) * 1.19

        # 5. Verificar XML generado
        xml_content = factura.save_xml()
        assert '<?xml version="1.0"' in xml_content
        assert '<TipoDTE>33</TipoDTE>' in xml_content
        assert '<Folio>1001</Folio>' in xml_content

        # 6. Verificar TED
        plantilla_ted = factura.get_plantilla_ted()
        assert plantilla_ted['TED']['DD']['MNT'] == 190400
        assert plantilla_ted['TED']['DD']['IT1'] == 'Servicio de desarrollo software'

        # 7. Recrear documento desde XML
        factory_2 = DTEFactory()
        documento_recreado = factory_2.create_from_xml(xml_content)

        assert isinstance(documento_recreado, FacturaAfecta)
        assert documento_recreado.get_folio() == factura.get_folio()
        assert documento_recreado.get_monto_total() == factura.get_monto_total()

    def test_multiple_document_types(self):
        """Test creación de múltiples tipos de documentos"""
        factory = DTEFactory()
        emisor = Contribuyente("76354771-K", "Mi Empresa")
        receptor = Contribuyente("66666666-6", "Cliente")

        # Factura afecta
        factura = factory.create_factura_afecta(
            emisor, receptor, 1001, '2023-12-01',
            [{'NmbItem': 'Producto', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        # Boleta afecta
        boleta = factory.create_boleta_afecta(
            emisor, 2001, '2023-12-01',
            [{'NmbItem': 'Servicio', 'QtyItem': 1, 'PrcItem': 500}]
        )

        # Nota de crédito
        nota = factory.create_nota_credito(
            emisor, receptor, 3001, '2023-12-01',
            [{'NmbItem': 'Descuento', 'QtyItem': 1, 'PrcItem': -100}],
            {'TpoDocRef': 33, 'FolioRef': 1001, 'CodRef': 1}
        )

        # Verificar tipos
        assert factura.get_codigo() == 33
        assert boleta.get_codigo() == 39
        assert nota.get_codigo() == 61

        # Verificar cálculos
        assert factura.get_monto_total() == 1190  # 1000 * 1.19
        assert boleta.get_monto_total() == 595    # 500 * 1.19
        assert nota.get_monto_total() == -119     # -100 * 1.19

    def test_error_handling(self):
        """Test manejo de errores en el workflow"""
        factory = DTEFactory()

        # XML inválido
        with pytest.raises(Exception):
            factory.create_from_xml("<invalid>xml</invalid>")

        # Tipo de documento no soportado
        with pytest.raises(ValueError):
            DocumentBag(999, {})  # Código inexistente

        # Datos incompletos
        with pytest.raises(ValueError):
            factory.create_document(33, {})  # Sin datos mínimos