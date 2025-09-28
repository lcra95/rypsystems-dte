"""
Ejemplo práctico de uso de servicios web del SII.

Demuestra cómo usar la integración completa con SOAP y REST
para enviar documentos y consultar estados.
"""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any

from rypsystems_dte.sii.base import SiiAmbiente, Contribuyente
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.webservices import (
    DocumentSender,
    StatusChecker,
    SendingProtocol,
    DocumentStatus
)
from rypsystems_dte.sii.webservices.exceptions import (
    SiiAuthenticationError,
    SiiValidationError,
    SiiCommunicationError
)


class SiiWebServicesDemo:
    """
    Demostración completa de servicios web del SII.

    Incluye autenticación, envío de documentos, consulta de estados
    y monitoreo continuo.
    """

    def __init__(self, environment: SiiAmbiente = SiiAmbiente.CERTIFICACION):
        """Inicializa demo con ambiente especificado."""
        self.environment = environment

        # Configurar servicios
        self.document_sender = DocumentSender(
            environment=environment,
            protocol=SendingProtocol.AUTO,  # Intenta REST primero, fallback a SOAP
            timeout=60,
            retry_attempts=3
        )

        self.status_checker = StatusChecker(
            environment=environment,
            timeout=30,
            retry_attempts=3,
            polling_interval=30
        )

        # Factory para crear documentos
        self.dte_factory = DTEFactory()

    def authenticate_services(self, credentials: Dict[str, Any]) -> bool:
        """
        Autentica ambos servicios SOAP y REST.

        Args:
            credentials: Diccionario con credenciales
            {
                'rut_company': '76354771-K',
                'soap': {
                    'certificate': 'contenido_certificado_pem',
                    'private_key': 'contenido_clave_privada_pem'
                },
                'rest': {
                    'api_key': 'clave_api_sii',
                    'api_secret': 'secreto_api_sii'
                }
            }

        Returns:
            True si al menos un servicio se autentica exitosamente
        """
        print("🔐 Iniciando autenticación de servicios SII...")

        auth_results = {
            'soap': False,
            'rest': False
        }

        # Autenticar SOAP
        if 'soap' in credentials:
            try:
                print("   📡 Autenticando servicio SOAP...")
                auth_results['soap'] = self.document_sender.authenticate_soap(
                    credentials['rut_company'],
                    credentials['soap']['certificate'],
                    credentials['soap']['private_key']
                )
                print(f"   ✅ SOAP: {'Exitoso' if auth_results['soap'] else 'Falló'}")
            except SiiAuthenticationError as e:
                print(f"   ❌ Error SOAP: {e}")

        # Autenticar REST
        if 'rest' in credentials:
            try:
                print("   🌐 Autenticando servicio REST...")
                auth_results['rest'] = self.document_sender.authenticate_rest(
                    credentials['rut_company'],
                    credentials['rest']['api_key'],
                    credentials['rest']['api_secret']
                )
                print(f"   ✅ REST: {'Exitoso' if auth_results['rest'] else 'Falló'}")
            except SiiAuthenticationError as e:
                print(f"   ❌ Error REST: {e}")

        success = any(auth_results.values())
        print(f"🔐 Autenticación: {'Exitosa' if success else 'Falló'}")

        return success

    def create_sample_documents(self) -> List[Any]:
        """
        Crea documentos de ejemplo para testing.

        Returns:
            Lista de documentos DTE de ejemplo
        """
        print("📄 Creando documentos de ejemplo...")

        # Contribuyentes de ejemplo
        emisor = Contribuyente('76354771-K', 'Mi Empresa Ltda.')
        receptor = Contribuyente('66666666-6', 'Cliente Ejemplo S.A.')

        documents = []

        # Factura Afecta
        try:
            factura = self.dte_factory.create_factura_afecta(
                emisor=emisor,
                receptor=receptor,
                folio=1001,
                fecha_emision='2023-12-01',
                detalle=[
                    {
                        'NmbItem': 'Producto A',
                        'QtyItem': 10,
                        'PrcItem': 1000
                    },
                    {
                        'NmbItem': 'Producto B',
                        'QtyItem': 5,
                        'PrcItem': 2000
                    }
                ]
            )
            documents.append(factura)
            print("   ✅ Factura Afecta creada")
        except Exception as e:
            print(f"   ❌ Error creando factura: {e}")

        # Nota de Crédito
        try:
            nota_credito = self.dte_factory.create_nota_credito(
                emisor=emisor,
                receptor=receptor,
                folio=3001,
                fecha_emision='2023-12-02',
                detalle=[
                    {
                        'NmbItem': 'Descuento por error',
                        'QtyItem': 1,
                        'PrcItem': -5000
                    }
                ],
                documento_referencia={
                    'TpoDocRef': 33,
                    'FolioRef': 1001,
                    'FchRef': '2023-12-01',
                    'CodRef': 1,
                    'RazonRef': 'Error en facturación'
                }
            )
            documents.append(nota_credito)
            print("   ✅ Nota de Crédito creada")
        except Exception as e:
            print(f"   ❌ Error creando nota de crédito: {e}")

        print(f"📄 {len(documents)} documentos creados exitosamente")
        return documents

    def send_documents(self, documents: List[Any]) -> List[Dict[str, Any]]:
        """
        Envía documentos al SII usando el servicio coordinado.

        Args:
            documents: Lista de documentos a enviar

        Returns:
            Lista de resultados de envío
        """
        print(f"📤 Enviando {len(documents)} documentos al SII...")

        # Verificar que estamos listos para enviar
        if not self.document_sender.is_ready_to_send():
            print("❌ No hay servicios autenticados para envío")
            return []

        # Mostrar estadísticas de conectividad
        connectivity = self.document_sender.test_connectivity()
        print("🔍 Estado de conectividad:")
        for service, status in connectivity.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {service}: {'OK' if status else 'Error'}")

        results = []

        for i, document in enumerate(documents, 1):
            print(f"\n📋 Enviando documento {i}/{len(documents)}")
            print(f"   📄 Tipo: {document.get_tipo_documento()}")
            print(f"   📊 Folio: {document.get_folio()}")
            print(f"   👤 Emisor: {document.get_rut_emisor()}")

            try:
                # Enviar documento
                result = self.document_sender.send_document(document)

                result_data = {
                    'document_id': document.get_id(),
                    'tipo_documento': document.get_tipo_documento(),
                    'folio': document.get_folio(),
                    'success': result.success,
                    'protocol_used': result.protocol_used,
                    'track_id': result.track_id,
                    'message': result.message,
                    'timestamp': result.timestamp,
                    'errors': result.errors
                }

                results.append(result_data)

                # Mostrar resultado
                status_icon = "✅" if result.success else "❌"
                print(f"   {status_icon} Resultado: {result.message}")
                print(f"   📡 Protocolo: {result.protocol_used.upper()}")
                if result.track_id:
                    print(f"   🔖 Track ID: {result.track_id}")

            except Exception as e:
                print(f"   ❌ Error enviando documento: {e}")
                result_data = {
                    'document_id': document.get_id(),
                    'success': False,
                    'error': str(e)
                }
                results.append(result_data)

        # Mostrar estadísticas finales
        print(f"\n📊 Estadísticas de envío:")
        stats = self.document_sender.get_sending_stats()
        print(f"   📈 Total enviados: {stats['total_sent']}")
        print(f"   📡 SOAP: {stats['soap_sent']}")
        print(f"   🌐 REST: {stats['rest_sent']}")
        print(f"   ❌ Fallos: {stats['failures']}")
        print(f"   ✅ Tasa de éxito: {stats['success_rate']}%")

        return results

    def check_document_statuses(self, document_queries: List[tuple]) -> List[Dict[str, Any]]:
        """
        Consulta estados de documentos en el SII.

        Args:
            document_queries: Lista de tuplas (rut_sender, rut_company, tipo_doc, folio)

        Returns:
            Lista de resultados de consulta
        """
        print(f"🔍 Consultando estado de {len(document_queries)} documentos...")

        results = []

        for i, query in enumerate(document_queries, 1):
            rut_sender, rut_company, tipo_doc, folio = query

            print(f"\n📋 Consulta {i}/{len(document_queries)}")
            print(f"   📄 Documento: {tipo_doc}-{folio}")
            print(f"   👤 RUT: {rut_sender}")

            try:
                # Consultar estado
                status_result = self.status_checker.check_document_status(
                    rut_sender, rut_company, tipo_doc, folio
                )

                result_data = {
                    'rut_sender': rut_sender,
                    'tipo_documento': tipo_doc,
                    'folio': folio,
                    'status': status_result.status.value,
                    'message': status_result.message,
                    'protocol_used': status_result.protocol_used,
                    'last_checked': status_result.last_checked,
                    'sii_details': status_result.sii_details
                }

                results.append(result_data)

                # Mostrar resultado
                status_icons = {
                    DocumentStatus.ACCEPTED: "✅",
                    DocumentStatus.REJECTED: "❌",
                    DocumentStatus.PENDING: "⏳",
                    DocumentStatus.PROCESSED: "🔄",
                    DocumentStatus.ERROR: "🚨",
                    DocumentStatus.NOT_FOUND: "❓",
                    DocumentStatus.UNKNOWN: "❔"
                }

                icon = status_icons.get(status_result.status, "❔")
                print(f"   {icon} Estado: {status_result.status.value}")
                print(f"   💬 Mensaje: {status_result.message}")
                print(f"   📡 Protocolo: {status_result.protocol_used.upper()}")

            except Exception as e:
                print(f"   ❌ Error consultando estado: {e}")
                result_data = {
                    'rut_sender': rut_sender,
                    'tipo_documento': tipo_doc,
                    'folio': folio,
                    'error': str(e)
                }
                results.append(result_data)

        return results

    def monitor_document_processing(self, rut_sender: str, rut_company: str,
                                   tipo_doc: int, folio: int,
                                   max_duration: int = 300) -> Dict[str, Any]:
        """
        Monitorea el procesamiento de un documento en tiempo real.

        Args:
            rut_sender: RUT del emisor
            rut_company: RUT de la empresa
            tipo_doc: Tipo de documento
            folio: Folio del documento
            max_duration: Duración máxima en segundos

        Returns:
            Resultado del monitoreo
        """
        print(f"⏱️ Iniciando monitoreo de documento {tipo_doc}-{folio}")
        print(f"   🕐 Duración máxima: {max_duration} segundos")

        # Iniciar monitoreo
        monitor_id = self.status_checker.start_monitoring(
            rut_sender, rut_company, tipo_doc, folio,
            check_interval=30,  # Consultar cada 30 segundos
            max_duration=max_duration
        )

        print(f"   🆔 Monitor ID: {monitor_id}")

        start_time = time.time()
        last_status = None

        try:
            while time.time() - start_time < max_duration:
                # Consultar estado actual
                result = self.status_checker.check_document_status(
                    rut_sender, rut_company, tipo_doc, folio
                )

                # Mostrar cambios de estado
                if result.status != last_status:
                    elapsed = int(time.time() - start_time)
                    print(f"   [{elapsed:03d}s] 🔄 Estado: {result.status.value} - {result.message}")
                    last_status = result.status

                    # Parar si el documento ya fue procesado completamente
                    if result.status in [DocumentStatus.ACCEPTED, DocumentStatus.REJECTED, DocumentStatus.ERROR]:
                        print(f"   ✅ Procesamiento completado: {result.status.value}")
                        break

                # Esperar antes de la siguiente consulta
                time.sleep(30)

            else:
                print(f"   ⏰ Tiempo de monitoreo agotado ({max_duration}s)")

        finally:
            # Detener monitoreo
            self.status_checker.stop_monitoring(monitor_id)
            print(f"   🛑 Monitoreo detenido")

        return {
            'monitor_id': monitor_id,
            'final_status': last_status.value if last_status else 'unknown',
            'duration': int(time.time() - start_time)
        }

    def demonstrate_bulk_operations(self, documents: List[Any]) -> Dict[str, Any]:
        """
        Demuestra operaciones masivas con múltiples documentos.

        Args:
            documents: Lista de documentos para operaciones masivas

        Returns:
            Resultados de las operaciones masivas
        """
        print("📦 Demostrando operaciones masivas...")

        results = {
            'bulk_send': None,
            'bulk_status_check': None,
            'performance_metrics': {}
        }

        # Envío masivo
        print("\n🚀 Envío masivo de documentos...")
        start_time = time.time()

        try:
            send_results = self.document_sender.send_multiple_documents(
                documents,
                stop_on_error=False  # Continuar aunque haya errores
            )

            send_duration = time.time() - start_time
            successful_sends = sum(1 for r in send_results if r.success)

            results['bulk_send'] = {
                'total_documents': len(documents),
                'successful': successful_sends,
                'failed': len(send_results) - successful_sends,
                'duration': send_duration,
                'documents_per_second': len(documents) / send_duration if send_duration > 0 else 0
            }

            print(f"   ✅ Enviados: {successful_sends}/{len(documents)}")
            print(f"   ⏱️ Tiempo: {send_duration:.2f}s")
            print(f"   📈 Velocidad: {results['bulk_send']['documents_per_second']:.2f} docs/s")

        except Exception as e:
            print(f"   ❌ Error en envío masivo: {e}")
            results['bulk_send'] = {'error': str(e)}

        # Consulta masiva de estados
        print("\n🔍 Consulta masiva de estados...")
        start_time = time.time()

        try:
            # Crear consultas para todos los documentos
            queries = [(doc.get_rut_emisor(), doc.get_rut_emisor(),
                       doc.get_tipo_documento(), doc.get_folio())
                      for doc in documents]

            status_results = self.status_checker.check_multiple_documents(queries)

            status_duration = time.time() - start_time

            # Contar estados
            status_counts = {}
            for result in status_results:
                status = result.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

            results['bulk_status_check'] = {
                'total_queries': len(queries),
                'duration': status_duration,
                'queries_per_second': len(queries) / status_duration if status_duration > 0 else 0,
                'status_distribution': status_counts
            }

            print(f"   ✅ Consultas: {len(queries)}")
            print(f"   ⏱️ Tiempo: {status_duration:.2f}s")
            print(f"   📈 Velocidad: {results['bulk_status_check']['queries_per_second']:.2f} consultas/s")
            print("   📊 Distribución de estados:")
            for status, count in status_counts.items():
                print(f"      {status}: {count}")

        except Exception as e:
            print(f"   ❌ Error en consulta masiva: {e}")
            results['bulk_status_check'] = {'error': str(e)}

        return results

    def run_complete_demo(self) -> Dict[str, Any]:
        """
        Ejecuta demostración completa de servicios web del SII.

        Returns:
            Resultados completos de la demostración
        """
        print("🎯 Iniciando demostración completa de servicios web SII")
        print(f"🏢 Ambiente: {self.environment.name.upper()}")
        print("=" * 60)

        demo_results = {
            'environment': self.environment.name.lower(),
            'start_time': datetime.now().isoformat(),
            'authentication': False,
            'documents_created': 0,
            'send_results': [],
            'status_results': [],
            'bulk_operations': {},
            'errors': []
        }

        try:
            # Paso 1: Autenticación (simulada para demo)
            print("\n🔐 PASO 1: Autenticación de servicios")

            # Para demo, usamos credenciales ficticias
            mock_credentials = {
                'rut_company': '76354771-K',
                'soap': {
                    'certificate': 'MOCK_CERTIFICATE_CONTENT',
                    'private_key': 'MOCK_PRIVATE_KEY_CONTENT'
                },
                'rest': {
                    'api_key': 'MOCK_API_KEY',
                    'api_secret': 'MOCK_API_SECRET'
                }
            }

            # En un entorno real, descomentarías esto:
            # demo_results['authentication'] = self.authenticate_services(mock_credentials)

            # Para demo, simulamos autenticación exitosa
            demo_results['authentication'] = True
            print("✅ Autenticación simulada exitosa")

            # Paso 2: Crear documentos de ejemplo
            print("\n📄 PASO 2: Creación de documentos")
            documents = self.create_sample_documents()
            demo_results['documents_created'] = len(documents)

            if not documents:
                raise Exception("No se pudieron crear documentos de ejemplo")

            # Paso 3: Envío de documentos (simulado)
            print("\n📤 PASO 3: Envío de documentos")
            print("ℹ️ Nota: En modo demo, el envío es simulado")

            # Simular resultados de envío
            for doc in documents:
                mock_result = {
                    'document_id': doc.get_id(),
                    'tipo_documento': doc.get_tipo_documento(),
                    'folio': doc.get_folio(),
                    'success': True,
                    'protocol_used': 'rest',
                    'track_id': f'TRK_{doc.get_folio()}',
                    'message': 'Enviado exitosamente (simulado)',
                    'timestamp': datetime.now().isoformat()
                }
                demo_results['send_results'].append(mock_result)
                print(f"   ✅ Documento {doc.get_tipo_documento()}-{doc.get_folio()}: Simulado exitoso")

            # Paso 4: Consulta de estados (simulado)
            print("\n🔍 PASO 4: Consulta de estados")
            print("ℹ️ Nota: En modo demo, las consultas son simuladas")

            for doc in documents:
                mock_status = {
                    'rut_sender': doc.get_rut_emisor(),
                    'tipo_documento': doc.get_tipo_documento(),
                    'folio': doc.get_folio(),
                    'status': 'accepted',
                    'message': 'Documento aceptado (simulado)',
                    'protocol_used': 'rest',
                    'last_checked': datetime.now().isoformat()
                }
                demo_results['status_results'].append(mock_status)
                print(f"   ✅ Estado {doc.get_tipo_documento()}-{doc.get_folio()}: Aceptado (simulado)")

            # Paso 5: Operaciones masivas (simulado)
            print("\n📦 PASO 5: Operaciones masivas")
            demo_results['bulk_operations'] = {
                'simulated': True,
                'total_documents': len(documents),
                'bulk_send_success_rate': 100,
                'bulk_status_check_success_rate': 100,
                'average_processing_time': 2.5
            }
            print("   ✅ Operaciones masivas simuladas exitosamente")

        except Exception as e:
            error_msg = f"Error en demostración: {e}"
            print(f"❌ {error_msg}")
            demo_results['errors'].append(error_msg)

        demo_results['end_time'] = datetime.now().isoformat()

        # Resumen final
        print("\n" + "=" * 60)
        print("📋 RESUMEN DE DEMOSTRACIÓN")
        print("=" * 60)
        print(f"🏢 Ambiente: {demo_results['environment'].upper()}")
        print(f"🔐 Autenticación: {'✅ Exitosa' if demo_results['authentication'] else '❌ Falló'}")
        print(f"📄 Documentos creados: {demo_results['documents_created']}")
        print(f"📤 Documentos enviados: {len(demo_results['send_results'])}")
        print(f"🔍 Estados consultados: {len(demo_results['status_results'])}")
        print(f"❌ Errores: {len(demo_results['errors'])}")

        if demo_results['errors']:
            print("\n🚨 Errores encontrados:")
            for error in demo_results['errors']:
                print(f"   • {error}")

        print("\n✅ Demostración completada")
        return demo_results


def main():
    """Función principal para ejecutar ejemplos."""
    print("🎯 Ejemplos de Servicios Web SII - rypsystems-dte")
    print("=" * 60)

    # Crear instancia de demo
    demo = SiiWebServicesDemo(SiiAmbiente.CERTIFICACION)

    # Ejecutar demostración completa
    results = demo.run_complete_demo()

    # Guardar resultados
    import json
    results_file = 'sii_webservices_demo_results.json'
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n📁 Resultados guardados en: {results_file}")


if __name__ == "__main__":
    main()