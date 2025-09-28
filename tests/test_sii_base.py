"""
Tests para el módulo base del SII.

Verifica que las funciones Python produzcan EXACTAMENTE
los mismos resultados que las versiones PHP originales.
"""

import pytest
from rypsystems_dte.sii.base import SiiAmbiente, Contribuyente, PartyIdentifier
from rypsystems_dte.sii.utils import RutValidator
from rypsystems_dte.sii.constants import CodigoDocumento, DOCUMENTOS_SII


class TestRutValidator:
    r"""Tests para validación de RUT - equivalencia con Derafu\L10n\Cl\Rut\Rut."""

    def test_format_valid_ruts(self):
        """Test formateo de RUTs válidos."""
        # Casos de prueba que deben funcionar igual que en PHP
        test_cases = [
            ("123456789", "12345678-9"),
            ("11111111K", "11111111-K"),
            ("111111111", "11111111-1"),
            (123456789, "12345678-9"),
            ("12345678-9", "12345678-9"),  # Ya formateado
            ("1-9", "1-9"),  # RUT corto
            ("76354771K", "76354771-K"),
        ]

        for input_rut, expected in test_cases:
            result = RutValidator.format(input_rut)
            assert result == expected, f"Format({input_rut}) expected {expected}, got {result}"

    def test_format_invalid_ruts(self):
        """Test formateo de RUTs inválidos."""
        invalid_cases = [
            "",
            "abc",
            "12345678X",  # Solo K es válido como letra
            "12345678-X",
            "123456789012345",  # Muy largo
        ]

        for invalid_rut in invalid_cases:
            with pytest.raises(ValueError):
                RutValidator.format(invalid_rut)

    def test_to_array_valid_ruts(self):
        """Test separación de RUT en número y DV."""
        test_cases = [
            ("12345678-9", (12345678, "9")),
            ("11111111-K", (11111111, "K")),
            ("1-9", (1, "9")),
            ("76354771K", (76354771, "K")),
            (123456789, (12345678, "9")),
        ]

        for input_rut, expected in test_cases:
            result = RutValidator.to_array(input_rut)
            assert result == expected, f"to_array({input_rut}) expected {expected}, got {result}"

    def test_validate_known_valid_ruts(self):
        """Test validación de RUTs que sabemos son válidos."""
        valid_ruts = [
            "11111111-1",  # RUT clásico de prueba
            "76354771-K",  # Otro RUT válido conocido
            "1-9",         # RUT mínimo válido
        ]

        for rut in valid_ruts:
            assert RutValidator.validate(rut), f"RUT {rut} debería ser válido"

    def test_validate_known_invalid_ruts(self):
        """Test validación de RUTs que sabemos son inválidos."""
        invalid_ruts = [
            "12345678-9",  # DV incorrecto
            "11111111-2",  # DV incorrecto
            "76354771-0",  # DV incorrecto
            "",            # Vacío
            "abc",         # No numérico
        ]

        for rut in invalid_ruts:
            assert not RutValidator.validate(rut), f"RUT {rut} debería ser inválido"

    def test_calcular_dv_algorithm(self):
        """Test del algoritmo de cálculo de DV."""
        # Casos donde conocemos el resultado esperado
        test_cases = [
            (11111111, "1"),
            (76354771, "K"),
            (1, "9"),
        ]

        for numero, expected_dv in test_cases:
            result = RutValidator._calcular_dv(numero)
            assert result == expected_dv, f"DV para {numero} expected {expected_dv}, got {result}"


class TestSiiAmbiente:
    """Tests para enum SiiAmbiente - equivalencia con enum PHP."""

    def test_enum_values(self):
        """Test valores del enum."""
        assert SiiAmbiente.PRODUCCION == 0
        assert SiiAmbiente.CERTIFICACION == 1

    def test_is_certificacion(self):
        """Test método is_certificacion."""
        assert not SiiAmbiente.PRODUCCION.is_certificacion()
        assert SiiAmbiente.CERTIFICACION.is_certificacion()

    def test_get_servidor_default(self):
        """Test obtención de servidor por defecto."""
        assert SiiAmbiente.PRODUCCION.get_servidor() == "palena"
        assert SiiAmbiente.CERTIFICACION.get_servidor() == "maullin"

        assert SiiAmbiente.PRODUCCION.get_servidor("default") == "palena"
        assert SiiAmbiente.CERTIFICACION.get_servidor("default") == "maullin"

    def test_get_servidor_www4(self):
        """Test obtención de servidor www4."""
        assert SiiAmbiente.PRODUCCION.get_servidor("www4") == "www4"
        assert SiiAmbiente.CERTIFICACION.get_servidor("www4") == "www4c"

    def test_get_wsdl_default(self):
        """Test generación de URL WSDL por defecto."""
        expected_prod = "https://palena.sii.cl/DTEWS/CrSeed.jws?WSDL"
        expected_cert = "https://maullin.sii.cl/DTEWS/CrSeed.jws?WSDL"

        assert SiiAmbiente.PRODUCCION.get_wsdl("CrSeed") == expected_prod
        assert SiiAmbiente.CERTIFICACION.get_wsdl("CrSeed") == expected_cert

    def test_get_wsdl_specific_service(self):
        """Test generación de URL WSDL para servicios específicos."""
        expected_prod = "https://palena.sii.cl/DTEWS/services/QueryEstDteAv?WSDL"
        expected_cert = "https://maullin.sii.cl/DTEWS/services/QueryEstDteAv?WSDL"

        assert SiiAmbiente.PRODUCCION.get_wsdl("QueryEstDteAv") == expected_prod
        assert SiiAmbiente.CERTIFICACION.get_wsdl("QueryEstDteAv") == expected_cert

    def test_get_url_default(self):
        """Test generación de URLs generales."""
        recurso = "/cgi_dte/UPL/DTEUpload"
        expected_prod = "https://palena.sii.cl/cgi_dte/UPL/DTEUpload"
        expected_cert = "https://maullin.sii.cl/cgi_dte/UPL/DTEUpload"

        assert SiiAmbiente.PRODUCCION.get_url(recurso) == expected_prod
        assert SiiAmbiente.CERTIFICACION.get_url(recurso) == expected_cert

    def test_get_url_anulacion(self):
        """Test URL específica para anulación."""
        recurso = "/anulacionMsvDteInternet"
        expected_prod = "https://www4.sii.cl/anulacionMsvDteInternet"
        expected_cert = "https://www4c.sii.cl/anulacionMsvDteInternet"

        assert SiiAmbiente.PRODUCCION.get_url(recurso) == expected_prod
        assert SiiAmbiente.CERTIFICACION.get_url(recurso) == expected_cert


class TestPartyIdentifier:
    """Tests para PartyIdentifier - equivalencia con clase PHP."""

    def test_creation_default_scheme(self):
        """Test creación con esquema por defecto."""
        identifier = PartyIdentifier(value="12345678-9")

        assert identifier.scheme_id == "CL-RUT"
        assert identifier.value == "12345678-9"

    def test_creation_custom_scheme(self):
        """Test creación con esquema personalizado."""
        identifier = PartyIdentifier(scheme_id="EMAIL", value="test@example.com")

        assert identifier.scheme_id == "EMAIL"
        assert identifier.value == "test@example.com"

    def test_get_id(self):
        """Test obtención de ID completo."""
        identifier = PartyIdentifier(value="12345678-9")
        assert identifier.get_id() == "CL-RUT:12345678-9"

        identifier_email = PartyIdentifier(scheme_id="EMAIL", value="test@example.com")
        assert identifier_email.get_id() == "EMAIL:test@example.com"

    def test_get_scheme_name(self):
        """Test obtención de nombre del esquema."""
        identifier = PartyIdentifier(value="12345678-9")
        assert identifier.get_scheme_name() == "Rol Único Tributario (RUT) de Chile"

        identifier_email = PartyIdentifier(scheme_id="EMAIL", value="test@example.com")
        assert identifier_email.get_scheme_name() == "Correo electrónico"

        # Esquema desconocido
        identifier_unknown = PartyIdentifier(scheme_id="UNKNOWN", value="test")
        assert identifier_unknown.get_scheme_name() == "UNKNOWN"

    def test_get_authority(self):
        """Test obtención de autoridad del esquema."""
        identifier = PartyIdentifier(value="12345678-9")
        assert identifier.get_authority() == "CL-SII"

        identifier_email = PartyIdentifier(scheme_id="EMAIL", value="test@example.com")
        assert identifier_email.get_authority() == "INTERNET"


class TestContribuyente:
    """Tests para Contribuyente - equivalencia con clase PHP."""

    def test_creation_valid_rut(self):
        """Test creación con RUT válido."""
        contribuyente = Contribuyente(rut="11111111-1", razon_social="Empresa Test")

        assert contribuyente.rut == 11111111
        assert contribuyente.dv == "1"
        assert contribuyente.razon_social == "Empresa Test"

    def test_creation_invalid_rut(self):
        """Test creación con RUT inválido debe fallar."""
        with pytest.raises(ValueError):
            Contribuyente(rut="12345678-9")  # DV incorrecto

    def test_creation_with_integer_rut(self):
        """Test creación con RUT como entero."""
        contribuyente = Contribuyente(rut=111111111)  # 11111111-1

        assert contribuyente.rut == 11111111
        assert contribuyente.dv == "1"

    def test_get_rut_methods(self):
        """Test métodos de obtención de RUT."""
        contribuyente = Contribuyente(rut="11111111-1")

        assert contribuyente.get_rut_as_int() == 11111111
        assert contribuyente.get_rut() == "11111111-1"

    def test_get_razon_social_with_value(self):
        """Test razón social cuando tiene valor."""
        contribuyente = Contribuyente(rut="11111111-1", razon_social="Empresa Test")
        assert contribuyente.get_razon_social() == "Empresa Test"

    def test_get_razon_social_without_value(self):
        """Test razón social cuando no tiene valor (debe retornar RUT)."""
        contribuyente = Contribuyente(rut="11111111-1")
        assert contribuyente.get_razon_social() == "11111111-1"

    def test_empty_values_converted_to_none(self):
        """Test que valores vacíos se convierten a None."""
        contribuyente = Contribuyente(
            rut="11111111-1",
            razon_social="",  # Vacío
            giro=None,
            telefono="  ",  # Solo espacios
        )

        assert contribuyente.razon_social is None
        assert contribuyente.giro is None
        assert contribuyente.telefono is None

    def test_all_getters(self):
        """Test todos los métodos getter."""
        contribuyente = Contribuyente(
            rut="11111111-1",
            razon_social="Empresa Test",
            giro="Servicios de prueba",
            actividad_economica=123456,
            telefono="+56912345678",
            email="test@empresa.cl",
            direccion="Calle Test 123",
            comuna="Santiago",
        )

        assert contribuyente.get_giro() == "Servicios de prueba"
        assert contribuyente.get_actividad_economica() == 123456
        assert contribuyente.get_telefono() == "+56912345678"
        assert contribuyente.get_email() == "test@empresa.cl"
        assert contribuyente.get_direccion() == "Calle Test 123"
        assert contribuyente.get_comuna() == "Santiago"


class TestCodigoDocumento:
    """Tests para enum CodigoDocumento."""

    def test_enum_values(self):
        """Test valores del enum."""
        assert CodigoDocumento.FACTURA_AFECTA == 33
        assert CodigoDocumento.FACTURA_EXENTA == 34
        assert CodigoDocumento.BOLETA_AFECTA == 39
        assert CodigoDocumento.NOTA_DEBITO == 56
        assert CodigoDocumento.NOTA_CREDITO == 61

    def test_get_nombre(self):
        """Test obtención de nombres."""
        assert CodigoDocumento.FACTURA_AFECTA.get_nombre() == "Factura electrónica"
        assert CodigoDocumento.BOLETA_AFECTA.get_nombre() == "Boleta electrónica"

    def test_get_alias(self):
        """Test obtención de alias."""
        assert CodigoDocumento.FACTURA_AFECTA.get_alias() == "FE"
        assert CodigoDocumento.BOLETA_AFECTA.get_alias() == "BE"


class TestDocumentosSII:
    """Tests para diccionario DOCUMENTOS_SII."""

    def test_factura_afecta_properties(self):
        """Test propiedades de factura afecta."""
        doc = DOCUMENTOS_SII[33]

        assert doc["nombre"] == "Factura electrónica"
        assert doc["electronico"] is True
        assert doc["disponible"] is True
        assert doc["alias"] == "FE"

    def test_documento_not_found(self):
        """Test documento no encontrado."""
        from rypsystems_dte.sii.constants import get_documento_info

        with pytest.raises(KeyError):
            get_documento_info(99999)

    def test_es_documento_electronico(self):
        """Test verificación de documento electrónico."""
        from rypsystems_dte.sii.constants import es_documento_electronico

        assert es_documento_electronico(33) is True  # Factura electrónica
        assert es_documento_electronico(30) is False  # Factura papel

    def test_es_documento_cedible(self):
        """Test verificación de documento cedible."""
        from rypsystems_dte.sii.constants import es_documento_cedible

        assert es_documento_cedible(33) is True  # Factura electrónica
        assert es_documento_cedible(39) is False  # Boleta electrónica