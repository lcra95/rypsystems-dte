# 🏛️ Guía Completa de Certificación SII

**Proceso paso a paso para certificarse con el SII usando RypSystems DTE**

## Tabla de Contenidos

1. [Prerequisitos](#prerequisitos)
2. [Paso 1: Preparación del Certificado Digital](#paso-1-preparación-del-certificado-digital)
3. [Paso 2: Configuración en el SII](#paso-2-configuración-en-el-sii)
4. [Paso 3: Configuración de la Librería](#paso-3-configuración-de-la-librería)
5. [Paso 4: Pruebas de Conectividad](#paso-4-pruebas-de-conectividad)
6. [Paso 5: Creación de Documentos de Prueba](#paso-5-creación-de-documentos-de-prueba)
7. [Paso 6: Envío al SII y Validación](#paso-6-envío-al-sii-y-validación)
8. [Paso 7: Proceso de Certificación](#paso-7-proceso-de-certificación)
9. [Paso 8: Migración a Producción](#paso-8-migración-a-producción)
10. [Solución de Problemas](#solución-de-problemas)

---

## Prerequisitos

### ✅ Documentos y Información Requerida

**Antes de comenzar, asegúrate de tener:**

- [ ] **RUT de la empresa** (formato: 12345678-9)
- [ ] **Certificado digital** emitido por una CA autorizada por el SII
- [ ] **Clave privada** del certificado (archivo .key o .pem)
- [ ] **Número de resolución** de autorización de DTE del SII
- [ ] **Fecha de resolución** de autorización
- [ ] **Código de actividad económica** de la empresa
- [ ] **Acceso al portal SII** con usuario y clave

### ✅ Entorno Técnico

- [ ] **Python 3.9+** instalado
- [ ] **RypSystems DTE** instalado (`pip install rypsystems-dte`)
- [ ] **Acceso a internet** para conectar con el SII
- [ ] **Permisos de administrador** para configurar certificados

---

## Paso 1: Preparación del Certificado Digital

### 1.1 Verificar el Certificado Digital

Primero, verifica que tu certificado digital esté en el formato correcto:

```bash
# Verificar el certificado (debe mostrar información del certificado)
openssl x509 -in certificado.pem -text -noout

# Verificar la clave privada (debe mostrar información de la clave)
openssl rsa -in clave_privada.key -check

# Verificar que la clave corresponde al certificado
openssl x509 -noout -modulus -in certificado.pem | openssl md5
openssl rsa -noout -modulus -in clave_privada.key | openssl md5
# Los dos hash MD5 deben ser idénticos
```

### 1.2 Convertir Certificado (si es necesario)

Si tu certificado está en formato P12/PFX, conviértelo a PEM:

```bash
# Extraer certificado del archivo P12
openssl pkcs12 -in certificado.p12 -out certificado.pem -clcerts -nokeys

# Extraer clave privada del archivo P12
openssl pkcs12 -in certificado.p12 -out clave_privada.key -nocerts -nodes

# Si tu clave tiene contraseña, eliminarla (opcional)
openssl rsa -in clave_privada.key -out clave_privada_sin_password.key
```

### 1.3 Instalar Certificado en el Sistema

```bash
# Crear directorio para certificados
sudo mkdir -p /etc/ssl/certificados_sii
sudo chmod 700 /etc/ssl/certificados_sii

# Copiar certificado y clave
sudo cp certificado.pem /etc/ssl/certificados_sii/
sudo cp clave_privada.key /etc/ssl/certificados_sii/

# Establecer permisos correctos
sudo chmod 644 /etc/ssl/certificados_sii/certificado.pem
sudo chmod 600 /etc/ssl/certificados_sii/clave_privada.key

# Cambiar propietario (reemplaza 'tu_usuario' con tu usuario)
sudo chown tu_usuario:tu_usuario /etc/ssl/certificados_sii/*
```

### 1.4 Verificar Instalación

```python
# test_certificado.py
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import datetime

def verificar_certificado():
    cert_path = "/etc/ssl/certificados_sii/certificado.pem"

    try:
        # Cargar certificado
        with open(cert_path, 'rb') as f:
            cert_data = f.read()

        cert = x509.load_pem_x509_certificate(cert_data, default_backend())

        # Verificar fechas
        now = datetime.datetime.utcnow()
        print(f"✅ Certificado válido desde: {cert.not_valid_before}")
        print(f"✅ Certificado válido hasta: {cert.not_valid_after}")

        if cert.not_valid_after < now:
            print("❌ ERROR: Certificado expirado")
            return False

        if cert.not_valid_before > now:
            print("❌ ERROR: Certificado aún no válido")
            return False

        # Mostrar información del certificado
        subject = cert.subject
        print(f"✅ Titular: {subject}")

        days_remaining = (cert.not_valid_after - now).days
        print(f"✅ Días restantes: {days_remaining}")

        return True

    except Exception as e:
        print(f"❌ Error verificando certificado: {e}")
        return False

if __name__ == "__main__":
    verificar_certificado()
```

---

## Paso 2: Configuración en el SII

### 2.1 Acceder al Portal SII

1. **Ir al portal del SII**: https://www.sii.cl
2. **Iniciar sesión** con tu RUT y clave
3. **Navegar a**: "Servicios Online" → "Facturación Electrónica"

### 2.2 Registrar tu Certificado en el SII

1. **Ir a**: "Registro de Certificados Digitales"
2. **Subir tu certificado**: Usar el archivo `certificado.pem`
3. **Verificar datos**: Confirmar que el RUT y nombre coincidan
4. **Guardar configuración**

### 2.3 Configurar Empresa para DTE

1. **Ir a**: "Configuración" → "Datos de la Empresa"
2. **Completar información requerida**:
   - Razón social
   - Dirección completa
   - Código de actividad económica
   - Teléfono y email
3. **Configurar DTE**:
   - Activar "Facturación Electrónica"
   - Seleccionar tipos de documentos a usar
   - Configurar rangos de folios

### 2.4 Obtener Información para Configuración

**Anota la siguiente información del portal SII:**

```yaml
# Información que necesitarás para la configuración
empresa:
  rut: "12345678-9"
  razon_social: "Tu Empresa SpA"
  giro: "Desarrollo de software"
  actividad_economica: 620200
  direccion: "Av. Principal 123, Santiago"
  comuna: "Santiago"
  telefono: "+56912345678"
  email: "facturacion@tuempresa.cl"

resolucion:
  numero: 80          # Número de resolución SII
  fecha: "2023-01-15" # Fecha de resolución

certificado:
  rut_titular: "12345678-9"  # RUT del titular del certificado
  fecha_vencimiento: "2024-12-31"
```

---

## Paso 3: Configuración de la Librería

### 3.1 Crear Archivo de Configuración

Crear `config_certificacion.yaml`:

```yaml
# config_certificacion.yaml - Configuración para Certificación SII

# IMPORTANTE: Este es el ambiente de CERTIFICACIÓN, NO producción
environment: "certification"
debug: true

# Configuración del SII para CERTIFICACIÓN
sii:
  environment: "certificacion"  # ⚠️ CRÍTICO: Debe ser "certificacion"

  # Datos de autenticación
  authentication:
    certificate_path: "/etc/ssl/certificados_sii/certificado.pem"
    private_key_path: "/etc/ssl/certificados_sii/clave_privada.key"
    rut_contribuyente: "12345678-9"           # ⚠️ CAMBIAR por tu RUT
    rut_empresa: "12345678-9"                 # ⚠️ CAMBIAR por tu RUT
    resolucion_numero: 80                     # ⚠️ CAMBIAR por tu número de resolución
    resolucion_fecha: "2023-01-15"           # ⚠️ CAMBIAR por tu fecha de resolución

  # Configuración de conexión para certificación
  connection_timeout: 60
  read_timeout: 120
  max_retries: 5
  retry_delay: 2.0
  verify_ssl: true

  # Rate limiting más permisivo para pruebas
  rate_limit:
    enabled: true
    requests_per_minute: 30
    requests_per_hour: 500

  # Logging detallado para debugging
  log_requests: true
  log_responses: true
  log_sensitive_data: false  # ⚠️ NUNCA cambiar a true en producción

# Configuración de logging para certificación
logging:
  level: "DEBUG"
  format: "json"
  output: "both"  # console y file
  file_path: "/var/log/rypsystems_dte/certificacion.log"
  console_output: true

# Features habilitados para certificación
features:
  strict_validation: true
  enhanced_logging: true
  beta_features: false
  performance_monitoring: true

# Datos de la empresa (completar con tus datos reales)
empresa:
  rut: "12345678-9"                    # ⚠️ CAMBIAR
  razon_social: "Tu Empresa SpA"       # ⚠️ CAMBIAR
  giro: "Desarrollo de software"       # ⚠️ CAMBIAR
  actividad_economica: 620200          # ⚠️ CAMBIAR
  direccion:
    calle: "Av. Principal 123"         # ⚠️ CAMBIAR
    comuna: "Santiago"                 # ⚠️ CAMBIAR
    ciudad: "Santiago"                 # ⚠️ CAMBIAR
  contacto:
    telefono: "+56912345678"           # ⚠️ CAMBIAR
    email: "facturacion@tuempresa.cl"  # ⚠️ CAMBIAR
```

### 3.2 Verificar Configuración

```python
# test_configuracion.py
from rypsystems_dte.config import ConfigManager

def verificar_configuracion():
    print("🔧 Verificando configuración...")

    try:
        # Cargar configuración
        manager = ConfigManager()
        manager.load_from_file("config_certificacion.yaml")

        # Verificar configuración básica
        environment = manager.get("environment")
        sii_env = manager.get("sii.environment")

        print(f"✅ Environment: {environment}")
        print(f"✅ SII Environment: {sii_env}")

        # Verificar que estamos en certificación
        if sii_env != "certificacion":
            print("❌ ERROR: Debe estar en ambiente de certificación")
            return False

        # Verificar certificado
        cert_path = manager.get("sii.authentication.certificate_path")
        key_path = manager.get("sii.authentication.private_key_path")

        import os
        if not os.path.exists(cert_path):
            print(f"❌ ERROR: Certificado no encontrado: {cert_path}")
            return False

        if not os.path.exists(key_path):
            print(f"❌ ERROR: Clave privada no encontrada: {key_path}")
            return False

        print(f"✅ Certificado encontrado: {cert_path}")
        print(f"✅ Clave privada encontrada: {key_path}")

        # Verificar datos de empresa
        rut = manager.get("sii.authentication.rut_contribuyente")
        resolucion = manager.get("sii.authentication.resolucion_numero")

        print(f"✅ RUT Contribuyente: {rut}")
        print(f"✅ Resolución: {resolucion}")

        return True

    except Exception as e:
        print(f"❌ ERROR en configuración: {e}")
        return False

if __name__ == "__main__":
    if verificar_configuracion():
        print("\n🎉 Configuración válida - Listo para continuar")
    else:
        print("\n❌ Configuración inválida - Revisar errores")
```

### 3.3 Configurar Variables de Entorno (Alternativo)

```bash
# .env.certificacion
export RYPSYSTEMS_DTE_ENVIRONMENT=certification
export RYPSYSTEMS_DTE_SII_ENVIRONMENT=certificacion
export RYPSYSTEMS_DTE_SII_CERTIFICATE_PATH=/etc/ssl/certificados_sii/certificado.pem
export RYPSYSTEMS_DTE_SII_PRIVATE_KEY_PATH=/etc/ssl/certificados_sii/clave_privada.key
export RYPSYSTEMS_DTE_SII_RUT_CONTRIBUYENTE=12345678-9
export RYPSYSTEMS_DTE_SII_RESOLUCION_NUMERO=80
export RYPSYSTEMS_DTE_SII_RESOLUCION_FECHA=2023-01-15
export RYPSYSTEMS_DTE_LOG_LEVEL=DEBUG

# Cargar variables
source .env.certificacion
```

---

## Paso 4: Pruebas de Conectividad

### 4.1 Test de Conectividad Básica

```python
# test_conectividad.py
import requests
from rypsystems_dte.config import SiiConfig

def test_conectividad_sii():
    print("🌐 Probando conectividad con SII...")

    # Configuración para certificación
    sii_config = SiiConfig.for_certification()

    # URLs del SII certificación
    urls_test = [
        "https://maullin.sii.cl/DTEWS/GetTokenFromSeed.jws",
        "https://maullin.sii.cl/DTEWS/QueryEstDte.jws",
        "https://maullin.sii.cl/DTEWS/UploadXML.jws"
    ]

    for url in urls_test:
        try:
            print(f"  Probando: {url}")
            response = requests.get(url, timeout=30, verify=True)
            print(f"  ✅ Status: {response.status_code}")

        except requests.exceptions.SSLError as e:
            print(f"  ❌ Error SSL: {e}")
        except requests.exceptions.Timeout:
            print(f"  ⚠️ Timeout - SII puede estar lento")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    print("✅ Test de conectividad completado")

if __name__ == "__main__":
    test_conectividad_sii()
```

### 4.2 Test de Autenticación SII

```python
# test_autenticacion.py
from rypsystems_dte.sii.integration import SiiClient
from rypsystems_dte.config import ConfigManager

def test_autenticacion():
    print("🔐 Probando autenticación con SII...")

    try:
        # Cargar configuración
        config = ConfigManager()
        config.load_from_file("config_certificacion.yaml")

        # Crear cliente SII
        client = SiiClient()

        # Intentar obtener token
        print("  Obteniendo seed del SII...")
        seed = client.get_seed()
        print(f"  ✅ Seed obtenido: {seed[:20]}...")

        print("  Firmando seed con certificado...")
        token = client.get_token(seed)
        print(f"  ✅ Token obtenido: {token[:20]}...")

        print("  Validando token...")
        is_valid = client.validate_token(token)
        print(f"  ✅ Token válido: {is_valid}")

        if is_valid:
            print("\n🎉 ¡Autenticación exitosa con el SII!")
            return True
        else:
            print("\n❌ Token inválido")
            return False

    except Exception as e:
        print(f"❌ Error en autenticación: {e}")
        return False

if __name__ == "__main__":
    test_autenticacion()
```

---

## Paso 5: Creación de Documentos de Prueba

### 5.1 Crear Primera Factura de Prueba

```python
# crear_factura_prueba.py
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.config import ConfigManager
import datetime

def crear_factura_certificacion():
    print("📄 Creando factura de certificación...")

    try:
        # Cargar configuración
        config = ConfigManager()
        config.load_from_file("config_certificacion.yaml")

        # Crear factory
        factory = DTEFactory()

        # Datos de la empresa (emisor) - CAMBIAR POR TUS DATOS REALES
        emisor = Contribuyente(
            rut="12345678-9",              # ⚠️ CAMBIAR por tu RUT
            nombre="Tu Empresa SpA"        # ⚠️ CAMBIAR por tu razón social
        )

        # Cliente de prueba (receptor) - USAR ESTOS DATOS PARA CERTIFICACIÓN
        receptor = Contribuyente(
            rut="66666666-6",              # RUT genérico para pruebas
            nombre="Cliente de Prueba"
        )

        # Fecha actual
        fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")

        # Crear factura de prueba
        factura = factory.create_factura_afecta(
            emisor=emisor,
            receptor=receptor,
            folio=1,                       # Comenzar con folio 1 para certificación
            fecha_emision=fecha_hoy,
            detalle=[
                {
                    "NmbItem": "Producto de Prueba Certificación",
                    "QtyItem": 1,
                    "PrcItem": 1000,
                    "UnmdItem": "UN"
                },
                {
                    "NmbItem": "Servicio de Prueba Certificación",
                    "QtyItem": 2,
                    "PrcItem": 2500,
                    "UnmdItem": "HR"
                }
            ]
        )

        # Obtener XML
        xml_content = factura.save_xml()

        # Guardar XML para revisión
        with open(f"factura_prueba_{factura.get_id()}.xml", "w", encoding="utf-8") as f:
            f.write(xml_content)

        print(f"✅ Factura creada: {factura.get_id()}")
        print(f"✅ XML guardado: factura_prueba_{factura.get_id()}.xml")
        print(f"✅ Total: $6,000")

        # Mostrar resumen
        datos = factura.get_datos()
        print("\n📋 Resumen del documento:")
        print(f"  Tipo: {datos['Documento']['Encabezado']['IdDoc']['TipoDTE']}")
        print(f"  Folio: {datos['Documento']['Encabezado']['IdDoc']['Folio']}")
        print(f"  Fecha: {datos['Documento']['Encabezado']['IdDoc']['FchEmis']}")
        print(f"  Emisor: {datos['Documento']['Encabezado']['Emisor']['RznSoc']}")
        print(f"  Receptor: {datos['Documento']['Encabezado']['Receptor']['RznSoc']}")
        print(f"  Total: ${datos['Documento']['Encabezado']['Totales']['MntTotal']:,}")

        return factura, xml_content

    except Exception as e:
        print(f"❌ Error creando factura: {e}")
        return None, None

if __name__ == "__main__":
    factura, xml = crear_factura_certificacion()
    if factura:
        print("\n🎉 Factura de prueba creada exitosamente")
    else:
        print("\n❌ Error creando factura de prueba")
```

### 5.2 Validar XML Generado

```python
# validar_xml.py
import xml.etree.ElementTree as ET
from lxml import etree

def validar_xml_dte(xml_file):
    print(f"✅ Validando XML: {xml_file}")

    try:
        # Validar que es XML bien formado
        with open(xml_file, 'r', encoding='utf-8') as f:
            xml_content = f.read()

        # Parse XML
        root = ET.fromstring(xml_content)
        print("✅ XML bien formado")

        # Verificar estructura DTE básica
        dte_elements = root.findall('.//DTE')
        if not dte_elements:
            print("❌ No se encontró elemento DTE")
            return False

        print(f"✅ Encontrados {len(dte_elements)} elementos DTE")

        # Verificar elementos críticos
        documento = root.find('.//Documento')
        if documento is None:
            print("❌ No se encontró elemento Documento")
            return False

        print("✅ Elemento Documento encontrado")

        # Verificar encabezado
        encabezado = documento.find('Encabezado')
        if encabezado is None:
            print("❌ No se encontró Encabezado")
            return False

        # Extraer información clave
        id_doc = encabezado.find('IdDoc')
        if id_doc is not None:
            tipo_dte = id_doc.find('TipoDTE').text if id_doc.find('TipoDTE') is not None else "N/A"
            folio = id_doc.find('Folio').text if id_doc.find('Folio') is not None else "N/A"
            fecha = id_doc.find('FchEmis').text if id_doc.find('FchEmis') is not None else "N/A"

            print(f"✅ Tipo DTE: {tipo_dte}")
            print(f"✅ Folio: {folio}")
            print(f"✅ Fecha: {fecha}")

        # Verificar totales
        totales = encabezado.find('Totales')
        if totales is not None:
            mnt_total = totales.find('MntTotal').text if totales.find('MntTotal') is not None else "N/A"
            print(f"✅ Total: ${mnt_total}")

        # Verificar TED (Timbre Electrónico)
        ted = root.find('.//TED')
        if ted is not None:
            print("✅ TED (Timbre Electrónico) presente")
        else:
            print("⚠️ TED no encontrado - verificar configuración")

        print("\n🎉 Validación XML exitosa")
        return True

    except ET.ParseError as e:
        print(f"❌ Error parseando XML: {e}")
        return False
    except Exception as e:
        print(f"❌ Error validando XML: {e}")
        return False

# Validar archivo creado anteriormente
if __name__ == "__main__":
    import glob
    xml_files = glob.glob("factura_prueba_*.xml")

    if xml_files:
        for xml_file in xml_files:
            validar_xml_dte(xml_file)
    else:
        print("❌ No se encontraron archivos XML de prueba")
```

---

## Paso 6: Envío al SII y Validación

### 6.1 Enviar Documento al SII (Certificación)

```python
# enviar_al_sii.py
from rypsystems_dte.sii.integration import SiiClient
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.config import ConfigManager
import datetime
import time

def enviar_factura_certificacion():
    print("📤 Enviando factura al SII (Certificación)...")

    try:
        # Cargar configuración
        config = ConfigManager()
        config.load_from_file("config_certificacion.yaml")

        # Crear cliente SII
        sii_client = SiiClient()

        # Crear factura (igual que antes)
        factory = DTEFactory()

        emisor = Contribuyente("12345678-9", "Tu Empresa SpA")  # ⚠️ CAMBIAR
        receptor = Contribuyente("66666666-6", "Cliente de Prueba")

        fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")

        factura = factory.create_factura_afecta(
            emisor=emisor,
            receptor=receptor,
            folio=1,
            fecha_emision=fecha_hoy,
            detalle=[{
                "NmbItem": "Producto Certificación SII",
                "QtyItem": 1,
                "PrcItem": 1000
            }]
        )

        print(f"✅ Factura creada: {factura.get_id()}")

        # Enviar al SII
        print("📡 Enviando al SII...")
        resultado = sii_client.submit_document(
            document=factura,
            company_rut="12345678-9"  # ⚠️ CAMBIAR por tu RUT
        )

        print(f"✅ Envío exitoso!")
        print(f"  Track ID: {resultado.track_id}")
        print(f"  Estado: {resultado.status}")

        # Esperar un momento y consultar estado
        print("\n⏳ Esperando 30 segundos para consultar estado...")
        time.sleep(30)

        print("📋 Consultando estado en el SII...")
        estado = sii_client.get_document_status(
            track_id=resultado.track_id,
            company_rut="12345678-9"  # ⚠️ CAMBIAR
        )

        print(f"✅ Estado actual: {estado.status}")
        print(f"  Detalles: {estado.details}")

        if estado.status == "ACEPTADO":
            print("\n🎉 ¡Documento ACEPTADO por el SII!")
        elif estado.status == "RECHAZADO":
            print("\n❌ Documento RECHAZADO por el SII")
            print(f"   Razón: {estado.error_message}")
        else:
            print(f"\n⏳ Documento en proceso: {estado.status}")

        return resultado

    except Exception as e:
        print(f"❌ Error enviando al SII: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    resultado = enviar_factura_certificacion()
    if resultado:
        print(f"\n📊 Resultado del envío:")
        print(f"  Track ID: {resultado.track_id}")
        print(f"  Guardar este Track ID para consultas futuras")
```

### 6.2 Consultar Estado de Documentos

```python
# consultar_estado.py
from rypsystems_dte.sii.integration import SiiClient
from rypsystems_dte.config import ConfigManager

def consultar_estado_documento(track_id, rut_empresa):
    print(f"📋 Consultando estado del documento...")
    print(f"  Track ID: {track_id}")
    print(f"  RUT Empresa: {rut_empresa}")

    try:
        # Cargar configuración
        config = ConfigManager()
        config.load_from_file("config_certificacion.yaml")

        # Crear cliente SII
        sii_client = SiiClient()

        # Consultar estado
        estado = sii_client.get_document_status(
            track_id=track_id,
            company_rut=rut_empresa
        )

        print(f"\n📊 Estado del documento:")
        print(f"  Estado: {estado.status}")
        print(f"  Descripción: {estado.details}")

        if estado.status == "ACEPTADO":
            print("✅ Documento ACEPTADO - Certificación exitosa para este documento")
        elif estado.status == "RECHAZADO":
            print("❌ Documento RECHAZADO")
            print(f"   Error: {estado.error_message}")
            print("   Revisar y corregir errores antes de reenviar")
        elif estado.status == "PENDIENTE":
            print("⏳ Documento PENDIENTE - El SII aún está procesando")
        else:
            print(f"❓ Estado desconocido: {estado.status}")

        return estado

    except Exception as e:
        print(f"❌ Error consultando estado: {e}")
        return None

# Consultar por Track ID específico
if __name__ == "__main__":
    # ⚠️ CAMBIAR por tu Track ID real obtenido del envío
    track_id = input("Ingresa el Track ID: ").strip()
    rut_empresa = input("Ingresa tu RUT (ej: 12345678-9): ").strip()

    if track_id and rut_empresa:
        consultar_estado_documento(track_id, rut_empresa)
    else:
        print("❌ Debes proporcionar Track ID y RUT")
```

---

## Paso 7: Proceso de Certificación

### 7.1 Set de Pruebas de Certificación

El SII requiere que pases un conjunto específico de pruebas. Aquí está el script para generar todos los documentos requeridos:

```python
# certificacion_completa.py
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente
from rypsystems_dte.sii.integration import SiiClient
from rypsystems_dte.config import ConfigManager
import datetime
import time

class CertificacionSII:
    def __init__(self):
        self.config = ConfigManager()
        self.config.load_from_file("config_certificacion.yaml")
        self.factory = DTEFactory()
        self.sii_client = SiiClient()

        # ⚠️ CAMBIAR por tus datos reales
        self.emisor = Contribuyente("12345678-9", "Tu Empresa SpA")
        self.rut_empresa = "12345678-9"

        # Clientes de prueba para certificación
        self.clientes_prueba = [
            Contribuyente("66666666-6", "Cliente Prueba 1"),
            Contribuyente("77777777-7", "Cliente Prueba 2"),
            Contribuyente("88888888-8", "Cliente Prueba 3"),
        ]

        self.resultados = []

    def crear_facturas_prueba(self):
        """Crear set de facturas para certificación"""
        print("📄 Creando facturas de prueba para certificación...")

        fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")

        # Factura simple
        factura1 = self.factory.create_factura_afecta(
            emisor=self.emisor,
            receptor=self.clientes_prueba[0],
            folio=1,
            fecha_emision=fecha_hoy,
            detalle=[{
                "NmbItem": "Producto Simple Certificación",
                "QtyItem": 1,
                "PrcItem": 10000
            }]
        )

        # Factura con múltiples ítems
        factura2 = self.factory.create_factura_afecta(
            emisor=self.emisor,
            receptor=self.clientes_prueba[1],
            folio=2,
            fecha_emision=fecha_hoy,
            detalle=[
                {
                    "NmbItem": "Producto A",
                    "QtyItem": 2,
                    "PrcItem": 5000
                },
                {
                    "NmbItem": "Producto B",
                    "QtyItem": 1,
                    "PrcItem": 15000
                },
                {
                    "NmbItem": "Servicio C",
                    "QtyItem": 3,
                    "PrcItem": 8000,
                    "UnmdItem": "HR"
                }
            ]
        )

        # Factura con descuentos
        factura3 = self.factory.create_factura_afecta(
            emisor=self.emisor,
            receptor=self.clientes_prueba[2],
            folio=3,
            fecha_emision=fecha_hoy,
            detalle=[{
                "NmbItem": "Producto con Descuento",
                "QtyItem": 5,
                "PrcItem": 20000,
                "DescuentoPct": 10  # 10% de descuento
            }]
        )

        return [factura1, factura2, factura3]

    def crear_boletas_prueba(self):
        """Crear boletas para certificación"""
        print("📄 Creando boletas de prueba para certificación...")

        fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")

        # Boleta simple
        boleta1 = self.factory.create_boleta_afecta(
            emisor=self.emisor,
            receptor=Contribuyente("66666666-6", "Consumidor Final"),
            folio=1001,
            fecha_emision=fecha_hoy,
            detalle=[{
                "NmbItem": "Venta al Detalle",
                "QtyItem": 1,
                "PrcItem": 5000
            }]
        )

        # Boleta con múltiples productos
        boleta2 = self.factory.create_boleta_afecta(
            emisor=self.emisor,
            receptor=Contribuyente("66666666-6", "Consumidor Final"),
            folio=1002,
            fecha_emision=fecha_hoy,
            detalle=[
                {
                    "NmbItem": "Producto Retail A",
                    "QtyItem": 2,
                    "PrcItem": 2500
                },
                {
                    "NmbItem": "Producto Retail B",
                    "QtyItem": 1,
                    "PrcItem": 7500
                }
            ]
        )

        return [boleta1, boleta2]

    def crear_notas_credito_prueba(self):
        """Crear notas de crédito para certificación"""
        print("📄 Creando notas de crédito de prueba...")

        fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")

        # Nota de crédito por anulación
        nota_credito1 = self.factory.create_nota_credito(
            emisor=self.emisor,
            receptor=self.clientes_prueba[0],
            folio=2001,
            fecha_emision=fecha_hoy,
            detalle=[{
                "NmbItem": "Anulación Factura 1",
                "QtyItem": 1,
                "PrcItem": -10000  # Negativo para crédito
            }],
            documento_referencia={
                "TpoDocRef": 33,    # Factura
                "FolioRef": 1,      # Folio de la factura original
                "FchRef": fecha_hoy,
                "CodRef": 1,        # Anula documento de referencia
                "RazonRef": "Anulación por error en facturación"
            }
        )

        # Nota de crédito por descuento
        nota_credito2 = self.factory.create_nota_credito(
            emisor=self.emisor,
            receptor=self.clientes_prueba[1],
            folio=2002,
            fecha_emision=fecha_hoy,
            detalle=[{
                "NmbItem": "Descuento Cliente Frecuente",
                "QtyItem": 1,
                "PrcItem": -5000
            }],
            documento_referencia={
                "TpoDocRef": 33,
                "FolioRef": 2,
                "FchRef": fecha_hoy,
                "CodRef": 3,        # Descuento
                "RazonRef": "Descuento por cliente frecuente"
            }
        )

        return [nota_credito1, nota_credito2]

    def enviar_documentos(self, documentos, tipo_doc):
        """Enviar documentos al SII"""
        print(f"\n📤 Enviando {tipo_doc} al SII...")

        for i, documento in enumerate(documentos, 1):
            try:
                print(f"  Enviando {tipo_doc} {i}: {documento.get_id()}")

                resultado = self.sii_client.submit_document(
                    document=documento,
                    company_rut=self.rut_empresa
                )

                self.resultados.append({
                    "tipo": tipo_doc,
                    "documento_id": documento.get_id(),
                    "track_id": resultado.track_id,
                    "status": resultado.status,
                    "timestamp": datetime.datetime.now().isoformat()
                })

                print(f"    ✅ Enviado - Track ID: {resultado.track_id}")

                # Pausa entre envíos para evitar rate limiting
                time.sleep(5)

            except Exception as e:
                print(f"    ❌ Error enviando: {e}")
                self.resultados.append({
                    "tipo": tipo_doc,
                    "documento_id": documento.get_id(),
                    "error": str(e),
                    "timestamp": datetime.datetime.now().isoformat()
                })

    def ejecutar_certificacion_completa(self):
        """Ejecutar proceso completo de certificación"""
        print("🏛️ Iniciando proceso completo de certificación SII")
        print("=" * 60)

        try:
            # 1. Crear documentos de prueba
            facturas = self.crear_facturas_prueba()
            boletas = self.crear_boletas_prueba()
            notas_credito = self.crear_notas_credito_prueba()

            # 2. Enviar documentos al SII
            self.enviar_documentos(facturas, "Factura")
            self.enviar_documentos(boletas, "Boleta")
            self.enviar_documentos(notas_credito, "Nota de Crédito")

            # 3. Guardar resultados
            self.guardar_resultados()

            # 4. Mostrar resumen
            self.mostrar_resumen()

            print("\n🎉 Proceso de certificación enviado al SII")
            print("⏳ Espera 24-48 horas para que el SII procese todos los documentos")
            print("📋 Consulta periódicamente el estado con consultar_estado.py")

        except Exception as e:
            print(f"❌ Error en certificación: {e}")
            import traceback
            traceback.print_exc()

    def guardar_resultados(self):
        """Guardar resultados en archivo"""
        import json

        with open("resultados_certificacion.json", "w") as f:
            json.dump(self.resultados, f, indent=2, ensure_ascii=False)

        print(f"✅ Resultados guardados en: resultados_certificacion.json")

    def mostrar_resumen(self):
        """Mostrar resumen de envíos"""
        print("\n📊 RESUMEN DE CERTIFICACIÓN")
        print("=" * 40)

        tipos = {}
        for resultado in self.resultados:
            tipo = resultado["tipo"]
            if tipo not in tipos:
                tipos[tipo] = {"enviados": 0, "errores": 0}

            if "error" in resultado:
                tipos[tipo]["errores"] += 1
            else:
                tipos[tipo]["enviados"] += 1

        for tipo, stats in tipos.items():
            print(f"{tipo}:")
            print(f"  ✅ Enviados: {stats['enviados']}")
            print(f"  ❌ Errores: {stats['errores']}")

        print(f"\n📝 Track IDs para seguimiento:")
        for resultado in self.resultados:
            if "track_id" in resultado:
                print(f"  {resultado['documento_id']}: {resultado['track_id']}")

if __name__ == "__main__":
    certificacion = CertificacionSII()
    certificacion.ejecutar_certificacion_completa()
```

### 7.2 Monitoreo del Proceso de Certificación

```python
# monitoreo_certificacion.py
import json
import time
from rypsystems_dte.sii.integration import SiiClient
from rypsystems_dte.config import ConfigManager

def monitorear_certificacion():
    print("📊 Monitoreando proceso de certificación...")

    try:
        # Cargar resultados de certificación
        with open("resultados_certificacion.json", "r") as f:
            resultados = json.load(f)

        # Configurar cliente SII
        config = ConfigManager()
        config.load_from_file("config_certificacion.yaml")
        sii_client = SiiClient()

        rut_empresa = "12345678-9"  # ⚠️ CAMBIAR por tu RUT

        print(f"Monitoreando {len(resultados)} documentos...")

        estados_actualizados = []

        for resultado in resultados:
            if "track_id" not in resultado:
                continue

            track_id = resultado["track_id"]
            documento_id = resultado["documento_id"]

            try:
                print(f"  Consultando: {documento_id}")

                estado = sii_client.get_document_status(
                    track_id=track_id,
                    company_rut=rut_empresa
                )

                estado_info = {
                    "documento_id": documento_id,
                    "track_id": track_id,
                    "status": estado.status,
                    "details": estado.details,
                    "last_check": time.time()
                }

                if estado.status == "ACEPTADO":
                    print(f"    ✅ ACEPTADO")
                elif estado.status == "RECHAZADO":
                    print(f"    ❌ RECHAZADO: {estado.error_message}")
                else:
                    print(f"    ⏳ {estado.status}")

                estados_actualizados.append(estado_info)

                # Pausa entre consultas
                time.sleep(2)

            except Exception as e:
                print(f"    ❌ Error consultando: {e}")

        # Guardar estados actualizados
        with open("estados_certificacion.json", "w") as f:
            json.dump(estados_actualizados, f, indent=2, ensure_ascii=False)

        # Mostrar resumen
        aceptados = len([e for e in estados_actualizados if e["status"] == "ACEPTADO"])
        rechazados = len([e for e in estados_actualizados if e["status"] == "RECHAZADO"])
        pendientes = len(estados_actualizados) - aceptados - rechazados

        print(f"\n📊 RESUMEN DE ESTADOS:")
        print(f"  ✅ Aceptados: {aceptados}")
        print(f"  ❌ Rechazados: {rechazados}")
        print(f"  ⏳ Pendientes: {pendientes}")

        if aceptados == len(estados_actualizados):
            print("\n🎉 ¡TODOS LOS DOCUMENTOS ACEPTADOS!")
            print("¡Tu certificación está completa!")

    except FileNotFoundError:
        print("❌ No se encontró archivo de resultados de certificación")
        print("   Ejecuta certificacion_completa.py primero")
    except Exception as e:
        print(f"❌ Error monitoreando: {e}")

if __name__ == "__main__":
    monitorear_certificacion()
```

---

## Paso 8: Migración a Producción

### 8.1 Configuración de Producción

Una vez que tu certificación sea aprobada por el SII, configura el ambiente de producción:

```yaml
# config_produccion.yaml
environment: "production"
debug: false

# Configuración SII PRODUCCIÓN
sii:
  environment: "produccion"  # ⚠️ CRÍTICO: Cambiar a producción

  authentication:
    certificate_path: "/etc/ssl/certificados_sii/certificado_produccion.pem"
    private_key_path: "/etc/ssl/certificados_sii/clave_privada_produccion.key"
    rut_contribuyente: "12345678-9"     # ⚠️ CAMBIAR
    rut_empresa: "12345678-9"           # ⚠️ CAMBIAR
    resolucion_numero: 80               # ⚠️ Tu número de resolución
    resolucion_fecha: "2023-01-15"     # ⚠️ Tu fecha de resolución

  # Configuración optimizada para producción
  connection_timeout: 30
  read_timeout: 60
  max_retries: 3
  retry_delay: 1.0
  verify_ssl: true

  # Rate limiting producción
  rate_limit:
    enabled: true
    requests_per_minute: 100
    requests_per_hour: 2000

  # Sin logging sensible en producción
  log_requests: true
  log_responses: false
  log_sensitive_data: false

# Logging producción
logging:
  level: "WARNING"
  format: "json"
  output: "file"
  file_path: "/var/log/rypsystems_dte/produccion.log"
  console_output: false

# Features producción
features:
  strict_validation: true
  enhanced_logging: false
  beta_features: false
  production_optimizations: true

# Seguridad producción
security:
  validate_certificates: true
  token_expiry: 3600
```

### 8.2 Test de Producción

```python
# test_produccion.py
from rypsystems_dte.config import ConfigManager, SiiConfig
from rypsystems_dte.sii.integration import SiiClient

def test_configuracion_produccion():
    print("🏭 Probando configuración de producción...")

    try:
        # Cargar configuración de producción
        config = ConfigManager()
        config.load_from_file("config_produccion.yaml")

        # Verificar que estamos en producción
        sii_env = config.get("sii.environment")
        if sii_env != "produccion":
            print("❌ ERROR: No está configurado para producción")
            return False

        print("✅ Configuración de producción cargada")

        # Verificar conectividad con SII producción
        sii_config = SiiConfig.for_production()
        print(f"✅ Endpoint producción: {sii_config.endpoints.get_token.url}")

        # Test de autenticación (sin crear documentos)
        client = SiiClient()

        print("🔐 Probando autenticación en producción...")
        seed = client.get_seed()
        token = client.get_token(seed)

        if token:
            print("✅ Autenticación exitosa en PRODUCCIÓN")
            print("🚨 ATENCIÓN: Ya estás conectado a producción")
            print("📄 Los próximos documentos serán REALES y VÁLIDOS")
            return True
        else:
            print("❌ Error en autenticación de producción")
            return False

    except Exception as e:
        print(f"❌ Error en test de producción: {e}")
        return False

if __name__ == "__main__":
    if test_configuracion_produccion():
        print("\n🎉 ¡Listo para producción!")
        print("\n⚠️  IMPORTANTE:")
        print("   - Todos los documentos ahora serán REALES")
        print("   - Tendrán valor legal y tributario")
        print("   - Usar folios secuenciales reales")
        print("   - Datos de clientes deben ser reales")
    else:
        print("\n❌ Configuración de producción fallida")
```

---

## Solución de Problemas

### Problemas Comunes y Soluciones

#### 1. Error de Certificado

**Síntomas:**
```
SSL Certificate verification failed
```

**Solución:**
```bash
# Verificar certificado
openssl x509 -in certificado.pem -text -noout

# Verificar fechas de validez
openssl x509 -in certificado.pem -dates -noout

# Si el certificado está expirado, obtener uno nuevo del proveedor
```

#### 2. Error de Autenticación SII

**Síntomas:**
```
Error getting token from SII
```

**Solución:**
```python
# Verificar configuración
from rypsystems_dte.config import get_config

rut = get_config("sii.authentication.rut_contribuyente")
print(f"RUT configurado: {rut}")

# Verificar que el RUT esté registrado en el SII
# Verificar que el certificado corresponda al RUT
```

#### 3. Documento Rechazado por SII

**Síntomas:**
```
Document status: RECHAZADO
```

**Solución:**
```python
# Consultar detalles del rechazo
estado = sii_client.get_document_status(track_id, rut_empresa)
print(f"Error: {estado.error_message}")

# Errores comunes:
# - RUT inválido
# - Folio duplicado
# - Datos faltantes
# - Montos incorrectos
```

#### 4. Error de Conectividad

**Síntomas:**
```
Connection timeout to SII
```

**Solución:**
```bash
# Verificar conectividad
curl -I https://maullin.sii.cl  # Para certificación
curl -I https://palena.sii.cl   # Para producción

# Verificar DNS
nslookup maullin.sii.cl
nslookup palena.sii.cl

# Verificar firewall (puertos 80 y 443)
```

### Script de Diagnóstico Completo

```python
# diagnostico_completo.py
import os
import requests
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from rypsystems_dte.config import ConfigManager
from rypsystems_dte.sii.integration import SiiClient
import datetime

def diagnostico_completo():
    print("🔍 DIAGNÓSTICO COMPLETO DEL SISTEMA")
    print("=" * 50)

    # 1. Verificar instalación
    print("\n1. Verificando instalación...")
    try:
        import rypsystems_dte
        print("✅ RypSystems DTE instalado correctamente")
    except ImportError:
        print("❌ RypSystems DTE no instalado")
        return

    # 2. Verificar configuración
    print("\n2. Verificando configuración...")
    try:
        config = ConfigManager()
        if os.path.exists("config_certificacion.yaml"):
            config.load_from_file("config_certificacion.yaml")
            print("✅ Configuración cargada")
        else:
            print("❌ Archivo de configuración no encontrado")
            return
    except Exception as e:
        print(f"❌ Error en configuración: {e}")
        return

    # 3. Verificar certificados
    print("\n3. Verificando certificados...")
    cert_path = config.get("sii.authentication.certificate_path")
    key_path = config.get("sii.authentication.private_key_path")

    if not os.path.exists(cert_path):
        print(f"❌ Certificado no encontrado: {cert_path}")
        return

    if not os.path.exists(key_path):
        print(f"❌ Clave privada no encontrada: {key_path}")
        return

    try:
        with open(cert_path, 'rb') as f:
            cert_data = f.read()
        cert = x509.load_pem_x509_certificate(cert_data, default_backend())

        now = datetime.datetime.utcnow()
        days_remaining = (cert.not_valid_after - now).days

        if days_remaining < 0:
            print("❌ Certificado expirado")
            return
        elif days_remaining < 30:
            print(f"⚠️ Certificado expira en {days_remaining} días")
        else:
            print(f"✅ Certificado válido ({days_remaining} días restantes)")

    except Exception as e:
        print(f"❌ Error verificando certificado: {e}")
        return

    # 4. Verificar conectividad SII
    print("\n4. Verificando conectividad SII...")
    sii_env = config.get("sii.environment")

    if sii_env == "certificacion":
        url = "https://maullin.sii.cl"
    else:
        url = "https://palena.sii.cl"

    try:
        response = requests.get(url, timeout=10)
        print(f"✅ Conectividad SII OK ({response.status_code})")
    except Exception as e:
        print(f"❌ Error conectividad SII: {e}")
        return

    # 5. Test de autenticación
    print("\n5. Probando autenticación...")
    try:
        client = SiiClient()
        seed = client.get_seed()
        token = client.get_token(seed)

        if token:
            print("✅ Autenticación exitosa")
        else:
            print("❌ Error en autenticación")
            return

    except Exception as e:
        print(f"❌ Error en autenticación: {e}")
        return

    # 6. Verificar permisos
    print("\n6. Verificando permisos de archivos...")
    cert_stat = os.stat(cert_path)
    key_stat = os.stat(key_path)

    cert_perms = oct(cert_stat.st_mode)[-3:]
    key_perms = oct(key_stat.st_mode)[-3:]

    print(f"  Certificado: {cert_perms} {'✅' if cert_perms == '644' else '⚠️'}")
    print(f"  Clave privada: {key_perms} {'✅' if key_perms == '600' else '⚠️'}")

    print("\n🎉 DIAGNÓSTICO COMPLETADO")
    print("✅ Sistema listo para certificación SII")

if __name__ == "__main__":
    diagnostico_completo()
```

---

## ✅ Checklist Final de Certificación

### Antes de Enviar Documentos al SII:

- [ ] Certificado digital instalado y válido
- [ ] Configuración de certificación creada
- [ ] Conectividad con SII verificada
- [ ] Autenticación funcionando
- [ ] Datos de empresa configurados correctamente
- [ ] Número y fecha de resolución correctos

### Durante el Proceso de Certificación:

- [ ] Set completo de documentos enviado (facturas, boletas, notas de crédito)
- [ ] Track IDs guardados para seguimiento
- [ ] Estados consultados periódicamente
- [ ] Errores corregidos y documentos reenviados

### Para Migrar a Producción:

- [ ] Certificación SII aprobada oficialmente
- [ ] Configuración de producción creada
- [ ] Certificados de producción instalados
- [ ] Test de conectividad en producción exitoso
- [ ] Folios reales configurados
- [ ] Proceso de respaldo implementado

---

**🎉 ¡Felicitaciones!**

Si has completado todos estos pasos exitosamente, tu sistema RypSystems DTE está listo para generar documentos tributarios electrónicos válidos en Chile. Recuerda mantener tus certificados actualizados y monitorear regularmente el estado de tus envíos al SII.

Para soporte adicional, consulta la documentación técnica completa en los demás archivos de esta carpeta `docs/`.