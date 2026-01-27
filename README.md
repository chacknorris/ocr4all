# OCR4All - Pipeline de Documentos

Sistema escalable para procesamiento OCR masivo de documentos con extracción de metadatos estructurados.

## Arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Bun)                        │
│  Dashboard → Documents → Templates → Export                      │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                      NGINX (Load Balancer)                       │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    API (FastAPI + async)                         │
│  /upload → /documents → /templates → /stats → /export            │
└──────────────────────────────────────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐  ┌───────────────────┐  ┌──────────────────┐
│ Storage (MinIO) │  │ Queue (Celery)    │  │ DB (PostgreSQL)  │
│ • originals/    │  │ • ocr_queue       │  │ • documents      │
│ • processed/    │  │ • extract_queue   │  │ • templates      │
└─────────────────┘  └───────────────────┘  │ • categories     │
                              │             │ • stats          │
                              ▼             └──────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│                    Workers (Celery - Scalable)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ OCR Workers │  │ OCR Workers │  │    Extract Workers      │  │
│  │   (x N)     │  │   (x N)     │  │        (x N)            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Caracteristicas

- **OCR con Tesseract 5.x** - Soporte LSTM, 100+ idiomas
- **Procesamiento masivo** - Cola de tareas con Celery
- **Templates configurables** - Patrones regex dinamicos por tipo de documento
- **Clasificacion automatica** - Scoring por keywords y patrones
- **Extraccion inteligente** - Normalizacion de RUT, moneda, fechas
- **Extraccion LLM** - Integracion con Ollama/OpenAI para campos complejos
- **Dashboard de estadisticas** - Metricas de rendimiento en tiempo real
- **Export CSV/JSON** - Descarga de datos procesados
- **Escalable** - Workers horizontalmente escalables
- **Multi-tenancy** - Organizaciones con API Keys y scopes
- **Webhooks** - Notificaciones en tiempo real de eventos
- **Rate limiting** - Control de uso por API key

## Requisitos

- Python 3.12+
- Bun 1.0+
- Docker & Docker Compose
- Tesseract OCR 5.x

### macOS
```bash
brew install tesseract tesseract-lang
```

### Ubuntu/Debian
```bash
sudo apt install tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng
```

## Inicio Rápido

### Con Make (recomendado)
```bash
# Configurar
cp .env.example .env

# Desarrollo
make dev        # Inicia PostgreSQL, Redis, MinIO
make dev-api    # Terminal 1
make dev-worker # Terminal 2
make dev-web    # Terminal 3

# Seed inicial
make db-seed
```

### Manual
```bash
# 1. Infraestructura
docker-compose up -d db redis minio

# 2. Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn api.main:app --reload --port 8000

# 3. Worker
PYTHONPATH=. celery -A workers.celery_app worker -l info -Q ocr,extract

# 4. Frontend
cd web && bun install && bun dev
```

### Producción
```bash
make build  # Build images
make prod   # Start production
```

### URLs
| Servicio | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |
| Flower (Celery) | http://localhost:5555 |

## API Endpoints

### Documentos
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/upload` | Subir documento |
| POST | `/api/v1/upload/batch` | Subir múltiples |
| GET | `/api/v1/documents` | Listar (paginado) |
| GET | `/api/v1/documents/{id}` | Detalle |
| DELETE | `/api/v1/documents/{id}` | Eliminar |
| GET | `/api/v1/documents/{id}/ocr` | Resultados OCR |
| GET | `/api/v1/documents/{id}/extractions` | Campos extraídos |
| PATCH | `/api/v1/documents/{id}/extractions/{eid}` | Corregir campo |
| POST | `/api/v1/documents/{id}/reprocess` | Reprocesar |

### Templates
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/templates` | Listar templates |
| POST | `/api/v1/templates` | Crear template |
| GET | `/api/v1/templates/{id}` | Detalle con campos |
| DELETE | `/api/v1/templates/{id}` | Eliminar |
| POST | `/api/v1/templates/{id}/fields` | Agregar campo |
| POST | `/api/v1/templates/seed-defaults` | Cargar defaults |

### Estadísticas
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/stats/overview` | Resumen general |
| GET | `/api/v1/stats/timeline` | Timeline por día |
| GET | `/api/v1/stats/by-type` | Stats por tipo |
| GET | `/api/v1/stats/extraction-accuracy` | Precisión campos |
| GET | `/api/v1/stats/queue-status` | Estado de cola |

### Export
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/export/documents` | Export documentos |
| GET | `/api/v1/export/extractions` | Export campos |

### Categorías
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/categories` | Listar categorías |
| GET | `/api/v1/categories/tree` | Árbol jerárquico |
| POST | `/api/v1/categories` | Crear categoría |
| POST | `/api/v1/categories/seed-defaults` | Cargar defaults |

### Autenticación (API Keys)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/auth/organizations` | Crear organización |
| GET | `/api/v1/auth/organizations/me` | Mi organización |
| POST | `/api/v1/auth/api-keys` | Crear API key |
| GET | `/api/v1/auth/api-keys` | Listar API keys |
| DELETE | `/api/v1/auth/api-keys/{id}` | Revocar API key |
| GET | `/api/v1/auth/api-keys/{id}/usage` | Estadísticas de uso |

### Webhooks
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/auth/webhook-events` | Eventos disponibles |
| POST | `/api/v1/auth/webhooks` | Crear webhook |
| GET | `/api/v1/auth/webhooks` | Listar webhooks |
| PATCH | `/api/v1/auth/webhooks/{id}` | Actualizar webhook |
| DELETE | `/api/v1/auth/webhooks/{id}` | Eliminar webhook |
| GET | `/api/v1/auth/webhooks/{id}/deliveries` | Ver entregas |
| POST | `/api/v1/auth/webhooks/deliveries/{id}/retry` | Reintentar entrega |

### Extracción LLM
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/documents/{id}/extract-llm` | Extracción con LLM |
| POST | `/api/v1/documents/{id}/extract-hybrid` | Extracción híbrida (regex + LLM) |

## Tipos de Documento

| Tipo | Campos Extraídos |
|------|------------------|
| Boleta | RUT emisor, N° boleta, Fecha, Total |
| Factura | RUT emisor/receptor, N° factura, Fecha, Neto, IVA, Total |
| Guía Despacho | RUT emisor, N° guía, Fecha |
| Nota de Crédito | RUT emisor, N° nota, Fecha, Total |

Los campos se normalizan automaticamente:
- **RUT**: `12345678-9` -> `12.345.678-9`
- **Moneda**: `$1.234.567` -> `1234567`
- **Fecha**: `25/01/2024` -> `2024-01-25`

## Integracion LLM

Para documentos complejos donde la extraccion por regex no funciona bien, se puede usar LLM:

### Ollama (Local)
```bash
# Iniciar Ollama con Docker
docker-compose --profile llm up -d

# Descargar modelo
docker exec -it ocr4all-ollama-1 ollama pull llama3.2

# Usar en API
curl -X POST "http://localhost:8000/api/v1/documents/{id}/extract-llm?provider=ollama"
```

### OpenAI
```bash
# Configurar API key en .env
LLM_PROVIDER=openai
LLM_API_KEY=sk-...

# Usar en API
curl -X POST "http://localhost:8000/api/v1/documents/{id}/extract-llm?provider=openai&model=gpt-4"
```

### Extraccion Hibrida
Combina regex (rapido) con LLM (para campos faltantes):
```bash
curl -X POST "http://localhost:8000/api/v1/documents/{id}/extract-hybrid"
```

## Estructura del Proyecto

```
ocr4all/
├── api/                    # FastAPI
│   ├── main.py
│   ├── routes/
│   │   ├── documents.py
│   │   ├── templates.py
│   │   ├── stats.py
│   │   ├── categories.py
│   │   └── export.py
│   └── schemas/
├── core/                   # Business logic
│   ├── config.py
│   ├── ocr.py
│   ├── pdf_handler.py
│   ├── preprocessing.py
│   ├── extractor.py
│   ├── classifier.py
│   └── storage.py
├── models/                 # SQLAlchemy
│   ├── database.py
│   └── document.py
├── workers/                # Celery
│   ├── celery_app.py
│   └── tasks.py
├── web/                    # Frontend (Bun + React)
│   └── src/
│       ├── components/
│       ├── lib/
│       └── types/
├── docker-compose.yml      # Development
├── docker-compose.prod.yml # Production
├── Dockerfile.prod
├── nginx.conf
├── Makefile
└── requirements.txt
```

## Roadmap

### Etapa 1 - Fundamentos ✅
- [x] API FastAPI async
- [x] Soporte PDF + imágenes
- [x] Cola Celery para procesamiento
- [x] Extracción básica por regex
- [x] UI de upload y revisión

### Etapa 2 - Templates ✅
- [x] Templates de extracción configurables
- [x] Post-procesadores (normalización)
- [x] Export CSV/JSON
- [x] UI gestión de templates

### Etapa 3 - Escalabilidad ✅
- [x] Categorías de documento dinámicas
- [x] Clasificador con scoring
- [x] Dashboard de estadísticas
- [x] Docker optimizado para producción
- [x] NGINX como reverse proxy
- [x] Workers escalables

### Etapa 4 - Avanzado
- [x] Integracion LLM para campos complejos (Ollama/OpenAI)
- [x] API publica con API Keys y scopes
- [x] Webhooks de notificacion
- [x] Multi-tenancy (Organizations)
- [ ] Entrenamiento de modelos Tesseract custom
- [ ] Integracion ERP

## Autenticacion

### API Keys
```bash
# Crear organizacion
curl -X POST http://localhost:8000/api/v1/auth/organizations \
  -H "Content-Type: application/json" \
  -d '{"name": "Mi Empresa", "slug": "mi-empresa"}'

# Crear API key (requiere admin key)
curl -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "X-API-Key: ocr4all_..." \
  -H "Content-Type: application/json" \
  -d '{"name": "Production", "scopes": ["read", "write"]}'
```

### Scopes
- `read`: Lectura de documentos y extracciones
- `write`: Subir documentos, modificar extracciones
- `admin`: Gestionar API keys, webhooks, organizacion

### Uso
```bash
curl http://localhost:8000/api/v1/documents \
  -H "X-API-Key: ocr4all_tu_api_key_aqui"
```

## Webhooks

Recibe notificaciones en tiempo real cuando ocurren eventos:

### Eventos Disponibles
- `document.uploaded` - Documento subido
- `document.processing` - Procesamiento iniciado
- `document.processed` - Documento procesado exitosamente
- `document.failed` - Error en procesamiento
- `document.deleted` - Documento eliminado
- `extraction.completed` - Extraccion completada
- `extraction.corrected` - Correccion manual aplicada
- `batch.completed` - Lote completado

### Verificacion de Firma
```python
import hmac
import hashlib

def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

## Licencia

MIT
# ocr4all
