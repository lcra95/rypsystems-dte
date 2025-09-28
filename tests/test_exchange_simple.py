"""
Simple Exchange Module Tests

Pruebas básicas para verificar funcionalidad del módulo Exchange.
"""

import pytest
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.exchange.enums import DocumentType, ProcessType
from rypsystems_dte.exchange.factory import ExchangeFactory


class TestExchangeBasic:
    """Pruebas básicas del módulo Exchange."""

    def test_document_type_enum(self):
        """Prueba funcionalidad básica del enum DocumentType."""
        invoice_type = DocumentType.INVOICE
        assert invoice_type.get_id() == 'urn:fdc:libredte.cl:2025:doc:invoice'
        assert invoice_type.is_valid_for_process(ProcessType.BILLING)
        assert not invoice_type.is_valid_for_process(ProcessType.TENDERING)

    def test_process_type_enum(self):
        """Prueba funcionalidad básica del enum ProcessType."""
        billing_process = ProcessType.BILLING
        assert billing_process.get_id() == 'urn:fdc:libredte.cl:2025:poacc:billing'

    def test_dte_mapping(self):
        """Prueba el mapeo desde códigos DTE."""
        invoice_type = DocumentType.try_from_dte(33)
        assert invoice_type == DocumentType.INVOICE

        unknown_type = DocumentType.try_from_dte(999)
        assert unknown_type is None

    def test_factory_creation(self):
        """Prueba la creación de fábrica."""
        factory = ExchangeFactory()
        assert factory is not None

    def test_factory_document_creation(self):
        """Prueba la creación de documento de intercambio."""
        factory = ExchangeFactory()

        document = factory.create_exchange_document(
            document={"test": "data"},
            document_type=DocumentType.INVOICE,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        assert document.get_sender_rut() == "76354771-K"
        assert document.get_receiver_rut() == "66666666-6"
        assert document.is_draft() is True

    def test_factory_envelope_creation(self):
        """Prueba la creación de sobre."""
        factory = ExchangeFactory()

        envelope = factory.create_envelope(
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        assert envelope.get_sender_rut() == "76354771-K"
        assert envelope.get_receiver_rut() == "66666666-6"
        assert envelope.is_draft() is True
        assert envelope.is_empty() is True

    def test_contribuyente_integration(self):
        """Prueba integración con Contribuyente."""
        contribuyente = Contribuyente("76354771-K", "Empresa Test S.A.")
        assert contribuyente.get_rut() == "76354771-K"
        assert contribuyente.razon_social == "Empresa Test S.A."