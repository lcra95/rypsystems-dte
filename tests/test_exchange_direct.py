"""
Direct Exchange Tests

Pruebas directas de componentes del módulo Exchange sin dependencias problemáticas.
"""

import pytest
import sys
import os

# Add src to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from rypsystems_dte.exchange.enums.document_type import DocumentType
from rypsystems_dte.exchange.enums.process_type import ProcessType


class TestDocumentTypeDirect:
    """Pruebas directas para DocumentType."""

    def test_document_type_values(self):
        """Prueba los valores básicos del enum."""
        assert DocumentType.INVOICE.value == 'urn:fdc:libredte.cl:2025:doc:invoice'
        assert DocumentType.CREDIT_NOTE.value == 'urn:fdc:libredte.cl:2025:doc:credit_note'

    def test_get_id_method(self):
        """Prueba el método get_id."""
        invoice = DocumentType.INVOICE
        assert invoice.get_id() == 'urn:fdc:libredte.cl:2025:doc:invoice'

    def test_process_validation(self):
        """Prueba la validación de procesos."""
        invoice = DocumentType.INVOICE
        billing = ProcessType.BILLING
        tendering = ProcessType.TENDERING

        assert invoice.is_valid_for_process(billing) is True
        assert invoice.is_valid_for_process(tendering) is False

    def test_reference_codes(self):
        """Prueba los códigos de referencia."""
        quotation = DocumentType.QUOTATION
        invoice = DocumentType.INVOICE

        assert quotation.get_reference_code() == 'COT'
        assert invoice.get_reference_code() == 'INV'

    def test_dte_mapping(self):
        """Prueba el mapeo desde códigos DTE chilenos."""
        # Factura electrónica (código 33)
        doc_type = DocumentType.try_from_dte(33)
        assert doc_type == DocumentType.INVOICE

        # Nota de crédito (código 61)
        doc_type = DocumentType.try_from_dte(61)
        assert doc_type == DocumentType.CREDIT_NOTE

        # Código inexistente
        doc_type = DocumentType.try_from_dte(999)
        assert doc_type is None


class TestProcessTypeDirect:
    """Pruebas directas para ProcessType."""

    def test_process_type_values(self):
        """Prueba los valores básicos del enum."""
        assert ProcessType.BILLING.value == 'urn:fdc:libredte.cl:2025:poacc:billing'
        assert ProcessType.QUOTING.value == 'urn:fdc:libredte.cl:2025:prac:quoting'

    def test_get_id_method(self):
        """Prueba el método get_id."""
        billing = ProcessType.BILLING
        assert billing.get_id() == 'urn:fdc:libredte.cl:2025:poacc:billing'


class TestDocumentProcessMapping:
    """Pruebas del mapeo entre documentos y procesos."""

    def test_quotation_processes(self):
        """Prueba los procesos válidos para cotizaciones."""
        quotation = DocumentType.QUOTATION

        assert quotation.is_valid_for_process(ProcessType.QUOTING)
        assert quotation.is_valid_for_process(ProcessType.SOURCING)
        assert not quotation.is_valid_for_process(ProcessType.BILLING)

    def test_invoice_processes(self):
        """Prueba los procesos válidos para facturas."""
        invoice = DocumentType.INVOICE

        assert invoice.is_valid_for_process(ProcessType.BILLING)
        assert not invoice.is_valid_for_process(ProcessType.QUOTING)

    def test_bid_processes(self):
        """Prueba los procesos válidos para ofertas."""
        bid = DocumentType.BID

        assert bid.is_valid_for_process(ProcessType.TENDERING)
        assert not bid.is_valid_for_process(ProcessType.BILLING)

    def test_b2b_processes(self):
        """Prueba los procesos válidos para documentos B2B."""
        b2b = DocumentType.B2B

        assert b2b.is_valid_for_process(ProcessType.BILLING)
        assert b2b.is_valid_for_process(ProcessType.FULFILLMENT)
        assert b2b.is_valid_for_process(ProcessType.REPORTING)
        assert not b2b.is_valid_for_process(ProcessType.QUOTING)