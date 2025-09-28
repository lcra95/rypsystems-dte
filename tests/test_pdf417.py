"""
Tests para el módulo PDF417

Verificación de generación de códigos de barras PDF417 para TED
"""

import pytest
import base64
from unittest.mock import patch, MagicMock

from rypsystems_dte.pdf417.generator import (
    PDF417Generator,
    TEDGenerator,
    generate_pdf417_data_uri,
    BARCODE_AVAILABLE
)


class TestPDF417Generator:
    """Tests para la clase PDF417Generator"""

    def test_init_success_with_barcode_available(self):
        """Test inicialización exitosa cuando python-barcode está disponible"""
        with patch('rypsystems_dte.pdf417.generator.BARCODE_AVAILABLE', True):
            generator = PDF417Generator()
            assert generator is not None

    def test_init_fails_without_barcode(self):
        """Test falla de inicialización cuando python-barcode no está disponible"""
        with patch('rypsystems_dte.pdf417.generator.BARCODE_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                PDF417Generator()
            assert "python-barcode is required" in str(exc_info.value)

    @pytest.mark.skipif(not BARCODE_AVAILABLE, reason="python-barcode not available")
    def test_generate_barcode_data_uri_format(self):
        """Test formato correcto del data URI generado"""
        generator = PDF417Generator()
        data_uri = generator.generate_barcode_data_uri("TEST_DATA")

        assert data_uri.startswith("data:image/png;base64,")

        # Verificar que la parte base64 es válida
        base64_part = data_uri.split(",")[1]
        try:
            base64.b64decode(base64_part)
        except Exception as e:
            pytest.fail(f"Invalid base64 data: {e}")

    @pytest.mark.skipif(not BARCODE_AVAILABLE, reason="python-barcode not available")
    def test_generate_barcode_png_returns_bytes(self):
        """Test que generate_barcode_png retorna bytes"""
        generator = PDF417Generator()
        png_data = generator.generate_barcode_png("TEST_DATA")

        assert isinstance(png_data, bytes)
        assert len(png_data) > 0
        # Verificar cabecera PNG
        assert png_data.startswith(b'\x89PNG')

    def test_generate_placeholder_png(self):
        """Test generación de imagen placeholder"""
        generator = PDF417Generator()
        png_data = generator._generate_placeholder_png("TEST_DATA", 200, 100)

        assert isinstance(png_data, bytes)
        assert len(png_data) > 0
        # Verificar cabecera PNG
        assert png_data.startswith(b'\x89PNG')

    @pytest.mark.skipif(not BARCODE_AVAILABLE, reason="python-barcode not available")
    def test_generate_barcode_with_custom_parameters(self):
        """Test generación con parámetros personalizados"""
        generator = PDF417Generator()
        data_uri = generator.generate_barcode_data_uri(
            "CUSTOM_DATA",
            width=2,
            height=2,
            color=(255, 0, 0)  # Rojo
        )

        assert data_uri.startswith("data:image/png;base64,")

    def test_generate_barcode_with_empty_data(self):
        """Test manejo de datos vacíos"""
        generator = PDF417Generator()
        # No debería fallar con datos vacíos
        data_uri = generator.generate_barcode_data_uri("")
        assert data_uri.startswith("data:image/png;base64,")

    def test_generate_barcode_with_special_characters(self):
        """Test manejo de caracteres especiales"""
        generator = PDF417Generator()
        special_data = "TED<>áéíóú&@#$%"
        data_uri = generator.generate_barcode_data_uri(special_data)
        assert data_uri.startswith("data:image/png;base64,")


class TestTEDGenerator:
    """Tests para la clase TEDGenerator"""

    def test_init_success(self):
        """Test inicialización exitosa"""
        with patch('rypsystems_dte.pdf417.generator.BARCODE_AVAILABLE', True):
            ted_gen = TEDGenerator()
            assert ted_gen.pdf417_generator is not None

    def test_validate_ted_data_valid(self):
        """Test validación de datos TED válidos"""
        ted_gen = TEDGenerator()
        valid_ted = """<TED><DD><RE>12345678-9</RE><TD>33</TD><F>123</F></DD></TED>"""

        assert ted_gen.validate_ted_data(valid_ted) is True

    def test_validate_ted_data_invalid_missing_elements(self):
        """Test validación de datos TED inválidos (elementos faltantes)"""
        ted_gen = TEDGenerator()
        invalid_ted = """<TED><DD><RE>12345678-9</RE></DD></TED>"""

        assert ted_gen.validate_ted_data(invalid_ted) is False

    def test_validate_ted_data_empty(self):
        """Test validación de datos TED vacíos"""
        ted_gen = TEDGenerator()

        assert ted_gen.validate_ted_data("") is False
        assert ted_gen.validate_ted_data(None) is False

    def test_validate_ted_data_wrong_type(self):
        """Test validación con tipo de datos incorrecto"""
        ted_gen = TEDGenerator()

        assert ted_gen.validate_ted_data(123) is False
        assert ted_gen.validate_ted_data([]) is False

    @pytest.mark.skipif(not BARCODE_AVAILABLE, reason="python-barcode not available")
    def test_generate_ted_barcode_success(self):
        """Test generación exitosa de código TED"""
        ted_gen = TEDGenerator()
        ted_data = """<TED><DD><RE>12345678-9</RE><TD>33</TD><F>123</F></DD></TED>"""

        barcode = ted_gen.generate_ted_barcode(ted_data)

        assert barcode.startswith("data:image/png;base64,")

    def test_generate_ted_barcode_with_complex_ted(self):
        """Test generación con TED complejo"""
        ted_gen = TEDGenerator()
        complex_ted = """<TED version="1.0">
            <DD>
                <RE>12345678-9</RE>
                <TD>33</TD>
                <F>123</F>
                <FE>2023-12-01</FE>
                <RR>87654321-0</RR>
                <RSR>Empresa Receptora</RSR>
                <MNT>1000</MNT>
                <IT1>Producto de prueba</IT1>
                <CAF>datos_caf</CAF>
                <TSTED>timestamp</TSTED>
            </DD>
            <FRMT algoritmo="SHA1withRSA">firma_digital</FRMT>
        </TED>"""

        barcode = ted_gen.generate_ted_barcode(complex_ted)
        assert barcode.startswith("data:image/png;base64,")


class TestGeneratePDF417DataURI:
    """Tests para la función de conveniencia generate_pdf417_data_uri"""

    @pytest.mark.skipif(not BARCODE_AVAILABLE, reason="python-barcode not available")
    def test_function_works(self):
        """Test que la función de conveniencia funciona"""
        data_uri = generate_pdf417_data_uri("TEST_DATA")
        assert data_uri.startswith("data:image/png;base64,")

    def test_function_compatibility_with_php(self):
        """Test compatibilidad con implementación PHP original"""
        # Simular datos TED reales
        ted_data = """<TED version="1.0"><DD><RE>76354771-K</RE><TD>33</TD><F>123</F><FE>2023-12-01</FE><RR>66666666-6</RR><RSR>Cliente Test</RSR><MNT>1000</MNT><IT1>Producto Test</IT1><CAF>datos_caf_aqui</CAF><TSTED>2023-12-01T10:30:00</TSTED></DD><FRMT algoritmo="SHA1withRSA">firma_aqui</FRMT></TED>"""

        data_uri = generate_pdf417_data_uri(ted_data)

        # Verificar formato correcto (compatible con PHP)
        assert data_uri.startswith("data:image/png;base64,")

        # Verificar que los datos base64 son válidos
        base64_part = data_uri.split(",")[1]
        try:
            decoded = base64.b64decode(base64_part)
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"Invalid base64 encoding: {e}")


class TestModuleIntegration:
    """Tests de integración del módulo completo"""

    def test_module_imports(self):
        """Test que todas las importaciones del módulo funcionan"""
        from rypsystems_dte.pdf417 import PDF417Generator, TEDGenerator, generate_pdf417_data_uri

        assert PDF417Generator is not None
        assert TEDGenerator is not None
        assert generate_pdf417_data_uri is not None

    @pytest.mark.skipif(not BARCODE_AVAILABLE, reason="python-barcode not available")
    def test_end_to_end_ted_workflow(self):
        """Test workflow completo de generación TED"""
        # 1. Crear generador TED
        ted_gen = TEDGenerator()

        # 2. Datos TED de ejemplo
        ted_data = """<TED version="1.0">
            <DD>
                <RE>76354771-K</RE>
                <TD>33</TD>
                <F>1001</F>
                <FE>2023-12-01</FE>
                <RR>66666666-6</RR>
                <RSR>Cliente de Prueba S.A.</RSR>
                <MNT>119000</MNT>
                <IT1>Servicio de Consultoría</IT1>
                <CAF>datos_caf_firmado</CAF>
                <TSTED>2023-12-01T15:30:45</TSTED>
            </DD>
            <FRMT algoritmo="SHA1withRSA">MGUCMEJvbGV0YSBObyBGaXNjYWwgRWplbXBsbyBkZSBUaW1icmUgRWxlY3Ryw7NuaWNvAhRkZW1v</FRMT>
        </TED>"""

        # 3. Validar datos TED
        assert ted_gen.validate_ted_data(ted_data) is True

        # 4. Generar código de barras
        barcode_uri = ted_gen.generate_ted_barcode(ted_data)

        # 5. Verificar resultado
        assert barcode_uri.startswith("data:image/png;base64,")

        # 6. Verificar que se puede decodificar el base64
        base64_data = barcode_uri.split(",")[1]
        png_bytes = base64.b64decode(base64_data)
        assert png_bytes.startswith(b'\x89PNG')

    def test_error_handling_without_dependencies(self):
        """Test manejo de errores sin dependencias"""
        with patch('rypsystems_dte.pdf417.generator.BARCODE_AVAILABLE', False):
            with pytest.raises(ImportError):
                PDF417Generator()


# Tests de performance (opcional, para casos de alto volumen)
class TestPerformance:
    """Tests de rendimiento para casos de alto volumen"""

    @pytest.mark.skipif(not BARCODE_AVAILABLE, reason="python-barcode not available")
    def test_multiple_barcode_generation_performance(self):
        """Test rendimiento generando múltiples códigos"""
        generator = PDF417Generator()

        import time
        start_time = time.time()

        # Generar 10 códigos de barras
        for i in range(10):
            data_uri = generator.generate_barcode_data_uri(f"TEST_DATA_{i}")
            assert data_uri.startswith("data:image/png;base64,")

        end_time = time.time()
        total_time = end_time - start_time

        # Debería generar 10 códigos en menos de 5 segundos
        assert total_time < 5.0, f"Performance issue: took {total_time}s for 10 barcodes"