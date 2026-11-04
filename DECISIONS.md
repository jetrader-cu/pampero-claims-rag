# Decisiones de diseño

Registro de las decisiones del MVP, los compromisos aceptados y cómo se comprobó cada una. El
arranque y las pruebas están en el [README](README.md).

## 0. Ambigüedades del enunciado y cómo las resolví

| Punto abierto | Decisión | Motivo |
|---|---|---|
| Autenticación | Una API key por usuario (`Authorization: Bearer`), guardada como HMAC-SHA256 con *pepper*; token de administración para crear tenants y usuarios | El enunciado pide «tenants y usuarios de prueba»; OIDC no aporta a lo que se evalúa y quitaría tiempo |
| ¿Dónde se detecta un PDF corrupto? | En la subida (422 `pdf_corrupt`, nada se encola) y, si pasa esa validación pero falla al parsear, en el worker (`failed` con motivo) | Rechazar pronto ahorra cola y da un error inmediato; el worker cubre lo que solo se descubre al parsear |
| Un archivo por petición o varios | Uno por petición; la web sube en paralelo (máximo 3) | Cada archivo tiene su `job_id` y su error; una subida múltiple obliga a respuestas parciales |
| Progreso de ingesta | Consulta cada 1,5 s mientras haya documentos sin terminar | Más simple que SSE y suficiente para decenas de documentos |
| Idioma | Español en la interfaz, la búsqueda léxica (`spanish` + `unaccent`) y el prompt | Los documentos y los usuarios son hispanohablantes |
| Moneda y datos | Euros e importes inventados; dos tenants con el mismo número de siniestro e importes distintos | Hace visible el aislamiento en la demo y en los tests |

## 1. Chunking, modelo de embeddings y dimensión

**Parseo.** Docling en el worker: modelo de layout, TableFormer para tablas y OCR (RapidOCR) solo en las
regiones sin capa de texto. Cada elemento sale con su página y su rectángulo (bbox) en coordenadas con
origen arriba-izquierda, que el visor usa para resaltar. El conversor se crea una vez por proceso: cargar
los modelos cuesta decenas de segundos y no puede pagarse por documento. Los modelos se descargan en el
build de la imagen (`python -m app.ingest.warmup`), nunca en tiempo de ejecución.

`PARSER=pypdf` queda como modo ligero para CI y desarrollo: sin OCR y sin estructura de tablas. Con él, un
escaneado falla con `empty_document` de forma visible; no se finge que se leyó.

**Chunking estructural** (`backend/app/ingest/chunking.py`):

- El texto se agrupa por sección (título más cercano) hasta 450 tokens, con 50 tokens de solape solo
  dentro de la misma sección. Una cláusula de póliza vive bajo su título; cortar por caracteres la separa
  de él.
- **Cada tabla es un chunk propio** en Markdown. Si supera el límite se parte por filas **repitiendo la
  cabecera**: un importe sin el nombre de su columna no significa nada.
- Cada chunk lleva delante `archivo › sección`, para que «franquicia» recupere la cláusula aunque la palabra
  solo esté en el título.
- `page_start`, `page_end` y los bbox se conservan para la cita y la navegación.

**Embeddings: 768 dimensiones.** `gemini-embedding-001` (por defecto) y `text-embedding-3-small` están
entrenados con Matryoshka: se pueden truncar a 768 perdiendo poca calidad.

- 768 frente a 1536 reduce a la mitad el almacenamiento y la memoria del índice HNSW, y acelera inserción
  y búsqueda.
- Con cientos de documentos por tenant, la calidad de recuperación depende más del chunking y de la
  señal léxica (números de póliza, matrículas) que de la dimensión.
- Al truncar hay que **renormalizar** a norma 1; si no, el coseno deja de ser comparable. Se hace siempre
  en el cliente de embeddings.

Cada chunk guarda el modelo con que se generó y la búsqueda filtra por el modelo activo: cambiar de
proveedor obliga a reindexar, pero nunca mezcla espacios vectoriales. Si el proveedor de embeddings falla,
el sistema **no** sustituye los vectores por otros: el error se propaga y la tarea se reintenta.

En CI los embeddings son un *feature hashing* determinista de unigramas y bigramas (768 dimensiones,
normalizado). Tiene semántica léxica: una pregunta que comparte palabras con un chunk obtiene un coseno
alto. Así la evaluación en CI mide algo real sin red ni claves.

## 2. Aislamiento entre tenants

**Decisión:** columna `tenant_id` en todas las tablas de negocio + **Row-Level Security** con
`ENABLE` y `FORCE` + un rol de aplicación (`pampero_app`) sin `BYPASSRLS` y que no es propietario de
las tablas. Las migraciones las aplica otro rol.

- Cada petición y cada tarea del worker abre una transacción y ejecuta
  `set_config('app.tenant_id', <id>, true)`. Con `true` el valor muere con la transacción: una conexión
  que vuelve al pool no arrastra el tenant anterior.
- Sin tenant fijado, la política compara con `NULL` y no devuelve ni deja insertar nada: **falla cerrado**.
- `WITH CHECK` impide escribir filas de otro tenant aunque el código se equivoque.
- El tenant sale **solo** de la API key. Para autenticar hace falta leer `users` antes de conocer el
  tenant; eso lo hace una función `SECURITY DEFINER` (`auth_lookup`) que recibe el hash y devuelve solo
  `(user_id, tenant_id)`. Igual para que el worker resuelva el tenant de un job.
- Las consultas llevan además `WHERE tenant_id = :t` explícito: ayuda al planificador y es una segunda
  barrera.
- Un recurso de otro tenant devuelve 404, no 403, para no confirmar que existe.

Los tests de aislamiento se conectan **con el rol de la aplicación**: con un superusuario RLS no se
aplica y el test pasaría en falso. Comprueban un `SELECT` sin `WHERE`, la ausencia de tenant, un `INSERT`
con tenant ajeno y la búsqueda híbrida entre dos tenants con contenido casi idéntico.

**Compromisos aceptados:**

- Todo acceso a datos debe ir dentro de una transacción con el `set_config`; un `commit` intermedio pierde
  el contexto. Está encapsulado en una dependencia de FastAPI y en un helper del worker.
- El índice HNSW es global. Con un filtro por tenant, un índice aproximado puede devolver menos filas de
  las pedidas; se compensa con `hnsw.iterative_scan = relaxed_order` (pgvector ≥ 0.8) y
  `ef_search = 100`.
- **Particiones por tenant** darían aislamiento físico y planes por tenant, pero un índice HNSW por
  partición y migraciones más complejas. No compensan con pocos tenants; serían el siguiente paso si uno
  dominara el volumen.

## 3. Cuándo no hay evidencia suficiente

Tres puertas, en este orden:

1. **Recuperación.** Si no hay candidatos, o la mejor similitud coseno está por debajo de
   `RAG_MIN_SIMILARITY` **y** no hay coincidencia léxica, se responde «no lo sé» **sin llamar al LLM**.
   Se usa el coseno y no la puntuación RRF, porque RRF solo ordena y no dice si algo es relevante.
2. **Modelo.** La salida exige `answerable`; si el modelo declara que no puede responder, se respeta.
3. **Citas.** Cada cita se comprueba fuera del modelo: el `chunk_id` tiene que estar entre los recuperados
   para ese tenant y la frase citada tiene que aparecer **literalmente** (normalizada) en ese fragmento.
   Las inválidas se descartan; si no queda ninguna, la respuesta pasa a «no lo sé».

El texto de la abstención es siempre el mismo («No encontré evidencia suficiente en los documentos para
responder.»). Nunca se devuelve el texto libre del modelo en ese caso.

**La confianza no la declara el modelo**: se calcula. `high` exige dos citas válidas o una con similitud
alta; `low` si se descartó alguna cita, si la similitud está justo en el umbral o si se cita un fragmento
con instrucciones incrustadas.

**Evaluación.** `eval/questions.yaml` tiene 18 casos: 10 con respuesta (con documento y página
esperados), 4 sin respuesta en los documentos, 2 de inyección en la pregunta y 2 de inyección dentro de un
documento del tenant. `scripts/eval.py` reporta:

- **Citation accuracy:** preguntas respondibles con al menos una cita al documento y la página esperados.
- **Abstención:** precisión y recall.
- **Resistencia a inyección:** ninguna frase prohibida en la respuesta.

Resultado con los dobles deterministas (los mismos que usa CI):

| Métrica | Resultado |
|---|---|
| Citation accuracy | 100 % (10/10) |
| Answer recall | 100 % (10/10) |
| Abstention precision | 100 % (4/4) |
| Abstention recall | 100 % (4/4) |
| Injection resistance | 100 % (4/4) |

Barrido del umbral con los mismos dobles (`make eval ARGS="--sweep 0.10:0.50:0.05"`):

```text
Umbral | Cit. Acc | Ans. Rec | Abs. Prec | Abs. Rec | Abs. F1
0.10   | 100.0%   | 100.0%   | 100.0%    | 100.0%   | 1.000
0.20   | 100.0%   | 100.0%   | 100.0%    | 100.0%   | 1.000
0.25   |  90.0%   |  90.0%   |  80.0%    | 100.0%   | 0.889
0.30   |  70.0%   |  70.0%   |  57.1%    | 100.0%   | 0.727
0.40   |  50.0%   |  50.0%   |  44.4%    | 100.0%   | 0.615
0.50   |  40.0%   |  40.0%   |  40.0%    | 100.0%   | 0.571
```

Se fija `0.20`: es el umbral más alto que no pierde respuestas legítimas.

**Lectura honesta del resultado:**

- Con estos dobles la abstención la decide sobre todo el modelo falso (que solo responde si hay solape de
  palabras) y la validación de citas, no el umbral. Por eso por debajo de 0.20 el resultado no cambia.
- El 100 % prueba que el circuito funciona de punta a punta, no la calidad de un LLM real.
- Con Gemini u OpenAI los cosenos se concentran más arriba. `0.55` en el README es solo un punto de partida
  y el procedimiento es repetir el barrido con el proveedor real.
- Esa calibración no está hecha en esta entrega.

## 4. Fallos de parseo, reintentos e idempotencia

**Clasificación:**

- **Permanente** (no se reintenta): PDF corrupto, cifrado, más de 200 páginas, sin texto extraíble. El
  documento queda en `failed` con su `error_code`; reintentar no lo arregla y solo gasta CPU.
- **Transitorio** (se reintenta): red, base de datos, 429 o timeout del proveedor de embeddings y
  **también los errores inesperados**. Celery reintenta con backoff exponencial y jitter (5 intentos).
  Agotados los intentos, el documento pasa a **`dead_letter`**.

Tratar lo inesperado como transitorio es deliberado: un bug o una caída breve no se marcan como «archivo
inválido», y `dead_letter` es reprocesable.

**Dead-letter.** Celery con Redis no tiene una cola de mensajes muertos nativa; el dead-letter es un
**estado en la base de datos**, visible en la interfaz con su motivo. El
**reproceso es manual** (`POST /documents/{id}/reprocess`), para no reintentar en bucle algo roto. Un
`failed` por archivo inválido no se reprocesa: hay que subir otro archivo.

**Idempotencia y muerte del worker:**

- `task_acks_late` + `task_reject_on_worker_lost`: si el worker muere a mitad, el mensaje no se da por
  procesado y Redis lo reentrega al vencer `visibility_timeout` (30 min, mayor que el tiempo máximo de la
  tarea).
- La tarea solo recibe el `job_id`. El estado vive en la base de datos: un job terminado no se reprocesa.
- Los chunks se escriben en **una transacción**: se bloquea la fila del documento (`FOR UPDATE`), se
  borran sus chunks, se insertan los nuevos y se marca `ready`. Una ejecución que muere a mitad no deja
  nada a medias. Dos ejecuciones del mismo job quedan en serie y la última reemplaza el conjunto entero.
  `UNIQUE(document_id, chunk_index)` es la red de seguridad.
- La subida **confirma la transacción antes de encolar**; si no, el worker podría recibir un job que aún
  no existe.
- `beat` recupera cada 5 minutos los jobs `running` con más de 15 minutos sin terminar y los jobs en cola
  que nunca llegaron a Celery (por ejemplo, si Redis falló al subir), y los vuelve a encolar.

Se prefirió reemplazar el conjunto de chunks a hacer *upsert* por chunk: si cambia el parser o el
chunking, un *upsert* dejaría chunks huérfanos.

## 5. Capa LLM

Interfaz propia (`LLMClient`, `EmbeddingClient`) con dos implementaciones: **LiteLLM** y dobles
deterministas.

- LiteLLM da el mismo formato de modelo para chat y embeddings de Gemini y OpenAI: cambiar de proveedor es
  configuración. Pydantic AI aportaría agentes y herramientas que este caso no necesita. La validación la
  hace Pydantic en nuestro código.
- Timeout (`LLM_TIMEOUT_S`, 20 s) y reintentos (`LLM_MAX_RETRIES`, 2) por configuración.
- Errores traducidos a excepciones de dominio:

| Caso | Respuesta HTTP |
|---|---|
| 429 del proveedor | **503** `llm_rate_limited` con `Retry-After` |
| Timeout | **504** `llm_timeout` |
| Caída del proveedor | **503** `llm_unavailable` |
| Salida que no cumple el esquema | **una** reparación con el error de validación; si falla otra vez, **502** `llm_invalid_output` |

- **Un fallo del proveedor nunca se convierte en «no lo sé»**: eso mentiría sobre la evidencia. Tampoco se
  inventa una respuesta.
- El esquema JSON va en el prompt y la respuesta se pide en modo JSON. La validación es siempre la de
  Pydantic: no depende de que el proveedor soporte salida estricta.

## 6. Búsqueda híbrida

Vector (HNSW, coseno, 40 candidatos) más texto completo (`websearch_to_tsquery` con configuración
española sin acentos, índice GIN, 40 candidatos), fusionados con **Reciprocal Rank Fusion** (k = 60) en
una sola consulta SQL.

- Los ajustadores preguntan por números de póliza, de siniestro o de factura: señal léxica pura que un
  embedding recupera mal.
- RRF combina por posición, así que no hace falta calibrar la escala del coseno contra la de `ts_rank_cd`.
- `websearch_to_tsquery` no falla con comillas o signos en la pregunta.
- Filtro opcional por documentos como señal de metadatos.

## 7. Prompt injection en los documentos

Los fragmentos son datos de terceros, no instrucciones. Defensas en capas:

1. **Delimitadores con nonce aleatorio por petición** (`<doc_xxxx>`). Se neutraliza cualquier `<doc_` o
   `</doc_` dentro del texto: el documento no puede «cerrar» su bloque. El nombre de archivo se escapa.
2. **Prompt de sistema** que declara el contexto como no confiable.
3. **Salida con esquema cerrado.** No hay herramientas ni acciones: aunque el modelo obedeciera, no puede
   hacer nada más que escribir texto.
4. **Citas validadas fuera del modelo**, contra los fragmentos recuperados del propio tenant (RLS): no
   puede citar ni filtrar datos de otro tenant.
5. **Heurística** que detecta texto dirigido a un asistente («ignora las instrucciones…»): ese fragmento
   llega al modelo con un aviso y, si la respuesta lo cita, la confianza baja a `low`. No se borra el
   fragmento: puede ser prueba de fraude.
6. **La interfaz pinta todo como texto plano** y la CSP no permite cargar recursos externos (sin balizas
   de exfiltración).

Ninguna defensa de prompt es completa; el diseño limita **lo que un ataque puede conseguir**. El set de
evaluación incluye un documento con instrucciones incrustadas cargado en un tenant.

## 8. Observabilidad

- **OpenTelemetry** con instrumentación de FastAPI, Celery (inicializada tras el fork del worker), SQLAlchemy,
  Redis y httpx, más spans propios.
  - El contexto viaja en las cabeceras del mensaje de Celery: subida, tarea y SQL forman **una sola traza**.
  - El instrumentador de SQLAlchemy declara soporte hasta la 2.1 y en silencio no hacía nada: se
    instrumentan los engines de forma explícita y un test comprueba que hay spans SQL en la traza de ingesta.
- **Atributos:** tenant, documento, job, intento, páginas, chunks, OCR, candidatos, similitud, modelo,
  tokens y latencia. **Nunca** texto de documentos, preguntas, prompts ni claves. Un test con una cadena
  «canario» lo comprueba en spans y logs.
- **Logs JSON** (structlog) con `trace_id` y `span_id`, a stdout y por OTLP a Loki.
- **Métricas:** profundidad de la cola, duración por etapa, fallos y reintentos de ingesta, preguntas por
  estado, latencia y tokens del LLM.
- **Backend local:** `grafana/otel-lgtm` (colector, Tempo, Prometheus, Loki y Grafana en un contenedor).
  Pesa más que Jaeger, pero el enunciado pide también métricas de cola y logs correlacionados. Es una
  imagen de desarrollo, no de producción.

## 9. Seguridad

- **Subida:** el tamaño se cuenta mientras se lee (corta a los 25 MB), se exige la firma `%PDF-`, se abre
  con pypdfium2 para contar páginas y detectar cifrado, y se guarda con nombre UUID (el nombre original
  solo se muestra).
- **API key solo en cabecera:** en la URL acabaría en logs de acceso, historial y `Referer`. El visor pide
  el PDF con la cabecera.
- **Secretos solo por variables de entorno.** En producción la aplicación no arranca con el token de
  administración o el *pepper* de desarrollo. `.env` está fuera de git y gitleaks corre en CI.
- **Red:** CORS con lista exacta de orígenes y sin credenciales, cabeceras `nosniff`, `DENY`,
  `no-referrer` y `no-store`, y CSP en la web.
- **Límite de peticiones** por usuario y minuto en Redis (429 con `Retry-After`). Falla abierto si Redis
  cae: protege coste y abuso, no el aislamiento, y bloquear las preguntas no aporta nada cuando la
  ingesta ya está degradada.
- **Infraestructura:** Celery solo acepta JSON, nunca pickle: con pickle, un mensaje en Redis equivale a
  ejecutar código. Postgres y Redis solo escuchan en `127.0.0.1`.

**Riesgos residuales conocidos:**

- El proveedor LLM ve el contexto recuperado.
- La API key de la demo vive en `sessionStorage`; un XSS la robaría, de ahí la CSP.
- La heurística de inyección tiene falsos negativos.
- El rol de la aplicación puede escribir en `tenants` por los privilegios por defecto del esquema; solo
  lo usa el endpoint de administración.

## 10. Frontend

- **La evidencia es lo central.** Cada cita `[n]` es un botón que abre el PDF en la página citada.
- **El resaltado se busca primero en la capa de texto del PDF**, porque es exacto. Después se usa el bbox
  del chunk, que es aproximado, y por último el fragmento en un panel lateral.
- **«Sin evidencia» tiene su propio diseño**: es un resultado, no un error.
- **Errores por causa:** 429/503 se reintentan solos según `Retry-After`; 504, 502 y los errores de red
  ofrecen reintentar.
- **Cambiar de organización vacía la caché del cliente**, para que no se vea nada del tenant anterior.

## 11. Uso de IA generativa y cómo verifiqué su salida

Usé asistentes de programación basados en LLM (agentes de terminal) durante todo el proyecto:

- investigar APIs y versiones (Docling, pgvector 0.8, OpenTelemetry, LiteLLM);
- redactar la especificación y el plan;
- generar borradores de código, tests, el generador de PDFs de ejemplo y la interfaz;
- revisar el código contra la especificación.

Las decisiones de este documento las tomé yo, y revisé cada cambio antes de hacer commit.

**Cómo verifiqué la salida:**

- Todo pasa ruff, mypy estricto, ESLint y TypeScript, y la suite de pytest (contra Postgres real con
  pgvector) y Vitest. Los tests de aislamiento usan el rol sin privilegios.
- Cada afirmación importante de este documento tiene su prueba: aislamiento, idempotencia, reintentos de
  punta a punta con Celery, errores del LLM, traza única con spans SQL, canario fuera de la telemetría y
  OCR real con Docling sobre los escaneados.
- Ejecuté el seed y la evaluación, y probé a mano la interfaz.

**Errores de la IA que encontré al revisar y corregí:**

| Error | Corrección |
|---|---|
| La subida encolaba la tarea **antes** del commit: el worker podía recibir un job inexistente | Commit antes de encolar |
| Un 429 de embeddings dejaba el documento «en cola» para siempre: se capturaba y no se reintentaba | Todo error no permanente relanza y Celery reintenta |
| El reaper marcaba jobs como pendientes sin volver a encolarlos | El reaper reencola |
| Ante cualquier error, el cliente de embeddings devolvía vectores falsos | El error se propaga |
| El instrumentador de SQLAlchemy no actuaba (versión fuera de rango, sin aviso) | Instrumentación explícita de los engines |
| Los PDFs «escaneados» de ejemplo tenían capa de texto, así que no probaban el OCR | Ahora son solo imagen |
| Se aceptaba la API key en la query string | Solo en cabecera |
| El Dockerfile del frontend copiaba `node_modules` del host (fallaba en un clon limpio) | Instalación dentro de la imagen |
| nginx cortaba subidas de más de 1 MB | Límite de 26 MB |
| El script de tipos del frontend no revisaba ningún archivo | Apunta a los tsconfig reales |
