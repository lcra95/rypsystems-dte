"""
Exchange Enums Tests

Pruebas para los enums del módulo Exchange.
"""

import pytest
from rypsystems_dte.exchange.enums import DocumentType, ProcessType


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

        invoice_type = DocumentType.INVOICE
        assert invoice_type.get_reference_code() == 'INV'

    def test_dte_mapping(self):
        """Prueba el mapeo desde códigos DTE."""
        invoice_type = DocumentType.try_from_dte(33)
        assert invoice_type == DocumentType.INVOICE

        credit_note_type = DocumentType.try_from_dte(61)
        assert credit_note_type == DocumentType.CREDIT_NOTE

        unknown_type = DocumentType.try_from_dte(999)
        assert unknown_type is None

    def test_all_document_types(self):
        """Prueba que todos los tipos de documento tengan ID válido."""
        for doc_type in DocumentType:
            assert doc_type.get_id().startswith('urn:fdc:libredte.cl:2025:doc:')


class TestProcessType:
    """Pruebas para el enum ProcessType."""

    def test_process_type_creation(self):
        """Prueba la creación de tipos de proceso."""
        billing_process = ProcessType.BILLING
        assert billing_process.get_id() == 'urn:fdc:libredte.cl:2025:poacc:billing'

        quoting_process = ProcessType.QUOTING
        assert quoting_process.get_id() == 'urn:fdc:libredte.cl:2025:prac:quoting'

    def test_all_process_types(self):
        """Prueba que todos los tipos de proceso tengan ID válido."""
        for process_type in ProcessType:
            process_id = process_type.get_id()
            assert process_id.startswith('urn:fdc:libredte.cl:2025:')
            assert ('prac:' in process_id or 'poacc:' in process_id or 'ctc:' in process_id)


class TestDocumentProcessCompatibility:
    """Pruebas de compatibilidad entre documentos y procesos."""

    def test_invoice_billing_compatibility(self):
        """Prueba compatibilidad entre factura y facturación."""
        invoice = DocumentType.INVOICE
        billing = ProcessType.BILLING
        assert invoice.is_valid_for_process(billing)

    def test_quotation_quoting_compatibility(self):
        """Prueba compatibilidad entre cotización y proceso de cotización."""
        quotation = DocumentType.QUOTATION
        quoting = ProcessType.QUOTING
        sourcing = ProcessType.SOURCING

        assert quotation.is_valid_for_process(quoting)
        assert quotation.is_valid_for_process(sourcing)

    def test_incompatible_combinations(self):
        """Prueba combinaciones incompatibles."""
        invoice = DocumentType.INVOICE
        tendering = ProcessType.TENDERING

        assert not invoice.is_valid_for_process(tendering)

    def test_bid_tendering_compatibility(self):
        """Prueba compatibilidad entre oferta y licitación."""
        bid = DocumentType.BID
        tendering = ProcessType.TENDERING

        assert bid.is_valid_for_process(tendering)
        assert not bid.is_valid_for_process(ProcessType.BILLING)