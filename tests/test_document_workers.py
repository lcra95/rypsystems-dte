"""
Tests for Document Workers System.

Comprehensive test suite for validation, sanitization, normalization, and rendering workers.
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
import json
import tempfile
from pathlib import Path

from rypsystems_dte.document.workers import (
    BaseWorker, WorkerResult, WorkerStatus, WorkerPipeline,
    ValidatorWorker, SanitizerWorker, NormalizerWorker, RendererWorker
)
from rypsystems_dte.document.workers.renderer import RenderFormat
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente


class TestBaseWorker:
    """Test base worker functionality."""

    def test_worker_creation(self):
        """Test worker creation with configuration."""
        config = {'test_param': 'value'}
        worker = TestWorkerImpl('TestWorker', config)

        assert worker.name == 'TestWorker'
        assert worker.config == config
        assert worker.get_config_value('test_param') == 'value'
        assert worker.get_config_value('missing_param', 'default') == 'default'

    def test_worker_result(self):
        """Test worker result functionality."""
        result = WorkerResult(
            worker_name='TestWorker',
            status=WorkerStatus.SUCCESS
        )

        # Test message handling
        result.add_error('E001', 'Test error', 'field1')
        result.add_warning('W001', 'Test warning')
        result.add_info('I001', 'Test info')

        assert result.has_errors()
        assert result.has_warnings()
        assert len(result.get_errors()) == 1
        assert len(result.get_warnings()) == 1
        assert result.get_errors()[0].code == 'E001'
        assert result.get_warnings()[0].code == 'W001'

    def test_worker_pipeline(self):
        """Test worker pipeline execution."""
        worker1 = TestWorkerImpl('Worker1')
        worker2 = TestWorkerImpl('Worker2')

        pipeline = WorkerPipeline([worker1, worker2])

        # Create test document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, '2023-12-01',
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        results = pipeline.process(document)

        assert len(results) == 2
        assert all(r.status == WorkerStatus.SUCCESS for r in results)
        assert results[0].worker_name == 'Worker1'
        assert results[1].worker_name == 'Worker2'

    def test_pipeline_error_handling(self):
        """Test pipeline error handling."""
        good_worker = TestWorkerImpl('GoodWorker')
        bad_worker = TestWorkerImpl('BadWorker', {'should_fail': True})

        pipeline = WorkerPipeline([good_worker, bad_worker])

        # Create test document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, '2023-12-01',
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        # Test with stop_on_error=True
        results = pipeline.process(document, stop_on_error=True)
        assert len(results) == 2  # Both executed, but second failed
        assert results[0].status == WorkerStatus.SUCCESS
        assert results[1].status == WorkerStatus.ERROR

        # Test with stop_on_error=False
        results = pipeline.process(document, stop_on_error=False)
        assert len(results) == 2


class TestWorkerImpl(BaseWorker):
    """Test implementation of BaseWorker."""

    def process(self, document, context=None):
        result = WorkerResult(
            worker_name=self.name,
            status=WorkerStatus.SUCCESS,
            document=document
        )

        if self.get_config_value('should_fail', False):
            result.status = WorkerStatus.ERROR
            result.add_error('test_error', 'Simulated error')

        return result


class TestValidatorWorker:
    """Test validator worker."""

    def test_validator_creation(self):
        """Test validator worker creation."""
        validator = ValidatorWorker()
        assert validator.name == 'ValidatorWorker'
        assert len(validator.rules) > 0

    def test_valid_document_validation(self):
        """Test validation of valid document."""
        validator = ValidatorWorker()

        # Create valid document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = validator.process(document)

        assert result.status in [WorkerStatus.SUCCESS, WorkerStatus.WARNING]
        assert not result.has_errors()

    def test_invalid_rut_validation(self):
        """Test validation with invalid RUT."""
        validator = ValidatorWorker()

        # Create document with invalid RUT
        factory = DTEFactory()
        emisor = Contribuyente('12345678-9', 'Test Emisor')  # Invalid RUT
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = validator.process(document)

        assert result.status == WorkerStatus.ERROR
        assert result.has_errors()
        assert any('RUT' in msg.message for msg in result.get_errors())

    def test_future_date_validation(self):
        """Test validation with future date."""
        validator = ValidatorWorker()

        # Create document with future date
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        future_date = '2030-12-31'
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, future_date,
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = validator.process(document)

        assert result.status == WorkerStatus.ERROR
        assert result.has_errors()
        assert any('futura' in msg.message for msg in result.get_errors())

    def test_negative_folio_validation(self):
        """Test validation with negative folio."""
        validator = ValidatorWorker()

        # Create document with negative folio
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, -1, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = validator.process(document)

        assert result.status == WorkerStatus.ERROR
        assert result.has_errors()
        assert any('positivo' in msg.message for msg in result.get_errors())

    def test_nota_credito_reference_validation(self):
        """Test nota de crédito reference validation."""
        validator = ValidatorWorker()

        # Create nota de crédito without reference
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_nota_credito(
            emisor=emisor,
            receptor=receptor,
            folio=3001,
            fecha_emision=str(date.today()),
            detalle=[{'NmbItem': 'Descuento', 'QtyItem': 1, 'PrcItem': -1000}]
            # Missing documento_referencia
        )

        result = validator.process(document)

        assert result.status == WorkerStatus.ERROR
        assert result.has_errors()
        assert any('referencia' in msg.message for msg in result.get_errors())

    def test_custom_validation_rules(self):
        """Test adding custom validation rules."""
        validator = ValidatorWorker()

        # Add custom rule
        def custom_rule(document, context):
            return False, "Custom validation failed"

        from rypsystems_dte.document.workers.validator import ValidationRule
        custom_validation = ValidationRule(
            "custom_test",
            "Custom test rule",
            custom_rule,
            "error"
        )
        validator.add_rule(custom_validation)

        # Create document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = validator.process(document)

        assert result.status == WorkerStatus.ERROR
        assert any('Custom validation failed' in msg.message for msg in result.get_errors())


class TestSanitizerWorker:
    """Test sanitizer worker."""

    def test_sanitizer_creation(self):
        """Test sanitizer worker creation."""
        sanitizer = SanitizerWorker()
        assert sanitizer.name == 'SanitizerWorker'
        assert sanitizer.config['normalize_unicode']

    def test_string_sanitization(self):
        """Test string sanitization."""
        sanitizer = SanitizerWorker()

        # Create document with text needing sanitization
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': '  Test Item with   extra   spaces  ', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = sanitizer.process(document)

        assert result.status == WorkerStatus.SUCCESS
        # Check if sanitization was applied
        if result.data.get('sanitization_actions'):
            assert len(result.data['sanitization_actions']) > 0

    def test_dangerous_character_removal(self):
        """Test removal of dangerous characters."""
        sanitizer = SanitizerWorker()

        # Create document with dangerous content
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': '<script>alert("xss")</script>Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = sanitizer.process(document)

        assert result.status == WorkerStatus.SUCCESS
        # Dangerous content should be removed
        processed_data = result.document.get_datos()
        detalle = processed_data.get('Detalle', [])
        if isinstance(detalle, list):
            item_name = detalle[0].get('NmbItem', '')
        else:
            item_name = detalle.get('NmbItem', '')

        assert '<script>' not in item_name

    def test_rut_normalization(self):
        """Test RUT format normalization."""
        sanitizer = SanitizerWorker()

        # Create document with unnormalized RUT
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1001, 'FchEmis': str(date.today())},
                'Emisor': {'RUTEmisor': '76.354.771K', 'RznSoc': 'Test Emisor'},
                'Receptor': {'RUTRecep': '66666666-6', 'RznSocRecep': 'Test Receptor'},
                'Totales': {'MntTotal': 1000}
            },
            'Detalle': [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        }

        from rypsystems_dte.dte.document import BaseDocument
        document = BaseDocument(datos)

        result = sanitizer.process(document)

        assert result.status == WorkerStatus.SUCCESS
        # RUT should be normalized
        processed_data = result.document.get_datos()
        rut_emisor = processed_data['Encabezado']['Emisor']['RUTEmisor']
        assert rut_emisor == '76354771-K'


class TestNormalizerWorker:
    """Test normalizer worker."""

    def test_normalizer_creation(self):
        """Test normalizer worker creation."""
        normalizer = NormalizerWorker()
        assert normalizer.name == 'NormalizerWorker'
        assert normalizer.config['normalize_rut_format']

    def test_document_structure_normalization(self):
        """Test document structure normalization."""
        normalizer = NormalizerWorker()

        # Create document with minimal structure
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': '33', 'Folio': '1001'},  # String values that should be converted
            }
        }

        from rypsystems_dte.dte.document import BaseDocument
        document = BaseDocument(datos)

        result = normalizer.process(document)

        assert result.status == WorkerStatus.SUCCESS
        processed_data = result.document.get_datos()

        # Check structure normalization
        assert 'Emisor' in processed_data['Encabezado']
        assert 'Receptor' in processed_data['Encabezado']

        # Check type conversion
        assert isinstance(processed_data['Encabezado']['IdDoc']['TipoDTE'], int)
        assert isinstance(processed_data['Encabezado']['IdDoc']['Folio'], int)

    def test_rut_format_normalization(self):
        """Test RUT format normalization."""
        normalizer = NormalizerWorker()

        # Create document with various RUT formats
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1001, 'FchEmis': str(date.today())},
                'Emisor': {'RUTEmisor': '76354771K', 'RznSoc': 'Test Emisor'},  # Without dots and hyphen
                'Receptor': {'RUTRecep': '66.666.666-6', 'RznSocRecep': 'Test Receptor'},  # With dots
                'Totales': {'MntTotal': 1000}
            },
            'Detalle': [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        }

        from rypsystems_dte.dte.document import BaseDocument
        document = BaseDocument(datos)

        result = normalizer.process(document)

        assert result.status == WorkerStatus.SUCCESS
        processed_data = result.document.get_datos()

        # Check RUT normalization
        rut_emisor = processed_data['Encabezado']['Emisor']['RUTEmisor']
        rut_receptor = processed_data['Encabezado']['Receptor']['RUTRecep']

        assert rut_emisor == '76.354.771-K'
        assert rut_receptor == '66.666.666-6'

    def test_date_normalization(self):
        """Test date format normalization."""
        normalizer = NormalizerWorker()

        # Create document with various date formats
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1001, 'FchEmis': '01/12/2023'},  # DD/MM/YYYY format
                'Emisor': {'RUTEmisor': '76354771-K', 'RznSoc': 'Test Emisor'},
                'Receptor': {'RUTRecep': '66666666-6', 'RznSocRecep': 'Test Receptor'},
                'Totales': {'MntTotal': 1000}
            },
            'Detalle': [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        }

        from rypsystems_dte.dte.document import BaseDocument
        document = BaseDocument(datos)

        result = normalizer.process(document)

        assert result.status == WorkerStatus.SUCCESS
        processed_data = result.document.get_datos()

        # Check date normalization to YYYY-MM-DD
        fecha_emis = processed_data['Encabezado']['IdDoc']['FchEmis']
        assert fecha_emis == '2023-12-01'

    def test_amount_normalization(self):
        """Test monetary amount normalization."""
        normalizer = NormalizerWorker()

        # Create document with decimal amounts
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1001, 'FchEmis': str(date.today())},
                'Emisor': {'RUTEmisor': '76354771-K', 'RznSoc': 'Test Emisor'},
                'Receptor': {'RUTRecep': '66666666-6', 'RznSocRecep': 'Test Receptor'},
                'Totales': {'MntTotal': 1000.50}  # With decimals
            },
            'Detalle': [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000.99}]
        }

        from rypsystems_dte.dte.document import BaseDocument
        document = BaseDocument(datos)

        result = normalizer.process(document)

        assert result.status == WorkerStatus.SUCCESS
        processed_data = result.document.get_datos()

        # Check amount rounding (Chilean pesos don't use decimals)
        mnt_total = processed_data['Encabezado']['Totales']['MntTotal']
        prc_item = processed_data['Detalle'][0]['PrcItem']

        assert isinstance(mnt_total, int)
        assert isinstance(prc_item, int)
        assert mnt_total == 1001  # Rounded
        assert prc_item == 1001   # Rounded

    def test_detalle_normalization(self):
        """Test detail section normalization."""
        normalizer = NormalizerWorker()

        # Create document with single detail item (not in list)
        datos = {
            'Encabezado': {
                'IdDoc': {'TipoDTE': 33, 'Folio': 1001, 'FchEmis': str(date.today())},
                'Emisor': {'RUTEmisor': '76354771-K', 'RznSoc': 'Test Emisor'},
                'Receptor': {'RUTRecep': '66666666-6', 'RznSocRecep': 'Test Receptor'},
                'Totales': {'MntTotal': 1000}
            },
            'Detalle': {'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}  # Single item, not list
        }

        from rypsystems_dte.dte.document import BaseDocument
        document = BaseDocument(datos)

        result = normalizer.process(document)

        assert result.status == WorkerStatus.SUCCESS
        processed_data = result.document.get_datos()

        # Check that detail is converted to list and line numbers added
        detalle = processed_data['Detalle']
        assert isinstance(detalle, list)
        assert len(detalle) == 1
        assert detalle[0]['NroLinDet'] == 1


class TestRendererWorker:
    """Test renderer worker."""

    def test_renderer_creation(self):
        """Test renderer worker creation."""
        renderer = RendererWorker()
        assert renderer.name == 'RendererWorker'
        assert renderer.config['default_format'] == RenderFormat.PDF

    def test_html_rendering(self):
        """Test HTML document rendering."""
        renderer = RendererWorker()

        # Create test document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = renderer.process(document, {'format': RenderFormat.HTML})

        assert result.status == WorkerStatus.SUCCESS
        assert result.data['format'] == RenderFormat.HTML
        assert result.data['content_type'] == 'text/html'
        assert 'rendered_content' in result.data
        assert 'Factura Electrónica' in result.data['rendered_content']

    def test_xml_rendering(self):
        """Test XML document rendering."""
        renderer = RendererWorker()

        # Create test document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = renderer.process(document, {'format': RenderFormat.XML})

        assert result.status == WorkerStatus.SUCCESS
        assert result.data['format'] == RenderFormat.XML
        assert result.data['content_type'] == 'application/xml'
        assert '<?xml' in result.data['rendered_content']

    def test_json_rendering(self):
        """Test JSON document rendering."""
        renderer = RendererWorker()

        # Create test document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = renderer.process(document, {'format': RenderFormat.JSON})

        assert result.status == WorkerStatus.SUCCESS
        assert result.data['format'] == RenderFormat.JSON
        assert result.data['content_type'] == 'application/json'

        # Validate JSON content
        json_content = json.loads(result.data['rendered_content'])
        assert 'Encabezado' in json_content

    def test_text_rendering(self):
        """Test plain text document rendering."""
        renderer = RendererWorker()

        # Create test document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = renderer.process(document, {'format': RenderFormat.TEXT})

        assert result.status == WorkerStatus.SUCCESS
        assert result.data['format'] == RenderFormat.TEXT
        assert result.data['content_type'] == 'text/plain'
        assert 'Factura Electrónica' in result.data['rendered_content']

    def test_file_output(self):
        """Test rendering to file."""
        renderer = RendererWorker()

        # Create test document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'test_document.html'

            result = renderer.process(document, {
                'format': RenderFormat.HTML,
                'output_path': str(output_path)
            })

            assert result.status == WorkerStatus.SUCCESS
            assert output_path.exists()
            assert output_path.read_text(encoding='utf-8')

    def test_invalid_format_error(self):
        """Test error handling for invalid format."""
        renderer = RendererWorker()

        # Create test document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        result = renderer.process(document, {'format': 'invalid_format'})

        assert result.status == WorkerStatus.ERROR
        assert result.has_errors()
        assert any('Unsupported format' in msg.message for msg in result.get_errors())


class TestWorkersIntegration:
    """Test complete workers pipeline integration."""

    def test_complete_pipeline(self):
        """Test complete document processing pipeline."""
        # Create pipeline with all workers
        validator = ValidatorWorker()
        sanitizer = SanitizerWorker()
        normalizer = NormalizerWorker()
        renderer = RendererWorker()

        pipeline = WorkerPipeline([validator, sanitizer, normalizer, renderer])

        # Create test document
        factory = DTEFactory()
        emisor = Contribuyente('76354771-K', 'Test Emisor')
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        # Process through pipeline
        results = pipeline.process(document, context={'format': RenderFormat.HTML})

        # Check all workers executed successfully
        assert len(results) == 4
        assert all(r.status in [WorkerStatus.SUCCESS, WorkerStatus.WARNING] for r in results)

        # Check final result has rendered content
        final_result = results[-1]
        assert 'rendered_content' in final_result.data
        assert final_result.data['format'] == RenderFormat.HTML

    def test_pipeline_with_validation_errors(self):
        """Test pipeline behavior with validation errors."""
        # Create pipeline that stops on errors
        validator = ValidatorWorker()
        sanitizer = SanitizerWorker()
        normalizer = NormalizerWorker()

        pipeline = WorkerPipeline([validator, sanitizer, normalizer])

        # Create invalid document
        factory = DTEFactory()
        emisor = Contribuyente('12345678-9', 'Test Emisor')  # Invalid RUT
        receptor = Contribuyente('66666666-6', 'Test Receptor')
        document = factory.create_factura_afecta(
            emisor, receptor, 1001, str(date.today()),
            [{'NmbItem': 'Test Item', 'QtyItem': 1, 'PrcItem': 1000}]
        )

        # Process with stop_on_error=True
        results = pipeline.process(document, stop_on_error=True)

        # Pipeline should stop at validation
        assert len(results) == 1
        assert results[0].status == WorkerStatus.ERROR
        assert results[0].worker_name == 'ValidatorWorker'

    def test_pipeline_validation(self):
        """Test pipeline configuration validation."""
        validator = ValidatorWorker()
        sanitizer = SanitizerWorker()

        pipeline = WorkerPipeline([validator, sanitizer])

        errors = pipeline.validate_pipeline()
        assert len(errors) == 0  # Should be valid

        # Test empty pipeline
        empty_pipeline = WorkerPipeline()
        errors = empty_pipeline.validate_pipeline()
        assert len(errors) > 0
        assert "no workers" in errors[0].lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])