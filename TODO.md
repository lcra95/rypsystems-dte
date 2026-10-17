# 📋 LibreDTE Translation Project - TODO List

## 🔍 **Estado actual (revisado 2026-10-17)**

La revisión de octubre de 2026 encontró que la firma, el timbraje, el sobre de
envío y la comunicación con el SII estaban simulados (marcaban el documento
como firmado sin firmar). Se reimplementaron siguiendo LibreDTE PHP y se
verificaron contra artefactos reales del SII:

### ✅ **Implementado y verificado**
- [x] **Certificado digital** (`firma/digital_certificate.py`): .pfx/.p12 (incluido cifrado legado RC2) y PEM. Probado con certificado real.
- [x] **Firma XML-DSig** (`firma/xml_signer.py`): formato SII, verificación independiente con xmllint + openssl. Corrige un bug de C14N de lxml/libxml2 con namespace por defecto.
- [x] **CAF** (`identifier/caf.py`): carga, vigencia, validación de la firma del SII (100.cer/300.cer) y CAF falsos para pruebas.
- [x] **Timbraje TED** (`firma/ted.py`): DD firmado con la clave del CAF. El TED del ejemplo oficial del SII se verifica correctamente.
- [x] **DTE timbrado y firmado** (`dte/builder.py`, `xml/encoder.py`): XML ISO-8859-1 que cumple `DTE_v10.xsd`.
- [x] **EnvioDTE** (`dte/envelope.py`): carátula y firma del SetDTE; cumple `EnvioDTE_v10.xsd`.
- [x] **Validación XSD** (`xml/schema.py`) con los esquemas oficiales.
- [x] **Autenticación SII** (`sii/webservices/soap_service.py`): semilla → getToken firmado → token. Probado en vivo en maullin.
- [x] **Envío y estados**: upload a `/cgi_dte/UPL/DTEUpload`, QueryEstUp y QueryEstDte (probados con respuestas en formato real; envío en vivo pendiente de CAF real).
- [x] **Script de certificación**: `examples/emitir_certificacion.py`.
- [x] **Normalizador** (`dte/normalizer.py`): traducción del NormalizerWorker de PHP para 33, 34, 39, 41, 46, 52, 56 y 61 (detalle, descuentos/recargos, impuestos adicionales y retenciones, IVA y totales, transporte, boletas, MntPagos, OtraMoneda). Los 35 casos YAML de LibreDTE PHP de esos tipos (no boleta) generan DTE válidos según el XSD con los mismos montos que PHP; las 7 boletas coinciden en montos.

### ⚠️ **Limitaciones conocidas**
- **Normalizador**: faltan exportación (110, 111, 112) y liquidación factura (43). Faltan los proveedores de datos de contribuyentes (se pueden inyectar con `emisor_provider`/`receptor_provider`) y la conversión de códigos de comuna a nombre. Igual que en PHP, los totales se calculan desde el detalle: no entregar Totales junto al Detalle.
- **Boletas** (39/41): no se envían por DTEUpload sino por la API REST de boletas del SII; no implementado.
- **`sii/webservices/rest_service.py` y `document_sender.py`**: el servicio REST con api_key no corresponde a una API real del SII, y `DocumentSender` envía DTE sueltos (el SII exige EnvioDTE). Usar `SoapService` + `DocumentEnvelope`.
- **Tests**: 63 tests heredados fallan (logging, config, workers, webservices) desde antes de esta revisión.

---

## 🎯 **PENDING TASKS**

### **⚡ HIGH VALUE (Significant User Impact)**

#### **1. TradingParties Component**
**Priority**: HIGH
**Status**: Partially implemented (basic Contribuyente only)
**PHP Reference**: `/src/Package/Billing/Component/TradingParties/`
**Description**: Advanced party management including multiple identification schemes, party relationships, and entity validation.
**Impact**: High - needed for complex multi-party transactions
**Files to enhance**: `src/rypsystems_dte/sii/base.py`
**Files to create**: `src/rypsystems_dte/trading_parties/`
**Estimated effort**: 2-3 days

#### **2. Exchange Workers (Communication Layer)**
**Priority**: HIGH
**Status**: Basic structure exists, workers missing
**PHP Reference**: `/src/Package/Billing/Component/Exchange/Worker/`
**Description**: Document exchange automation including:
- **Sender Strategies**: SII, Email, Direct transfer
- **Receiver Handlers**: Document reception and processing
- **Handler Coordination**: Multi-strategy document distribution
**Impact**: Medium - needed for automated document exchange
**Files to create**: `src/rypsystems_dte/exchange/workers/`
**Estimated effort**: 3-4 days

#### **3. Document Template Rendering System**
**Priority**: HIGH
**Status**: Missing entirely
**PHP Reference**: `/src/Package/Billing/Component/Document/Worker/Renderer/Strategy/Template/`
**Description**: Generate PDF and HTML representations of documents using templates including:
- PDF generation with proper formatting
- HTML templates for web display
- Custom template support
- Styling and branding options
**Impact**: Medium - important for user-facing document display
**Files to create**: `src/rypsystems_dte/rendering/`
**Estimated effort**: 2-3 days

#### **4. Performance Benchmarks and Optimization**
**Priority**: HIGH
**Status**: Not addressed
**Description**: Benchmarking, profiling, and optimization for high-volume processing including:
- Performance profiling tools
- Memory usage optimization
- Concurrent processing support
- Caching strategies
**Impact**: Medium - important for enterprise deployment
**Files to create**: `benchmarks/`, performance optimizations throughout
**Estimated effort**: 2-3 days

#### **5. Production-Ready Deployment Scripts**
**Priority**: HIGH
**Status**: Missing entirely
**Description**: Docker containers, deployment scripts, and production configuration including:
- Docker containerization
- Kubernetes manifests
- CI/CD pipeline configuration
- Environment setup scripts
**Impact**: High - needed for real-world usage
**Files to create**: `docker/`, `deploy/`, `.github/workflows/`
**Estimated effort**: 2-3 days

### **🔧 QUALITY OF LIFE (Nice to Have)**

#### **6. Document BatchProcessor**
**Priority**: MEDIUM
**Status**: Missing entirely
**PHP Reference**: `/src/Package/Billing/Component/Document/Worker/BatchProcessor/`
**Description**: Bulk document processing from spreadsheets, CSV files, and other batch sources including:
- Excel/CSV file processing
- Batch validation and error reporting
- Progress tracking for large batches
- Concurrent processing support
**Impact**: Medium - important for enterprise users with high volume
**Files to create**: `src/rypsystems_dte/batch/`
**Estimated effort**: 2-3 days

#### **7. Repository Pattern for Document Storage**
**Priority**: MEDIUM
**Status**: Missing entirely
**Description**: Abstracted document storage with multiple backend support including:
- Database storage abstraction
- File system storage
- Cloud storage integration
- Document versioning and history
**Impact**: Medium - needed for persistent document management
**Files to create**: `src/rypsystems_dte/repository/`
**Estimated effort**: 2 days

#### **8. Comprehensive API Documentation**
**Priority**: MEDIUM
**Status**: Basic docstrings only
**Description**: Comprehensive API documentation with examples and tutorials including:
- Sphinx-based documentation
- API reference with examples
- Tutorial and getting started guides
- Integration examples
**Impact**: Medium - important for adoption
**Files to create**: `docs/`, enhanced docstrings
**Estimated effort**: 2-3 days

#### **9. Email Exchange Strategy**
**Priority**: MEDIUM
**Status**: Missing entirely
**Description**: Document distribution via email with proper formatting and security including:
- SMTP integration
- Email templates
- Attachment handling
- Security and encryption
**Impact**: Medium - alternative distribution method
**Files to create**: `src/rypsystems_dte/exchange/strategies/email/`
**Estimated effort**: 1-2 days

### **📚 SPECIALIZED (Domain-Specific Features)**

#### **10. Identifier Component** (✅ CAF implementado en `identifier/caf.py`)
**Priority**: LOW
**Status**: Basic implementation only
**PHP Reference**: `/src/Package/Billing/Component/Identifier/`
**Description**: Advanced party identification supporting multiple schemes (RUT, Email, Custom) with validation and authority mapping.
**Impact**: Medium - needed for international transactions
**Files to enhance**: `src/rypsystems_dte/sii/base.py`
**Estimated effort**: 1-2 days

#### **11. Document Parser Workers**
**Priority**: LOW
**Status**: Missing entirely
**PHP Reference**: `/src/Package/Billing/Component/Document/Worker/Parser/`
**Description**: Parse documents from various input formats including:
- Form data parsing
- Structured data conversion
- Legacy format migration
- Data validation and cleaning
**Impact**: Medium - useful for data migration and integration
**Files to create**: `src/rypsystems_dte/document/parsers/`
**Estimated effort**: 2 days

#### **12. Book Component**
**Priority**: LOW
**Status**: Missing entirely
**PHP Reference**: `/src/Package/Billing/Component/Book/`
**Description**: Document book management for accounting and audit compliance including:
- Document sequence tracking
- Book period management
- Audit trail maintenance
- Compliance reporting
**Impact**: Low - specialized feature for accounting integration
**Files to create**: `src/rypsystems_dte/book/`
**Estimated effort**: 1-2 days

#### **13. OwnershipTransfer Component**
**Priority**: LOW
**Status**: Missing entirely
**PHP Reference**: `/src/Package/Billing/Component/OwnershipTransfer/`
**Description**: Handles document ownership transfers and chain of custody including:
- Transfer request processing
- Chain of custody tracking
- Ownership validation
- Transfer history maintenance
**Impact**: Low - specialized feature for logistics companies
**Files to create**: `src/rypsystems_dte/ownership/`
**Estimated effort**: 1-2 days

---

## 📈 **IMPLEMENTATION ROADMAP**

### **Phase 1: Production Foundation** (COMPLETED)
1. ✅ SII Web Services Integration
2. ✅ Digital Signature Validation
3. ✅ Advanced Validation Rules
4. ✅ Comprehensive Error Handling
5. ✅ Configuration Management

### **Phase 2: User Experience** (2-3 weeks)
1. TradingParties Component
2. Exchange Workers
3. Template Rendering System
4. Performance Optimization
5. Production Deployment

### **Phase 3: Enterprise Features** (1-2 weeks)
1. Document BatchProcessor
2. Repository Pattern
3. API Documentation
4. Email Exchange Strategy

### **Phase 4: Specialized Features** (1-2 weeks)
1. Book Component
2. OwnershipTransfer Component
3. Document Parsing System
4. Identifier Component

---

## 🎯 **CURRENT NEXT TASK**

**READY TO START**: TradingParties Component

This is the next most critical remaining component that provides advanced party management including multiple identification schemes, party relationships, and entity validation for complex multi-party transactions.

---

**Instructions**: Remove completed tasks from this file as they are finished. Keep this file updated with current progress and remaining work.