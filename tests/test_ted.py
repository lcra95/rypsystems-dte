"""
Tests para el módulo TED (Timbre Electrónico DTE)

Verificación de generación y validación de TED según normativa SII
"""

import pytest
import xml.etree.ElementTree as ET
from datetime import datetime

from rypsystems_dte.firma.ted import (
    TEDData,
    TEDBuilder,
    TEDValidator,
    create_ted_from_document,
    generate_ted_barcode_from_data
)


class TestTEDData:
    """Tests para la clase TEDData"""

    def test_ted_data_creation_valid(self):
        """Test creación exitosa de TEDData con datos válidos"""
        ted_data = TEDData(
            rut_emisor="76354771-K",
            tipo_documento=33,
            folio=1001,
            fecha_emision="2023-12-01",
            rut_receptor="66666666-6",
            razon_social_receptor="Cliente Test S.A.",
            monto_total=119000,
            primer_item="Servicio de consultoría"
        )

        assert ted_data.rut_emisor == "76354771-K"
        assert ted_data.tipo_documento == 33
        assert ted_data.folio == 1001
        assert ted_data.monto_total == 119000

    def test_ted_data_rut_validation(self):
        """Test validación de RUT en TEDData"""
        # RUT válido
        ted_data = TEDData(
            rut_emisor="11111111-1",
            tipo_documento=33,
            folio=1,
            fecha_emision="2023-12-01",
            rut_receptor="22222222-2",
            razon_social_receptor="Test",
            monto_total=1000
        )
        assert ted_data.rut_emisor == "11111111-1"

        # RUT inválido
        with pytest.raises(ValueError, match="RUT inválido"):
            TEDData(
                rut_emisor="12345678-0",  # DV incorrecto
                tipo_documento=33,
                folio=1,
                fecha_emision="2023-12-01",
                rut_receptor="11111111-1",
                razon_social_receptor="Test",
                monto_total=1000
            )

    def test_ted_data_text_truncation(self):
        """Test truncamiento de campos de texto a 40 caracteres"""
        long_text = "Esta es una razón social muy larga que excede los 40 caracteres permitidos"

        ted_data = TEDData(
            rut_emisor="11111111-1",
            tipo_documento=33,
            folio=1,
            fecha_emision="2023-12-01",
            rut_receptor="22222222-2",
            razon_social_receptor=long_text,
            monto_total=1000,
            primer_item=long_text
        )

        assert len(ted_data.razon_social_receptor) == 40
        assert len(ted_data.primer_item) == 40
        assert ted_data.razon_social_receptor == long_text[:40]

    def test_ted_data_fecha_validation(self):
        """Test validación de formato de fecha"""
        # Fecha válida
        ted_data = TEDData(
            rut_emisor="11111111-1",
            tipo_documento=33,
            folio=1,
            fecha_emision="2023-12-01",
            rut_receptor="22222222-2",
            razon_social_receptor="Test",
            monto_total=1000
        )
        assert ted_data.fecha_emision == "2023-12-01"

        # Fecha inválida
        with pytest.raises(ValueError, match="Formato de fecha inválido"):
            TEDData(
                rut_emisor="11111111-1",
                tipo_documento=33,
                folio=1,
                fecha_emision="01/12/2023",  # Formato incorrecto
                rut_receptor="22222222-2",
                razon_social_receptor="Test",
                monto_total=1000
            )


class TestTEDBuilder:
    """Tests para la clase TEDBuilder"""

    def setup_method(self):
        """Setup para cada test"""
        self.builder = TEDBuilder()
        self.sample_ted_data = TEDData(
            rut_emisor="76354771-K",
            tipo_documento=33,
            folio=1001,
            fecha_emision="2023-12-01",
            rut_receptor="66666666-6",
            razon_social_receptor="Cliente Test S.A.",
            monto_total=119000,
            primer_item="Servicio de consultoría"
        )

    def test_build_ted_template_structure(self):
        """Test estructura correcta de plantilla TED"""
        template = self.builder.build_ted_template(self.sample_ted_data)

        # Verificar estructura básica
        assert 'TED' in template
        ted = template['TED']
        assert '@attributes' in ted
        assert ted['@attributes']['version'] == '1.0'
        assert 'DD' in ted
        assert 'FRMT' in ted

    def test_build_ted_template_dd_content(self):
        """Test contenido correcto del elemento DD"""
        template = self.builder.build_ted_template(self.sample_ted_data)
        dd = template['TED']['DD']

        assert dd['RE'] == "76354771-K"
        assert dd['TD'] == 33
        assert dd['F'] == 1001
        assert dd['FE'] == "2023-12-01"
        assert dd['RR'] == "66666666-6"
        assert dd['RSR'] == "Cliente Test S.A."
        assert dd['MNT'] == 119000
        assert dd['IT1'] == "Servicio de consultoría"
        assert dd['CAF'] == ""  # Vacío inicialmente
        assert dd['TSTED'] == ""  # Vacío inicialmente

    def test_build_ted_template_frmt_structure(self):
        """Test estructura del elemento FRMT"""
        template = self.builder.build_ted_template(self.sample_ted_data)
        frmt = template['TED']['FRMT']

        assert '@attributes' in frmt
        assert frmt['@attributes']['algoritmo'] == 'SHA1withRSA'
        assert frmt['@value'] == ''  # Vacío inicialmente

    def test_build_ted_from_document_data(self):
        """Test construcción de TED desde datos de documento"""
        document_data = {
            'Encabezado': {
                'IdDoc': {
                    'TipoDTE': 33,
                    'Folio': 1001,
                    'FchEmis': '2023-12-01'
                },
                'Emisor': {
                    'RUTEmisor': '76354771-K'
                },
                'Receptor': {
                    'RUTRecep': '66666666-6',
                    'RznSocRecep': 'Cliente Test S.A.'
                },
                'Totales': {
                    'MntTotal': 119000
                }
            },
            'Detalle': [
                {'NmbItem': 'Servicio de consultoría'},
                {'NmbItem': 'Otro item'}
            ]
        }

        template = self.builder.build_ted_from_document_data(document_data)
        dd = template['TED']['DD']

        assert dd['RE'] == "76354771-K"
        assert dd['TD'] == 33
        assert dd['F'] == 1001
        assert dd['IT1'] == "Servicio de consultoría"  # Solo primer item

    def test_build_ted_from_document_data_single_detail(self):
        """Test construcción con detalle único (no lista)"""
        document_data = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '11111111-1'},
                'Receptor': {'RUTRecep': '22222222-2', 'RznSocRecep': 'Test'},
                'Totales': {'MntTotal': 1000}
            },
            'Detalle': {'NmbItem': 'Item único'}
        }

        template = self.builder.build_ted_from_document_data(document_data)
        assert template['TED']['DD']['IT1'] == "Item único"

    def test_generate_ted_xml_valid(self):
        """Test generación de XML válido"""
        template = self.builder.build_ted_template(self.sample_ted_data)
        ted_xml = self.builder.generate_ted_xml(template)

        # Verificar que es XML válido
        root = ET.fromstring(ted_xml)
        assert root.tag == 'TED'

        # Verificar elementos principales
        dd = root.find('DD')
        frmt = root.find('FRMT')
        assert dd is not None
        assert frmt is not None

    def test_generate_ted_canonicalized(self):
        """Test generación de TED canonicalizado"""
        template = self.builder.build_ted_template(self.sample_ted_data)
        canonicalized = self.builder.generate_ted_canonicalized(template)

        assert isinstance(canonicalized, str)
        assert len(canonicalized) > 0
        assert '<TED' in canonicalized

    def test_generate_ted_barcode(self):
        """Test generación de código de barras TED"""
        template = self.builder.build_ted_template(self.sample_ted_data)
        barcode = self.builder.generate_ted_barcode(template)

        assert barcode.startswith("data:image/png;base64,")


class TestTEDValidator:
    """Tests para la clase TEDValidator"""

    def test_validate_ted_structure_valid(self):
        """Test validación de estructura TED válida"""
        valid_ted = {
            'TED': {
                '@attributes': {'version': '1.0'},
                'DD': {
                    'RE': '76354771-K',
                    'TD': 33,
                    'F': 1001,
                    'FE': '2023-12-01',
                    'RR': '66666666-6',
                    'RSR': 'Cliente Test',
                    'MNT': 119000
                },
                'FRMT': {
                    '@attributes': {'algoritmo': 'SHA1withRSA'},
                    '@value': 'firma_aqui'
                }
            }
        }

        assert TEDValidator.validate_ted_structure(valid_ted) is True

    def test_validate_ted_structure_missing_fields(self):
        """Test validación con campos faltantes"""
        invalid_ted = {
            'TED': {
                'DD': {
                    'RE': '76354771-K',
                    'TD': 33
                    # Faltan campos requeridos
                },
                'FRMT': {
                    '@attributes': {'algoritmo': 'SHA1withRSA'}
                }
            }
        }

        assert TEDValidator.validate_ted_structure(invalid_ted) is False

    def test_validate_ted_structure_invalid_format(self):
        """Test validación con formato inválido"""
        invalid_formats = [
            {},  # Vacío
            {'TED': {}},  # Sin DD y FRMT
            {'OTHER': {}},  # Sin TED
            "not_a_dict",  # No es diccionario
            None  # None
        ]

        for invalid_ted in invalid_formats:
            assert TEDValidator.validate_ted_structure(invalid_ted) is False

    def test_validate_ted_xml_valid(self):
        """Test validación de XML TED válido"""
        valid_xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
        <TED version="1.0">
            <DD>
                <RE>76354771-K</RE>
                <TD>33</TD>
                <F>1001</F>
                <FE>2023-12-01</FE>
                <RR>66666666-6</RR>
                <RSR>Cliente Test</RSR>
                <MNT>119000</MNT>
            </DD>
            <FRMT algoritmo="SHA1withRSA">firma_aqui</FRMT>
        </TED>"""

        assert TEDValidator.validate_ted_xml(valid_xml) is True

    def test_validate_ted_xml_invalid(self):
        """Test validación de XML TED inválido"""
        invalid_xmls = [
            "<NOTTED></NOTTED>",  # Elemento raíz incorrecto
            "<TED><DD></DD></TED>",  # Sin FRMT
            "<TED><FRMT></FRMT></TED>",  # Sin DD
            "<TED><DD><RE>test</RE></DD><FRMT></FRMT></TED>",  # Campos faltantes
            "xml_malformado<",  # XML malformado
            ""  # Vacío
        ]

        for invalid_xml in invalid_xmls:
            assert TEDValidator.validate_ted_xml(invalid_xml) is False

    def test_extract_ted_data_from_xml_valid(self):
        """Test extracción de datos desde XML válido"""
        xml_ted = """<TED version="1.0">
            <DD>
                <RE>76354771-K</RE>
                <TD>33</TD>
                <F>1001</F>
                <FE>2023-12-01</FE>
                <RR>66666666-6</RR>
                <RSR>Cliente Test S.A.</RSR>
                <MNT>119000</MNT>
                <IT1>Servicio consultoría</IT1>
                <CAF>datos_caf</CAF>
                <TSTED>2023-12-01T10:30:00</TSTED>
            </DD>
        </TED>"""

        ted_data = TEDValidator.extract_ted_data_from_xml(xml_ted)

        assert ted_data is not None
        assert ted_data.rut_emisor == "76354771-K"
        assert ted_data.tipo_documento == 33
        assert ted_data.folio == 1001
        assert ted_data.monto_total == 119000.0

    def test_extract_ted_data_from_xml_invalid(self):
        """Test extracción desde XML inválido"""
        invalid_xmls = [
            "<TED></TED>",  # Sin DD
            "<NOTTED><DD></DD></NOTTED>",  # Elemento incorrecto
            "xml_malformado",  # No es XML
            ""  # Vacío
        ]

        for invalid_xml in invalid_xmls:
            assert TEDValidator.extract_ted_data_from_xml(invalid_xml) is None

    def test_verify_ted_signature_basic(self):
        """Verificación criptográfica de la firma TED con la clave del CAF"""
        from rypsystems_dte.firma.ted import stamp_document_data
        from rypsystems_dte.identifier import CafFaker
        from rypsystems_dte.xml.encoder import XmlEncoder, save_xml

        caf = CafFaker(rut='76192083-9', tipo_documento=33).create()
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2026-10-17'},
                'Emisor': {'RUTEmisor': '76192083-9'},
                'Receptor': {'RUTRecep': '66666666-6', 'RznSocRecep': 'Cliente'},
                'Totales': {'MntTotal': 1190},
            },
            'Detalle': [{'NmbItem': 'Producto'}],
        }
        xml = save_xml(XmlEncoder().encode(stamp_document_data(datos, 33, caf)))

        assert TEDValidator.verify_ted_signature(xml, caf) is True
        assert TEDValidator.verify_ted_signature(xml.replace(b'<F>1</F>', b'<F>2</F>'), caf) is False

        # Firma inventada o ausente
        xml_with_fake_signature = """<TED>
            <DD><RE>test</RE></DD>
            <FRMT>firma_digital_aqui_muy_larga</FRMT>
        </TED>"""
        assert TEDValidator.verify_ted_signature(xml_with_fake_signature, caf) is False

        xml_without_signature = """<TED>
            <DD><RE>test</RE></DD>
            <FRMT></FRMT>
        </TED>"""
        assert TEDValidator.verify_ted_signature(xml_without_signature) is False


class TestConvenienceFunctions:
    """Tests para funciones de conveniencia"""

    def test_create_ted_from_document(self):
        """Test función create_ted_from_document"""
        document_data = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1, 'FchEmis': '2023-12-01'},
                'Emisor': {'RUTEmisor': '11111111-1'},
                'Receptor': {'RUTRecep': '22222222-2', 'RznSocRecep': 'Test'},
                'Totales': {'MntTotal': 1000}
            },
            'Detalle': {'NmbItem': 'Test item'}
        }

        ted_template = create_ted_from_document(document_data)

        assert 'TED' in ted_template
        assert ted_template['TED']['DD']['TD'] == 33

    def test_generate_ted_barcode_from_data(self):
        """Test función generate_ted_barcode_from_data"""
        ted_data = TEDData(
            rut_emisor="11111111-1",
            tipo_documento=33,
            folio=1,
            fecha_emision="2023-12-01",
            rut_receptor="22222222-2",
            razon_social_receptor="Test",
            monto_total=1000
        )

        barcode = generate_ted_barcode_from_data(ted_data)
        assert barcode.startswith("data:image/png;base64,")


class TestIntegration:
    """Tests de integración del módulo TED completo"""

    def test_end_to_end_ted_workflow(self):
        """Test workflow completo de generación TED"""
        # 1. Datos de documento
        document_data = {
            'Encabezado': {
                'IdDoc': {
                    'TipoDTE': 33,
                    'Folio': 1001,
                    'FchEmis': '2023-12-01'
                },
                'Emisor': {
                    'RUTEmisor': '76354771-K'
                },
                'Receptor': {
                    'RUTRecep': '66666666-6',
                    'RznSocRecep': 'Cliente de Prueba S.A.'
                },
                'Totales': {
                    'MntTotal': 119000
                }
            },
            'Detalle': [
                {'NmbItem': 'Servicio de consultoría especializada'}
            ]
        }

        # 2. Crear TED
        builder = TEDBuilder()
        ted_template = builder.build_ted_from_document_data(document_data)

        # 3. Validar estructura
        assert TEDValidator.validate_ted_structure(ted_template) is True

        # 4. Generar XML
        ted_xml = builder.generate_ted_xml(ted_template)
        assert TEDValidator.validate_ted_xml(ted_xml) is True

        # 5. Extraer datos del XML
        extracted_data = TEDValidator.extract_ted_data_from_xml(ted_xml)
        assert extracted_data is not None
        assert extracted_data.tipo_documento == 33

        # 6. Generar código de barras
        barcode = builder.generate_ted_barcode(ted_template)
        assert barcode.startswith("data:image/png;base64,")

    def test_ted_data_roundtrip(self):
        """Test roundtrip: TEDData → XML → TEDData"""
        original_data = TEDData(
            rut_emisor="76354771-K",
            tipo_documento=33,
            folio=1001,
            fecha_emision="2023-12-01",
            rut_receptor="66666666-6",
            razon_social_receptor="Cliente Test S.A.",
            monto_total=119000,
            primer_item="Servicio consultoría"
        )

        # Generar template y XML
        builder = TEDBuilder()
        template = builder.build_ted_template(original_data)
        xml = builder.generate_ted_xml(template)

        # Extraer datos del XML
        extracted_data = TEDValidator.extract_ted_data_from_xml(xml)

        # Verificar equivalencia
        assert extracted_data is not None
        assert extracted_data.rut_emisor == original_data.rut_emisor
        assert extracted_data.tipo_documento == original_data.tipo_documento
        assert extracted_data.folio == original_data.folio
        assert extracted_data.monto_total == original_data.monto_total