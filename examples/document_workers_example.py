"""
Ejemplo de uso del Document Workers System.

Demuestra cómo usar el sistema de workers para procesamiento completo de documentos
incluyendo validación, sanitización, normalización y renderizado.
"""

import sys
import os
from datetime import date
from pathlib import Path

# Add src to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.document.workers import (
    ValidatorWorker, SanitizerWorker, NormalizerWorker, RendererWorker,
    WorkerPipeline, WorkerStatus
)
from rypsystems_dte.document.workers.renderer import RenderFormat
from rypsystems_dte.document.workers.validator import ValidationRule


def ejemplo_validacion_basica():
    """Ejemplo básico de validación de documentos."""
    print("=== EJEMPLO VALIDACIÓN BÁSICA ===")

    # Crear documento válido
    factory = DTEFactory()
    emisor = Contribuyente("76354771-K", "Mi Empresa S.A.")
    receptor = Contribuyente("66666666-6", "Cliente S.A.")

    factura = factory.create_factura_afecta(
        emisor=emisor,
        receptor=receptor,
        folio=1001,
        fecha_emision=str(date.today()),
        detalle=[{
            'NmbItem': 'Producto de ejemplo',
            'QtyItem': 10,
            'PrcItem': 1000
        }]
    )

    print(f"✅ Documento creado: {factura.get_id()}")

    # Crear validador
    validator = ValidatorWorker()

    print("🔍 Ejecutando validación...")
    result = validator.process(factura)

    print(f"📊 Estado: {result.status}")
    print(f"📊 Reglas ejecutadas: {result.data.get('rules_executed', 0)}")

    if result.has_errors():
        print("❌ Errores encontrados:")
        for error in result.get_errors():
            print(f"   - {error.code}: {error.message}")
    else:
        print("✅ Validación exitosa")

    if result.has_warnings():
        print("⚠️  Advertencias:")
        for warning in result.get_warnings():
            print(f"   - {warning.code}: {warning.message}")

    return result


def ejemplo_validacion_con_errores():
    """Ejemplo de validación con errores."""
    print("\n=== EJEMPLO VALIDACIÓN CON ERRORES ===")

    # Crear documento con errores
    factory = DTEFactory()
    emisor = Contribuyente("12345678-9", "Empresa con RUT inválido")  # RUT inválido
    receptor = Contribuyente("66666666-6", "Cliente S.A.")

    try:
        factura = factory.create_factura_afecta(
            emisor=emisor,
            receptor=receptor,
            folio=-1,  # Folio inválido
            fecha_emision="2030-12-31",  # Fecha futura
            detalle=[{
                'NmbItem': '  Producto con espacios extra  ',
                'QtyItem': 0,  # Cantidad inválida
                'PrcItem': 1000
            }]
        )

        print(f"✅ Documento creado: {factura.get_id()}")

        # Validar
        validator = ValidatorWorker()
        result = validator.process(factura)

        print(f"📊 Estado: {result.status}")

        if result.has_errors():
            print("❌ Errores encontrados:")
            for error in result.get_errors():
                print(f"   - {error.code}: {error.message}")

        return result

    except Exception as e:
        print(f"❌ Error creando documento: {e}")
        return None


def ejemplo_sanitizacion():
    """Ejemplo de sanitización de datos."""
    print("\n=== EJEMPLO SANITIZACIÓN ===")

    # Crear documento con datos que necesitan sanitización
    datos = {
        'Encabezado': {
            'IdDoc': {'TipoDTE': 33, 'Folio': 1001, 'FchEmis': str(date.today())},
            'Emisor': {
                'RUTEmisor': '76.354.771K',  # RUT sin formato estándar
                'RznSoc': '  Mi Empresa S.A.  '  # Espacios extra
            },
            'Receptor': {
                'RUTRecep': '66666666-6',
                'RznSocRecep': 'Cliente & Asociados  <script>alert("xss")</script>'  # Contenido peligroso
            },
            'Totales': {'MntTotal': 1000}
        },
        'Detalle': [{
            'NmbItem': '  Producto\t\tcon\n\nespacios\textra  ',  # Espacios y tabs
            'QtyItem': 1,
            'PrcItem': 1000
        }]
    }

    from rypsystems_dte.dte.document import FacturaAfecta
    document = FacturaAfecta(datos)

    print("📝 Datos originales:")
    print(f"   RUT Emisor: '{datos['Encabezado']['Emisor']['RUTEmisor']}'")
    print(f"   Receptor: '{datos['Encabezado']['Receptor']['RznSocRecep']}'")
    print(f"   Item: '{datos['Detalle'][0]['NmbItem']}'")

    # Sanitizar
    sanitizer = SanitizerWorker()
    result = sanitizer.process(document)

    print(f"\n📊 Estado: {result.status}")
    print(f"📊 Acciones aplicadas: {result.data.get('actions_count', 0)}")

    if result.data.get('sanitization_actions'):
        print("🧹 Acciones de sanitización:")
        for action in result.data['sanitization_actions'][:5]:  # Mostrar solo las primeras 5
            print(f"   - {action}")

    # Mostrar datos sanitizados
    datos_sanitizados = result.document.get_datos()
    print("\n✨ Datos sanitizados:")
    print(f"   RUT Emisor: '{datos_sanitizados['Encabezado']['Emisor']['RUTEmisor']}'")
    print(f"   Receptor: '{datos_sanitizados['Encabezado']['Receptor']['RznSocRecep']}'")
    print(f"   Item: '{datos_sanitizados['Detalle'][0]['NmbItem']}'")

    return result


def ejemplo_normalizacion():
    """Ejemplo de normalización de estructura."""
    print("\n=== EJEMPLO NORMALIZACIÓN ===")

    # Crear documento con estructura que necesita normalización
    datos = {
        'Encabezado': {
            'IdDoc': {
                'TipoDTE': '33',  # String que debería ser int
                'Folio': '1001',  # String que debería ser int
                'FchEmis': '01/12/2023'  # Formato de fecha no estándar
            },
            'Emisor': {
                'RUTEmisor': '76354771K',  # Sin puntos ni guión
                'RznSoc': 'mi empresa s.a.'  # Sin capitalización
            },
            'Totales': {
                'MntTotal': 1000.50  # Con decimales (pesos chilenos no usan decimales)
            }
        },
        'Detalle': {  # Single item, no es lista
            'NmbItem': 'Producto de ejemplo',
            'QtyItem': '1',  # String que debería ser numeric
            'PrcItem': 1000.99  # Con decimales
        }
    }

    from rypsystems_dte.dte.document import FacturaAfecta
    document = FacturaAfecta(datos)

    print("📝 Estructura original:")
    print(f"   TipoDTE: {datos['Encabezado']['IdDoc']['TipoDTE']} ({type(datos['Encabezado']['IdDoc']['TipoDTE'])})")
    print(f"   Fecha: {datos['Encabezado']['IdDoc']['FchEmis']}")
    print(f"   RUT: {datos['Encabezado']['Emisor']['RUTEmisor']}")
    print(f"   Monto: {datos['Encabezado']['Totales']['MntTotal']}")
    print(f"   Detalle es lista: {isinstance(datos['Detalle'], list)}")

    # Normalizar
    normalizer = NormalizerWorker()
    result = normalizer.process(document)

    print(f"\n📊 Estado: {result.status}")
    print(f"📊 Acciones aplicadas: {result.data.get('actions_count', 0)}")

    if result.data.get('normalization_actions'):
        print("🔧 Acciones de normalización:")
        for action in result.data['normalization_actions'][:8]:  # Mostrar solo las primeras 8
            print(f"   - {action}")

    # Mostrar datos normalizados
    datos_normalizados = result.document.get_datos()
    print("\n✨ Estructura normalizada:")
    print(f"   TipoDTE: {datos_normalizados['Encabezado']['IdDoc']['TipoDTE']} ({type(datos_normalizados['Encabezado']['IdDoc']['TipoDTE'])})")
    print(f"   Fecha: {datos_normalizados['Encabezado']['IdDoc']['FchEmis']}")
    print(f"   RUT: {datos_normalizados['Encabezado']['Emisor']['RUTEmisor']}")
    print(f"   Monto: {datos_normalizados['Encabezado']['Totales']['MntTotal']}")
    print(f"   Detalle es lista: {isinstance(datos_normalizados['Detalle'], list)}")
    print(f"   Emisor existe: {'Emisor' in datos_normalizados['Encabezado']}")
    print(f"   Receptor existe: {'Receptor' in datos_normalizados['Encabezado']}")

    return result


def ejemplo_renderizado():
    """Ejemplo de renderizado de documentos."""
    print("\n=== EJEMPLO RENDERIZADO ===")

    # Crear documento
    factory = DTEFactory()
    emisor = Contribuyente("76354771-K", "Mi Empresa S.A.")
    receptor = Contribuyente("66666666-6", "Cliente S.A.")

    factura = factory.create_factura_afecta(
        emisor=emisor,
        receptor=receptor,
        folio=1001,
        fecha_emision=str(date.today()),
        detalle=[
            {'NmbItem': 'Producto A', 'QtyItem': 2, 'PrcItem': 1500},
            {'NmbItem': 'Producto B', 'QtyItem': 1, 'PrcItem': 2000}
        ]
    )

    print(f"✅ Documento creado: {factura.get_id()}")

    # Crear renderer
    renderer = RendererWorker()

    # Renderizar en diferentes formatos
    formatos = [
        (RenderFormat.HTML, 'factura.html'),
        (RenderFormat.XML, 'factura.xml'),
        (RenderFormat.JSON, 'factura.json'),
        (RenderFormat.TEXT, 'factura.txt')
    ]

    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)

    for formato, filename in formatos:
        print(f"\n🎨 Renderizando en formato {formato.upper()}...")

        output_path = output_dir / filename
        result = renderer.process(factura, {
            'format': formato,
            'output_path': str(output_path)
        })

        print(f"📊 Estado: {result.status}")
        print(f"📊 Tipo contenido: {result.data.get('content_type')}")
        print(f"📊 Tamaño: {result.data.get('size_bytes', 0):,} bytes")

        if result.status == WorkerStatus.SUCCESS:
            print(f"✅ Archivo guardado: {output_path}")

            # Mostrar preview del contenido
            if formato == RenderFormat.TEXT:
                preview = result.data['rendered_content'][:200] + "..."
                print(f"📄 Preview:\n{preview}")

        if result.has_errors():
            print("❌ Errores:")
            for error in result.get_errors():
                print(f"   - {error.message}")

    return result


def ejemplo_pipeline_completo():
    """Ejemplo de pipeline completo de procesamiento."""
    print("\n=== EJEMPLO PIPELINE COMPLETO ===")

    # Crear documento con varios problemas
    datos = {
        'Encabezado': {
            'IdDoc': {
                'TipoDTE': '33',  # String
                'Folio': '1001',  # String
                'FchEmis': '01-12-2023'  # Formato no estándar
            },
            'Emisor': {
                'RUTEmisor': '76.354.771K',  # Sin formato estándar
                'RznSoc': '  Mi Empresa & Cia.  '  # Espacios extra
            },
            'Receptor': {
                'RUTRecep': '66666666-6',
                'RznSocRecep': 'Cliente S.A.'
            },
            'Totales': {
                'MntNeto': 1000,
                'IVA': 190,
                'MntTotal': 1190
            }
        },
        'Detalle': {  # Single item
            'NmbItem': '  Producto con espacios  ',
            'QtyItem': '1',
            'PrcItem': '1000'
        }
    }

    from rypsystems_dte.dte.document import FacturaAfecta
    document = FacturaAfecta(datos)

    print("📝 Documento original creado")

    # Crear pipeline con todos los workers
    validator = ValidatorWorker()
    sanitizer = SanitizerWorker()
    normalizer = NormalizerWorker()
    renderer = RendererWorker()

    pipeline = WorkerPipeline([validator, sanitizer, normalizer, renderer])

    print("🔧 Pipeline creado con 4 workers:")
    print("   1. ValidatorWorker - Validación de reglas de negocio")
    print("   2. SanitizerWorker - Limpieza de datos")
    print("   3. NormalizerWorker - Normalización de estructura")
    print("   4. RendererWorker - Renderizado a HTML")

    # Ejecutar pipeline
    print("\n🚀 Ejecutando pipeline...")
    context = {'format': RenderFormat.HTML}
    results = pipeline.process(document, context, stop_on_error=False)

    print(f"\n📊 Pipeline completado: {len(results)} workers ejecutados")

    # Mostrar resultados de cada worker
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.worker_name}:")
        print(f"   Estado: {result.status}")
        print(f"   Tiempo: {result.execution_time:.3f}s")

        if result.has_errors():
            print("   ❌ Errores:")
            for error in result.get_errors()[:3]:  # Mostrar solo los primeros 3
                print(f"      - {error.code}: {error.message}")

        if result.has_warnings():
            print("   ⚠️  Advertencias:")
            for warning in result.get_warnings()[:3]:
                print(f"      - {warning.code}: {warning.message}")

        # Información específica del worker
        if result.worker_name == 'SanitizerWorker':
            actions = result.data.get('actions_count', 0)
            if actions > 0:
                print(f"   🧹 Acciones de sanitización: {actions}")

        elif result.worker_name == 'NormalizerWorker':
            actions = result.data.get('actions_count', 0)
            if actions > 0:
                print(f"   🔧 Acciones de normalización: {actions}")

        elif result.worker_name == 'RendererWorker':
            size = result.data.get('size_bytes', 0)
            if size > 0:
                print(f"   🎨 Contenido generado: {size:,} bytes")

    # Estado final del pipeline
    errors = sum(1 for r in results if r.has_errors())
    warnings = sum(1 for r in results if r.has_warnings())
    success = sum(1 for r in results if r.status == WorkerStatus.SUCCESS)

    print(f"\n📈 Resumen final:")
    print(f"   ✅ Workers exitosos: {success}")
    print(f"   ❌ Workers con errores: {errors}")
    print(f"   ⚠️  Workers con advertencias: {warnings}")

    if results[-1].status == WorkerStatus.SUCCESS:
        print("   🎉 Pipeline completado exitosamente")

        # Guardar resultado final
        output_file = Path('output/pipeline_result.html')
        output_file.parent.mkdir(exist_ok=True)
        output_file.write_text(results[-1].data['rendered_content'], encoding='utf-8')
        print(f"   📄 Resultado guardado en: {output_file}")

    return results


def ejemplo_validacion_personalizada():
    """Ejemplo de validación con reglas personalizadas."""
    print("\n=== EJEMPLO VALIDACIÓN PERSONALIZADA ===")

    # Definir regla personalizada
    def validar_monto_minimo(document, context):
        """Validar que el monto total sea mayor a un mínimo."""
        datos = document.get_datos()
        totales = datos.get('Encabezado', {}).get('Totales', {})
        mnt_total = totales.get('MntTotal', 0)

        minimo = context.get('monto_minimo', 1000)
        if mnt_total < minimo:
            return False, f"Monto total ${mnt_total:,} es menor al mínimo ${minimo:,}"

        return True, ""

    # Crear validador con regla personalizada
    validator = ValidatorWorker()
    regla_personalizada = ValidationRule(
        "monto_minimo",
        "El monto total debe ser mayor al mínimo establecido",
        validar_monto_minimo,
        "error"
    )
    validator.add_rule(regla_personalizada)

    print("✅ Regla personalizada agregada: monto_minimo")

    # Crear documento con monto bajo
    factory = DTEFactory()
    emisor = Contribuyente("76354771-K", "Mi Empresa S.A.")
    receptor = Contribuyente("66666666-6", "Cliente S.A.")

    factura = factory.create_factura_afecta(
        emisor=emisor,
        receptor=receptor,
        folio=1001,
        fecha_emision=str(date.today()),
        detalle=[{'NmbItem': 'Producto barato', 'QtyItem': 1, 'PrcItem': 500}]  # Monto bajo
    )

    print(f"📝 Documento creado con monto: ${factura.get_datos()['Encabezado']['Totales']['MntTotal']:,}")

    # Validar con contexto personalizado
    context = {'monto_minimo': 1000}
    result = validator.process(factura, context)

    print(f"📊 Estado: {result.status}")
    print(f"📊 Reglas ejecutadas: {result.data.get('rules_executed', 0)}")

    if result.has_errors():
        print("❌ Errores encontrados:")
        for error in result.get_errors():
            print(f"   - {error.code}: {error.message}")
            if error.code == 'monto_minimo':
                print("   ⭐ Esta es nuestra regla personalizada!")

    return result


def main():
    """Función principal que ejecuta todos los ejemplos."""
    print("🚀 EJEMPLOS DEL DOCUMENT WORKERS SYSTEM - RypSystems DTE")
    print("=" * 70)

    try:
        # Crear directorio de salida
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)

        # Ejecutar ejemplos
        ejemplo_validacion_basica()
        ejemplo_validacion_con_errores()
        ejemplo_sanitizacion()
        ejemplo_normalizacion()
        ejemplo_renderizado()
        ejemplo_pipeline_completo()
        ejemplo_validacion_personalizada()

        print("\n" + "=" * 70)
        print("✅ TODOS LOS EJEMPLOS COMPLETADOS")
        print("\n📝 NOTAS IMPORTANTES:")
        print("   - Los workers pueden ejecutarse individualmente o en pipeline")
        print("   - Cada worker tiene configuración personalizable")
        print("   - Los errores se capturan y reportan detalladamente")
        print("   - El sistema es extensible con reglas y workers personalizados")
        print("   - Los archivos generados están en el directorio 'output/'")

    except Exception as e:
        print(f"\n❌ Error ejecutando ejemplos: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()