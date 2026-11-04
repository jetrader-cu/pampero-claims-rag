# Pampero Claims Assistant

Asistente RAG multi-tenant para reclamaciones de seguros de vehículos (Aseguradora Pampero, compañía
ficticia). Un ajustador sube PDFs de su organización —pólizas, peritajes, facturas de taller, algunos
escaneados y con tablas—, el sistema los procesa en segundo plano y después responde preguntas en
lenguaje natural con **citas verificables** (documento, página y fragmento) o dice explícitamente que
**no lo sabe**. Los datos de una organización nunca se mezclan con los de otra.

Las decisiones de diseño, los compromisos aceptados y los resultados de la evaluación están en
[`DECISIONS.md`](DECISIONS.md).

## Arranque en un comando

Requisitos: Docker con Compose v2, unos 8 GB de RAM libres para Docker y unos 12 GB de disco
(la imagen del worker incluye Docling, PyTorch CPU y los modelos de layout, tablas y OCR).

```bash
make up
```

Equivale a `docker compose up -d --build --wait`. El primer build tarda varios minutos (descarga de
PyTorch CPU y de los modelos de Docling); los siguientes usan la caché. **No hace falta ninguna clave**:
por defecto se usan un LLM y unos embeddings falsos y deterministas.

Cargar los datos de ejemplo (dos organizaciones, sus usuarios y sus documentos):

```bash
make seed
```

| Servicio | URL | Para qué |
|---|---|---|
| Web | http://localhost:5173 | Interfaz del ajustador |
| API | http://localhost:8000/docs | OpenAPI interactiva |
| Grafana | http://localhost:3000 | Trazas (Tempo), métricas (Prometheus) y logs (Loki) |

Servicios de `docker-compose.yml`: `db` (PostgreSQL 17 + pgvector 0.8), `redis`, `migrate` (aplica
Alembic y termina), `api`, `worker` (Celery + Docling), `beat` (reintentos de jobs huérfanos), `web`
(nginx con el frontend y proxy a la API) y `otel-lgtm` (colector OpenTelemetry + Tempo + Prometheus +
Loki + Grafana).

Para parar: `make down`. Para borrar también datos y volúmenes: `make reset`.

## Datos de ejemplo

`make seed` crea dos organizaciones con estas claves de demo:

| Organización | API key de demo | Documentos |
|---|---|---|
| Pampero Norte | `pampero_key_demo_norte` | póliza AP-2024-0012, peritaje SIN-2024-9901 (tabla de daños), factura FAC-2024-104 (tabla con IVA), atestado escaneado (solo imagen, se lee por OCR) y un anexo con instrucciones maliciosas incrustadas |
| Pampero Sur | `pampero_key_demo_sur` | póliza AP-2024-0088, peritaje SIN-2024-9901, factura FAC-2024-550 e informe escaneado |

El mismo número de siniestro (`SIN-2024-9901`) existe en las dos organizaciones con importes distintos:
preguntar por él desde cada una es la prueba visible del aislamiento. Hay además un PDF truncado en
`samples/comun/archivo_corrupto.pdf` para ver el rechazo. Los PDFs se generan con
`scripts/generate_samples.py` y todos los datos son inventados.

Recorrido sugerido en la web:

1. Entrar con `pampero_key_demo_norte`.
2. Subir un PDF y ver sus etapas: en cola → leyendo → fragmentando → indexando → listo.
3. Preguntar «¿Cuál es el deducible por daños propios de la póliza AP-2024-0012?» y pulsar la cita
   `[1]`: el visor abre la página y resalta el fragmento.
4. Preguntar algo que no está en los documentos («¿Qué cubre la póliza en caso de granizo sobre
   cosechas?»): la respuesta es «No encontré evidencia suficiente…», sin citas.
5. Cambiar a `pampero_key_demo_sur` y preguntar por el total del siniestro SIN-2024-9901.
6. Pulsar «Ver traza» en una respuesta para abrirla en Grafana.

Lo mismo por API:

```bash
curl -s -H "Authorization: Bearer pampero_key_demo_norte" -F file=@samples/norte/poliza_AP-2024-0012.pdf http://localhost:8000/api/v1/documents
```

```bash
curl -s -H "Authorization: Bearer pampero_key_demo_norte" -H "Content-Type: application/json" -d '{"question":"¿Cuál es el deducible por daños propios?"}' http://localhost:8000/api/v1/questions
```

Crear organizaciones y usuarios propios (la clave se muestra una sola vez):

```bash
curl -s -X POST -H "X-Admin-Token: pampero-dev-admin-token" -H "Content-Type: application/json" -d '{"slug":"demo","name":"Demo"}' http://localhost:8000/api/v1/tenants
```

```bash
curl -s -X POST -H "X-Admin-Token: pampero-dev-admin-token" -H "Content-Type: application/json" -d '{"email":"ajustador@demo.local"}' http://localhost:8000/api/v1/tenants/<tenant_id>/users
```

## Usar un LLM real

Crear un `.env` en la raíz (ver `.env.example`) y reconstruir:

```dotenv
LLM_PROVIDER=litellm
LLM_MODEL=gemini/gemini-2.5-flash
EMBEDDING_PROVIDER=litellm
EMBEDDING_MODEL=gemini/gemini-embedding-001
GEMINI_API_KEY=...
RAG_MIN_SIMILARITY=0.55
```

Con OpenAI: `LLM_MODEL=openai/gpt-4.1-mini`, `EMBEDDING_MODEL=openai/text-embedding-3-small` y
`OPENAI_API_KEY`. Cada chunk guarda el modelo de embeddings con que se generó y la búsqueda solo compara
vectores del mismo modelo: al cambiar de proveedor hay que reprocesar los documentos (`make reset` y
`make seed`). El umbral `0.55` es un punto de partida; se calibra con `make eval ARGS="--sweep 0.30:0.80:0.05"`.

## Ver una traza completa

1. Subir un documento o hacer una pregunta. La respuesta HTTP trae la cabecera `X-Trace-Id` (en la web,
   «Ver traza» la abre directamente).
2. En Grafana (http://localhost:3000) → Explore → origen **Tempo** → pegar el trace id.
3. Una subida muestra en la misma traza: `POST /api/v1/documents` → publicación en Celery → tarea
   `ingest_document` en el worker → `ingest.parse` / `ingest.chunk` / `ingest.embed` / `ingest.persist`
   → sentencias SQL. Una pregunta: `POST /api/v1/questions` → embedding → `retrieval.hybrid` (SQL) →
   `gen_ai.chat` con modelo, tokens y latencia.
4. Los spans llevan `app.tenant_id`, `app.document_id`, `app.job_id`, intento, páginas, chunks, uso de
   OCR, candidatos y similitud. Nunca llevan texto de documentos, preguntas ni claves.
5. Desde un span, «Logs for this span» abre en Loki los logs JSON con el mismo `trace_id`.
6. El dashboard «Pampero Claims Assistant — Observabilidad» muestra la profundidad de la cola, la
   duración por etapa, fallos y reintentos, preguntas por estado, latencia y tokens del LLM.

## Pruebas

Todo lo que corre en CI se puede ejecutar en local con Postgres 17 + pgvector y Redis en marcha
(por ejemplo, los de `make up`, que se exponen en `127.0.0.1:54329` y `127.0.0.1:63799`).

```bash
make lint
```

```bash
make test
```

`make lint` ejecuta ruff, mypy estricto, ESLint y TypeScript. `make test` ejecuta pytest (unitarias e
integración contra Postgres real con pgvector) y Vitest. Variables para el backend fuera de Docker:

```bash
export DATABASE_URL_OWNER=postgresql+psycopg://postgres:postgres@localhost:54329/pampero DATABASE_URL=postgresql+asyncpg://pampero_app:pampero_app_secret@localhost:54329/pampero DATABASE_SYNC_URL=postgresql+psycopg://pampero_app:pampero_app_secret@localhost:54329/pampero REDIS_URL=redis://localhost:63799/0 CELERY_BROKER_URL=redis://localhost:63799/0
```

Partes destacadas de la suite:

| Qué demuestra | Dónde |
|---|---|
| Un tenant nunca ve chunks de otro, ni con un `SELECT` sin `WHERE` (RLS con el rol de la app) | `backend/tests/integration/test_rls.py`, `test_retrieval.py` |
| Reintentos idempotentes, 429 de embeddings, Celery de punta a punta, jobs huérfanos, dead-letter | `test_ingestion_reliability.py`, `test_ingestion_retries.py` |
| LLM con 429, timeout y salida fuera de esquema (con una reparación) | `test_questions_api.py`, `unit/test_llm_structured.py` |
| Inyección en documentos y validación de citas | `test_security_injection.py`, `unit/test_injection_heuristic.py`, `unit/test_citations.py` |
| Traza HTTP → Celery → SQL y que ni spans ni logs contienen texto del documento | `test_observability.py` |
| OCR real de los escaneados con Docling (marcador `docling`, fuera del CI ligero) | `test_sample_documents.py` |

Las pruebas con Docling necesitan su entorno (la imagen del worker o `uv sync --extra worker`):
`uv run pytest -m docling`.

### Evaluación de citas y abstención

```bash
make eval
```

Ejecuta las 18 preguntas de `eval/questions.yaml` (10 con respuesta, 4 sin respuesta en los
documentos, 2 de inyección en la pregunta y 2 de inyección dentro de un documento) y reporta cuántas
citan el documento y la página correctos, la precisión y el recall de la abstención y la resistencia a
inyección. `ARGS="--sweep 0.10:0.80:0.05"` barre el umbral de similitud. En CI corre con
`--assert` y falla si baja de los umbrales.

## Estructura

```
backend/   FastAPI, Celery, pipeline de ingesta, RAG, capa LLM, migraciones Alembic y tests
frontend/  React 19 + Vite + Tailwind + shadcn/Radix, visor PDF con react-pdf
docker/    init de Postgres y dashboard/provisión de Grafana
samples/   PDFs ficticios por organización (norte, sur) y casos comunes (corrupto, inyección)
eval/      preguntas de evaluación
scripts/   generación de muestras, seed y evaluación
```

## Qué está terminado

- Subida con validación (firma `%PDF-`, 25 MB, 200 páginas, cifrado) y respuesta 202 inmediata con
  `job_id`; deduplicación por SHA-256 dentro de cada organización.
- Ingesta en Celery: Docling (OCR para escaneados, tablas con TableFormer), chunking estructural,
  embeddings de 768 dimensiones y persistencia atómica; reintentos con backoff, dead-letter visible y
  reproceso manual; recuperación de jobs huérfanos.
- Búsqueda híbrida (HNSW coseno + texto completo en español) fusionada con RRF y aislamiento con
  Row-Level Security.
- Respuesta estructurada validada con Pydantic, citas comprobadas contra los fragmentos recuperados,
  confianza calculada y abstención explícita.
- Capa LLM propia sobre LiteLLM con timeout, reintentos, proveedor falso y errores 503/504/502 definidos.
- Frontend con progreso por documento, preguntas, citas y navegación al fragmento en el PDF.
- OpenTelemetry de extremo a extremo, logs JSON con `trace_id` y métricas de cola y RAG.
- Límite de peticiones por usuario, CORS estricto, cabeceras de seguridad, secretos solo por entorno.
- CI con lint, tipos, tests, evaluación, auditoría de dependencias, build de imágenes y gitleaks.

## Qué no está terminado

- Umbral de abstención calibrado con un proveedor real: la evaluación publicada usa los dobles
  deterministas; con Gemini u OpenAI hay que repetir el barrido.
- Resaltado exacto de la frase citada mediante coordenadas: el bbox guardado es el del chunk; el visor
  busca la frase en la capa de texto y, si no la encuentra, usa el área del chunk o muestra el fragmento.
- Autenticación real (OIDC) y roles: hay una API key por usuario y un token de administración para la demo.
- Almacenamiento de PDFs en un bucket: se usa un volumen compartido entre API y worker.
- Progreso por SSE: la web consulta cada 1,5 s mientras haya documentos sin terminar.

## Qué haría con más tiempo

- Calibrar el umbral con el proveedor real y ampliar el set de evaluación con más documentos y un juez
  LLM para medir fidelidad, no solo la cita.
- Reranker (cross-encoder) sobre los candidatos de RRF y bbox por frase citada.
- S3/MinIO con URLs firmadas, OIDC con roles, cuotas de tokens por organización.
- Separar colas por prioridad y escalar workers; particionar por tenant si alguno domina el volumen.
- Extracción estructurada de campos (importes, fechas, números de póliza) para filtros por metadatos.
