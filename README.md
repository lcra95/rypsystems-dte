# rypsystems-dte

Librería Python para documentos tributarios electrónicos (DTE) del SII de Chile.

Hace normalización y cálculo de totales, timbraje (TED), firma XML-DSig, el sobre EnvioDTE o EnvioBOLETA, el envío al SII y la consulta de estados. También genera el PDF (carta y térmico 80 mm), maneja el intercambio entre contribuyentes y registra la aceptación o el reclamo de documentos (Ley 20.956).

Es una traducción a Python de [LibreDTE](https://www.libredte.cl) y se distribuye bajo **AGPL-3.0-or-later**; ver `COPYING` y `NOTICE`.

## Instalación

```bash
pip install "rypsystems-dte @ https://github.com/lcra95/rypsystems-dte/archive/refs/tags/v0.3.0.tar.gz"
# desarrollo
pip install -e ".[test]"
```

## Uso

```python
from rypsystems_dte import Caf, ClienteSii, DigitalCertificate, DtePdf, SiiEnvironment
from rypsystems_dte import anular, armar_envio, emitir_documento

certificado = DigitalCertificate.from_file('firma.pfx', 'clave')
caf = Caf.from_file('FoliosSII...33....xml')

doc = emitir_documento({
    'Encabezado': {
        'IdDoc': {'TipoDTE': 33, 'Folio': 31, 'FmaPago': 2},
        'Emisor': {'RUTEmisor': '78532566-4', 'RznSoc': '...', 'GiroEmis': '...', 'Acteco': 620900,
                   'DirOrigen': '...', 'CmnaOrigen': '...'},
        'Receptor': {'RUTRecep': '60803000-K', 'RznSocRecep': '...', 'GiroRecep': '...',
                     'DirRecep': '...', 'CmnaRecep': '...'},
    },
    'Detalle': [{'NmbItem': 'Servicio', 'QtyItem': 1, 'PrcItem': 100000}],
}, caf, certificado)                       # totales calculados, timbrado, firmado y validado

envio = armar_envio([doc], certificado, fecha_resolucion='2026-10-17', numero_resolucion=0)
sii = ClienteSii(certificado, SiiEnvironment.CERTIFICACION)
track_id = sii.enviar(envio, doc.emisor)  # EnvioDTE por DTEUpload; boletas por la API REST
estado = sii.consultar_envio(track_id, doc.emisor, boletas=doc.es_boleta)

pdf = DtePdf().render(doc.xml)
nc = anular(doc, folio=20, caf=caf_61, certificado=certificado)   # NC 61 con CodRef 1
```

Reglas:
- **Sin estado global ni archivos.** El folio, el CAF y el certificado los entrega quien llama, porque asignar folios sin repetirlos es responsabilidad de la aplicación.
- **Errores:** todos heredan de `RypDteError`. `EmisionError` cubre los datos, el CAF, el esquema, el timbre y la firma; `SiiWebServiceException`, la comunicación con el SII.

Boletas: cada boleta se envía al SII por su API REST. El Resumen de Ventas Diarias (antes Reporte de Consumo de Folios) dejó de enviarse desde el 1 de agosto de 2022 (Res. Ex. SII N° 53 de 2022), así que no se genera.

Otros módulos:
- `rypsystems_dte.intercambio`: EnvioDTE recibidos, respuestas y recibos de mercaderías.
- `RegistroReclamoService`: aceptar o reclamar documentos recibidos y consultar sus eventos.
- `rypsystems_dte.libro`: libros de compra, venta y guías (solo los pide la certificación).

## Certificación con el SII

Los scripts de `examples/` cubren todas las etapas (usan `pip install -e ".[examples]"`):

| Etapa | Script |
|---|---|
| Set de pruebas y simulación | `set_pruebas.py --set examples/sets/<set>.yaml --empresa empresa.yaml --pfx ... --pass-file ... [--enviar --consultar]` |
| Libros | `libros_certificacion.py`, `libro_guias_certificacion.py` |
| Intercambio | `intercambio_certificacion.py --envio ENVIO_DTE.xml ...` |
| Muestras impresas | `muestras_impresion.py --empresa ... --para-sii` |
| Aceptación o reclamo | `reclamo_dte.py ACD --emisor ... --tipo 33 --folio ...` |

## Tests

```bash
pytest
```

Algunos tests usan los casos de LibreDTE PHP en `../libredte-php-original`; si no está, se omiten.
