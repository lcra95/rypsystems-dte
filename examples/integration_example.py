"""
Ejemplo de uso del Integration Component.

Demuestra cómo usar el módulo de integración SII para enviar documentos
y consultar estados usando tanto SOAP como REST.
"""

import sys
import os
from datetime import date

# Add src to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from rypsystems_dte.sii.base import SiiAmbiente, Contribuyente
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.integration.sii_client import SiiClient, create_sii_client
from rypsystems_dte.integration.exceptions import (
    SiiAuthenticationException,
    SiiConnectionException,
    IntegrationException
)


def ejemplo_basico_integracion():
    """Ejemplo básico de integración con SII."""
    print("=== EJEMPLO BÁSICO DE INTEGRACIÓN SII ===")

    # 1. Crear cliente SII para ambiente de certificación
    print("1. Creando cliente SII...")
    sii_client = create_sii_client(
        ambiente=SiiAmbiente.CERTIFICACION,
        prefer_rest=True,
        timeout=30
    )

    print(f"   ✅ Cliente creado para ambiente: {sii_client.ambiente.name}")
    print(f"   ✅ Protocolo preferido: {'REST' if sii_client.prefer_rest else 'SOAP'}")

    # 2. Obtener estado de autenticación (antes de autenticar)
    print("\n2. Estado de autenticación inicial:")
    status = sii_client.get_authentication_status()
    for key, value in status.items():
        print(f"   {key}: {value}")

    return sii_client


def ejemplo_autenticacion_certificado(sii_client):
    """Ejemplo de autenticación con certificado (SOAP)."""
    print("\n=== AUTENTICACIÓN CON CERTIFICADO (SOAP) ===")

    try:
        # Simular certificado y clave privada
        certificate_content = """-----BEGIN CERTIFICATE-----
MIICertificateContentHere...
-----END CERTIFICATE-----"""

        private_key_content = """-----BEGIN PRIVATE KEY-----
MIIPrivateKeyContentHere...
-----END PRIVATE KEY-----"""

        print("1. Intentando autenticación con certificado...")
        success = sii_client.authenticate_with_certificate(
            rut_company="76354771-K",
            certificate_content=certificate_content,
            private_key_content=private_key_content
        )

        if success:
            print("   ✅ Autenticación exitosa via SOAP")
            print(f"   ✅ RUT empresa: {sii_client.current_rut_company}")
            print(f"   ✅ Método: {sii_client.auth_method}")
        else:
            print("   ❌ Autenticación falló")

    except SiiAuthenticationException as e:
        print(f"   ⚠️  Error de autenticación: {e}")
        print("   (Esto es esperado en el ejemplo, certificado simulado)")

    except Exception as e:
        print(f"   ❌ Error inesperado: {e}")


def ejemplo_autenticacion_api_key(sii_client):
    """Ejemplo de autenticación con API key (REST)."""
    print("\n=== AUTENTICACIÓN CON API KEY (REST) ===")

    try:
        print("1. Intentando autenticación con API key...")
        success = sii_client.authenticate_with_api_key(
            rut_company="76354771-K",
            api_key="test_api_key",
            api_secret="test_api_secret"
        )

        if success:
            print("   ✅ Autenticación exitosa via REST")
            print(f"   ✅ RUT empresa: {sii_client.current_rut_company}")
            print(f"   ✅ Método: {sii_client.auth_method}")
        else:
            print("   ❌ Autenticación falló")

    except SiiAuthenticationException as e:
        print(f"   ⚠️  Error de autenticación: {e}")
        print("   (Esto es esperado en el ejemplo, API key simulada)")

    except Exception as e:
        print(f"   ❌ Error inesperado: {e}")


def ejemplo_creacion_y_envio_documento():
    """Ejemplo de creación y envío de documento."""
    print("\n=== CREACIÓN Y ENVÍO DE DOCUMENTO ===")

    # 1. Crear documento DTE
    print("1. Creando documento DTE...")
    factory = DTEFactory()
    emisor = Contribuyente("76354771-K", "Mi Empresa S.A.")
    receptor = Contribuyente("66666666-6", "Cliente S.A.")

    factura = factory.create_factura_afecta(
        emisor=emisor,
        receptor=receptor,
        folio=1001,
        fecha_emision="2023-12-01",
        detalle=[{
            'NmbItem': 'Producto de ejemplo',
            'QtyItem': 10,
            'PrcItem': 1000
        }]
    )

    print(f"   ✅ Documento creado: {factura.get_id()}")
    print(f"   ✅ Tipo: {factura.get_codigo()} - Folio: {factura.get_folio()}")
    print(f"   ✅ Emisor: {factura.get_rut_emisor()}")
    print(f"   ✅ Receptor: {factura.get_rut_receptor()}")

    # 2. Simular envío al SII (requiere autenticación real)
    print("\n2. Simulando envío al SII...")
    try:
        # Crear cliente simulado para demostración
        sii_client = create_sii_client(ambiente=SiiAmbiente.CERTIFICACION)

        # Intentar envío (fallará sin autenticación real)
        response = factura.submit_to_sii(sii_client, validate_only=True)
        print(f"   ✅ Respuesta SII: {response.message}")

    except SiiAuthenticationException as e:
        print(f"   ⚠️  Error de autenticación: {e}")
        print("   (Esto es esperado - se requiere autenticación real)")

    except Exception as e:
        print(f"   ❌ Error: {e}")

    return factura


def ejemplo_consulta_estado_documento(factura):
    """Ejemplo de consulta de estado de documento."""
    print("\n=== CONSULTA DE ESTADO DE DOCUMENTO ===")

    try:
        # Crear cliente para consulta
        sii_client = create_sii_client(ambiente=SiiAmbiente.CERTIFICACION)

        print("1. Consultando estado de documento...")
        print(f"   Documento: {factura.get_id()}")
        print(f"   Folio: {factura.get_folio()}")

        # Intentar consulta (fallará sin autenticación real)
        response = factura.query_sii_status(sii_client)
        print(f"   ✅ Estado obtenido: {response.message}")

    except SiiAuthenticationException as e:
        print(f"   ⚠️  Error de autenticación: {e}")
        print("   (Esto es esperado - se requiere autenticación real)")

    except Exception as e:
        print(f"   ❌ Error: {e}")


def ejemplo_consulta_por_fechas():
    """Ejemplo de consulta de documentos por rango de fechas."""
    print("\n=== CONSULTA POR RANGO DE FECHAS ===")

    try:
        sii_client = create_sii_client(ambiente=SiiAmbiente.CERTIFICACION)

        print("1. Consultando documentos por fecha...")
        date_from = date(2023, 12, 1)
        date_to = date(2023, 12, 31)

        print(f"   Rango: {date_from} - {date_to}")

        # Intentar consulta por fechas
        response = sii_client.query_document_status(
            date_from=date_from,
            date_to=date_to,
            document_types=[33, 61]  # Facturas y notas de crédito
        )

        print(f"   ✅ Consulta realizada: {response.message}")

    except SiiAuthenticationException as e:
        print(f"   ⚠️  Error de autenticación: {e}")
        print("   (Esto es esperado - se requiere autenticación real)")

    except Exception as e:
        print(f"   ❌ Error: {e}")


def ejemplo_manejo_errores():
    """Ejemplo de manejo de diferentes tipos de errores."""
    print("\n=== MANEJO DE ERRORES ===")

    # 1. Error de conexión simulado
    print("1. Simulando error de conexión...")
    try:
        sii_client = SiiClient(ambiente=SiiAmbiente.CERTIFICACION, timeout=1)
        # Esto podría generar timeout en conexión real
        print("   ⚠️  En conexión real, timeout podría ocurrir")

    except SiiConnectionException as e:
        print(f"   ❌ Error de conexión: {e}")

    except Exception as e:
        print(f"   ❌ Error: {e}")

    # 2. Error de validación simulado
    print("\n2. Ejemplo de error de validación...")
    try:
        from rypsystems_dte.integration.models.sii_request import SiiQueryRequest
        from datetime import date

        # Intentar crear request con fecha futura (debería fallar)
        request = SiiQueryRequest(
            request_id="test",
            rut_company="76354771-K",
            rut_sender="76354771-K",
            date_from=date(2030, 1, 1)  # Fecha futura
        )

    except ValueError as e:
        print(f"   ✅ Validación funcionando: {e}")

    # 3. Tipos de errores disponibles
    print("\n3. Tipos de errores disponibles:")
    from rypsystems_dte.integration.exceptions import (
        IntegrationException,
        SiiConnectionException,
        SiiAuthenticationException,
        SiiValidationException,
        SiiTimeoutException
    )

    error_types = [
        IntegrationException,
        SiiConnectionException,
        SiiAuthenticationException,
        SiiValidationException,
        SiiTimeoutException
    ]

    for error_type in error_types:
        print(f"   - {error_type.__name__}: {error_type.__doc__.strip()}")


def main():
    """Función principal que ejecuta todos los ejemplos."""
    print("🚀 EJEMPLOS DE INTEGRACIÓN SII - RypSystems DTE")
    print("=" * 60)

    try:
        # 1. Ejemplo básico
        sii_client = ejemplo_basico_integracion()

        # 2. Ejemplos de autenticación
        ejemplo_autenticacion_certificado(sii_client)
        ejemplo_autenticacion_api_key(sii_client)

        # 3. Creación y envío de documento
        factura = ejemplo_creacion_y_envio_documento()

        # 4. Consulta de estado
        ejemplo_consulta_estado_documento(factura)

        # 5. Consulta por fechas
        ejemplo_consulta_por_fechas()

        # 6. Manejo de errores
        ejemplo_manejo_errores()

        print("\n" + "=" * 60)
        print("✅ TODOS LOS EJEMPLOS COMPLETADOS")
        print("\n📝 NOTAS IMPORTANTES:")
        print("   - Los ejemplos usan datos simulados para demostración")
        print("   - Para uso real, necesitas certificado válido o API keys del SII")
        print("   - El ambiente de certificación requiere credenciales reales")
        print("   - Los errores de autenticación son esperados en este ejemplo")

    except Exception as e:
        print(f"\n❌ Error ejecutando ejemplos: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()