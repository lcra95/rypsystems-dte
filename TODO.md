# Pendientes

Estado al 2026-10-18. El plan completo está en `~/.claude/plans/jaunty-growing-goblet.md`: core (este repositorio) → servicio DTE REST → sistema principal privado.

## Hecho
- **Firma y timbraje:** certificado, firma XML-DSig, CAF, TED y validación XSD.
- **Documentos:** normalizador para 33, 34, 39, 41, 43, 46, 52, 56, 61, 110, 111 y 112, y los sobres EnvioDTE y EnvioBOLETA.
- **SII:** autenticación, DTEUpload, QueryEstUp y QueryEstDte; API REST de boletas; registro de aceptación o reclamo (Ley 20.956).
- **Intercambio:** RecepcionEnvio, EnvioRecibos y ResultadoDTE.
- **Otros:** PDF carta y térmico 80 mm con el timbre vectorial; libros de compra, venta y guías.
- **Interfaz pública** (`emision.py`): emitir, armar envío, anular y `ClienteSii`.
- **Certificación** (`certificacion/`): *parser* del set de pruebas del SII y del de boletas, emisión de sets, libros y muestras impresas. Reproduce exactamente lo que el SII aceptó a RYP.
- **Certificación de RYP AI SYSTEMS:** set de pruebas, simulación e intercambio aprobados; muestras impresas en revisión del SII.

## Core (Fase 0)
- [ ] Tipo de cambio oficial (dólar observado) como proveedor que se inyecta; hoy `TpoCambio` va en los datos.
- [ ] Confirmar si las boletas exigen hoy el Resumen de Ventas Diarias (aparece en el menú del SII) e implementarlo si corresponde.
- [ ] Prueba en vivo de los hosts de producción: solo autenticación y consultas.
- [ ] `libros_certificacion.py`, `libro_guias_certificacion.py` y `muestras_impresion.py` siguen con su propia lógica; podrían usar `rypsystems_dte.certificacion`.
- [ ] Revisar `dte/document.py`, `dte/factory.py`, `xml/document.py` y `pdf417/`: heredados de la traducción y fuera del flujo de `emision.py`.

## Servicio DTE (Fase 1, repo `rypsystems-dte-api`)
- [ ] FastAPI + PostgreSQL + cola de tareas: empresas, certificados cifrados, CAF, folios atómicos, documentos, envíos y webhooks.
