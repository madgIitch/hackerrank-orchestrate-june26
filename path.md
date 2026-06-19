# Plan de sprints — Multi-Modal Evidence Review

> Documento de planificación SDD. Cada sprint tiene un objetivo, tareas, entregable y un **gate determinista**: no se avanza al siguiente hasta que el gate pasa. Una feature en progreso a la vez, commits frecuentes sobre `main`.

---

## 0. Objetivo del reto (resumen operativo)

Construir un sistema que, para cada reclamación de daño (`car`, `laptop`, `package`), combine:

1. **Imágenes** (fuente de verdad principal),
2. **Conversación del usuario** (define qué hay que verificar),
3. **Historial del usuario** (añade contexto de riesgo, **no** anula evidencia visual clara),
4. **Requisitos mínimos de evidencia** (`evidence_requirements.csv`),

y produzca un `output.csv` con 14 columnas en orden estricto, valores dentro de los enums permitidos, más una carpeta `evaluation/` y un `evaluation_report.md` con análisis de coste/latencia/rate limits.

El criterio de éxito real del hackathon no es solo acertar `claim_status`: es demostrar **rigor de ingeniería** (gates deterministas, evaluación medida, análisis operativo honesto). Eso juega a tu favor.

---

## 1. Decisiones de arquitectura (acordar antes del Sprint 1)

Estas decisiones condicionan todos los sprints. Conviene fijarlas y no tocarlas salvo que la evaluación lo exija.

**1.1. Híbrido percepción-LLM + reglas deterministas.**
El LLM multimodal hace *solo percepción y razonamiento estructurado*: describe qué ve, qué parte, qué tipo de daño, calidad de imagen, severidad. Las reglas deterministas (Python) hacen el resto: cumplimiento de `evidence_requirements`, coerción a enums permitidos, flags de historial, reconciliación `valid_image` ↔ `risk_flags`. Esto encaja con tu estilo de gates y reduce variabilidad.

**1.2. Una llamada multimodal por reclamación, no por imagen.**
Todas las imágenes de una `claim` van en una sola petición con la conversación. Esto minimiza nº de llamadas (clave para el análisis de coste) y permite al modelo razonar sobre el conjunto (p. ej. "la matrícula aparece en img_1 pero el daño en img_2").

**1.3. Salida JSON estricta + capa de validación.**
El modelo devuelve JSON con un esquema fijo. Un validador en Python: parsea, comprueba enums, y ante valor inválido **degrada a `unknown`/`none`** en vez de romper. Nunca confiar en que el modelo respete los enums sin verificar.

**1.4. Prompt caching del bloque estático.**
El esquema, los enums y `evidence_requirements.csv` son **constantes en todas las llamadas**. Van en un bloque de sistema con `cache_control` para abaratar drásticamente los tokens de entrada. Esto es a la vez optimización real y un punto fuerte del análisis operativo.

**1.5. Separación dataset → pipeline → eval → report.**
El mismo pipeline procesa `sample_claims.csv` (con labels, para evaluar) y `claims.csv` (sin labels, para producir `output.csv`). La evaluación nunca se mezcla con la inferencia final.

**Stack sugerido:** Python, `anthropic` SDK (modelo Claude con visión; valida en pricing actual qué tier te cuadra coste/calidad), `pandas`, `pillow` para redimensionar/normalizar imágenes, `pydantic` para validar el JSON de salida, `tenacity` para retries con backoff.

---

## 2. Sprints

### Sprint 0 — Setup y reconocimiento de datos
**Objetivo:** entender el dataset antes de escribir lógica. La mayoría de errores en este tipo de retos vienen de no haber mirado los datos.

Tareas:
- Scaffold del repo: `dataset/`, `src/`, `evaluation/`, `README.md`, gestión de dependencias.
- Cargar los 4 CSV y perfilar `sample_claims.csv`: distribución de `claim_status`, de `claim_object`, de `issue_type`, cuántos casos por tipo. Saber si está balanceado cambia tu estrategia de prompt.
- Inspeccionar visualmente 8–10 imágenes de `images/sample/` para entender resolución, ruido, casos de borde (borrosas, recortadas, objeto equivocado, instrucciones de texto incrustadas).
- Volcar a `src/schema.py` el esquema de salida (14 columnas, orden exacto) y **todos los enums permitidos** como constantes.
- Mapear `evidence_requirements.csv` a una estructura de lookup por `(claim_object, applies_to)`.

**Entregable:** notebook/script de perfilado + `schema.py` + un `findings.md` corto con la distribución de labels y los casos de borde detectados.

**Gate:** todos los archivos cargan, **todas** las rutas de `image_paths` del sample resuelven a un fichero existente, y los enums están definidos como única fuente de verdad.

---

### Sprint 1 — Capa de IO y datos
**Objetivo:** entradas y salidas sólidas y testeadas, sin tocar el modelo todavía.

Tareas:
- `ClaimLoader`: parsea filas, separa `image_paths` por `;`, deriva `image_id` (filename sin extensión).
- Join con `user_history.csv` por `user_id` (manejar usuarios sin historial).
- Lookup de `evidence_requirements` por objeto + familia de issue, con fallback a reglas `all`.
- `ImageLoader`: carga → redimensiona si hace falta → base64, con control de tamaño (las imágenes grandes disparan tokens).
- `OutputWriter`: escribe CSV forzando **orden de columnas** y validando que cada valor está en el enum permitido.

**Entregable:** módulos de IO + tests que pasan una fila stub por load → (stub de inferencia) → write.

**Gate:** round-trip de una fila del sample produce un CSV válido (14 columnas, orden correcto, valores en enums). Edge cases cubiertos: usuario sin historial, claim con 1 imagen y con N imágenes.

---

### Sprint 2 — Pipeline vertical de una reclamación
**Objetivo:** la primera rebanada vertical completa: una claim real → una fila de salida válida vía LLM.

Tareas:
- Primer prompt de sistema: esquema + enums + requisitos de evidencia relevantes (con `cache_control`).
- Prompt de usuario: imágenes (base64) + transcript + `claim_object`.
- Forzar salida JSON estricta (sin markdown, sin preámbulo).
- Parser + validador (`pydantic`): coerciona a enums, degrada a `unknown`/`none` ante valores fuera de rango.
- Ejecutar sobre 1–3 claims del sample de punta a punta.

**Entregable:** `pipeline.py` que produce una fila de salida válida para una claim real.

**Gate:** una claim de cada tipo de objeto (`car`, `laptop`, `package`) genera una fila que pasa la validación de esquema sin intervención manual.

---

### Sprint 3 — Prompt engineering y lógica de decisión
**Objetivo:** que el contenido sea correcto, no solo válido. Aquí está el grueso del valor.

Tareas:
- Iterar el prompt para extraer bien: claim real del transcript, `issue_type`, `object_part`, `supporting_image_ids`, `severity`, y justificaciones **ancladas en lo que se ve en las imágenes** (mencionando IDs).
- Codificar la regla central: *las imágenes son la fuente de verdad; el historial no anula evidencia visual clara por sí solo*. El `claim_status` (`supported` / `contradicted` / `not_enough_information`) sale de las imágenes contrastadas con la claim.
- Post-proceso determinista: cuando el conjunto de imágenes no cumple el mínimo de evidencia → empujar hacia `not_enough_information` aunque el modelo "intuya".
- Distinguir bien los tres estados: `contradicted` (la imagen muestra lo contrario de lo reclamado) vs `not_enough_information` (no se puede determinar).

**Entregable:** prompt versionado (en `prompts/`) + lógica de reconciliación determinista.

**Gate:** la accuracy de `claim_status` sobre el sample supera un baseline que fijarás tras la primera evaluación del Sprint 5 (sugerencia: itera hasta meseta, registra cada versión de prompt y su score).

---

### Sprint 4 — Suficiencia de evidencia y risk flags
**Objetivo:** completar los campos de evidencia y riesgo, que es donde se nota el rigor.

Tareas:
- Conectar `evidence_requirements` a `evidence_standard_met` + `evidence_standard_met_reason`. La regla determinista decide si el set de imágenes cubre el mínimo para esa familia de issue.
- **Risk flags visuales** (del análisis de imagen): `blurry_image`, `cropped_or_obstructed`, `low_light_or_glare`, `wrong_angle`, `wrong_object`, `wrong_object_part`, `damage_not_visible`, `claim_mismatch`, `possible_manipulation`, `non_original_image`, `text_instruction_present`.
- **Risk flags de historial** (deterministas, de `user_history`): `user_history_risk`, `manual_review_required` derivados de `history_flags`, ratios de aceptación/rechazo y `last_90_days_claim_count`.
- Reconciliar `valid_image`: si las imágenes no son usables para revisión automática → `valid_image=false` y coherencia con los flags.

**Entregable:** módulo de evidencia + módulo de riesgo, ambos testeados contra casos del sample.

**Gate:** `evidence_standard_met`, `risk_flags` y `valid_image` igualan las labels del sample a una tasa objetivo (define el umbral tras ver la matriz de errores).

---

### Sprint 5 — Harness de evaluación
**Objetivo:** medir, no adivinar. Este sprint puede ir en paralelo conceptual con el 3–4: evalúas, ves errores, ajustas prompt.

Tareas:
- `evaluation/run_eval.py`: corre el pipeline sobre `sample_claims.csv` y compara predicción vs esperado **campo a campo**.
- Métricas: accuracy de `claim_status` + **matriz de confusión** (es la métrica reina), accuracy por campo para el resto, y una tabla de los peores casos con la imagen y el porqué.
- Bucle de iteración: errores → hipótesis → ajuste de prompt o de regla → re-evaluar. Registrar cada iteración.

**Entregable:** harness reproducible + reporte de métricas con matriz de confusión + log de iteraciones.

**Gate:** métricas documentadas, al menos N iteraciones registradas, y mejora demostrable respecto al baseline del Sprint 2.

---

### Sprint 6 — Coste, latencia y análisis operativo
**Objetivo:** el `evaluation_report.md` que pide explícitamente el reto. Muchos participantes lo dejan flojo; aquí ganas puntos baratos.

Tareas:
- Contar tokens de entrada/salida por llamada (suma real del sample run; las imágenes cuentan según resolución, de ahí el redimensionado del Sprint 1).
- Activar y medir el ahorro de **prompt caching** del bloque estático.
- Estrategia de rate limits: concurrencia controlada, **retry con backoff exponencial** (`tenacity`), respeto de TPM/RPM, y mención de batching/throttling.
- Redactar `evaluation/evaluation_report.md` con: nº aproximado de llamadas (sample y test), tokens in/out, nº de imágenes procesadas, **coste estimado del test completo** con supuestos de pricing explícitos (usa las tarifas publicadas actuales y deja la fórmula visible), latencia/runtime, y la estrategia de TPM/RPM + caching + retry.

**Entregable:** `evaluation_report.md` completo con números reales del sample y extrapolación al test.

**Gate:** el reporte contiene cifras reales (no placeholders) y supuestos de coste justificados.

---

### Sprint 7 — Run completo, empaquetado y entrega
**Objetivo:** producir los entregables finales validados.

Tareas:
- Ejecutar el pipeline sobre `claims.csv` → `output.csv` (todas las filas).
- `README.md`: arquitectura, cómo ejecutar, decisiones de diseño y trade-offs (incluye el porqué del híbrido y de una llamada por claim).
- Ensamblar `code.zip`: código, `prompts/`, configs, `README.md`, carpeta `evaluation/`.
- Preparar el `chat_transcript`.
- **Validación final automática**: nº de filas de `output.csv` == nº de filas de `claims.csv`, las 14 columnas presentes y en orden, **todos** los valores dentro de los enums permitidos.

**Entregable:** `code.zip` + `output.csv` + `chat_transcript`.

**Gate:** los tres entregables existen y `output.csv` pasa el validador de esquema al 100%.

---

## 3. Riesgos y mitigaciones

- **El modelo no respeta los enums:** capa de validación con coerción a `unknown`/`none` (Sprint 1–2), nunca confiar en el output crudo.
- **Confundir `contradicted` con `not_enough_information`:** es el error más probable y el más penalizado. Trátalo explícitamente en el prompt y en la matriz de confusión (Sprint 3/5).
- **Coste descontrolado por imágenes grandes:** redimensionado en el loader + prompt caching (Sprint 1/6).
- **Historial pisando la evidencia visual:** regla dura de que el historial solo alimenta `risk_flags`, nunca cambia `claim_status` por sí solo (Sprint 3/4).
- **Rate limits durante el run del test:** concurrencia limitada + backoff antes de producir `output.csv` (Sprint 6).

---

## 4. Checklist de entrega final

- [ ] `output.csv` con una fila por cada fila de `claims.csv`, 14 columnas en orden, valores válidos.
- [ ] `code.zip` con código ejecutable, `prompts/`, configs, `README.md` y `evaluation/`.
- [ ] `evaluation/evaluation_report.md` con análisis operativo completo.
- [ ] `chat_transcript`.
- [ ] Métricas de evaluación documentadas (matriz de confusión de `claim_status`).

---

## 5. Nota sobre el tamaño de los sprints

El plan está pensado para ejecutarse con agentes de coding (Claude Code / Codex) feature a feature. Si la ventana del hackathon es corta (24–48h), comprime así: Sprints 0–2 son el "must" del MVP funcional, el 3 y el 5 son donde se gana la puntuación de calidad, y el 6 es el que mejor relación esfuerzo/recompensa tiene de cara al jurado. El 4 puede recortarse a flags básicos si vas justo de tiempo.