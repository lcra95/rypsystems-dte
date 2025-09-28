# RypSystems DTE - Production Deployment Guide

**Complete production deployment guide for enterprise environments**

## Table of Contents

1. [Production Readiness Checklist](#production-readiness-checklist)
2. [Infrastructure Requirements](#infrastructure-requirements)
3. [Security Configuration](#security-configuration)
4. [Environment Setup](#environment-setup)
5. [Monitoring and Observability](#monitoring-and-observability)
6. [High Availability Setup](#high-availability-setup)
7. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
8. [Performance Tuning](#performance-tuning)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Maintenance Procedures](#maintenance-procedures)

---

## Production Readiness Checklist

### Pre-Deployment Validation

- [ ] **Certificates Configured**
  - [ ] SII production certificates installed
  - [ ] Certificate expiration monitoring set up
  - [ ] Private key permissions secured (600)
  - [ ] Certificate chain validated

- [ ] **Configuration Validated**
  - [ ] Production configuration file created
  - [ ] Environment variables secured
  - [ ] Feature flags configured for production
  - [ ] Database connections tested

- [ ] **Security Measures**
  - [ ] TLS/SSL enabled for all connections
  - [ ] Rate limiting configured
  - [ ] Input validation implemented
  - [ ] Secrets management configured
  - [ ] Access controls implemented

- [ ] **Performance Optimization**
  - [ ] Connection pooling configured
  - [ ] Caching strategy implemented
  - [ ] Resource limits set
  - [ ] Load balancing configured

- [ ] **Monitoring Setup**
  - [ ] Health checks implemented
  - [ ] Metrics collection configured
  - [ ] Alerting rules defined
  - [ ] Log aggregation set up

- [ ] **Backup Strategy**
  - [ ] Configuration backup procedure
  - [ ] Certificate backup procedure
  - [ ] Database backup strategy
  - [ ] Recovery procedures tested

### Post-Deployment Validation

- [ ] **Functional Testing**
  - [ ] Document creation tested
  - [ ] SII integration verified
  - [ ] Error handling validated
  - [ ] Performance benchmarks met

- [ ] **Security Testing**
  - [ ] Vulnerability scan completed
  - [ ] Penetration testing performed
  - [ ] Certificate validation confirmed
  - [ ] Access controls verified

- [ ] **Monitoring Validation**
  - [ ] Metrics are being collected
  - [ ] Alerts are firing correctly
  - [ ] Logs are being aggregated
  - [ ] Health checks are passing

---

## Infrastructure Requirements

### Minimum Production Requirements

```yaml
# Minimum Infrastructure Specifications
compute:
  cpu: 2 cores
  memory: 4 GB RAM
  disk: 20 GB SSD
  network: 1 Gbps

software:
  os: Ubuntu 20.04 LTS or CentOS 8
  python: 3.9+
  reverse_proxy: nginx or Apache
  monitoring: Prometheus + Grafana

security:
  tls: 1.2+
  firewall: enabled
  intrusion_detection: fail2ban
  log_monitoring: rsyslog + centralized logging
```

### Recommended Production Architecture

```
                    Internet
                        │
                ┌───────┴────────┐
                │  Load Balancer │
                │   (HAProxy)    │
                └───────┬────────┘
                        │
            ┌───────────┴───────────┐
            │                       │
    ┌───────▼────────┐    ┌────────▼────────┐
    │   App Server   │    │   App Server    │
    │   (DTE API)    │    │   (DTE API)     │
    └───────┬────────┘    └────────┬────────┘
            │                      │
            └───────────┬──────────┘
                        │
        ┌───────────────▼────────────────┐
        │                                │
┌───────▼─────┐  ┌─────────▼─────┐  ┌────▼─────┐
│   Redis     │  │  PostgreSQL   │  │  SII     │
│  (Cache)    │  │ (Persistence) │  │ Service  │
└─────────────┘  └───────────────┘  └──────────┘
```

### Container Deployment (Docker)

```dockerfile
# Production Dockerfile
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r dte && useradd -r -g dte dte

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .
RUN pip install -e .

# Create necessary directories
RUN mkdir -p /var/log/rypsystems_dte /etc/ssl/certificates \
    && chown -R dte:dte /var/log/rypsystems_dte /etc/ssl/certificates

# Security configurations
RUN chmod 700 /etc/ssl/certificates

# Switch to non-root user
USER dte

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "gevent", "app:app"]
```

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  dte-api:
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - RYPSYSTEMS_DTE_ENVIRONMENT=production
      - RYPSYSTEMS_DTE_SII_ENVIRONMENT=produccion
      - RYPSYSTEMS_DTE_LOG_LEVEL=WARNING
      - DATABASE_URL=postgresql://dte_user:${DB_PASSWORD}@postgres:5432/dte_prod
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./certificates:/etc/ssl/certificates:ro
      - ./config.prod.yaml:/app/config.yaml:ro
      - ./logs:/var/log/rypsystems_dte
    depends_on:
      - postgres
      - redis
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - dte-api

  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: dte_prod
      POSTGRES_USER: dte_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres-backup:/backup
    deploy:
      resources:
        limits:
          memory: 2G

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    deploy:
      resources:
        limits:
          memory: 512M

  prometheus:
    image: prom/prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

### Kubernetes Deployment

```yaml
# k8s-production.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: dte-production

---
apiVersion: v1
kind: Secret
metadata:
  name: dte-secrets
  namespace: dte-production
type: Opaque
data:
  database-url: <base64-encoded-database-url>
  redis-password: <base64-encoded-redis-password>
  sii-certificate: <base64-encoded-certificate>
  sii-private-key: <base64-encoded-private-key>

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: dte-config
  namespace: dte-production
data:
  config.yaml: |
    environment: "production"
    debug: false
    sii:
      environment: "produccion"
      verify_ssl: true
      rate_limit:
        enabled: true
        requests_per_minute: 100
        requests_per_hour: 2000
    logging:
      level: "WARNING"
      format: "json"
      output: "console"
    security:
      validate_certificates: true
    features:
      beta_features: false
      production_optimizations: true

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dte-api
  namespace: dte-production
  labels:
    app: dte-api
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: dte-api
  template:
    metadata:
      labels:
        app: dte-api
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
      containers:
      - name: dte-api
        image: your-registry/dte-api:latest
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
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: dte-secrets
              key: redis-password
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
          readOnly: true
        - name: certificates
          mountPath: /etc/ssl/certificates
          readOnly: true
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
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
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
      volumes:
      - name: config
        configMap:
          name: dte-config
      - name: certificates
        secret:
          secretName: dte-secrets
          items:
          - key: sii-certificate
            path: sii.pem
            mode: 0644
          - key: sii-private-key
            path: sii.key
            mode: 0600

---
apiVersion: v1
kind: Service
metadata:
  name: dte-api-service
  namespace: dte-production
  labels:
    app: dte-api
spec:
  selector:
    app: dte-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dte-api-hpa
  namespace: dte-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dte-api
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

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: dte-api-ingress
  namespace: dte-production
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
  - hosts:
    - api.yourcompany.com
    secretName: dte-api-tls
  rules:
  - host: api.yourcompany.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: dte-api-service
            port:
              number: 80
```

---

## Security Configuration

### TLS/SSL Configuration

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    upstream dte_backend {
        server dte-api:8000;
        keepalive 32;
    }

    server {
        listen 80;
        server_name api.yourcompany.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name api.yourcompany.com;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # Security
        client_max_body_size 10M;

        # Rate limiting
        limit_req zone=api burst=20 nodelay;

        location / {
            proxy_pass http://dte_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        location /health {
            proxy_pass http://dte_backend;
            access_log off;
        }
    }
}
```

### Environment Variables Security

```bash
#!/bin/bash
# secure_env_setup.sh

# Create secure environment file
cat > .env.production << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://dte_user:SECURE_PASSWORD@postgres:5432/dte_prod
DB_PASSWORD=SECURE_DB_PASSWORD

# Redis Configuration
REDIS_URL=redis://:SECURE_REDIS_PASSWORD@redis:6379/0
REDIS_PASSWORD=SECURE_REDIS_PASSWORD

# SII Configuration
RYPSYSTEMS_DTE_ENVIRONMENT=production
RYPSYSTEMS_DTE_SII_ENVIRONMENT=produccion
RYPSYSTEMS_DTE_SII_CERTIFICATE_PATH=/etc/ssl/certificates/sii.pem
RYPSYSTEMS_DTE_SII_PRIVATE_KEY_PATH=/etc/ssl/certificates/sii.key
RYPSYSTEMS_DTE_SII_RUT_CONTRIBUYENTE=YOUR_RUT_HERE

# Security
RYPSYSTEMS_DTE_LOG_SENSITIVE_DATA=false
RYPSYSTEMS_DTE_SECURITY_VALIDATE_CERTIFICATES=true

# Monitoring
GRAFANA_PASSWORD=SECURE_GRAFANA_PASSWORD
PROMETHEUS_USER=admin
PROMETHEUS_PASSWORD=SECURE_PROMETHEUS_PASSWORD
EOF

# Secure the file
chmod 600 .env.production
chown dte:dte .env.production

# Generate random passwords
openssl rand -base64 32 > db_password.txt
openssl rand -base64 32 > redis_password.txt
openssl rand -base64 32 > grafana_password.txt

echo "Environment file created with secure permissions"
echo "Update .env.production with the generated passwords"
```

### Certificate Management

```bash
#!/bin/bash
# certificate_management.sh

CERT_DIR="/etc/ssl/certificates"
BACKUP_DIR="/backup/certificates"

# Create directories
mkdir -p $CERT_DIR $BACKUP_DIR
chmod 700 $CERT_DIR

# Function to install certificate
install_certificate() {
    local cert_file=$1
    local key_file=$2
    local name=$3

    if [ ! -f "$cert_file" ] || [ ! -f "$key_file" ]; then
        echo "Certificate or key file not found"
        exit 1
    fi

    # Validate certificate
    openssl x509 -in "$cert_file" -text -noout > /dev/null
    if [ $? -ne 0 ]; then
        echo "Invalid certificate format"
        exit 1
    fi

    # Install with secure permissions
    cp "$cert_file" "$CERT_DIR/${name}.pem"
    cp "$key_file" "$CERT_DIR/${name}.key"

    chmod 644 "$CERT_DIR/${name}.pem"
    chmod 600 "$CERT_DIR/${name}.key"
    chown dte:dte "$CERT_DIR/${name}."*

    echo "Certificate $name installed successfully"
}

# Function to check certificate expiration
check_certificate_expiration() {
    local cert_file=$1
    local warning_days=${2:-30}

    local expiry_date=$(openssl x509 -in "$cert_file" -enddate -noout | cut -d= -f2)
    local expiry_epoch=$(date -d "$expiry_date" +%s)
    local current_epoch=$(date +%s)
    local days_remaining=$(( (expiry_epoch - current_epoch) / 86400 ))

    if [ $days_remaining -lt 0 ]; then
        echo "CRITICAL: Certificate has expired"
        return 2
    elif [ $days_remaining -lt $warning_days ]; then
        echo "WARNING: Certificate expires in $days_remaining days"
        return 1
    else
        echo "Certificate is valid for $days_remaining days"
        return 0
    fi
}

# Function to backup certificates
backup_certificates() {
    local backup_file="$BACKUP_DIR/certificates_$(date +%Y%m%d_%H%M%S).tar.gz"

    tar -czf "$backup_file" -C "$CERT_DIR" .
    chmod 600 "$backup_file"

    echo "Certificates backed up to $backup_file"

    # Keep only last 30 backups
    find "$BACKUP_DIR" -name "certificates_*.tar.gz" -type f -mtime +30 -delete
}

# Main execution
case "$1" in
    install)
        install_certificate "$2" "$3" "$4"
        ;;
    check)
        check_certificate_expiration "$2" "$3"
        ;;
    backup)
        backup_certificates
        ;;
    *)
        echo "Usage: $0 {install|check|backup} [args...]"
        echo "  install <cert_file> <key_file> <name>"
        echo "  check <cert_file> [warning_days]"
        echo "  backup"
        exit 1
        ;;
esac
```

---

## Environment Setup

### Production Configuration

```yaml
# config.production.yaml
environment: "production"
debug: false

# Logging Configuration
logging:
  level: "WARNING"
  format: "json"
  output: "file"
  file_path: "/var/log/rypsystems_dte/production.log"
  max_file_size: 10485760  # 10MB
  backup_count: 10
  console_output: false

# SII Configuration
sii:
  environment: "produccion"

  authentication:
    certificate_path: "/etc/ssl/certificates/sii.pem"
    private_key_path: "/etc/ssl/certificates/sii.key"
    rut_contribuyente: "${RYPSYSTEMS_DTE_SII_RUT_CONTRIBUYENTE}"
    resolucion_numero: 123
    resolucion_fecha: "2023-01-01"
    token_lifetime: 21600  # 6 hours
    auto_refresh_token: true

  # Connection settings
  connection_timeout: 30
  read_timeout: 60
  max_retries: 3
  retry_delay: 2.0
  verify_ssl: true

  # Rate limiting
  rate_limit:
    enabled: true
    requests_per_minute: 100
    requests_per_hour: 2000
    burst_limit: 20
    backoff_factor: 2.0
    max_backoff: 120

  # Security
  log_requests: true
  log_responses: false
  log_sensitive_data: false

# Database Configuration
database:
  host: "${DATABASE_HOST:-postgres}"
  port: 5432
  database: "dte_prod"
  username: "dte_user"
  password: "${DB_PASSWORD}"
  ssl_mode: "require"
  pool_size: 20
  pool_timeout: 30
  pool_recycle: 3600

# Cache Configuration
cache:
  enabled: true
  backend: "redis"
  redis_url: "${REDIS_URL}"
  ttl: 3600
  max_size: 10000
  compression: true

# Security Configuration
security:
  validate_certificates: true
  certificate_path: "/etc/ssl/certificates/"
  ca_bundle_path: "/etc/ssl/certs/ca-certificates.crt"
  encryption_key: "${ENCRYPTION_KEY}"
  token_expiry: 3600
  session_timeout: 1800

# Performance Configuration
performance:
  max_concurrent_requests: 100
  request_timeout: 30
  retry_attempts: 3
  retry_delay: 2.0
  enable_gzip: true
  connection_pool_size: 50
  worker_processes: 4

# Feature Flags
features:
  strict_validation: true
  enhanced_logging: false
  beta_features: false
  production_optimizations: true
  performance_monitoring: true
  cache_optimization: true
  retry_improvements: true

# Monitoring Configuration
monitoring:
  enabled: true
  metrics_endpoint: "/metrics"
  health_endpoint: "/health"
  ready_endpoint: "/ready"
  prometheus_port: 9090

  alerts:
    error_rate_threshold: 0.05  # 5%
    response_time_threshold: 1.0  # 1 second
    memory_usage_threshold: 0.8  # 80%
    cpu_usage_threshold: 0.7   # 70%

# Application Configuration
app:
  name: "RypSystems DTE"
  version: "1.0.0"
  timezone: "America/Santiago"
  locale: "es_CL"
  max_request_size: 10485760  # 10MB

# HTTP Configuration
http:
  user_agent: "RypSystems-DTE/1.0 (Production)"
  additional_headers:
    X-Application: "RypSystems-DTE"
    X-Version: "1.0.0"
    X-Environment: "production"
```

### Database Setup

```sql
-- production_database_setup.sql

-- Create database and user
CREATE DATABASE dte_prod;
CREATE USER dte_user WITH ENCRYPTED PASSWORD 'SECURE_PASSWORD';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE dte_prod TO dte_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dte_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dte_user;

-- Connect to dte_prod database
\c dte_prod;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create tables for tracking and logging
CREATE TABLE IF NOT EXISTS document_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(100) NOT NULL UNIQUE,
    document_type VARCHAR(20) NOT NULL,
    folio INTEGER NOT NULL,
    rut_emisor VARCHAR(12) NOT NULL,
    rut_receptor VARCHAR(12) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'created',
    sii_track_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    xml_content TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS api_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id VARCHAR(100) NOT NULL,
    endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time NUMERIC(10,3) NOT NULL,
    client_ip INET,
    user_agent TEXT,
    request_size INTEGER,
    response_size INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC(15,6) NOT NULL,
    metric_tags JSONB,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_document_tracking_document_id ON document_tracking(document_id);
CREATE INDEX idx_document_tracking_created_at ON document_tracking(created_at);
CREATE INDEX idx_document_tracking_status ON document_tracking(status);
CREATE INDEX idx_api_logs_created_at ON api_logs(created_at);
CREATE INDEX idx_api_logs_endpoint ON api_logs(endpoint);
CREATE INDEX idx_system_metrics_name_time ON system_metrics(metric_name, recorded_at);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_document_tracking_updated_at
    BEFORE UPDATE ON document_tracking
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Set table permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dte_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dte_user;
```

### Application Startup Script

```bash
#!/bin/bash
# start_production.sh

set -euo pipefail

# Configuration
APP_DIR="/app"
LOG_DIR="/var/log/rypsystems_dte"
PID_FILE="/var/run/dte-api.pid"
USER="dte"
GROUP="dte"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_DIR/startup.log"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Do not run as root. Use the dte user."
    exit 1
fi

# Pre-flight checks
pre_flight_checks() {
    log "Starting pre-flight checks..."

    # Check Python version
    python_version=$(python3 --version | cut -d' ' -f2)
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"; then
        log "ERROR: Python 3.9+ required, found $python_version"
        exit 1
    fi
    log "Python version check passed: $python_version"

    # Check configuration file
    if [ ! -f "$APP_DIR/config.yaml" ]; then
        log "ERROR: Configuration file not found: $APP_DIR/config.yaml"
        exit 1
    fi
    log "Configuration file found"

    # Validate configuration
    if ! python3 -c "
import yaml
from rypsystems_dte.config import ConfigManager
try:
    manager = ConfigManager()
    manager.load_from_file('$APP_DIR/config.yaml')
    manager.validate()
    print('Configuration validation passed')
except Exception as e:
    print(f'Configuration validation failed: {e}')
    exit(1)
"; then
        log "ERROR: Configuration validation failed"
        exit 1
    fi
    log "Configuration validation passed"

    # Check certificates
    cert_path=$(python3 -c "
from rypsystems_dte.config import get_config
print(get_config('sii.authentication.certificate_path', ''))
")

    if [ -n "$cert_path" ] && [ ! -f "$cert_path" ]; then
        log "ERROR: Certificate file not found: $cert_path"
        exit 1
    fi
    log "Certificate checks passed"

    # Check database connectivity
    if ! python3 -c "
from rypsystems_dte.config import get_config
import psycopg2
try:
    db_url = get_config('database.url')
    if db_url:
        conn = psycopg2.connect(db_url)
        conn.close()
        print('Database connection successful')
    else:
        print('No database configured')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
"; then
        log "ERROR: Database connectivity check failed"
        exit 1
    fi
    log "Database connectivity check passed"

    # Check Redis connectivity
    if ! python3 -c "
from rypsystems_dte.config import get_config
import redis
try:
    redis_url = get_config('cache.redis_url')
    if redis_url:
        r = redis.Redis.from_url(redis_url)
        r.ping()
        print('Redis connection successful')
    else:
        print('No Redis configured')
except Exception as e:
    print(f'Redis connection failed: {e}')
    exit(1)
"; then
        log "ERROR: Redis connectivity check failed"
        exit 1
    fi
    log "Redis connectivity check passed"

    log "All pre-flight checks passed"
}

# Start application
start_application() {
    log "Starting DTE API application..."

    # Change to app directory
    cd "$APP_DIR"

    # Start with gunicorn
    exec gunicorn \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --worker-class gevent \
        --worker-connections 1000 \
        --max-requests 10000 \
        --max-requests-jitter 1000 \
        --timeout 30 \
        --keep-alive 5 \
        --user "$USER" \
        --group "$GROUP" \
        --pid "$PID_FILE" \
        --access-logfile "$LOG_DIR/access.log" \
        --error-logfile "$LOG_DIR/error.log" \
        --log-level warning \
        --preload \
        app:app
}

# Signal handlers
cleanup() {
    log "Received shutdown signal, cleaning up..."
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid"
            wait "$pid"
        fi
        rm -f "$PID_FILE"
    fi
    log "Cleanup completed"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Main execution
main() {
    # Create log directory if it doesn't exist
    mkdir -p "$LOG_DIR"

    # Run pre-flight checks
    pre_flight_checks

    # Start application
    start_application
}

# Run main function
main "$@"
```

---

## Monitoring and Observability

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'dte-api'
    static_configs:
      - targets: ['dte-api:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis-exporter'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### Alert Rules

```yaml
# alerts.yml
groups:
  - name: dte-api
    rules:
    - alert: DTEAPIDown
      expr: up{job="dte-api"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "DTE API is down"
        description: "DTE API has been down for more than 1 minute"

    - alert: DTEAPIHighErrorRate
      expr: (rate(http_requests_total{job="dte-api",status=~"5.."}[5m]) / rate(http_requests_total{job="dte-api"}[5m])) > 0.05
      for: 2m
      labels:
        severity: critical
      annotations:
        summary: "High error rate in DTE API"
        description: "Error rate is {{ $value | humanizePercentage }} for the last 5 minutes"

    - alert: DTEAPIHighLatency
      expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="dte-api"}[5m])) > 1
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High latency in DTE API"
        description: "95th percentile latency is {{ $value }}s for the last 5 minutes"

    - alert: DTEAPIHighMemoryUsage
      expr: process_resident_memory_bytes{job="dte-api"} / 1024 / 1024 / 1024 > 2
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High memory usage in DTE API"
        description: "Memory usage is {{ $value }}GB"

    - alert: DTECertificateExpiring
      expr: (certificate_expiry_seconds - time()) / 86400 < 30
      for: 1h
      labels:
        severity: warning
      annotations:
        summary: "Certificate expiring soon"
        description: "Certificate {{ $labels.certificate_name }} expires in {{ $value }} days"

    - alert: DTESIIConnectionFailure
      expr: increase(sii_connection_failures_total[1h]) > 10
      for: 0m
      labels:
        severity: critical
      annotations:
        summary: "Multiple SII connection failures"
        description: "{{ $value }} SII connection failures in the last hour"

  - name: infrastructure
    rules:
    - alert: DatabaseDown
      expr: up{job="postgres-exporter"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Database is down"
        description: "PostgreSQL database has been down for more than 1 minute"

    - alert: RedisDown
      expr: up{job="redis-exporter"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Redis is down"
        description: "Redis cache has been down for more than 1 minute"

    - alert: HighDiskUsage
      expr: (node_filesystem_size_bytes{fstype!="tmpfs"} - node_filesystem_avail_bytes{fstype!="tmpfs"}) / node_filesystem_size_bytes{fstype!="tmpfs"} > 0.85
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High disk usage"
        description: "Disk usage is {{ $value | humanizePercentage }} on {{ $labels.device }}"

    - alert: HighCPUUsage
      expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High CPU usage"
        description: "CPU usage is {{ $value }}% on {{ $labels.instance }}"
```

### Custom Metrics

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time
import psutil
from rypsystems_dte.config import get_config

# Define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

DOCUMENT_CREATION_COUNT = Counter(
    'dte_documents_created_total',
    'Total documents created',
    ['document_type', 'status']
)

DOCUMENT_CREATION_DURATION = Histogram(
    'dte_document_creation_duration_seconds',
    'Document creation duration',
    ['document_type']
)

SII_REQUESTS = Counter(
    'sii_requests_total',
    'Total SII requests',
    ['operation', 'status']
)

SII_CONNECTION_FAILURES = Counter(
    'sii_connection_failures_total',
    'Total SII connection failures'
)

CERTIFICATE_EXPIRY = Gauge(
    'certificate_expiry_seconds',
    'Certificate expiry time',
    ['certificate_name']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_database_connections',
    'Active database connections'
)

MEMORY_USAGE = Gauge(
    'process_memory_usage_bytes',
    'Process memory usage in bytes'
)

CPU_USAGE = Gauge(
    'process_cpu_usage_percent',
    'Process CPU usage percentage'
)

class MetricsCollector:
    def __init__(self):
        self.start_time = time.time()

    def track_request(self, method, endpoint, status_code, duration):
        """Track HTTP request metrics"""
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).inc()

        REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

    def track_document_creation(self, document_type, success, duration):
        """Track document creation metrics"""
        status = "success" if success else "failure"

        DOCUMENT_CREATION_COUNT.labels(
            document_type=document_type,
            status=status
        ).inc()

        if success:
            DOCUMENT_CREATION_DURATION.labels(
                document_type=document_type
            ).observe(duration)

    def track_sii_request(self, operation, success):
        """Track SII request metrics"""
        status = "success" if success else "failure"

        SII_REQUESTS.labels(
            operation=operation,
            status=status
        ).inc()

        if not success:
            SII_CONNECTION_FAILURES.inc()

    def update_certificate_expiry(self, cert_name, expiry_seconds):
        """Update certificate expiry metric"""
        CERTIFICATE_EXPIRY.labels(
            certificate_name=cert_name
        ).set(expiry_seconds)

    def update_system_metrics(self):
        """Update system metrics"""
        # Memory usage
        process = psutil.Process()
        memory_info = process.memory_info()
        MEMORY_USAGE.set(memory_info.rss)

        # CPU usage
        cpu_percent = process.cpu_percent()
        CPU_USAGE.set(cpu_percent)

        # Database connections (if configured)
        try:
            db_url = get_config('database.url')
            if db_url:
                # This would require a database connection to get active connections
                # Implementation depends on your database setup
                pass
        except Exception:
            pass

    def get_metrics(self):
        """Get all metrics in Prometheus format"""
        # Update system metrics before returning
        self.update_system_metrics()
        return generate_latest()

# Global metrics collector instance
metrics_collector = MetricsCollector()

# Decorator for tracking function calls
def track_duration(metric_name, labels=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                if metric_name == "document_creation":
                    doc_type = kwargs.get('document_type', 'unknown')
                    metrics_collector.track_document_creation(doc_type, True, duration)

                return result
            except Exception as e:
                duration = time.time() - start_time

                if metric_name == "document_creation":
                    doc_type = kwargs.get('document_type', 'unknown')
                    metrics_collector.track_document_creation(doc_type, False, duration)

                raise
        return wrapper
    return decorator
```

### Health Checks

```python
# health_checks.py
import time
import psutil
from dataclasses import dataclass
from typing import Dict, List, Optional
from rypsystems_dte.config import get_config, ConfigManager
from rypsystems_dte.sii.integration import SiiClient

@dataclass
class HealthCheckResult:
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    duration_ms: float
    message: str
    details: Optional[Dict] = None

class HealthChecker:
    def __init__(self):
        self.checks = [
            self.check_application,
            self.check_configuration,
            self.check_certificates,
            self.check_database,
            self.check_redis,
            self.check_sii_connectivity,
            self.check_system_resources,
            self.check_disk_space,
        ]

    def run_all_checks(self) -> Dict:
        """Run all health checks"""
        results = []
        overall_status = "healthy"
        start_time = time.time()

        for check in self.checks:
            try:
                result = check()
                results.append(result)

                if result.status == "unhealthy":
                    overall_status = "unhealthy"
                elif result.status == "degraded" and overall_status == "healthy":
                    overall_status = "degraded"

            except Exception as e:
                results.append(HealthCheckResult(
                    name=check.__name__,
                    status="unhealthy",
                    duration_ms=0,
                    message=f"Health check failed: {str(e)}"
                ))
                overall_status = "unhealthy"

        total_duration = (time.time() - start_time) * 1000

        return {
            "status": overall_status,
            "timestamp": time.time(),
            "duration_ms": total_duration,
            "checks": [
                {
                    "name": result.name,
                    "status": result.status,
                    "duration_ms": result.duration_ms,
                    "message": result.message,
                    "details": result.details
                }
                for result in results
            ]
        }

    def check_application(self) -> HealthCheckResult:
        """Check basic application health"""
        start_time = time.time()

        try:
            # Basic import test
            from rypsystems_dte.dte.factory import DTEFactory
            factory = DTEFactory()

            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="application",
                status="healthy",
                duration_ms=duration_ms,
                message="Application is running normally"
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name="application",
                status="unhealthy",
                duration_ms=duration_ms,
                message=f"Application check failed: {str(e)}"
            )

    def check_configuration(self) -> HealthCheckResult:
        """Check configuration validity"""
        start_time = time.time()

        try:
            config_manager = ConfigManager()
            config_manager.validate()

            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="configuration",
                status="healthy",
                duration_ms=duration_ms,
                message="Configuration is valid"
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name="configuration",
                status="unhealthy",
                duration_ms=duration_ms,
                message=f"Configuration validation failed: {str(e)}"
            )

    def check_certificates(self) -> HealthCheckResult:
        """Check certificate validity and expiration"""
        start_time = time.time()

        try:
            cert_path = get_config('sii.authentication.certificate_path')
            if not cert_path:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    name="certificates",
                    status="healthy",
                    duration_ms=duration_ms,
                    message="No certificates configured"
                )

            # Check certificate file exists and is readable
            import os
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            import datetime

            if not os.path.exists(cert_path):
                raise FileNotFoundError(f"Certificate file not found: {cert_path}")

            # Load and validate certificate
            with open(cert_path, 'rb') as f:
                cert_data = f.read()

            cert = x509.load_pem_x509_certificate(cert_data, default_backend())

            # Check expiration
            now = datetime.datetime.utcnow()
            days_until_expiry = (cert.not_valid_after - now).days

            duration_ms = (time.time() - start_time) * 1000

            if days_until_expiry < 0:
                return HealthCheckResult(
                    name="certificates",
                    status="unhealthy",
                    duration_ms=duration_ms,
                    message="Certificate has expired",
                    details={"days_until_expiry": days_until_expiry}
                )
            elif days_until_expiry < 30:
                return HealthCheckResult(
                    name="certificates",
                    status="degraded",
                    duration_ms=duration_ms,
                    message=f"Certificate expires in {days_until_expiry} days",
                    details={"days_until_expiry": days_until_expiry}
                )
            else:
                return HealthCheckResult(
                    name="certificates",
                    status="healthy",
                    duration_ms=duration_ms,
                    message=f"Certificate is valid for {days_until_expiry} days",
                    details={"days_until_expiry": days_until_expiry}
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name="certificates",
                status="unhealthy",
                duration_ms=duration_ms,
                message=f"Certificate check failed: {str(e)}"
            )

    def check_database(self) -> HealthCheckResult:
        """Check database connectivity"""
        start_time = time.time()

        try:
            db_url = get_config('database.url')
            if not db_url:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    name="database",
                    status="healthy",
                    duration_ms=duration_ms,
                    message="No database configured"
                )

            import psycopg2

            # Test connection
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            duration_ms = (time.time() - start_time) * 1000

            if result[0] == 1:
                return HealthCheckResult(
                    name="database",
                    status="healthy",
                    duration_ms=duration_ms,
                    message="Database connection successful"
                )
            else:
                return HealthCheckResult(
                    name="database",
                    status="unhealthy",
                    duration_ms=duration_ms,
                    message="Database query returned unexpected result"
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name="database",
                status="unhealthy",
                duration_ms=duration_ms,
                message=f"Database connection failed: {str(e)}"
            )

    def check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity"""
        start_time = time.time()

        try:
            redis_url = get_config('cache.redis_url')
            if not redis_url:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    name="redis",
                    status="healthy",
                    duration_ms=duration_ms,
                    message="No Redis configured"
                )

            import redis

            # Test connection
            r = redis.Redis.from_url(redis_url)
            r.ping()

            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="redis",
                status="healthy",
                duration_ms=duration_ms,
                message="Redis connection successful"
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name="redis",
                status="degraded",  # Redis failure is degraded, not unhealthy
                duration_ms=duration_ms,
                message=f"Redis connection failed: {str(e)}"
            )

    def check_sii_connectivity(self) -> HealthCheckResult:
        """Check SII service connectivity"""
        start_time = time.time()

        try:
            # Basic connectivity test (without authentication)
            import requests

            sii_env = get_config('sii.environment', 'certificacion')
            if sii_env == 'produccion':
                url = "https://palena.sii.cl"
            else:
                url = "https://maullin.sii.cl"

            response = requests.get(url, timeout=10, verify=True)

            duration_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return HealthCheckResult(
                    name="sii_connectivity",
                    status="healthy",
                    duration_ms=duration_ms,
                    message="SII service is reachable"
                )
            else:
                return HealthCheckResult(
                    name="sii_connectivity",
                    status="degraded",
                    duration_ms=duration_ms,
                    message=f"SII service returned status {response.status_code}"
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name="sii_connectivity",
                status="degraded",
                duration_ms=duration_ms,
                message=f"SII connectivity check failed: {str(e)}"
            )

    def check_system_resources(self) -> HealthCheckResult:
        """Check system resource usage"""
        start_time = time.time()

        try:
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Process-specific metrics
            process = psutil.Process()
            process_memory = process.memory_info().rss / 1024 / 1024  # MB
            process_cpu = process.cpu_percent()

            duration_ms = (time.time() - start_time) * 1000

            details = {
                "system_memory_percent": memory_percent,
                "system_cpu_percent": cpu_percent,
                "process_memory_mb": process_memory,
                "process_cpu_percent": process_cpu
            }

            # Determine status based on thresholds
            if memory_percent > 90 or cpu_percent > 90:
                status = "unhealthy"
                message = "System resources critically high"
            elif memory_percent > 80 or cpu_percent > 80:
                status = "degraded"
                message = "System resources moderately high"
            else:
                status = "healthy"
                message = "System resources normal"

            return HealthCheckResult(
                name="system_resources",
                status=status,
                duration_ms=duration_ms,
                message=message,
                details=details
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name="system_resources",
                status="unhealthy",
                duration_ms=duration_ms,
                message=f"System resource check failed: {str(e)}"
            )

    def check_disk_space(self) -> HealthCheckResult:
        """Check disk space usage"""
        start_time = time.time()

        try:
            disk_usage = psutil.disk_usage('/')
            used_percent = (disk_usage.used / disk_usage.total) * 100

            duration_ms = (time.time() - start_time) * 1000

            details = {
                "total_gb": disk_usage.total / 1024 / 1024 / 1024,
                "used_gb": disk_usage.used / 1024 / 1024 / 1024,
                "free_gb": disk_usage.free / 1024 / 1024 / 1024,
                "used_percent": used_percent
            }

            if used_percent > 95:
                status = "unhealthy"
                message = f"Disk space critically low: {used_percent:.1f}% used"
            elif used_percent > 85:
                status = "degraded"
                message = f"Disk space moderately high: {used_percent:.1f}% used"
            else:
                status = "healthy"
                message = f"Disk space normal: {used_percent:.1f}% used"

            return HealthCheckResult(
                name="disk_space",
                status=status,
                duration_ms=duration_ms,
                message=message,
                details=details
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name="disk_space",
                status="unhealthy",
                duration_ms=duration_ms,
                message=f"Disk space check failed: {str(e)}"
            )

# Global health checker instance
health_checker = HealthChecker()
```

---

This production deployment guide provides comprehensive coverage of all aspects needed for a successful enterprise deployment of the RypSystems DTE system. The documentation includes security best practices, monitoring setup, performance optimization, and operational procedures for maintaining a production system.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Create comprehensive API documentation for multi-language client integration", "status": "completed", "activeForm": "Creating comprehensive API documentation for multi-language client integration"}]