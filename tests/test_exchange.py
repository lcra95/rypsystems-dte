"""
Tests for Exchange Module

Pruebas unitarias para el módulo de intercambio de documentos.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.exchange.enums import DocumentType, ProcessType
from rypsystems_dte.exchange.entities import Sender, Receiver, PartyEndpoint
from rypsystems_dte.exchange.support import ExchangeDocument, Envelope, ExchangeBag
from rypsystems_dte.exchange.factory import ExchangeFactory
from rypsystems_dte.exchange.service import ExchangeService
from rypsystems_dte.exchange.exceptions import ExchangeException


class TestDocumentType:
    """Pruebas para el enum DocumentType."""

    def test_document_type_creation(self):
        """Prueba la creación de tipos de documento."""
        invoice_type = DocumentType.INVOICE
        assert invoice_type.get_id() == 'urn:fdc:libredte.cl:2025:doc:invoice'

    def test_process_validation(self):
        """Prueba la validación de procesos para tipos de documento."""
        invoice_type = DocumentType.INVOICE
        billing_process = ProcessType.BILLING

        assert invoice_type.is_valid_for_process(billing_process)
        assert not invoice_type.is_valid_for_process(ProcessType.TENDERING)

    def test_reference_code(self):
        """Prueba la obtención de códigos de referencia."""
        quotation_type = DocumentType.QUOTATION
        assert quotation_type.get_reference_code() == 'COT'

    def test_dte_mapping(self):
        """Prueba el mapeo desde códigos DTE."""
        invoice_type = DocumentType.try_from_dte(33)
        assert invoice_type == DocumentType.INVOICE

        credit_note_type = DocumentType.try_from_dte(61)
        assert credit_note_type == DocumentType.CREDIT_NOTE

        unknown_type = DocumentType.try_from_dte(999)
        assert unknown_type is None


class TestProcessType:
    """Pruebas para el enum ProcessType."""

    def test_process_type_creation(self):
        """Prueba la creación de tipos de proceso."""
        billing_process = ProcessType.BILLING
        assert billing_process.get_id() == 'urn:fdc:libredte.cl:2025:poacc:billing'


class TestSender:
    """Pruebas para la entidad Sender."""

    @pytest.fixture
    def contribuyente(self):
        """Fixture para contribuyente de prueba."""
        return Contribuyente("76354771-K", "Empresa Emisora S.A.")

    @pytest.fixture
    def sender(self, contribuyente):
        """Fixture para emisor de prueba."""
        return Sender(
            contribuyente=contribuyente,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            certificate_path="/path/to/cert.pem",
            private_key_path="/path/to/key.pem"
        )

    def test_sender_creation(self, sender):
        """Prueba la creación de un emisor."""
        assert sender.get_rut() == "76354771-K"
        assert sender.get_name() == "Empresa Emisora S.A."
        assert sender.can_sign() is True

    def test_sender_validation(self, contribuyente):
        """Prueba la validación de compatibilidad documento-proceso."""
        with pytest.raises(ValueError, match="no es válido para el proceso"):
            Sender(
                contribuyente=contribuyente,
                document_type=DocumentType.INVOICE,
                process_type=ProcessType.TENDERING  # Incompatible
            )

    def test_sender_to_dict(self, sender):
        """Prueba la conversión a diccionario."""
        data = sender.to_dict()
        assert data['rut'] == "76354771-K"
        assert data['can_sign'] is True


class TestReceiver:
    """Pruebas para la entidad Receiver."""

    @pytest.fixture
    def contribuyente(self):
        """Fixture para contribuyente receptor."""
        return Contribuyente("66666666-6", "Cliente Receptor S.A.")

    @pytest.fixture
    def receiver(self, contribuyente):
        """Fixture para receptor de prueba."""
        return Receiver(
            contribuyente=contribuyente,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            notification_email="test@example.com",
            auto_accept=True
        )

    def test_receiver_creation(self, receiver):
        """Prueba la creación de un receptor."""
        assert receiver.get_rut() == "66666666-6"
        assert receiver.should_auto_accept() is True
        assert receiver.has_notification_email() is True

    def test_receiver_accepts_types(self, receiver):
        """Prueba la aceptación de tipos de documento y proceso."""
        assert receiver.accepts_document_type(DocumentType.INVOICE) is True
        assert receiver.accepts_document_type(DocumentType.CREDIT_NOTE) is False
        assert receiver.accepts_process_type(ProcessType.BILLING) is True

    def test_invalid_email(self, contribuyente):
        """Prueba la validación de email."""
        with pytest.raises(ValueError, match="formato válido"):
            Receiver(
                contribuyente=contribuyente,
                document_type=DocumentType.INVOICE,
                process_type=ProcessType.BILLING,
                notification_email="invalid-email"
            )


class TestPartyEndpoint:
    """Pruebas para la entidad PartyEndpoint."""

    @pytest.fixture
    def contribuyente(self):
        """Fixture para contribuyente."""
        return Contribuyente("76354771-K", "Empresa Test S.A.")

    @pytest.fixture
    def endpoint(self, contribuyente):
        """Fixture para endpoint de prueba."""
        return PartyEndpoint(
            contribuyente=contribuyente,
            endpoint_url="https://api.example.com/exchange",
            authentication_type="api_key",
            api_key="test-api-key"
        )

    def test_endpoint_creation(self, endpoint):
        """Prueba la creación de un endpoint."""
        assert endpoint.endpoint_url == "https://api.example.com/exchange"
        assert endpoint.is_ready_for_connection() is True

    def test_auth_headers(self, endpoint):
        """Prueba la generación de headers de autenticación."""
        headers = endpoint.get_auth_headers()
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "test-api-key"

    def test_invalid_url(self, contribuyente):
        """Prueba la validación de URL."""
        with pytest.raises(ValueError, match="URL válida"):
            PartyEndpoint(
                contribuyente=contribuyente,
                endpoint_url="invalid-url"
            )

    def test_basic_auth(self, contribuyente):
        """Prueba la autenticación básica."""
        endpoint = PartyEndpoint(
            contribuyente=contribuyente,
            endpoint_url="https://api.example.com",
            authentication_type="basic",
            username="user",
            password="pass"
        )

        headers = endpoint.get_auth_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")


class TestExchangeDocument:
    """Pruebas para ExchangeDocument."""

    @pytest.fixture
    def mock_document(self):
        """Fixture para documento mock."""
        doc = Mock()
        doc.save_xml.return_value = "<xml>test</xml>"
        return doc

    @pytest.fixture
    def exchange_document(self, mock_document):
        """Fixture para documento de intercambio."""
        return ExchangeDocument(
            document=mock_document,
            document_type=DocumentType.INVOICE,
            document_id="DOC_001",
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

    def test_document_creation(self, exchange_document):
        """Prueba la creación de un documento de intercambio."""
        assert exchange_document.get_id() == "DOC_001"
        assert exchange_document.is_draft() is True
        assert exchange_document.can_retry() is True

    def test_document_status_changes(self, exchange_document):
        """Prueba los cambios de estado del documento."""
        exchange_document.mark_as_sent()
        assert exchange_document.is_sent() is True

        exchange_document.mark_as_received()
        assert exchange_document.is_received() is True

        exchange_document.mark_as_accepted()
        assert exchange_document.is_accepted() is True

    def test_document_xml_content(self, exchange_document):
        """Prueba la obtención del contenido XML."""
        xml_content = exchange_document.get_xml_content()
        assert xml_content == "<xml>test</xml>"

    def test_document_expiration(self):
        """Prueba la expiración de documentos."""
        expired_doc = ExchangeDocument(
            document={},
            document_type=DocumentType.INVOICE,
            document_id="EXPIRED_001",
            sender_rut="76354771-K",
            receiver_rut="66666666-6",
            expires_at=datetime.now() - timedelta(hours=1)
        )

        assert expired_doc.is_expired() is True
        assert expired_doc.can_retry() is False


class TestEnvelope:
    """Pruebas para Envelope."""

    @pytest.fixture
    def envelope(self):
        """Fixture para sobre de prueba."""
        return Envelope(
            envelope_id="ENV_001",
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

    @pytest.fixture
    def exchange_document(self):
        """Fixture para documento de intercambio."""
        return ExchangeDocument(
            document={},
            document_type=DocumentType.INVOICE,
            document_id="DOC_001",
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

    def test_envelope_creation(self, envelope):
        """Prueba la creación de un sobre."""
        assert envelope.get_id() == "ENV_001"
        assert envelope.is_empty() is True
        assert envelope.is_draft() is True

    def test_add_document(self, envelope, exchange_document):
        """Prueba agregar documento al sobre."""
        success = envelope.add_document(exchange_document)
        assert success is True
        assert envelope.get_document_count() == 1
        assert envelope.is_empty() is False

    def test_add_incompatible_document(self, envelope):
        """Prueba agregar documento incompatible."""
        incompatible_doc = ExchangeDocument(
            document={},
            document_type=DocumentType.CREDIT_NOTE,  # Tipo diferente
            document_id="DOC_002",
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        success = envelope.add_document(incompatible_doc)
        assert success is False

    def test_seal_envelope(self, envelope, exchange_document):
        """Prueba sellar un sobre."""
        envelope.add_document(exchange_document)
        success = envelope.seal()
        assert success is True
        assert envelope.is_sealed() is True

    def test_envelope_status_flow(self, envelope, exchange_document):
        """Prueba el flujo de estados del sobre."""
        envelope.add_document(exchange_document)
        envelope.seal()

        envelope.mark_as_sent()
        assert envelope.is_sent() is True

        envelope.mark_as_received()
        assert envelope.is_received() is True

        envelope.mark_as_processed()
        assert envelope.is_processed() is True


class TestExchangeBag:
    """Pruebas para ExchangeBag."""

    @pytest.fixture
    def bag(self):
        """Fixture para bolsa de prueba."""
        return ExchangeBag(
            bag_id="BAG_001",
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

    @pytest.fixture
    def envelope(self):
        """Fixture para sobre."""
        return Envelope(
            envelope_id="ENV_001",
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

    def test_bag_creation(self, bag):
        """Prueba la creación de una bolsa."""
        assert bag.get_id() == "BAG_001"
        assert bag.is_empty() is True
        assert bag.is_draft() is True

    def test_add_envelope(self, bag, envelope):
        """Prueba agregar sobre a la bolsa."""
        success = bag.add_envelope(envelope)
        assert success is True
        assert bag.get_envelope_count() == 1

    def test_add_incompatible_envelope(self, bag):
        """Prueba agregar sobre incompatible."""
        incompatible_env = Envelope(
            envelope_id="ENV_002",
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut="12345678-9",  # RUT diferente
            receiver_rut="66666666-6"
        )

        success = bag.add_envelope(incompatible_env)
        assert success is False

    def test_get_document_types(self, bag):
        """Prueba obtener tipos de documento únicos."""
        env1 = Envelope(
            envelope_id="ENV_001",
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        env2 = Envelope(
            envelope_id="ENV_002",
            document_type=DocumentType.CREDIT_NOTE,
            process_type=ProcessType.BILLING,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        bag.add_envelope(env1)
        bag.add_envelope(env2)

        doc_types = bag.get_document_types()
        assert len(doc_types) == 2
        assert DocumentType.INVOICE in doc_types
        assert DocumentType.CREDIT_NOTE in doc_types


class TestExchangeFactory:
    """Pruebas para ExchangeFactory."""

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

        assert isinstance(sender, Sender)
        assert sender.get_rut() == "76354771-K"

    def test_create_receiver(self, factory, contribuyente_receptor):
        """Prueba la creación de receptor."""
        receiver = factory.create_receiver(
            contribuyente=contribuyente_receptor,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            auto_accept=True
        )

        assert isinstance(receiver, Receiver)
        assert receiver.should_auto_accept() is True

    def test_create_exchange_document(self, factory):
        """Prueba la creación de documento de intercambio."""
        document = factory.create_exchange_document(
            document={"test": "data"},
            document_type=DocumentType.INVOICE,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        assert isinstance(document, ExchangeDocument)
        assert document.get_sender_rut() == "76354771-K"

    def test_create_envelope(self, factory):
        """Prueba la creación de sobre."""
        envelope = factory.create_envelope(
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        assert isinstance(envelope, Envelope)
        assert envelope.is_draft() is True

    def test_create_envelope_with_documents(self, factory):
        """Prueba la creación de sobre con documentos."""
        documents = [{"test": "data1"}, {"test": "data2"}]

        envelope = factory.create_envelope_with_documents(
            documents=documents,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        assert envelope.get_document_count() == 2


class TestExchangeService:
    """Pruebas para ExchangeService."""

    @pytest.fixture
    def service(self):
        """Fixture para servicio."""
        return ExchangeService()

    @pytest.fixture
    def sender(self):
        """Fixture para emisor."""
        contribuyente = Contribuyente("76354771-K", "Empresa Emisora S.A.")
        return Sender(
            contribuyente=contribuyente,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING
        )

    @pytest.fixture
    def receiver(self):
        """Fixture para receptor."""
        contribuyente = Contribuyente("66666666-6", "Cliente Receptor S.A.")
        return Receiver(
            contribuyente=contribuyente,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            endpoint_url="https://api.example.com/exchange"
        )

    @pytest.fixture
    def exchange_document(self):
        """Fixture para documento."""
        return ExchangeDocument(
            document={"test": "data"},
            document_type=DocumentType.INVOICE,
            document_id="DOC_001",
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

    @patch('requests.Session.post')
    def test_send_document_success(self, mock_post, service, exchange_document, sender, receiver):
        """Prueba el envío exitoso de documento."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_response.content = b'{"status": "ok"}'
        mock_post.return_value = mock_response

        result = service.send_document(exchange_document, sender, receiver)

        assert result['success'] is True
        assert exchange_document.is_sent() is True

    def test_send_document_compatibility_error(self, service, sender, receiver):
        """Prueba error de compatibilidad en envío."""
        incompatible_doc = ExchangeDocument(
            document={"test": "data"},
            document_type=DocumentType.CREDIT_NOTE,  # Tipo diferente
            document_id="DOC_002",
            sender_rut="76354771-K",
            receiver_rut="66666666-6"
        )

        with pytest.raises(ExchangeException, match="Tipo de documento no coincide"):
            service.send_document(incompatible_doc, sender, receiver)

    def test_receive_document(self, service):
        """Prueba la recepción de documento."""
        contribuyente = Contribuyente("66666666-6", "Cliente Receptor S.A.")
        receiver = Receiver(
            contribuyente=contribuyente,
            document_type=DocumentType.INVOICE,
            process_type=ProcessType.BILLING,
            auto_accept=True
        )

        document_data = {
            'document_id': 'DOC_001',
            'sender_rut': '76354771-K',
            'document': {'test': 'data'},
            'metadata': {}
        }

        document = service.receive_document(document_data, receiver)

        assert document.is_received() is True
        assert document.is_accepted() is True  # Auto-accept enabled