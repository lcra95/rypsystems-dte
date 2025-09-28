# RypSystems DTE - Integration Guide

**Practical integration guide for multi-language backend systems**

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Patterns](#architecture-patterns)
3. [Client Implementation Examples](#client-implementation-examples)
4. [Configuration Patterns](#configuration-patterns)
5. [Error Handling Strategies](#error-handling-strategies)
6. [Performance Optimization](#performance-optimization)
7. [Security Best Practices](#security-best-practices)
8. [Testing Strategies](#testing-strategies)
9. [Deployment Patterns](#deployment-patterns)
10. [Migration Guides](#migration-guides)

---

## Quick Start

### 5-Minute Setup

1. **Install the library:**
```bash
pip install rypsystems-dte
```

2. **Create basic configuration:**
```yaml
# config.yaml
environment: "development"
sii:
  environment: "certificacion"
  authentication:
    certificate_path: "/path/to/cert.pem"
    private_key_path: "/path/to/key.pem"
    rut_contribuyente: "12345678-9"
```

3. **Create your first document:**
```python
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente

factory = DTEFactory()
emisor = Contribuyente("76354771-K", "Mi Empresa")
receptor = Contribuyente("12345678-9", "Cliente")

factura = factory.create_factura_afecta(
    emisor=emisor,
    receptor=receptor,
    folio=1001,
    fecha_emision="2023-12-01",
    detalle=[{"NmbItem": "Producto", "QtyItem": 1, "PrcItem": 1000}]
)

print(factura.save_xml())
```

### Verification Checklist

- [ ] Library installed successfully
- [ ] Configuration file created
- [ ] Certificates configured (for SII integration)
- [ ] First document created
- [ ] XML output validated

---

## Architecture Patterns

### Pattern 1: Microservice Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   DTE Service   │
│   (React/Vue)   │───▶│   (Node/Java)   │───▶│   (Python)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                               ┌─────────────────┐
                                               │   SII Service   │
                                               │   (Chilean Tax) │
                                               └─────────────────┘
```

**Advantages:**
- Language independence
- Scalable and maintainable
- Clear separation of concerns
- Easy to test and deploy

**Implementation:**
```python
# dte_service.py
from flask import Flask, request, jsonify
from rypsystems_dte.dte.factory import DTEFactory

app = Flask(__name__)
factory = DTEFactory()

@app.route('/health')
def health():
    return {"status": "healthy", "service": "dte"}

@app.route('/api/v1/documents', methods=['POST'])
def create_document():
    data = request.json
    # Document creation logic
    return jsonify(result)
```

### Pattern 2: Shared Library Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Application   │    │   RypSystems    │
│   (Any Lang)    │───▶│   DTE Library   │
└─────────────────┘    └─────────────────┘
                              │
                       ┌─────────────────┐
                       │   SII Service   │
                       └─────────────────┘
```

**Advantages:**
- Direct integration
- Lower latency
- Simplified deployment
- Better performance

**Implementation:**
- Python: Direct import
- Node.js: Python child process
- Java: Jython or subprocess
- C#: IronPython or subprocess

### Pattern 3: Event-Driven Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Producer      │    │   Message       │    │   DTE Consumer  │
│   (Any Lang)    │───▶│   Queue         │───▶│   (Python)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                               ┌─────────────────┐
                                               │   SII Service   │
                                               └─────────────────┘
```

**Advantages:**
- Asynchronous processing
- High scalability
- Fault tolerance
- Decoupled systems

**Implementation:**
```python
# consumer.py
import pika
import json
from rypsystems_dte.dte.factory import DTEFactory

def process_message(ch, method, properties, body):
    request = json.loads(body)
    # Process DTE request
    result = create_document(request)
    # Send response
    send_response(result, properties.reply_to)
```

---

## Client Implementation Examples

### Node.js Client

```javascript
// dte-client.js
const axios = require('axios');
const { spawn } = require('child_process');

class DTEClient {
    constructor(config) {
        this.config = config;
        this.baseURL = config.baseURL || 'http://localhost:8000';
    }

    // HTTP API approach
    async createInvoiceHTTP(invoiceData) {
        try {
            const response = await axios.post(`${this.baseURL}/api/v1/documents/factura`, invoiceData);
            return response.data;
        } catch (error) {
            throw new Error(`DTE API Error: ${error.response?.data?.error || error.message}`);
        }
    }

    // CLI approach
    async createInvoiceCLI(invoiceData) {
        return new Promise((resolve, reject) => {
            const dataFile = `/tmp/invoice_${Date.now()}.json`;
            require('fs').writeFileSync(dataFile, JSON.stringify(invoiceData));

            const python = spawn('python', [
                '-m', 'rypsystems_dte.cli',
                '--action', 'create-factura',
                '--data', dataFile
            ]);

            let output = '';
            let error = '';

            python.stdout.on('data', (data) => {
                output += data.toString();
            });

            python.stderr.on('data', (data) => {
                error += data.toString();
            });

            python.on('close', (code) => {
                require('fs').unlinkSync(dataFile); // Cleanup

                if (code === 0) {
                    resolve({ xml: output, success: true });
                } else {
                    reject(new Error(`DTE CLI Error: ${error}`));
                }
            });
        });
    }
}

// Usage
const client = new DTEClient({ baseURL: 'http://localhost:8000' });

const invoiceData = {
    emisor: { rut: "76354771-K", nombre: "Mi Empresa" },
    receptor: { rut: "12345678-9", nombre: "Cliente" },
    folio: 1001,
    fecha_emision: "2023-12-01",
    detalle: [
        { NmbItem: "Producto", QtyItem: 1, PrcItem: 1000 }
    ]
};

// Using HTTP API
client.createInvoiceHTTP(invoiceData)
    .then(result => console.log('Invoice created:', result.document_id))
    .catch(error => console.error('Error:', error.message));
```

### Java Client

```java
// DTEClient.java
import java.io.*;
import java.net.http.*;
import java.nio.file.*;
import com.fasterxml.jackson.databind.ObjectMapper;

public class DTEClient {
    private final String baseURL;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    public DTEClient(String baseURL) {
        this.baseURL = baseURL;
        this.httpClient = HttpClient.newHttpClient();
        this.objectMapper = new ObjectMapper();
    }

    // HTTP API approach
    public DTEResponse createInvoice(InvoiceData invoiceData) throws Exception {
        String jsonData = objectMapper.writeValueAsString(invoiceData);

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(baseURL + "/api/v1/documents/factura"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(jsonData))
            .build();

        HttpResponse<String> response = httpClient.send(request,
            HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() == 200) {
            return objectMapper.readValue(response.body(), DTEResponse.class);
        } else {
            throw new RuntimeException("DTE API Error: " + response.body());
        }
    }

    // CLI approach
    public DTEResponse createInvoiceCLI(InvoiceData invoiceData) throws Exception {
        // Create temporary JSON file
        Path tempFile = Files.createTempFile("invoice_", ".json");
        objectMapper.writeValue(tempFile.toFile(), invoiceData);

        try {
            ProcessBuilder pb = new ProcessBuilder(
                "python", "-m", "rypsystems_dte.cli",
                "--action", "create-factura",
                "--data", tempFile.toString()
            );

            Process process = pb.start();

            String output = new String(process.getInputStream().readAllBytes());
            String error = new String(process.getErrorStream().readAllBytes());

            int exitCode = process.waitFor();

            if (exitCode == 0) {
                return new DTEResponse(true, output, null);
            } else {
                throw new RuntimeException("DTE CLI Error: " + error);
            }
        } finally {
            Files.deleteIfExists(tempFile);
        }
    }

    // Data classes
    public static class InvoiceData {
        public Party emisor;
        public Party receptor;
        public int folio;
        public String fecha_emision;
        public List<DetailItem> detalle;

        // constructors, getters, setters
    }

    public static class Party {
        public String rut;
        public String nombre;

        public Party(String rut, String nombre) {
            this.rut = rut;
            this.nombre = nombre;
        }
    }

    public static class DetailItem {
        public String NmbItem;
        public int QtyItem;
        public int PrcItem;

        public DetailItem(String name, int qty, int price) {
            this.NmbItem = name;
            this.QtyItem = qty;
            this.PrcItem = price;
        }
    }

    public static class DTEResponse {
        public boolean success;
        public String xml;
        public String documentId;
        public String error;

        // constructors, getters, setters
    }
}

// Usage
DTEClient client = new DTEClient("http://localhost:8000");

InvoiceData invoice = new InvoiceData();
invoice.emisor = new Party("76354771-K", "Mi Empresa");
invoice.receptor = new Party("12345678-9", "Cliente");
invoice.folio = 1001;
invoice.fecha_emision = "2023-12-01";
invoice.detalle = Arrays.asList(
    new DetailItem("Producto", 1, 1000)
);

DTEResponse response = client.createInvoice(invoice);
System.out.println("Document ID: " + response.documentId);
```

### PHP Client

```php
<?php
// DTEClient.php

class DTEClient {
    private $baseURL;
    private $httpClient;

    public function __construct($baseURL = 'http://localhost:8000') {
        $this->baseURL = $baseURL;
        $this->httpClient = new GuzzleHttp\Client();
    }

    // HTTP API approach
    public function createInvoice($invoiceData) {
        try {
            $response = $this->httpClient->post($this->baseURL . '/api/v1/documents/factura', [
                'json' => $invoiceData,
                'headers' => ['Content-Type' => 'application/json']
            ]);

            return json_decode($response->getBody(), true);

        } catch (GuzzleHttp\Exception\RequestException $e) {
            throw new Exception('DTE API Error: ' . $e->getMessage());
        }
    }

    // CLI approach
    public function createInvoiceCLI($invoiceData) {
        $tempFile = tempnam(sys_get_temp_dir(), 'invoice_') . '.json';
        file_put_contents($tempFile, json_encode($invoiceData));

        $command = sprintf(
            'python -m rypsystems_dte.cli --action create-factura --data %s 2>&1',
            escapeshellarg($tempFile)
        );

        $output = shell_exec($command);
        unlink($tempFile); // Cleanup

        if ($output === null) {
            throw new Exception('DTE CLI Error: Failed to execute command');
        }

        // Check for error in output
        if (strpos($output, 'ERROR:') !== false) {
            throw new Exception('DTE CLI Error: ' . $output);
        }

        return ['success' => true, 'xml' => $output];
    }
}

// Usage
$client = new DTEClient();

$invoiceData = [
    'emisor' => ['rut' => '76354771-K', 'nombre' => 'Mi Empresa'],
    'receptor' => ['rut' => '12345678-9', 'nombre' => 'Cliente'],
    'folio' => 1001,
    'fecha_emision' => '2023-12-01',
    'detalle' => [
        ['NmbItem' => 'Producto', 'QtyItem' => 1, 'PrcItem' => 1000]
    ]
];

try {
    $result = $client->createInvoice($invoiceData);
    echo "Document created: " . $result['document_id'] . "\n";
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
}
?>
```

### C# Client

```csharp
// DTEClient.cs
using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Diagnostics;
using System.IO;

public class DTEClient
{
    private readonly HttpClient httpClient;
    private readonly string baseURL;

    public DTEClient(string baseURL = "http://localhost:8000")
    {
        this.baseURL = baseURL;
        this.httpClient = new HttpClient();
    }

    // HTTP API approach
    public async Task<DTEResponse> CreateInvoiceAsync(InvoiceData invoiceData)
    {
        try
        {
            string jsonData = JsonSerializer.Serialize(invoiceData);
            var content = new StringContent(jsonData, Encoding.UTF8, "application/json");

            var response = await httpClient.PostAsync($"{baseURL}/api/v1/documents/factura", content);

            if (response.IsSuccessStatusCode)
            {
                string responseJson = await response.Content.ReadAsStringAsync();
                return JsonSerializer.Deserialize<DTEResponse>(responseJson);
            }
            else
            {
                string error = await response.Content.ReadAsStringAsync();
                throw new Exception($"DTE API Error: {error}");
            }
        }
        catch (Exception e)
        {
            throw new Exception($"DTE Client Error: {e.Message}");
        }
    }

    // CLI approach
    public async Task<DTEResponse> CreateInvoiceCLIAsync(InvoiceData invoiceData)
    {
        string tempFile = Path.GetTempFileName() + ".json";

        try
        {
            string jsonData = JsonSerializer.Serialize(invoiceData);
            await File.WriteAllTextAsync(tempFile, jsonData);

            var startInfo = new ProcessStartInfo
            {
                FileName = "python",
                Arguments = $"-m rypsystems_dte.cli --action create-factura --data \"{tempFile}\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(startInfo);
            await process.WaitForExitAsync();

            string output = await process.StandardOutput.ReadToEndAsync();
            string error = await process.StandardError.ReadToEndAsync();

            if (process.ExitCode == 0)
            {
                return new DTEResponse { Success = true, XML = output };
            }
            else
            {
                throw new Exception($"DTE CLI Error: {error}");
            }
        }
        finally
        {
            if (File.Exists(tempFile))
                File.Delete(tempFile);
        }
    }

    // Data classes
    public class InvoiceData
    {
        public Party Emisor { get; set; }
        public Party Receptor { get; set; }
        public int Folio { get; set; }
        public string FechaEmision { get; set; }
        public DetailItem[] Detalle { get; set; }
    }

    public class Party
    {
        public string Rut { get; set; }
        public string Nombre { get; set; }
    }

    public class DetailItem
    {
        public string NmbItem { get; set; }
        public int QtyItem { get; set; }
        public int PrcItem { get; set; }
    }

    public class DTEResponse
    {
        public bool Success { get; set; }
        public string XML { get; set; }
        public string DocumentId { get; set; }
        public string Error { get; set; }
    }
}

// Usage
var client = new DTEClient();

var invoice = new DTEClient.InvoiceData
{
    Emisor = new DTEClient.Party { Rut = "76354771-K", Nombre = "Mi Empresa" },
    Receptor = new DTEClient.Party { Rut = "12345678-9", Nombre = "Cliente" },
    Folio = 1001,
    FechaEmision = "2023-12-01",
    Detalle = new[]
    {
        new DTEClient.DetailItem { NmbItem = "Producto", QtyItem = 1, PrcItem = 1000 }
    }
};

var result = await client.CreateInvoiceAsync(invoice);
Console.WriteLine($"Document ID: {result.DocumentId}");
```

### Go Client

```go
// dte_client.go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io/ioutil"
    "net/http"
    "os"
    "os/exec"
    "time"
)

type DTEClient struct {
    BaseURL    string
    HTTPClient *http.Client
}

type Party struct {
    Rut    string `json:"rut"`
    Nombre string `json:"nombre"`
}

type DetailItem struct {
    NmbItem  string `json:"NmbItem"`
    QtyItem  int    `json:"QtyItem"`
    PrcItem  int    `json:"PrcItem"`
}

type InvoiceData struct {
    Emisor       Party        `json:"emisor"`
    Receptor     Party        `json:"receptor"`
    Folio        int          `json:"folio"`
    FechaEmision string       `json:"fecha_emision"`
    Detalle      []DetailItem `json:"detalle"`
}

type DTEResponse struct {
    Success    bool   `json:"success"`
    DocumentID string `json:"document_id"`
    XML        string `json:"xml"`
    Error      string `json:"error"`
}

func NewDTEClient(baseURL string) *DTEClient {
    if baseURL == "" {
        baseURL = "http://localhost:8000"
    }

    return &DTEClient{
        BaseURL: baseURL,
        HTTPClient: &http.Client{
            Timeout: 30 * time.Second,
        },
    }
}

// HTTP API approach
func (c *DTEClient) CreateInvoice(invoiceData InvoiceData) (*DTEResponse, error) {
    jsonData, err := json.Marshal(invoiceData)
    if err != nil {
        return nil, fmt.Errorf("json marshal error: %w", err)
    }

    resp, err := c.HTTPClient.Post(
        c.BaseURL+"/api/v1/documents/factura",
        "application/json",
        bytes.NewBuffer(jsonData),
    )
    if err != nil {
        return nil, fmt.Errorf("http request error: %w", err)
    }
    defer resp.Body.Close()

    body, err := ioutil.ReadAll(resp.Body)
    if err != nil {
        return nil, fmt.Errorf("read response error: %w", err)
    }

    var response DTEResponse
    if err := json.Unmarshal(body, &response); err != nil {
        return nil, fmt.Errorf("json unmarshal error: %w", err)
    }

    if resp.StatusCode != 200 {
        return nil, fmt.Errorf("API error: %s", response.Error)
    }

    return &response, nil
}

// CLI approach
func (c *DTEClient) CreateInvoiceCLI(invoiceData InvoiceData) (*DTEResponse, error) {
    // Create temporary file
    tempFile, err := ioutil.TempFile("", "invoice_*.json")
    if err != nil {
        return nil, fmt.Errorf("create temp file error: %w", err)
    }
    defer os.Remove(tempFile.Name())

    // Write invoice data to file
    jsonData, err := json.Marshal(invoiceData)
    if err != nil {
        return nil, fmt.Errorf("json marshal error: %w", err)
    }

    if _, err := tempFile.Write(jsonData); err != nil {
        return nil, fmt.Errorf("write temp file error: %w", err)
    }
    tempFile.Close()

    // Execute Python CLI
    cmd := exec.Command("python", "-m", "rypsystems_dte.cli",
        "--action", "create-factura",
        "--data", tempFile.Name())

    output, err := cmd.CombinedOutput()
    if err != nil {
        return nil, fmt.Errorf("CLI execution error: %s", string(output))
    }

    return &DTEResponse{
        Success: true,
        XML:     string(output),
    }, nil
}

// Usage example
func main() {
    client := NewDTEClient("")

    invoice := InvoiceData{
        Emisor:   Party{Rut: "76354771-K", Nombre: "Mi Empresa"},
        Receptor: Party{Rut: "12345678-9", Nombre: "Cliente"},
        Folio:    1001,
        FechaEmision: "2023-12-01",
        Detalle: []DetailItem{
            {NmbItem: "Producto", QtyItem: 1, PrcItem: 1000},
        },
    }

    result, err := client.CreateInvoice(invoice)
    if err != nil {
        fmt.Printf("Error: %v\n", err)
        return
    }

    fmt.Printf("Document created: %s\n", result.DocumentID)
}
```

---

## Configuration Patterns

### Environment-Based Configuration

```yaml
# config.dev.yaml
environment: "development"
debug: true
sii:
  environment: "certificacion"
  verify_ssl: false
logging:
  level: "DEBUG"
features:
  beta_features: true

---
# config.prod.yaml
environment: "production"
debug: false
sii:
  environment: "produccion"
  verify_ssl: true
logging:
  level: "WARNING"
security:
  validate_certificates: true
features:
  beta_features: false
```

### Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openssl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .
RUN pip install -e .

# Create directories
RUN mkdir -p /var/log/rypsystems_dte /etc/ssl/certificates

# Set environment variables
ENV PYTHONPATH=/app
ENV RYPSYSTEMS_DTE_CONFIG_PATH=/app/config.yaml

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from rypsystems_dte.config import ConfigManager; ConfigManager().validate()" || exit 1

EXPOSE 8000

CMD ["python", "api_server.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  dte-service:
    build: .
    ports:
      - "8000:8000"
    environment:
      - RYPSYSTEMS_DTE_ENVIRONMENT=production
      - RYPSYSTEMS_DTE_SII_ENVIRONMENT=produccion
      - RYPSYSTEMS_DTE_LOG_LEVEL=INFO
    volumes:
      - ./certificates:/etc/ssl/certificates:ro
      - ./config.prod.yaml:/app/config.yaml:ro
      - ./logs:/var/log/rypsystems_dte
    restart: unless-stopped
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: dte_tracking
      POSTGRES_USER: dte_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  redis_data:
  postgres_data:
```

### Kubernetes Configuration

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dte-service
  labels:
    app: dte-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: dte-service
  template:
    metadata:
      labels:
        app: dte-service
    spec:
      containers:
      - name: dte-service
        image: your-registry/dte-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: RYPSYSTEMS_DTE_ENVIRONMENT
          value: "production"
        - name: RYPSYSTEMS_DTE_SII_ENVIRONMENT
          value: "produccion"
        - name: RYPSYSTEMS_DTE_LOG_LEVEL
          value: "WARNING"
        volumeMounts:
        - name: certificates
          mountPath: /etc/ssl/certificates
          readOnly: true
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
          readOnly: true
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: certificates
        secret:
          secretName: sii-certificates
      - name: config
        configMap:
          name: dte-config

---
apiVersion: v1
kind: Service
metadata:
  name: dte-service
spec:
  selector:
    app: dte-service
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: dte-config
data:
  config.yaml: |
    environment: "production"
    debug: false
    sii:
      environment: "produccion"
      verify_ssl: true
    logging:
      level: "WARNING"
      format: "json"
    features:
      beta_features: false
```

---

## Error Handling Strategies

### Centralized Error Handling

```python
# error_handler.py
from rypsystems_dte.logging import ErrorHandler, ErrorSeverity
import functools
import time

class DTEErrorHandler:
    def __init__(self):
        self.error_handler = ErrorHandler()
        self.error_counts = {}
        self.circuit_breakers = {}

    def handle_with_retry(self, max_retries=3, backoff_factor=1.0):
        """Decorator for automatic retry with exponential backoff"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None

                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e

                        # Classify error
                        classification = self.error_handler.handle_error(e, {
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": max_retries
                        })

                        # Don't retry if not recoverable or on last attempt
                        if not classification.recoverable or attempt == max_retries:
                            break

                        # Exponential backoff
                        sleep_time = backoff_factor * (2 ** attempt)
                        time.sleep(sleep_time)

                raise last_exception
            return wrapper
        return decorator

    def circuit_breaker(self, failure_threshold=5, recovery_timeout=60):
        """Circuit breaker pattern implementation"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                func_name = func.__name__

                # Initialize circuit breaker state
                if func_name not in self.circuit_breakers:
                    self.circuit_breakers[func_name] = {
                        'failures': 0,
                        'last_failure': None,
                        'state': 'closed'  # closed, open, half-open
                    }

                breaker = self.circuit_breakers[func_name]

                # Check circuit breaker state
                if breaker['state'] == 'open':
                    if time.time() - breaker['last_failure'] > recovery_timeout:
                        breaker['state'] = 'half-open'
                    else:
                        raise Exception(f"Circuit breaker open for {func_name}")

                try:
                    result = func(*args, **kwargs)

                    # Reset on success
                    if breaker['state'] == 'half-open':
                        breaker['state'] = 'closed'
                        breaker['failures'] = 0

                    return result

                except Exception as e:
                    breaker['failures'] += 1
                    breaker['last_failure'] = time.time()

                    if breaker['failures'] >= failure_threshold:
                        breaker['state'] = 'open'

                    raise

            return wrapper
        return decorator

# Usage examples
error_handler = DTEErrorHandler()

@error_handler.handle_with_retry(max_retries=3, backoff_factor=1.0)
@error_handler.circuit_breaker(failure_threshold=5, recovery_timeout=60)
def create_document_with_protection(data):
    # Your document creation logic
    pass
```

### Error Response Standardization

```python
# error_responses.py
from dataclasses import dataclass
from typing import Optional, Dict, Any
import traceback

@dataclass
class ErrorResponse:
    success: bool = False
    error_code: str = ""
    error_message: str = ""
    error_details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: Optional[str] = None
    trace_id: Optional[str] = None

@dataclass
class SuccessResponse:
    success: bool = True
    data: Any = None
    request_id: Optional[str] = None
    timestamp: Optional[str] = None

class ResponseBuilder:
    @staticmethod
    def success(data=None, request_id=None):
        return SuccessResponse(
            data=data,
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat()
        )

    @staticmethod
    def error(error_code, error_message, details=None, request_id=None):
        return ErrorResponse(
            error_code=error_code,
            error_message=error_message,
            error_details=details,
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat()
        )

    @staticmethod
    def from_exception(exception, request_id=None, include_trace=False):
        error_details = {
            "exception_type": type(exception).__name__
        }

        if include_trace:
            error_details["traceback"] = traceback.format_exc()

        return ErrorResponse(
            error_code="INTERNAL_ERROR",
            error_message=str(exception),
            error_details=error_details,
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat()
        )

# Usage in API endpoints
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route('/api/v1/documents/factura', methods=['POST'])
def create_factura():
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

    try:
        data = request.json

        # Validate input
        if not data:
            return jsonify(ResponseBuilder.error(
                "INVALID_INPUT",
                "Request body is required",
                request_id=request_id
            ).__dict__), 400

        # Create document
        result = create_document(data)

        return jsonify(ResponseBuilder.success(
            data=result,
            request_id=request_id
        ).__dict__)

    except ValidationError as e:
        return jsonify(ResponseBuilder.error(
            "VALIDATION_ERROR",
            "Invalid document data",
            details={"validation_errors": str(e)},
            request_id=request_id
        ).__dict__), 400

    except SiiError as e:
        return jsonify(ResponseBuilder.error(
            "SII_ERROR",
            "SII service error",
            details={"sii_error": str(e)},
            request_id=request_id
        ).__dict__), 502

    except Exception as e:
        return jsonify(ResponseBuilder.from_exception(
            e, request_id=request_id
        ).__dict__), 500
```

---

## Performance Optimization

### Connection Pooling

```python
# connection_pool.py
import threading
import queue
import time
from rypsystems_dte.sii.integration import SiiClient

class SiiConnectionPool:
    def __init__(self, max_connections=10, connection_timeout=30):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.pool = queue.Queue(maxsize=max_connections)
        self.active_connections = 0
        self.lock = threading.Lock()

        # Pre-create some connections
        for _ in range(min(3, max_connections)):
            self._create_connection()

    def _create_connection(self):
        """Create a new SII client connection"""
        with self.lock:
            if self.active_connections < self.max_connections:
                client = SiiClient()
                self.pool.put(client)
                self.active_connections += 1
                return True
        return False

    def get_connection(self, timeout=None):
        """Get a connection from the pool"""
        try:
            # Try to get existing connection
            client = self.pool.get(timeout=timeout or self.connection_timeout)
            return client
        except queue.Empty:
            # Try to create new connection
            if self._create_connection():
                return self.pool.get()
            else:
                raise Exception("Connection pool exhausted")

    def return_connection(self, client):
        """Return a connection to the pool"""
        try:
            self.pool.put_nowait(client)
        except queue.Full:
            # Pool is full, close connection
            with self.lock:
                self.active_connections -= 1

    def close_all(self):
        """Close all connections in the pool"""
        while not self.pool.empty():
            try:
                client = self.pool.get_nowait()
                # Close client connection if needed
            except queue.Empty:
                break

        with self.lock:
            self.active_connections = 0

# Usage
pool = SiiConnectionPool(max_connections=10)

def submit_document_pooled(document_data):
    client = pool.get_connection()
    try:
        result = client.submit_document(document_data)
        return result
    finally:
        pool.return_connection(client)
```

### Caching Strategy

```python
# caching.py
import redis
import json
import hashlib
import pickle
from functools import wraps

class DTECache:
    def __init__(self, redis_url=None, default_ttl=3600):
        self.default_ttl = default_ttl

        if redis_url:
            self.redis_client = redis.Redis.from_url(redis_url)
            self.use_redis = True
        else:
            self.local_cache = {}
            self.use_redis = False

    def cache_result(self, ttl=None, key_prefix="dte"):
        """Decorator to cache function results"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self._generate_key(key_prefix, func.__name__, args, kwargs)

                # Try to get from cache
                result = self._get(cache_key)
                if result is not None:
                    return result

                # Execute function and cache result
                result = func(*args, **kwargs)
                self._set(cache_key, result, ttl or self.default_ttl)

                return result
            return wrapper
        return decorator

    def _generate_key(self, prefix, func_name, args, kwargs):
        """Generate cache key from function call"""
        key_data = {
            'function': func_name,
            'args': args,
            'kwargs': kwargs
        }
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{prefix}:{func_name}:{key_hash}"

    def _get(self, key):
        """Get value from cache"""
        if self.use_redis:
            try:
                data = self.redis_client.get(key)
                return pickle.loads(data) if data else None
            except Exception:
                return None
        else:
            return self.local_cache.get(key)

    def _set(self, key, value, ttl):
        """Set value in cache"""
        if self.use_redis:
            try:
                self.redis_client.setex(key, ttl, pickle.dumps(value))
            except Exception:
                pass  # Cache failure shouldn't break application
        else:
            self.local_cache[key] = value
            # TODO: Implement TTL for local cache

# Usage
cache = DTECache(redis_url="redis://localhost:6379/0")

@cache.cache_result(ttl=1800, key_prefix="document")
def create_document_cached(document_data):
    # Expensive document creation logic
    return create_document(document_data)
```

### Async Processing

```python
# async_processor.py
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import time

class AsyncDTEProcessor:
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def create_document_async(self, document_data):
        """Create document asynchronously"""
        loop = asyncio.get_event_loop()

        # Run CPU-bound document creation in thread pool
        result = await loop.run_in_executor(
            self.executor,
            self._create_document_sync,
            document_data
        )

        return result

    def _create_document_sync(self, document_data):
        """Synchronous document creation (CPU-bound)"""
        from rypsystems_dte.dte.factory import DTEFactory
        from rypsystems_dte.sii.base import Contribuyente

        factory = DTEFactory()
        # Document creation logic...
        return result

    async def submit_to_sii_async(self, document):
        """Submit document to SII asynchronously"""
        if not self.session:
            raise RuntimeError("AsyncDTEProcessor not initialized")

        try:
            async with self.session.post(
                "https://sii-endpoint.cl/upload",
                data=document.save_xml(),
                headers={'Content-Type': 'application/xml'},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                return await response.json()

        except asyncio.TimeoutError:
            raise Exception("SII submission timeout")
        except Exception as e:
            raise Exception(f"SII submission failed: {str(e)}")

    async def process_batch_async(self, document_requests):
        """Process multiple documents concurrently"""
        tasks = []

        for request in document_requests:
            task = asyncio.create_task(
                self.create_document_async(request)
            )
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful = []
        failed = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed.append({
                    "request": document_requests[i],
                    "error": str(result)
                })
            else:
                successful.append(result)

        return {
            "successful": successful,
            "failed": failed,
            "total_processed": len(document_requests),
            "success_rate": len(successful) / len(document_requests)
        }

# Usage
async def main():
    requests = [
        {"type": "factura", "data": {...}},
        {"type": "boleta", "data": {...}},
        # ... more requests
    ]

    async with AsyncDTEProcessor(max_workers=8) as processor:
        results = await processor.process_batch_async(requests)

        print(f"Processed {results['total_processed']} documents")
        print(f"Success rate: {results['success_rate']:.2%}")

# Run
if __name__ == "__main__":
    asyncio.run(main())
```

---

## Security Best Practices

### Certificate Management

```python
# certificate_security.py
import os
import stat
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import datetime

class SecureCertificateManager:
    def __init__(self, certificate_dir="/etc/ssl/certificates"):
        self.certificate_dir = Path(certificate_dir)
        self.ensure_secure_directory()

    def ensure_secure_directory(self):
        """Ensure certificate directory has proper permissions"""
        if not self.certificate_dir.exists():
            self.certificate_dir.mkdir(mode=0o700, parents=True)

        # Check and fix permissions
        current_mode = self.certificate_dir.stat().st_mode
        if stat.S_IMODE(current_mode) != 0o700:
            self.certificate_dir.chmod(0o700)

    def validate_certificate(self, cert_path, key_path=None):
        """Validate certificate and optionally private key"""
        try:
            # Load and validate certificate
            with open(cert_path, 'rb') as f:
                cert_data = f.read()

            cert = x509.load_pem_x509_certificate(cert_data, default_backend())

            # Check expiration
            now = datetime.datetime.utcnow()
            if cert.not_valid_after < now:
                raise ValueError("Certificate has expired")

            if cert.not_valid_before > now:
                raise ValueError("Certificate is not yet valid")

            # Warning for certificates expiring soon
            days_until_expiry = (cert.not_valid_after - now).days
            if days_until_expiry < 30:
                print(f"WARNING: Certificate expires in {days_until_expiry} days")

            # Validate private key if provided
            if key_path and Path(key_path).exists():
                self._validate_key_permissions(key_path)

            return True

        except Exception as e:
            raise ValueError(f"Certificate validation failed: {str(e)}")

    def _validate_key_permissions(self, key_path):
        """Ensure private key has secure permissions"""
        key_stat = Path(key_path).stat()

        # Private key should only be readable by owner
        if stat.S_IMODE(key_stat.st_mode) != 0o600:
            Path(key_path).chmod(0o600)
            print(f"Fixed permissions for {key_path}")

    def install_certificate(self, cert_content, key_content=None, name="default"):
        """Securely install certificate and key"""
        cert_path = self.certificate_dir / f"{name}.pem"

        # Write certificate
        with open(cert_path, 'w') as f:
            f.write(cert_content)
        cert_path.chmod(0o644)

        # Write private key if provided
        if key_content:
            key_path = self.certificate_dir / f"{name}.key"
            with open(key_path, 'w') as f:
                f.write(key_content)
            key_path.chmod(0o600)  # Secure permissions for private key

        # Validate installation
        self.validate_certificate(cert_path, key_path if key_content else None)

        return str(cert_path)

# Usage
cert_manager = SecureCertificateManager()

# Validate existing certificates
try:
    cert_manager.validate_certificate("/path/to/cert.pem", "/path/to/key.pem")
    print("Certificate is valid and secure")
except ValueError as e:
    print(f"Certificate issue: {e}")
```

### Request Validation

```python
# request_validation.py
from marshmallow import Schema, fields, validate, ValidationError
from functools import wraps

class PartySchema(Schema):
    rut = fields.Str(required=True, validate=validate.Regexp(r'^\d{7,8}-[0-9K]$'))
    nombre = fields.Str(required=True, validate=validate.Length(min=1, max=100))

class DetailItemSchema(Schema):
    NmbItem = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    QtyItem = fields.Int(required=True, validate=validate.Range(min=1))
    PrcItem = fields.Int(required=True, validate=validate.Range(min=0))
    UnmdItem = fields.Str(missing="UN", validate=validate.Length(max=4))

class InvoiceSchema(Schema):
    emisor = fields.Nested(PartySchema, required=True)
    receptor = fields.Nested(PartySchema, required=True)
    folio = fields.Int(required=True, validate=validate.Range(min=1))
    fecha_emision = fields.Date(required=True, format='%Y-%m-%d')
    detalle = fields.List(fields.Nested(DetailItemSchema), required=True, validate=validate.Length(min=1))

def validate_request(schema_class):
    """Decorator to validate request data"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract data from request (adjust based on framework)
            if 'request' in kwargs:
                data = kwargs['request'].json
            elif 'data' in kwargs:
                data = kwargs['data']
            else:
                raise ValueError("No data to validate")

            # Validate data
            schema = schema_class()
            try:
                validated_data = schema.load(data)
                kwargs['validated_data'] = validated_data
                return func(*args, **kwargs)
            except ValidationError as e:
                raise ValueError(f"Validation error: {e.messages}")

        return wrapper
    return decorator

# Usage
@validate_request(InvoiceSchema)
def create_invoice_endpoint(request, validated_data):
    # Use validated_data instead of raw request data
    return create_invoice(validated_data)
```

### Rate Limiting

```python
# rate_limiting.py
import time
import threading
from collections import defaultdict, deque

class RateLimiter:
    def __init__(self, requests_per_minute=60, requests_per_hour=1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_windows = defaultdict(deque)
        self.hour_windows = defaultdict(deque)
        self.lock = threading.Lock()

    def is_allowed(self, client_id):
        """Check if request is allowed for client"""
        with self.lock:
            now = time.time()

            # Clean old entries
            self._clean_old_entries(client_id, now)

            # Check limits
            minute_count = len(self.minute_windows[client_id])
            hour_count = len(self.hour_windows[client_id])

            if minute_count >= self.requests_per_minute:
                return False, f"Rate limit exceeded: {minute_count} requests in last minute"

            if hour_count >= self.requests_per_hour:
                return False, f"Rate limit exceeded: {hour_count} requests in last hour"

            # Record request
            self.minute_windows[client_id].append(now)
            self.hour_windows[client_id].append(now)

            return True, f"Request allowed: {minute_count + 1}/{self.requests_per_minute} per minute, {hour_count + 1}/{self.requests_per_hour} per hour"

    def _clean_old_entries(self, client_id, now):
        """Remove old entries from windows"""
        # Clean minute window (60 seconds)
        minute_window = self.minute_windows[client_id]
        while minute_window and now - minute_window[0] > 60:
            minute_window.popleft()

        # Clean hour window (3600 seconds)
        hour_window = self.hour_windows[client_id]
        while hour_window and now - hour_window[0] > 3600:
            hour_window.popleft()

def rate_limit(requests_per_minute=60, requests_per_hour=1000):
    """Decorator for rate limiting"""
    limiter = RateLimiter(requests_per_minute, requests_per_hour)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract client ID (adjust based on your authentication system)
            client_id = kwargs.get('client_id') or 'default'

            allowed, message = limiter.is_allowed(client_id)
            if not allowed:
                raise Exception(f"Rate limit exceeded: {message}")

            return func(*args, **kwargs)
        return wrapper
    return decorator

# Usage
@rate_limit(requests_per_minute=100, requests_per_hour=2000)
def create_document_with_rate_limit(data, client_id):
    # Document creation logic
    pass
```

---

## Testing Strategies

### Unit Testing

```python
# test_dte_creation.py
import pytest
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente

class TestDTECreation:
    def setup_method(self):
        """Setup for each test"""
        self.factory = DTEFactory()
        self.emisor = Contribuyente("76354771-K", "Test Company")
        self.receptor = Contribuyente("12345678-9", "Test Client")

    def test_create_basic_factura(self):
        """Test basic invoice creation"""
        factura = self.factory.create_factura_afecta(
            emisor=self.emisor,
            receptor=self.receptor,
            folio=1001,
            fecha_emision="2023-12-01",
            detalle=[
                {"NmbItem": "Test Product", "QtyItem": 1, "PrcItem": 1000}
            ]
        )

        assert factura is not None
        assert factura.get_id() == "76354771-K_T033F000001001"
        assert factura.get_rut_emisor() == "76354771-K"

    def test_factura_xml_generation(self):
        """Test XML generation for invoice"""
        factura = self.factory.create_factura_afecta(
            emisor=self.emisor,
            receptor=self.receptor,
            folio=1001,
            fecha_emision="2023-12-01",
            detalle=[
                {"NmbItem": "Test Product", "QtyItem": 1, "PrcItem": 1000}
            ]
        )

        xml = factura.save_xml()
        assert xml is not None
        assert "DTE" in xml
        assert "Documento" in xml
        assert "76354771-K" in xml

    def test_invalid_rut_validation(self):
        """Test RUT validation"""
        with pytest.raises(ValueError):
            Contribuyente("invalid-rut", "Test Company")

    def test_empty_detalle_validation(self):
        """Test empty detail validation"""
        with pytest.raises(ValueError):
            self.factory.create_factura_afecta(
                emisor=self.emisor,
                receptor=self.receptor,
                folio=1001,
                fecha_emision="2023-12-01",
                detalle=[]  # Empty detail should fail
            )

    @pytest.mark.parametrize("document_type,folio", [
        ("factura_afecta", 1001),
        ("boleta_afecta", 2001),
        ("nota_credito", 3001),
    ])
    def test_multiple_document_types(self, document_type, folio):
        """Test creation of different document types"""
        if document_type == "factura_afecta":
            doc = self.factory.create_factura_afecta(
                emisor=self.emisor,
                receptor=self.receptor,
                folio=folio,
                fecha_emision="2023-12-01",
                detalle=[{"NmbItem": "Test", "QtyItem": 1, "PrcItem": 1000}]
            )
        elif document_type == "boleta_afecta":
            doc = self.factory.create_boleta_afecta(
                emisor=self.emisor,
                receptor=self.receptor,
                folio=folio,
                fecha_emision="2023-12-01",
                detalle=[{"NmbItem": "Test", "QtyItem": 1, "PrcItem": 1000}]
            )
        elif document_type == "nota_credito":
            doc = self.factory.create_nota_credito(
                emisor=self.emisor,
                receptor=self.receptor,
                folio=folio,
                fecha_emision="2023-12-01",
                detalle=[{"NmbItem": "Test", "QtyItem": 1, "PrcItem": -1000}],
                documento_referencia={
                    "TpoDocRef": 33,
                    "FolioRef": 1001,
                    "CodRef": 1
                }
            )

        assert doc is not None
        assert str(folio) in doc.get_id()
```

### Integration Testing

```python
# test_integration.py
import pytest
import requests
import time
from pathlib import Path

class TestAPIIntegration:
    @pytest.fixture(scope="class")
    def api_base_url(self):
        """API base URL for testing"""
        return "http://localhost:8000"

    @pytest.fixture(scope="class")
    def test_data(self):
        """Sample test data"""
        return {
            "emisor": {"rut": "76354771-K", "nombre": "Test Company"},
            "receptor": {"rut": "12345678-9", "nombre": "Test Client"},
            "folio": int(time.time()),  # Unique folio
            "fecha_emision": "2023-12-01",
            "detalle": [
                {"NmbItem": "Test Product", "QtyItem": 1, "PrcItem": 1000}
            ]
        }

    def test_health_endpoint(self, api_base_url):
        """Test API health check"""
        response = requests.get(f"{api_base_url}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_create_factura_api(self, api_base_url, test_data):
        """Test factura creation via API"""
        response = requests.post(
            f"{api_base_url}/api/v1/documents/factura",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "document_id" in result
        assert "xml" in result

    def test_invalid_data_handling(self, api_base_url):
        """Test API error handling for invalid data"""
        invalid_data = {"invalid": "data"}

        response = requests.post(
            f"{api_base_url}/api/v1/documents/factura",
            json=invalid_data,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 400
        result = response.json()
        assert result["success"] is False
        assert "error" in result

    def test_rate_limiting(self, api_base_url, test_data):
        """Test API rate limiting"""
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = requests.post(
                f"{api_base_url}/api/v1/documents/factura",
                json=test_data,
                headers={"Content-Type": "application/json"}
            )
            responses.append(response)
            time.sleep(0.1)

        # Should have some successful requests
        successful = [r for r in responses if r.status_code == 200]
        assert len(successful) > 0

        # May have rate limited requests (429)
        rate_limited = [r for r in responses if r.status_code == 429]
        # This depends on your rate limiting configuration
```

### Load Testing

```python
# load_test.py
import asyncio
import aiohttp
import time
import statistics
from concurrent.futures import ThreadPoolExecutor

class LoadTester:
    def __init__(self, base_url, max_concurrent=50):
        self.base_url = base_url
        self.max_concurrent = max_concurrent
        self.results = []

    async def single_request(self, session, data):
        """Make a single request and record timing"""
        start_time = time.time()

        try:
            async with session.post(
                f"{self.base_url}/api/v1/documents/factura",
                json=data,
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                end_time = time.time()

                return {
                    "success": response.status == 200,
                    "status_code": response.status,
                    "response_time": end_time - start_time,
                    "error": None if response.status == 200 else result.get("error")
                }
        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "status_code": 0,
                "response_time": end_time - start_time,
                "error": str(e)
            }

    async def run_load_test(self, total_requests=1000, requests_per_second=10):
        """Run load test with specified parameters"""
        print(f"Starting load test: {total_requests} requests at {requests_per_second} RPS")

        # Calculate delay between requests
        delay = 1.0 / requests_per_second

        # Test data template
        base_data = {
            "emisor": {"rut": "76354771-K", "nombre": "Test Company"},
            "receptor": {"rut": "12345678-9", "nombre": "Test Client"},
            "fecha_emision": "2023-12-01",
            "detalle": [
                {"NmbItem": "Load Test Product", "QtyItem": 1, "PrcItem": 1000}
            ]
        }

        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=self.max_concurrent)
        ) as session:

            tasks = []
            start_time = time.time()

            for i in range(total_requests):
                # Create unique folio for each request
                data = base_data.copy()
                data["folio"] = 10000 + i

                # Create task
                task = asyncio.create_task(self.single_request(session, data))
                tasks.append(task)

                # Rate limiting
                if (i + 1) % requests_per_second == 0:
                    await asyncio.sleep(delay * requests_per_second)

            # Wait for all requests to complete
            self.results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time

            self.analyze_results(total_time)

    def analyze_results(self, total_time):
        """Analyze load test results"""
        successful = [r for r in self.results if r["success"]]
        failed = [r for r in self.results if not r["success"]]

        response_times = [r["response_time"] for r in self.results]

        print("\n=== Load Test Results ===")
        print(f"Total requests: {len(self.results)}")
        print(f"Successful: {len(successful)} ({len(successful)/len(self.results)*100:.1f}%)")
        print(f"Failed: {len(failed)} ({len(failed)/len(self.results)*100:.1f}%)")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Actual RPS: {len(self.results)/total_time:.2f}")

        if response_times:
            print(f"\nResponse Time Statistics:")
            print(f"Min: {min(response_times):.3f}s")
            print(f"Max: {max(response_times):.3f}s")
            print(f"Mean: {statistics.mean(response_times):.3f}s")
            print(f"Median: {statistics.median(response_times):.3f}s")
            print(f"95th percentile: {self.percentile(response_times, 95):.3f}s")
            print(f"99th percentile: {self.percentile(response_times, 99):.3f}s")

        # Error analysis
        if failed:
            print(f"\nError Analysis:")
            error_counts = {}
            for result in failed:
                error = result.get("error", "Unknown")
                error_counts[error] = error_counts.get(error, 0) + 1

            for error, count in error_counts.items():
                print(f"  {error}: {count} occurrences")

    def percentile(self, data, percent):
        """Calculate percentile"""
        data_sorted = sorted(data)
        index = (percent / 100) * len(data_sorted)

        if index.is_integer():
            return data_sorted[int(index) - 1]
        else:
            lower = data_sorted[int(index)]
            upper = data_sorted[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

# Usage
async def main():
    tester = LoadTester("http://localhost:8000", max_concurrent=50)

    # Test scenarios
    scenarios = [
        {"total_requests": 100, "requests_per_second": 5},   # Light load
        {"total_requests": 500, "requests_per_second": 20},  # Medium load
        {"total_requests": 1000, "requests_per_second": 50}, # Heavy load
    ]

    for scenario in scenarios:
        print(f"\n{'='*50}")
        await tester.run_load_test(**scenario)
        await asyncio.sleep(5)  # Rest between tests

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Deployment Patterns

### Blue-Green Deployment

```bash
#!/bin/bash
# blue_green_deploy.sh

# Configuration
DOCKER_REGISTRY="your-registry.com"
APP_NAME="dte-service"
NEW_VERSION=$1
HEALTH_CHECK_URL="http://localhost:8000/health"
TIMEOUT=300

if [ -z "$NEW_VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

# Current active environment
CURRENT=$(docker ps --filter "name=${APP_NAME}" --filter "status=running" --format "{{.Names}}" | head -1)

if [[ $CURRENT == *"blue"* ]]; then
    ACTIVE="blue"
    STANDBY="green"
else
    ACTIVE="green"
    STANDBY="blue"
fi

echo "Current active: $ACTIVE"
echo "Deploying to: $STANDBY"

# Stop standby container if running
docker stop ${APP_NAME}-${STANDBY} 2>/dev/null || true
docker rm ${APP_NAME}-${STANDBY} 2>/dev/null || true

# Deploy new version to standby
echo "Deploying version $NEW_VERSION to $STANDBY environment..."
docker run -d \
    --name ${APP_NAME}-${STANDBY} \
    --network app-network \
    -p 808${STANDBY:0:1}:8000 \
    -v ./certificates:/etc/ssl/certificates:ro \
    -v ./config.prod.yaml:/app/config.yaml:ro \
    -e RYPSYSTEMS_DTE_ENVIRONMENT=production \
    ${DOCKER_REGISTRY}/${APP_NAME}:${NEW_VERSION}

# Health check
echo "Waiting for $STANDBY environment to be ready..."
for i in $(seq 1 $TIMEOUT); do
    if curl -f ${HEALTH_CHECK_URL/8000/808${STANDBY:0:1}} >/dev/null 2>&1; then
        echo "$STANDBY environment is healthy"
        break
    fi

    if [ $i -eq $TIMEOUT ]; then
        echo "Health check failed for $STANDBY environment"
        docker logs ${APP_NAME}-${STANDBY}
        exit 1
    fi

    sleep 1
done

# Switch traffic (update load balancer or reverse proxy)
echo "Switching traffic to $STANDBY environment..."
# Update nginx/haproxy/cloudflare configuration
./update_load_balancer.sh $STANDBY

# Verify traffic switch
sleep 10
if curl -f $HEALTH_CHECK_URL >/dev/null 2>&1; then
    echo "Traffic successfully switched to $STANDBY"

    # Stop old environment
    echo "Stopping old $ACTIVE environment..."
    docker stop ${APP_NAME}-${ACTIVE}
    docker rm ${APP_NAME}-${ACTIVE}

    echo "Deployment successful!"
else
    echo "Health check failed after traffic switch, rolling back..."
    ./update_load_balancer.sh $ACTIVE
    docker stop ${APP_NAME}-${STANDBY}
    docker rm ${APP_NAME}-${STANDBY}
    exit 1
fi
```

### Rolling Deployment with Kubernetes

```yaml
# k8s-rolling-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dte-service
  labels:
    app: dte-service
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: dte-service
  template:
    metadata:
      labels:
        app: dte-service
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: dte-service
        image: your-registry/dte-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: RYPSYSTEMS_DTE_ENVIRONMENT
          value: "production"
        - name: RYPSYSTEMS_DTE_SII_ENVIRONMENT
          value: "produccion"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: dte-secrets
              key: database-url
        volumeMounts:
        - name: certificates
          mountPath: /etc/ssl/certificates
          readOnly: true
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
          readOnly: true
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
      volumes:
      - name: certificates
        secret:
          secretName: sii-certificates
          defaultMode: 0600
      - name: config
        configMap:
          name: dte-config
      imagePullSecrets:
      - name: registry-secret

---
# Service
apiVersion: v1
kind: Service
metadata:
  name: dte-service
  labels:
    app: dte-service
spec:
  selector:
    app: dte-service
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dte-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dte-service
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy DTE Service

on:
  push:
    branches: [main]
    tags: ['v*']

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -e .

    - name: Run tests
      run: |
        python -m pytest tests/ -v --cov=rypsystems_dte

    - name: Security scan
      run: |
        pip install bandit safety
        bandit -r src/
        safety check

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
    - uses: actions/checkout@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v2
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}

    - name: Build and push Docker image
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: staging

    steps:
    - name: Deploy to staging
      run: |
        # Deploy to staging environment
        kubectl set image deployment/dte-service \
          dte-service=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:main \
          --namespace=staging

        kubectl rollout status deployment/dte-service --namespace=staging

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    environment: production

    steps:
    - name: Deploy to production
      run: |
        # Blue-green deployment to production
        kubectl set image deployment/dte-service \
          dte-service=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.ref_name }} \
          --namespace=production

        kubectl rollout status deployment/dte-service --namespace=production

        # Run smoke tests
        kubectl run smoke-test --rm -i --restart=Never \
          --image=appropriate/curl \
          -- curl -f http://dte-service.production.svc.cluster.local/health
```

---

## Migration Guides

### From LibreDTE to RypSystems DTE

```python
# migration_libredte_to_rypsystems.py
"""
Migration guide from LibreDTE PHP to RypSystems DTE Python
"""

# LibreDTE PHP equivalent
"""
$LibreDTE = new \sasco\LibreDTE\Sii();
$emisor = new \sasco\LibreDTE\Sii\Contribuyente('76354771-K');
$receptor = new \sasco\LibreDTE\Sii\Contribuyente('12345678-9');

$dte = new \sasco\LibreDTE\Sii\Dte\Documento\DTE();
$dte->setEmisor($emisor);
$dte->setReceptor($receptor);
$dte->setTipo(33); // Factura
$dte->setFolio(1001);
$dte->setFecha('2023-12-01');
$dte->agregarItem([
    'NmbItem' => 'Producto',
    'QtyItem' => 1,
    'PrcItem' => 1000
]);

$xml = $dte->generar();
"""

# RypSystems DTE Python equivalent
from rypsystems_dte.dte.factory import DTEFactory
from rypsystems_dte.sii.base import Contribuyente

# Create factory and parties
factory = DTEFactory()
emisor = Contribuyente("76354771-K", "Mi Empresa")
receptor = Contribuyente("12345678-9", "Cliente")

# Create document
factura = factory.create_factura_afecta(
    emisor=emisor,
    receptor=receptor,
    folio=1001,
    fecha_emision="2023-12-01",
    detalle=[
        {"NmbItem": "Producto", "QtyItem": 1, "PrcItem": 1000}
    ]
)

# Generate XML
xml = factura.save_xml()

class LibreDTEMigrator:
    """Helper class for migrating from LibreDTE patterns"""

    def __init__(self):
        self.factory = DTEFactory()

    def migrate_document(self, libredte_data):
        """Convert LibreDTE data structure to RypSystems format"""

        # Map document types
        type_mapping = {
            33: "factura_afecta",
            39: "boleta_afecta",
            61: "nota_credito",
            56: "nota_debito"
        }

        doc_type = type_mapping.get(libredte_data.get("tipo"))
        if not doc_type:
            raise ValueError(f"Unsupported document type: {libredte_data.get('tipo')}")

        # Convert parties
        emisor = Contribuyente(
            libredte_data["emisor"]["rut"],
            libredte_data["emisor"]["razon_social"]
        )
        receptor = Contribuyente(
            libredte_data["receptor"]["rut"],
            libredte_data["receptor"]["razon_social"]
        )

        # Convert detail items
        detalle = []
        for item in libredte_data["detalle"]:
            detalle.append({
                "NmbItem": item["NmbItem"],
                "QtyItem": item["QtyItem"],
                "PrcItem": item["PrcItem"],
                "UnmdItem": item.get("UnmdItem", "UN")
            })

        # Create document based on type
        if doc_type == "factura_afecta":
            return self.factory.create_factura_afecta(
                emisor=emisor,
                receptor=receptor,
                folio=libredte_data["folio"],
                fecha_emision=libredte_data["fecha"],
                detalle=detalle
            )
        elif doc_type == "boleta_afecta":
            return self.factory.create_boleta_afecta(
                emisor=emisor,
                receptor=receptor,
                folio=libredte_data["folio"],
                fecha_emision=libredte_data["fecha"],
                detalle=detalle
            )
        # Add other document types as needed

    def migrate_configuration(self, libredte_config):
        """Convert LibreDTE configuration to RypSystems format"""

        rypsystems_config = {
            "environment": "development" if libredte_config.get("certificacion") else "production",
            "sii": {
                "environment": "certificacion" if libredte_config.get("certificacion") else "produccion",
                "authentication": {
                    "certificate_path": libredte_config.get("certificado"),
                    "private_key_path": libredte_config.get("private_key"),
                    "rut_contribuyente": libredte_config.get("rut")
                }
            }
        }

        return rypsystems_config

# Usage example
migrator = LibreDTEMigrator()

# Sample LibreDTE data structure
libredte_data = {
    "tipo": 33,
    "folio": 1001,
    "fecha": "2023-12-01",
    "emisor": {
        "rut": "76354771-K",
        "razon_social": "Mi Empresa SpA"
    },
    "receptor": {
        "rut": "12345678-9",
        "razon_social": "Cliente SPA"
    },
    "detalle": [
        {
            "NmbItem": "Producto Migrado",
            "QtyItem": 1,
            "PrcItem": 1000
        }
    ]
}

# Migrate document
document = migrator.migrate_document(libredte_data)
print(f"Migrated document ID: {document.get_id()}")
```

This comprehensive integration guide provides practical examples and patterns for integrating RypSystems DTE with any backend system. The examples demonstrate real-world usage patterns and best practices for production deployment.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Create comprehensive API documentation for multi-language client integration", "status": "completed", "activeForm": "Creating comprehensive API documentation for multi-language client integration"}]