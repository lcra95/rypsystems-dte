"""
Test Exchange Factory

Pruebas para verificar la funcionalidad de ExchangeFactory después de migración a Pydantic V2.
"""

import pytest
import sys
import os

# Add src to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.exchange.enums.document_type import DocumentType
from rypsystems_dte.exchange.enums.process_type import ProcessType
from rypsystems_dte.exchange.factory import ExchangeFactory


class TestExchangeFactory:
    """Pruebas para ExchangeFactory con Pydantic V2."""

    @pytest.fixture
    def factory(self):
        """Fixture para fábrica."""
        return ExchangeFactory()

    @pytest.fixture
    def contribuyente_emisor(self):
        """Fixture para contribuyente emisor."""
        return Contribuyente("76354771-K", "Empresa Emisora S.A.")

    @pytest.fixture
    def contribuyente_receptor(self):
        """Fixture para contribuyente receptor."""
        return Contribuyente("66666666-6", "Cliente Receptor S.A.")

    def test_create_sender(self, factory, contribuyente_emisor):
        """Prueba la creación de emisor."""
        sender = factory.create_sender(
            contribuyente=contribuyente_emisor,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING
        )

        assert sender.get_rut() == "76354771-K"
        assert sender.get_name() == "Empresa Emisora S.A."
        assert sender.document_type == DocumentType.INVOICE
        assert sender.process_type == ProcessType.BILLING

    def test_create_receiver(self, factory, contribuyente_receptor):
        """Prueba la creación de receptor."""
        receiver = factory.create_receiver(
            contribuyente=contribuyente_receptor,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            auto_accept=True
        )

        assert receiver.get_rut() == "66666666-6"
        assert receiver.get_name() == "Cliente Receptor S.A."
        assert receiver.should_auto_accept() is True

    def test_create_party_endpoint(self, factory, contribuyente_emisor):
        """Prueba la creación de endpoint."""
        endpoint = factory.create_party_endpoint(
            contribuyente=contribuyente_emisor,
            endpoint_url="https://api.example.com/exchange",
            authentication_type="api_key",
            api_key="test-key"
        )

        assert endpoint.endpoint_url == "https://api.example.com/exchange"
        assert endpoint.authentication_type == "api_key"
        assert endpoint.is_ready_for_connection() is True

    def test_create_exchange_document(self, factory):
        """Prueba la creación de documento de intercambio."""
        document = factory.create_exchange_document(
            document={"test": "data"},
            document_type=DocumentType.INVOICE,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        assert document.get_sender_rut() == "76354771-K"
        assert document.get_receiver_rut() == "66666666-6"
        assert document.document_type == DocumentType.INVOICE
        assert document.is_draft() is True

    def test_create_envelope(self, factory):
        """Prueba la creación de sobre."""
        envelope = factory.create_envelope(
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        assert envelope.get_sender_rut() == "76354771-K"
        assert envelope.get_receiver_rut() == "66666666-6"
        assert envelope.document_type == DocumentType.INVOICE
        assert envelope.process_type == ProcessType.BILLING
        assert envelope.is_draft() is True
        assert envelope.is_empty() is True

    def test_create_exchange_bag(self, factory):
        """Prueba la creación de bolsa."""
        bag = factory.create_exchange_bag(
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        assert bag.get_sender_rut() == "76354771-K"
        assert bag.get_receiver_rut() == "66666666-6"
        assert bag.is_draft() is True
        assert bag.is_empty() is True

    def test_envelope_with_documents(self, factory):
        """Prueba crear sobre con documentos."""
        documents = [{"test": "data1"}, {"test": "data2"}]

        envelope = factory.create_envelope_with_documents(
            documents=documents,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        assert envelope.get_document_count() == 2
        assert not envelope.is_empty()

    def test_validation_error_incompatible_types(self, factory, contribuyente_emisor):
        """Prueba error de validación con tipos incompatibles."""
        from rypsystems_dte.exchange.exceptions import ExchangeException

        with pytest.raises(ExchangeException, match="no es válido para el proceso"):
            factory.create_sender(
                contribuyente=contribuyente_emisor,
                document_type=DocumentType.INVOICE,
                process_type=ProcessType.TENDERING  # Incompatible
            )