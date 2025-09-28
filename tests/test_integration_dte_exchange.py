"""
Integration Test: DTE + Exchange

Pruebas de integración end-to-end entre los módulos DTE y Exchange.
"""

import pytest
import sys
import os

# Add src to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.exchange.factory import ExchangeFactory
from rypsystems_dte.exchange.enums.document_type import DocumentType
from rypsystems_dte.exchange.enums.process_type import ProcessType


class TestDTEExchangeIntegration:
    """Pruebas de integración entre DTE y Exchange."""

    @pytest.fixture
    def dte_factory(self):
        """Fixture para fábrica DTE."""
        return DTEFactory()

    @pytest.fixture
    def exchange_factory(self):
        """Fixture para fábrica Exchange."""
        return ExchangeFactory()

    @pytest.fixture
    def emisor(self):
        """Fixture para contribuyente emisor."""
        return Contribuyente("76354771-K", "Mi Empresa S.A.")

    @pytest.fixture
    def receptor(self):
        """Fixture para contribuyente receptor."""
        return Contribuyente("66666666-6", "Cliente Ejemplo S.A.")

    def test_create_factura_and_exchange_document(self, dte_factory, exchange_factory, emisor, receptor):
        """Prueba crear factura DTE y preparar para intercambio."""

        # 1. Crear factura DTE
        factura = dte_factory.create_factura_afecta(
            emisor=emisor,
            receptor=receptor,
            folio=1001,
            fecha_emision="2023-12-01",
            detalle=[{
                'NmbItem': 'Producto de Prueba',
                'QtyItem': 10,
                'PrcItem': 1000
            }]
        )

        # Verificar factura creada correctamente
        assert factura.get_id() == "76354771-K_T033F000001001"
        assert factura.get_rut_emisor() == "76354771-K"

        # 2. Crear documento de intercambio desde la factura DTE
        exchange_doc = exchange_factory.create_exchange_document(
            document=factura,
            document_type=DocumentType.INVOICE,
            sender_rut=emisor.get_rut(),
            receiver_rut=receptor.get_rut()
        )

        # Verificar documento de intercambio
        assert exchange_doc.get_sender_rut() == "76354771-K"
        assert exchange_doc.get_receiver_rut() == "66666666-6"
        assert exchange_doc.document_type == DocumentType.INVOICE
        assert exchange_doc.is_draft() is True

        # 3. Verificar que se puede extraer XML del DTE
        xml_content = exchange_doc.get_xml_content()
        assert xml_content is not None
        assert '<DTE' in xml_content
        assert 'version="1.0"' in xml_content

    def test_create_envelope_with_multiple_dtes(self, dte_factory, exchange_factory, emisor, receptor):
        """Prueba crear sobre con múltiples documentos DTE."""

        # 1. Crear múltiples facturas DTE
        facturas = []
        for i in range(3):
            factura = dte_factory.create_factura_afecta(
                emisor=emisor,
                receptor=receptor,
                folio=1001 + i,
                fecha_emision="2023-12-01",
                detalle=[{
                    'NmbItem': f'Producto {i+1}',
                    'QtyItem': 5,
                    'PrcItem': 500 * (i+1)
                }]
            )
            facturas.append(factura)

        # 2. Crear sobre con las facturas
        envelope = exchange_factory.create_envelope_with_documents(
            documents=facturas,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut=emisor.get_rut(),
            receiver_rut=receptor.get_rut()
        )

        # Verificar sobre
        assert envelope.get_document_count() == 3
        assert not envelope.is_empty()
        assert envelope.document_type == DocumentType.INVOICE
        assert envelope.process_type == ProcessType.BILLING

        # 3. Verificar que todos los documentos del sobre tienen XML
        for doc in envelope.documents:
            xml_content = doc.get_xml_content()
            assert xml_content is not None
            assert '<DTE' in xml_content

    def test_exchange_compatibility_validation(self, exchange_factory, emisor, receptor):
        """Prueba validaciones de compatibilidad en Exchange."""

        # 1. Crear emisor y receptor para intercambio
        sender = exchange_factory.create_sender(
            contribuyente=emisor,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING
        )

        receiver = exchange_factory.create_receiver(
            contribuyente=receptor,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            auto_accept=True
        )

        # Verificar entidades creadas
        assert sender.document_type == DocumentType.INVOICE
        assert receiver.document_type == DocumentType.INVOICE
        assert receiver.should_auto_accept() is True

        # 2. Verificar que los tipos son compatibles
        assert sender.document_type.is_valid_for_process(sender.process_type)
        assert receiver.document_type.is_valid_for_process(receiver.process_type)

    def test_dte_mapping_to_exchange_document_type(self):
        """Prueba mapeo de códigos DTE a tipos de documento Exchange."""

        # Verificar mapeos principales
        assert DocumentType.try_from_dte(33) == DocumentType.INVOICE  # Factura electrónica
        assert DocumentType.try_from_dte(61) == DocumentType.CREDIT_NOTE  # Nota de crédito
        assert DocumentType.try_from_dte(56) == DocumentType.DEBIT_NOTE  # Nota de débito
        assert DocumentType.try_from_dte(52) == DocumentType.DISPATCH_ADVICE  # Guía de despacho

        # Verificar mapeo inexistente
        assert DocumentType.try_from_dte(999) is None

    def test_complete_exchange_workflow(self, dte_factory, exchange_factory, emisor, receptor):
        """Prueba workflow completo de intercambio."""

        # 1. Crear DTE
        factura = dte_factory.create_factura_afecta(
            emisor=emisor,
            receptor=receptor,
            folio=2001,
            fecha_emision="2023-12-01",
            detalle=[{
                'NmbItem': 'Servicio de Consultoría',
                'QtyItem': 1,
                'PrcItem': 100000
            }]
        )

        # 2. Crear entidades de intercambio
        sender = exchange_factory.create_sender(
            contribuyente=emisor,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING
        )

        receiver = exchange_factory.create_receiver(
            contribuyente=receptor,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING
        )

        # 3. Crear documento de intercambio
        exchange_doc = exchange_factory.create_exchange_document(
            document=factura,
            document_type=DocumentType.INVOICE,
            sender_rut=sender.get_rut(),
            receiver_rut=receiver.get_rut()
        )

        # 4. Crear sobre
        envelope = exchange_factory.create_envelope(
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut=sender.get_rut(),
            receiver_rut=receiver.get_rut()
        )

        # 5. Agregar documento al sobre
        success = envelope.add_document(exchange_doc)
        assert success is True

        # 6. Sellar sobre
        sealed = envelope.seal()
        assert sealed is True
        assert envelope.is_sealed() is True

        # 7. Verificar integridad
        assert envelope.verify_checksum() is True

        # 8. Obtener estadísticas
        envelope_dict = envelope.to_dict()
        assert envelope_dict['document_count'] == 1
        assert envelope_dict['has_signature'] is False  # Sin firma aún
        assert envelope_dict['total_size'] > 0