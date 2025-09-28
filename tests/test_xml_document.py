"""
Tests para el módulo XML de DTE.

Verifica que las funciones Python produzcan EXACTAMENTE
los mismos resultados que las versiones PHP originales.
"""

import pytest
from xml.etree import ElementTree as ET

from rypsystems_dte.xml.document import XmlDocument, DocumentBuilder, Document
from rypsystems_dte.xml.tags import TagXmlRepository, DteTagValidator


class TestXmlDocument:
    """Tests para XmlDocument - equivalencia con XmlDocumentInterface de PHP."""

    def test_create_empty_document(self):
        """Test creación de documento vacío."""
        doc = XmlDocument()
        assert doc.root.tag == "root"

    def test_create_from_string(self):
        """Test creación desde string XML."""
        xml_str = """<?xml version="1.0" encoding="ISO-8859-1"?>
        <DTE>
            <Documento>
                <Encabezado>
                    <IdDoc>
                        <TipoDTE>33</TipoDTE>
                        <Folio>123</Folio>
                    </IdDoc>
                </Encabezado>
            </Documento>
        </DTE>"""

        doc = XmlDocument(xml_str)
        assert doc.root.tag == "DTE"

    def test_create_from_invalid_xml(self):
        """Test creación desde XML inválido debe fallar."""
        invalid_xml = "<invalid><unclosed>"

        with pytest.raises(ValueError, match="XML inválido"):
            XmlDocument(invalid_xml)

    def test_query_simple_xpath(self):
        """Test consulta XPath simple."""
        xml_str = """<DTE>
            <Documento>
                <Encabezado>
                    <IdDoc>
                        <TipoDTE>33</TipoDTE>
                        <Folio>123</Folio>
                    </IdDoc>
                </Encabezado>
            </Documento>
        </DTE>"""

        doc = XmlDocument(xml_str)

        # Test consulta que retorna texto
        tipo_dte = doc.query('//TipoDTE')
        assert tipo_dte == "33"

        folio = doc.query('//Folio')
        assert folio == "123"

    def test_query_complex_xpath(self):
        """Test consulta XPath que retorna estructura."""
        xml_str = """<DTE>
            <Documento>
                <Encabezado>
                    <IdDoc>
                        <TipoDTE>33</TipoDTE>
                        <Folio>123</Folio>
                    </IdDoc>
                    <Emisor>
                        <RUTEmisor>12345678-9</RUTEmisor>
                        <RznSoc>Empresa Test</RznSoc>
                    </Emisor>
                </Encabezado>
            </Documento>
        </DTE>"""

        doc = XmlDocument(xml_str)

        # Test consulta que retorna diccionario
        id_doc = doc.query('//IdDoc')
        assert isinstance(id_doc, dict)
        assert id_doc['TipoDTE'] == "33"
        assert id_doc['Folio'] == "123"

        emisor = doc.query('//Emisor')
        assert isinstance(emisor, dict)
        assert emisor['RUTEmisor'] == "12345678-9"
        assert emisor['RznSoc'] == "Empresa Test"

    def test_query_multiple_elements(self):
        """Test consulta XPath que retorna múltiples elementos."""
        xml_str = """<DTE>
            <Documento>
                <Detalle>
                    <NmbItem>Producto 1</NmbItem>
                    <QtyItem>10</QtyItem>
                </Detalle>
                <Detalle>
                    <NmbItem>Producto 2</NmbItem>
                    <QtyItem>5</QtyItem>
                </Detalle>
            </Documento>
        </DTE>"""

        doc = XmlDocument(xml_str)

        detalles = doc.query('//Detalle')
        assert isinstance(detalles, list)
        assert len(detalles) == 2
        assert detalles[0]['NmbItem'] == "Producto 1"
        assert detalles[1]['NmbItem'] == "Producto 2"

    def test_query_nonexistent(self):
        """Test consulta de elemento inexistente."""
        xml_str = "<DTE><Documento></Documento></DTE>"
        doc = XmlDocument(xml_str)

        result = doc.query('//NoExiste')
        assert result is None

    def test_to_array(self):
        """Test conversión completa a array."""
        xml_str = """<DTE>
            <Documento>
                <Encabezado>
                    <IdDoc>
                        <TipoDTE>33</TipoDTE>
                    </IdDoc>
                </Encabezado>
            </Documento>
        </DTE>"""

        doc = XmlDocument(xml_str)
        array = doc.to_array()

        assert 'DTE' in array
        assert 'Documento' in array['DTE']
        assert 'Encabezado' in array['DTE']['Documento']
        assert array['DTE']['Documento']['Encabezado']['IdDoc']['TipoDTE'] == "33"

    def test_save_xml(self):
        """Test generación XML."""
        xml_str = "<DTE><Documento><TipoDTE>33</TipoDTE></Documento></DTE>"
        doc = XmlDocument(xml_str)

        xml_output = doc.save_xml()

        # Verificar que contenga la declaración XML correcta
        assert xml_output.startswith('<?xml version="1.0" encoding="ISO-8859-1"?>')
        assert '<DTE>' in xml_output
        assert '<TipoDTE>33</TipoDTE>' in xml_output

    def test_get_xml_alias(self):
        """Test que get_xml() sea alias de save_xml()."""
        xml_str = "<DTE><Documento></Documento></DTE>"
        doc = XmlDocument(xml_str)

        assert doc.get_xml() == doc.save_xml()

    def test_c14n_with_iso88591_encoding_flattened(self):
        """Test canonicalización C14N."""
        xml_str = """<DTE>
            <Documento>
                <TED version="1.0">
                    <DD>
                        <RE>12345678-9</RE>
                        <TD>33</TD>
                    </DD>
                </TED>
            </Documento>
        </DTE>"""

        doc = XmlDocument(xml_str)

        # Test canonicalización de TED
        ted_flattened = doc.c14n_with_iso88591_encoding_flattened('//TED')
        assert ted_flattened is not None
        assert '<TED version="1.0">' in ted_flattened
        assert '<RE>12345678-9</RE>' in ted_flattened
        assert '<TD>33</TD>' in ted_flattened
        # Verificar que está "aplanado" (sin espacios)
        assert '\n' not in ted_flattened
        assert '  ' not in ted_flattened

    def test_c14n_nonexistent_element(self):
        """Test canonicalización de elemento inexistente."""
        xml_str = "<DTE><Documento></Documento></DTE>"
        doc = XmlDocument(xml_str)

        result = doc.c14n_with_iso88591_encoding_flattened('//NoExiste')
        assert result is None

    def test_element_with_attributes(self):
        """Test manejo de elementos con atributos."""
        xml_str = """<DTE>
            <Documento ID="F1T33">
                <TED version="1.0">
                    <DD>Data</DD>
                </TED>
            </Documento>
        </DTE>"""

        doc = XmlDocument(xml_str)

        documento = doc.query('//Documento')
        assert isinstance(documento, dict)
        assert '@attributes' in documento
        assert documento['@attributes']['ID'] == "F1T33"

        ted = doc.query('//TED')
        assert '@attributes' in ted
        assert ted['@attributes']['version'] == "1.0"


class TestDocumentBuilder:
    """Tests para DocumentBuilder - construcción de documentos DTE."""

    def test_create_simple_dte(self):
        """Test creación de DTE simple."""
        datos = {
            'ID': 'F1T33',
            'Encabezado': {
                'IdDoc': {
                    'TipoDTE': 33,
                    'Folio': 1
                },
                'Emisor': {
                    'RUTEmisor': '12345678-9',
                    'RznSoc': 'Empresa Test'
                }
            }
        }

        doc = DocumentBuilder.create_dte_document(datos)

        assert isinstance(doc, XmlDocument)
        assert doc.query('//TipoDTE') == "33"
        assert doc.query('//Folio') == "1"
        assert doc.query('//RUTEmisor') == "12345678-9"

        # Verificar atributos
        documento = doc.query('//Documento')
        assert documento['@attributes']['ID'] == 'F1T33'

    def test_create_dte_with_detalle(self):
        """Test creación de DTE con detalles."""
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1}
            },
            'Detalle': [
                {
                    'NroLinDet': 1,
                    'NmbItem': 'Producto 1',
                    'QtyItem': 10,
                    'PrcItem': 1000
                },
                {
                    'NroLinDet': 2,
                    'NmbItem': 'Producto 2',
                    'QtyItem': 5,
                    'PrcItem': 2000
                }
            ]
        }

        doc = DocumentBuilder.create_dte_document(datos)

        detalles = doc.query('//Detalle')
        assert isinstance(detalles, list)
        assert len(detalles) == 2
        assert detalles[0]['NmbItem'] == 'Producto 1'
        assert detalles[1]['NmbItem'] == 'Producto 2'

    def test_create_dte_with_nested_elements(self):
        """Test creación con elementos anidados complejos."""
        datos = {
            'Encabezado': {
                'IdDoc': {
                    'TipoDTE': 33,
                    'Folio': 1
                },
                'Totales': {
                    'MntNeto': 10000,
                    'TasaIVA': 19,
                    'IVA': 1900,
                    'MntTotal': 11900
                }
            }
        }

        doc = DocumentBuilder.create_dte_document(datos)

        totales = doc.query('//Totales')
        assert totales['MntNeto'] == "10000"
        assert totales['TasaIVA'] == "19"
        assert totales['IVA'] == "1900"
        assert totales['MntTotal'] == "11900"


class TestDocument:
    """Tests para Document - contenedor de documentos."""

    def test_create_empty_document(self):
        """Test creación de documento vacío."""
        doc = Document()

        assert doc.content == ""
        assert doc.attachments == []
        assert doc.document_type == "B2B"
        assert doc.metadata == {}

    def test_create_document_with_content(self):
        """Test creación con contenido."""
        content = "<DTE><Documento></Documento></DTE>"
        doc = Document(content=content)

        assert doc.get_content() == content
        assert doc.get_content_size() > 0

    def test_document_id_generation(self):
        """Test generación automática de ID."""
        doc = Document()

        # Primera llamada genera ID
        id1 = doc.get_id()
        assert isinstance(id1, str)
        assert len(id1) > 0

        # Segunda llamada retorna el mismo ID
        id2 = doc.get_id()
        assert id1 == id2

        # Documento diferente tiene ID diferente
        doc2 = Document()
        id3 = doc2.get_id()
        assert id1 != id3

    def test_add_attachment(self):
        """Test agregar archivos adjuntos."""
        doc = Document()

        attachment1 = "archivo1.pdf"
        attachment2 = "archivo2.xml"

        doc.add_attachment(attachment1)
        doc.add_attachment(attachment2)

        attachments = doc.get_attachments()
        assert len(attachments) == 2
        assert attachment1 in attachments
        assert attachment2 in attachments

    def test_metadata_management(self):
        """Test manejo de metadatos."""
        doc = Document()

        # Agregar metadatos individuales
        doc.add_metadata('tipo', 'DTE')
        doc.add_metadata('version', '1.0')

        metadata = doc.get_metadata()
        assert metadata['tipo'] == 'DTE'
        assert metadata['version'] == '1.0'

        # Establecer metadatos completos
        new_metadata = {'emisor': '12345678-9', 'fecha': '2023-01-01'}
        doc.set_metadata(new_metadata)

        metadata = doc.get_metadata()
        assert metadata == new_metadata

    def test_to_dict(self):
        """Test conversión a diccionario."""
        doc = Document(
            content="<xml>test</xml>",
            document_type="DTE"
        )
        doc.add_metadata('test', 'value')

        dict_data = doc.to_dict()

        assert 'id' in dict_data
        assert dict_data['content'] == "<xml>test</xml>"
        assert dict_data['document_type'] == "DTE"
        assert dict_data['metadata']['test'] == 'value'
        assert 'content_size' in dict_data

    def test_to_json_serializable(self):
        """Test conversión a formato JSON serializable."""
        doc = Document(content="<xml>test</xml>")

        json_data = doc.to_json_serializable()

        # Contenido debe estar en base64
        assert 'content' in json_data
        import base64
        decoded = base64.b64decode(json_data['content']).decode('utf-8')
        assert decoded == "<xml>test</xml>"


class TestTagXmlRepository:
    """Tests para TagXmlRepository - mapeo de tags XML."""

    def test_get_tag_info(self):
        """Test obtención de información de tag."""
        info = TagXmlRepository.get_tag_info('FmaPagExp')

        assert info is not None
        assert info['glosa'] == 'Forma pago exp.'
        assert info['entity'] == 'AduanaFormaPago'

    def test_get_tag_info_nonexistent(self):
        """Test tag inexistente."""
        info = TagXmlRepository.get_tag_info('TagInexistente')
        assert info is None

    def test_get_tag_glosa(self):
        """Test obtención de glosa."""
        glosa = TagXmlRepository.get_tag_glosa('CodModVenta')
        assert glosa == 'Mod. venta'

        glosa_none = TagXmlRepository.get_tag_glosa('NoExiste')
        assert glosa_none is None

    def test_get_tag_entity(self):
        """Test obtención de entidad."""
        entity = TagXmlRepository.get_tag_entity('CodPaisRecep')
        assert entity == 'AduanaPais'

        entity_none = TagXmlRepository.get_tag_entity('TotClauVenta')  # No tiene entidad
        assert entity_none is None

    def test_has_entity(self):
        """Test verificación de entidad."""
        assert TagXmlRepository.has_entity('CodViaTransp') is True
        assert TagXmlRepository.has_entity('Booking') is False

    def test_get_tags_by_entity(self):
        """Test obtención de tags por entidad."""
        pais_tags = TagXmlRepository.get_tags_by_entity('AduanaPais')

        assert 'CodPaisRecep' in pais_tags
        assert 'CodPaisDestin' in pais_tags
        assert 'Nacionalidad' in pais_tags

        # Verificar que no contiene tags de otras entidades
        assert 'FmaPagExp' not in pais_tags

    def test_get_aduana_tags(self):
        """Test obtención de tags de Aduana."""
        aduana_tags = TagXmlRepository.get_aduana_tags()

        # Debe contener tags con entidades de Aduana
        assert 'FmaPagExp' in aduana_tags
        assert 'CodModVenta' in aduana_tags
        assert 'CodPaisRecep' in aduana_tags

        # No debe contener tags sin entidad de Aduana
        for tag, info in aduana_tags.items():
            assert 'entity' in info
            assert info['entity'].startswith('Aduana')


class TestDteTagValidator:
    """Tests para DteTagValidator - validación de tags DTE."""

    def test_validate_required_tags_factura_afecta(self):
        """Test validación de tags requeridos para factura afecta."""
        xml_data = {
            'DTE': {
                'Documento': {
                    'Encabezado': {
                        'IdDoc': {
                            'TipoDTE': 33,
                            'Folio': 123,
                            'FchEmis': '2023-01-01'
                        },
                        'Emisor': {
                            'RUTEmisor': '12345678-9',
                            'RznSoc': 'Empresa Test'
                        },
                        'Receptor': {
                            'RUTRecep': '87654321-0',
                            'RznSocRecep': 'Cliente Test'
                        },
                        'Totales': {
                            'MntNeto': 10000,
                            'TasaIVA': 19,
                            'IVA': 1900,
                            'MntTotal': 11900
                        }
                    }
                }
            }
        }

        validation = DteTagValidator.validate_required_tags(xml_data, 33)

        assert validation['valid'] is True
        assert validation['missing_tags'] == []
        assert validation['tipo_dte'] == 33

    def test_validate_required_tags_missing(self):
        """Test validación con tags faltantes."""
        xml_data = {
            'DTE': {
                'Documento': {
                    'Encabezado': {
                        'IdDoc': {
                            'TipoDTE': 33,
                            'Folio': 123
                            # Falta FchEmis
                        },
                        'Emisor': {
                            'RUTEmisor': '12345678-9'
                            # Falta RznSoc
                        }
                        # Falta Receptor y Totales
                    }
                }
            }
        }

        validation = DteTagValidator.validate_required_tags(xml_data, 33)

        assert validation['valid'] is False
        assert 'FchEmis' in validation['missing_tags']
        assert 'RznSoc' in validation['missing_tags']
        assert 'RUTRecep' in validation['missing_tags']

    def test_is_export_document(self):
        """Test detección de documento de exportación."""
        # Documento con varios tags de exportación
        export_data = {
            'DTE': {
                'Exportaciones': {
                    'Encabezado': {
                        'IdDoc': {'TipoDTE': 110},
                        'Transporte': {
                            'CodModVenta': 1,
                            'CodClauVenta': 2,
                            'TotClauVenta': 1000,
                            'CodViaTransp': 1,
                            'CodPtoEmbarque': 'VALPA'
                        }
                    }
                }
            }
        }

        assert DteTagValidator.is_export_document(export_data) is True

        # Documento nacional sin tags de exportación
        national_data = {
            'DTE': {
                'Documento': {
                    'Encabezado': {
                        'IdDoc': {'TipoDTE': 33},
                        'Emisor': {'RUTEmisor': '12345678-9'}
                    }
                }
            }
        }

        assert DteTagValidator.is_export_document(national_data) is False

    def test_validate_tag_values(self):
        """Test validación de valores de tags específicos."""
        # Validación TipoDTE válido
        validation = DteTagValidator.validate_tag_values('TipoDTE', 33)
        assert validation['valid'] is True

        # Validación TipoDTE inválido
        validation = DteTagValidator.validate_tag_values('TipoDTE', 999)
        assert validation['valid'] is False
        assert 'Tipo de DTE inválido' in validation['errors']

        # Validación fecha válida
        validation = DteTagValidator.validate_tag_values('FchEmis', '2023-01-01')
        assert validation['valid'] is True

        # Validación fecha inválida
        validation = DteTagValidator.validate_tag_values('FchEmis', '2023/01/01')
        assert validation['valid'] is False

        # Validación monto válido
        validation = DteTagValidator.validate_tag_values('MntTotal', '10000')
        assert validation['valid'] is True

        # Validación monto inválido
        validation = DteTagValidator.validate_tag_values('MntTotal', 'abc')
        assert validation['valid'] is False

        # Validación tasa IVA válida
        validation = DteTagValidator.validate_tag_values('TasaIVA', '19')
        assert validation['valid'] is True

        # Validación tasa IVA inválida
        validation = DteTagValidator.validate_tag_values('TasaIVA', '150')
        assert validation['valid'] is False