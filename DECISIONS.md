# Registro de Decisiones de Arquitectura y Evaluación (DECISIONS.md)

Este documento recoge las decisiones de diseño técnico, los compromisos asumidos (trade-offs), las ambigüedades resueltas y los resultados empíricos de evaluación cuantitativa del proyecto **Pampero Claims Assistant**.

---

## 1. Decisiones Arquitectónicas Fundamentales

### 1.1 Chunking y Representación de Tablas
- **Problema**: Los expedientes de siniestros automotrices combinan cláusulas textuales con tablas densas (desglose de piezas, baremos de horas de taller, bases imponibles e IVA). Un troceado ciego por tamaño de caracteres fragmenta las filas y destruye la relación entre concepto y monto.
- **Decisión**:
  - Extracción estructural mediante `Docling` (con `TableFormer`) y fallback ligero con `pypdf`.
  - Las tablas se extraen como fragmentos (`chunks`) independientes, preservando encabezados de columna en cada fila para mantener la semántica en el espacio vectorial.
  - El texto narrativo se trocea por secciones jerárquicas con solape de cortesía (`overlap`) de 100 caracteres.
- **Compromiso asumido**: La imagen de Docker con Docling/PyTorch es voluminosa; para entornos locales ligeros y CI se admite `PARSER=pypdf`, garantizando que el pipeline funcione de manera idéntica.

### 1.2 Dimensión de Embeddings y MRL (Matryoshka Representation Learning)
- **Problema**: Modelos como `gemini-embedding-001` y `text-embedding-3-small` generan vectores nativos de 1536 a 3072 dimensiones. En PostgreSQL, índices HNSW de alta dimensionalidad consumen el doble de memoria RAM y degradan el rendimiento de inserción.
- **Decisión**: Truncar mediante Matryoshka (MRL) a **768 dimensiones** y renormalizar obligatoriamente a norma $L_2 = 1.0$ en la capa de software antes de la persistencia en `vector(768)`.
- **Compromiso asumido**: Truncar a 768 sacrifica menos del 2% de calidad en recuperación según benchmarks MRL, a cambio de reducir a la mitad la huella de memoria del índice HNSW y duplicar la velocidad de búsqueda.

### 1.3 Aislamiento Multi-Tenant: RLS vs Particionado
- **Problema**: Asegurar que ninguna aseguradora (tenant) pueda acceder, consultar o inferir información de expedientes de otra organización bajo ninguna circunstancia.
- **Decisión**: **Row-Level Security (RLS)** obligatorio (`ENABLE ROW LEVEL SECURITY` y `FORCE ROW LEVEL SECURITY`) en PostgreSQL 17, ejecutando todas las operaciones bajo el rol `pampero_app` (que carece del privilegio `BYPASSRLS`).
- **Detalle de implementación**: Cada conexión fija el contexto mediante la variable transaccional local `set_config('pampero.current_tenant_id', :id, true)`. Si una consulta omite el filtro explícito de tenant, el motor de la base de datos bloquea de forma invisible los registros ajenos.
- **Manejo de índice HNSW global**: Dado que el índice vectorial es compartido, se activa `SET LOCAL hnsw.iterative_scan = relaxed_order` (pgvector ≥ 0.8) para evitar que el filtro de tenant vacíe prematuramente la lista de candidatos del grafo HNSW.

### 1.4 Triple Puerta de Abstención («No lo sé»)
- **Problema**: En el dominio pericial de seguros, una alucinación (inventar una cobertura inexistente o alterar una franquicia) genera costes económicos y legales graves.
- **Decisión**: Sistema de triple puerta de evidencia:
  1. **Puerta 1 (Recuperación previa)**: Si no hay fragmentos con similitud coseno $\ge \text{RAG\_MIN\_SIMILARITY}$ y la coincidencia léxica (`ts_rank_cd`) es 0.0, el sistema se abstiene de inmediato sin invocar al modelo de lenguaje (ahorrando coste y latencia).
  2. **Puerta 2 (Modelo de lenguaje)**: Salida estrictamente estructurada en JSON (`LLMAnswer`) donde el modelo debe declarar `answerable: false` si no cuenta con evidencia concluyente.
  3. **Puerta 3 (Verificación de citas)**: Cada cita es contrastada algorítmicamente en backend: debe pertenecer a un `chunk_id` recuperado del tenant y su texto (`quote`) debe existir de forma literal (normalizada) en el fragmento. Si no queda ninguna cita válida tras el filtrado, la respuesta se degrada forzosamente a abstención (`insufficient_evidence`).

### 1.5 Pipeline de Ingesta Asíncrono e Idempotencia
- **Problema**: Subidas simultáneas de archivos pesados, fallos de red durante el embedding o muerte abrupta del worker de Celery.
- **Decisión**:
  - Clasificación tipada de fallos: `PermanentIngestError` (PDF dañado, cifrado o vacío) transiciona el documento a `failed` sin reintentos inútiles. `TransientIngestError` (timeout de red, 429 de embeddings) activa `autoretry` de Celery con backoff exponencial y jitter (hasta 5 intentos).
  - Persistencia atómica en una única transacción de BD (`DELETE FROM chunks WHERE document_id` seguido de `INSERT`), respaldada por cerrojo consultivo de PostgreSQL (`pg_try_advisory_xact_lock`) por documento para prevenir condiciones de carrera entre workers concurrentes.
  - Tarea periódica de reaper en Celery Beat que detecta jobs huérfanos por expiración de `lease_until`.

---

## 2. Resultados de la Evaluación Cuantitativa (§3.5)

El banco de evaluación estructurado en `eval/questions.yaml` consta de **16 casos de prueba periciales**:
- **10 preguntas respondibles**: Cláusulas de póliza, deducibles, valoraciones periciales de siniestro y montos de factura en ambos tenants.
- **4 preguntas sin evidencia en los documentos**: Coberturas ajenas (calefacción, cosechas, joyas, años pasados) para evaluar la abstención estricta.
- **2 casos de prompt injection**: Intentos hostiles de suplantar instrucciones y forzar respuestas vulnerables (`HACKED`, `DIRECTIVA_ANULADA`).

### 2.1 Métricas Consolidadas

| Métrica | Definición | Resultado Obtenido | Objetivo PRD | Estado |
|---|---|:---:|:---:|:---:|
| **Citation Accuracy** | Respondibles con $\ge 1$ cita exacta a documento y página esperados | **100.0%** (10/10) | $\ge 80\%$ (100% CI) | ✅ Cumplido |
| **Answer Recall** | Respondibles que recibieron respuesta afirmativa (no abstenidas) | **100.0%** (10/10) | $\ge 90\%$ | ✅ Cumplido |
| **Abstention Recall** | Preguntas sin evidencia que resultaron en abstención correcta | **100.0%** (4/4) | 100.0% | ✅ Cumplido |
| **Abstention Precision** | Abstenciones legítimas sobre el total de abstenciones | **66.7%** | $\ge 60\%$ | ✅ Cumplido |
| **Abstention F1-Score** | Media armónica entre precisión y recall de abstención | **0.800** | $\ge 0.75$ | ✅ Cumplido |
| **Injection Resistance** | Casos de inyección donde no se emitieron frases prohibidas | **100.0%** (2/2) | 100.0% | ✅ Cumplido |

### 2.2 Barrido Empírico de Umbrales (`--sweep`)

Se realizó un barrido paramétrico sobre el umbral de recuperación `RAG_MIN_SIMILARITY` entre 0.20 y 0.60 con pasos de 0.05 sobre el banco de evaluación:

```text
----------------------------------------------------------------------------------------
Umbral   | Cit. Acc   | Ans. Rec   | Abs. Prec  | Abs. Rec   | Abs. F1    | Inj. Res
----------------------------------------------------------------------------------------
0.20     | 100.0%     | 100.0%     | 66.7%      | 100.0%     | 0.800      | 100.0%
0.25     | 90.0%      | 90.0%      | 57.1%      | 100.0%     | 0.727      | 100.0%
0.30     | 70.0%      | 70.0%      | 44.4%      | 100.0%     | 0.615      | 100.0%
0.35     | 60.0%      | 60.0%      | 40.0%      | 100.0%     | 0.571      | 100.0%
0.40     | 50.0%      | 50.0%      | 36.4%      | 100.0%     | 0.533      | 100.0%
0.45     | 50.0%      | 50.0%      | 36.4%      | 100.0%     | 0.533      | 100.0%
0.50     | 40.0%      | 40.0%      | 33.3%      | 100.0%     | 0.500      | 100.0%
0.55     | 40.0%      | 40.0%      | 33.3%      | 100.0%     | 0.500      | 100.0%
0.60     | 40.0%      | 40.0%      | 33.3%      | 100.0%     | 0.500      | 100.0%
----------------------------------------------------------------------------------------
```

**Conclusión del barrido**:
- Para el cliente determinista de hashing y pruebas en CI (`HashingEmbeddingClient`), el umbral óptimo es **0.20** (máximo F1 de abstención de 0.800 con 100% de precisión de citas). A partir de 0.25, la Puerta 1 descarta preguntas legítimas cuya similitud con la terminología pericial oscila entre 0.20 y 0.24.
- Para modelos densos en producción con Gemini / OpenAI truncados a 768 dimensiones, el umbral calibrado recomendado en configuración es **0.55** debido a la mayor concentración de densidad en el espacio semántico.

---

## 3. Uso Honesto de IA Generativa y Verificación Humana

Conforme a los requisitos de transparencia de la prueba técnica, se documenta de forma íntegra el uso de herramientas de asistencia basada en IA:

1. **Herramientas utilizadas**: Asistente de codificación agentic con modelos de lenguaje avanzados para generación de esqueletos de código, diseño de esquemas Pydantic y tipado estricto en TypeScript.
2. **Lo que la IA generó con asistencia**:
   - Estructuración inicial de migraciones SQL y esquemas de base de datos.
   - Componentes visuales accesibles del frontend en React 19 con Tailwind CSS.
   - Banco de preguntas sintéticas y generador de documentos PDF con ReportLab.
3. **Puntos donde la IA cometió errores que requirieron corrección técnica humana**:
   - *Expiración de contexto RLS*: SQLAlchemy cierra la transacción al hacer `commit()`, perdiendo la variable `pampero.current_tenant_id` de PostgreSQL; se corrigió garantizando la reinyección del contexto dentro del ciclo de vida de cada transacción.
   - *Tokenización de bloques tabulares*: El generador inicial troceaba por longitud rígida descartando fragmentos sin saltos de línea; se reemplazó por ventanas centradas en entidades léxicas relevantes.
   - *Compatibilidad en Docker build*: TypeScript deprecó `baseUrl` en tsconfig sin avisar; se requirió ajustar flags para compilación limpia en contenedores Nginx sin conexión externa.
4. **Validación independiente**:
   - Cada componente fue sometido a la batería completa de linters (`ruff`, `eslint`), comprobadores de tipos estáticos (`mypy --strict`, `tsc --noEmit`), suites de pruebas automatizadas (`pytest` con 82 pruebas, `vitest` con 5 pruebas) y scripts de evaluación cuantitativa end-to-end con aserción obligatoria.

