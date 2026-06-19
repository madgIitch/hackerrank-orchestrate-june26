# Arquitectura

> El agente lo lee antes de implementar. Mantén aquí el contexto que no cabe en una feature concreta.

## Visión general

Producto/proyecto:

Usuarios principales:

Objetivo no negociable:

## Componentes

- (rellenar) Componente:
  - Responsabilidad:
  - Entradas/salidas:
  - Dueño/riesgo:

## Flujo de datos

1. (rellenar)

## Integraciones externas

- (rellenar) Servicio/API:
  - Contrato:
  - Credenciales/config:
  - Entorno local/CI:

## Restricciones conocidas

- (rellenar) Rendimiento, seguridad, compatibilidad, despliegue, coste, etc.

## Decisiones abiertas

- (rellenar) Preguntas que bloquean diseño futuro.

<!-- Los specs aprobados se anexan debajo con marcadores harness:<id>. -->

<!-- harness:1 -->
## 1 · Setup, reconocimiento de datos y esquema base

Preparar la estructura del proyecto, perfilar los CSV de sample, revisar imagenes de ejemplo y definir el esquema de salida con los enums permitidos como fuente de verdad.

### Scope aprobado

  - `dataset/**`
  - `evaluation/**`
  - `prompts/**`
  - `code/**`
  - `docs/**`
  - `tests/**`
  - `README.md`
  - `pyproject.toml`
  - `requirements.txt`

### Contexto técnico

- **data_model:** El contrato de salida queda fijado con exactamente 14 columnas en este orden: user_id, image_paths, user_claim, claim_object, evidence_standard_met, evidence_standard_met_reason, risk_flags, issue_type, object_part, claim_status, claim_status_justification, supporting_image_ids, valid_image, severity. Los enums aprobados son fuente de verdad centralizada: claim_status = supported, contradicted, not_enough_information; claim_object = car, laptop, package; issue_type = dent, scratch, crack, glass_shatter, broken_part, missing_part, torn_packaging, crushed_packaging, water_damage, stain, none, unknown; object_part por claim_object: car = front_bumper, rear_bumper, door, hood, windshield, side_mirror, headlight, taillight, fender, quarter_panel, body, unknown; laptop = screen, keyboard, trackpad, hinge, lid, corner, port, base, body, unknown; package = box, package_corner, package_side, seal, label, contents, item, unknown; risk_flags = none, blurry_image, cropped_or_obstructed, low_light_or_glare, wrong_angle, wrong_object, wrong_object_part, damage_not_visible, claim_mismatch, possible_manipulation, non_original_image, text_instruction_present, user_history_risk, manual_review_required; severity = none, low, medium, high, unknown. valid_image y evidence_standard_met son booleanos serializados en CSV como true/false.
- **external_contracts:** Rutas canonicas: dataset/sample_claims.csv, dataset/claims.csv, dataset/user_history.csv, dataset/evidence_requirements.csv, dataset/images/sample/** y dataset/images/test/**. Salidas de esta feature: codigo bajo code/ si se usa esa estructura, tests bajo tests/ si se crean, reporte de perfilado bajo evaluation/ o code/evaluation/ segun la estructura elegida, y documentacion en README.md/docs. La salida final del reto sera output.csv en la raiz, pero esta feature no debe generar predicciones finales; si se genera una plantilla, debe ser solo para validar columnas y no confundirse con la entrega final. CSV en UTF-8, con cabecera, delimitador coma, quoting estandar de csv/pandas y preservando los textos originales de user_claim.
- **edge_cases:** image_paths multiples se separan por punto y coma, recortando espacios y descartando segmentos vacios accidentales; si no queda ninguna ruta, la fila del sample es invalida. image_id se deriva del nombre de archivo sin extension. Los valores categoricos se normalizan con trim y lowercase solo para validar/perfilar; el output debe usar exactamente los enums canonicos. claim_object solo permite car, laptop o package. object_part se valida contra el enum correspondiente al claim_object y, si no puede determinarse en fases posteriores, se usara unknown. No existe claim_id en el contrato y no debe asumirse. Filas duplicadas se reportan como hallazgo, pero no se deduplican automaticamente.
- **ui_states:** No hay interfaz de usuario en esta feature; el resultado esperado son estructura de proyecto, scripts/notebooks, documentacion, reporte de perfilado y validaciones locales.

<!-- harness:2 -->
## 2 · Capa de IO y datos

Construir loaders y writers deterministas para claims, historial, requisitos de evidencia, imagenes y salida CSV valida, sin depender todavia del modelo.

### Scope aprobado

  - `code/schema.py`
  - `code/profile_data.py`
  - `code/io_data.py`
  - `tests/test_io_data.py`
  - `docs/ARCHITECTURE.md`
  - `docs/DECISIONS.md`
  - `spec/**`
  - `progress/**`

### Contexto técnico

- **data_model:** Los loaders exponen dataclasses tipadas propias del proyecto y solo serializan a dict en los bordes CSV. ClaimLoader devuelve ClaimRecord con user_id, image_paths normalizados, image_ids, user_claim y claim_object. El enriquecimiento devuelve EnrichedClaim con claim y history. El historial ausente se representa de forma determinista como UserHistory(user_id=<claim user_id>, past_claim_count=0, accept_claim=0, manual_review_claim=0, rejected_claim=0, last_90_days_claim_count=0, history_flags="none", history_summary="No history available").
- **external_contracts:** ImageLoader devuelve ImagePayload con image_id, source_path, media_type, width, height, base64_data, resized, original_width, original_height y byte_size. El payload no es data URL: usa base64 crudo y media_type separado. max_dimension=1024. Si ancho y alto son <= 1024, no reescala y conserva bytes/formato originales. Si alguna dimension supera 1024, reescala manteniendo aspect ratio, convierte a JPEG RGB quality=85 y media_type="image/jpeg". Las rutas relativas se resuelven contra dataset/. No hay llamadas a modelo ni red.
- **edge_cases:** EvidenceRequirements.lookup recibe claim_object y una issue_family normalizada por el caller. En esta feature no se infiere familia desde texto libre, salvo helper permitido issue_family_for_issue_type(issue_type) con mapeo inicial: dent/scratch -> "dent or scratch"; crack/glass_shatter/broken_part/missing_part -> "crack, broken, or missing part"; torn_packaging/crushed_packaging -> "torn or crushed packaging"; water_damage/stain -> "water damage or stain"; none/unknown -> "general claim review". Precedencia: 1) claim_object exacto y applies_to exacto; 2) claim_object=all y applies_to exacto; 3) claim_object exacto y applies_to="general claim review"; 4) claim_object=all y applies_to="general claim review". Multiples coincidencias en el mismo nivel se devuelven todas en orden original del CSV.
- **ui_states:** No hay UI para esta feature; es capa de IO/datos con tests automatizados.

<!-- harness:3 -->
## 3 · Pipeline vertical de una reclamacion

Procesar una claim real de punta a punta mediante analisis multimodal, salida JSON estricta, validacion y fila de output valida.

### Scope aprobado

  - `code/pipeline.py`
  - `code/prompt_builder.py`
  - `code/model_client.py`
  - `code/parser_validator.py`
  - `prompts/system_prompt.txt`
  - `tests/test_pipeline.py`
  - `docs/ARCHITECTURE.md`
  - `docs/DECISIONS.md`
  - `spec/**`
  - `progress/**`

### Contexto técnico

- **data_model:** El modelo produce un JSON candidato con exactamente 10 campos de decision: evidence_standard_met, evidence_standard_met_reason, risk_flags, issue_type, object_part, claim_status, claim_status_justification, supporting_image_ids, valid_image, severity. Los campos de entrada user_id, image_paths, user_claim y claim_object se preservan desde ClaimRecord sin pasar por el modelo. Normalizacion via schema.py/OutputWriter: enums invalidos a unknown/none/not_enough_information segun el campo, booleanos invalidos a false, listas invalidas filtradas.
- **external_contracts:** Gemini por defecto (coste), capa ModelClient aislada y configurable por env vars. GEMINI_API_KEY para la key, GEMINI_MODEL para el modelo con default Gemini Flash documentado en README. JSON estricto forzado con mecanismo nativo del proveedor. Transcript proviene del campo user_claim de ClaimRecord; no hay archivo separado.
- **edge_cases:** Fallo parcial de imagenes: continuar con las restantes, marcar manual_review_required en risk_flags, reflejar evidencia parcial en evidence_standard_met_reason y claim_status_justification; si la imagen faltante impide verificar, claim_status=not_enough_information y evidence_standard_met=false. Sin imagenes usables: fila fallback con valid_image=false, evidence_standard_met=false, risk_flags=manual_review_required, supporting_image_ids=none, claim_status=not_enough_information.
- **ui_states:** Sin UI. Salida es OutputRow/dict validado por claim. Coherente con el resto del proyecto.

<!-- harness:4 -->
## 4 · Prompting y logica de decision

Mejorar la calidad de las decisiones para issue_type, object_part, supporting_image_ids, severity y claim_status, priorizando evidencia visual sobre historial.

### Scope aprobado

  - `prompts/system_prompt.txt`
  - `prompts/system_prompt_v2.txt`
  - `code/prompt_builder.py`
  - `code/parser_validator.py`
  - `code/pipeline.py`
  - `code/evaluation/main.py`
  - `evaluation/evaluation_report.md`
  - `tests/test_pipeline.py`
  - `tests/test_parser_validator.py`
  - `docs/ARCHITECTURE.md`
  - `docs/DECISIONS.md`
  - `spec/**`
  - `progress/**`

### Contexto técnico

- **data_model:** PROMPT_VERSION='v2' como constante en código; el pipeline registra la versión en PipelineLog por ejecución. El prompt mejorado vive en prompts/system_prompt_v2.txt; prompts/system_prompt.txt se preserva sin modificar como baseline de feature 3. La versión NO se añade al output.csv (contrato de 14 columnas fijo); evaluation/evaluation_report.md debe indicar prompt_version tanto para el baseline v1 como para la estrategia v2.
- **external_contracts:** El prompt mejorado se guarda en prompts/system_prompt_v2.txt y se selecciona vía constante PROMPT_VERSION='v2' o parámetro en el prompt builder; v2 es el default del pipeline tras esta feature. prompts/system_prompt.txt se conserva sin reemplazar para reproducir el baseline v1. Evaluación y producción usan la misma selección por defecto; los scripts de evaluación pueden recibir versión explícita para correr comparativas.
- **edge_cases:** Flujo de dos pasadas máximo. Pasada 1: extracción/triage multimodal corto para identificar claim normalizada, issue_type candidato, object_part candidato, observaciones visuales e image_ids relevantes; con ese resultado se buscan los evidence_requirements exactos. Pasada 2: decisión final con transcript, imágenes, resumen de pasada 1, requisitos exactos e historial. Si la pasada 1 falla o devuelve valores inutilizables, se cae a requisitos generales y la pasada 2 debe poder producir not_enough_information. Máximo 2 llamadas por claim. El hardcode de issue_family_for_issue_type('unknown') se elimina; el flujo de dos pasadas es el mecanismo documentado en DECISIONS.md.
- **ui_states:** No hay UI. El output sigue siendo output.csv y evaluation/evaluation_report.md. Las justificaciones son campos de texto en el CSV.

<!-- harness:5 -->
## 5 · Suficiencia de evidencia y risk flags

Implementar reglas deterministas para evidence_standard_met, valid_image y risk_flags visuales y de historial.

### Scope aprobado

  - `code/evidence_rules.py`
  - `code/parser_validator.py`
  - `code/pipeline.py`
  - `code/schema.py`
  - `code/evaluation/main.py`
  - `tests/test_evidence_rules.py`
  - `tests/test_pipeline.py`
  - `tests/test_parser_validator.py`
  - `evaluation/evaluation_report.md`
  - `docs/ARCHITECTURE.md`
  - `docs/DECISIONS.md`
  - `spec.json`
  - `spec/**`
  - `progress/**`

### Contexto técnico

- **data_model:** Las reglas deterministas se implementan como post-proceso: el modelo aporta la decisión normalizada (evidence_standard_met, evidence_standard_met_reason, risk_flags, supporting_image_ids, valid_image, claim_status), pero la capa determinista en code/evidence_rules.py prevalece para evidence_standard_met, valid_image, risk_flags estructurales y cualquier degradación de claim_status derivada de evidencia insuficiente. No se añade model_visual_observations al contrato de 10 campos ni al output.csv; el visual_summary de feature 4 puede usarse como contexto interno/log pero no como condición basada en parsing de texto libre. La frontera es explícita: el modelo propone, las reglas corrigen si entran en conflicto con evidence_requirements.csv o el contrato de schema.py.
- **external_contracts:** evidence_requirements.csv y user_history.csv ya tienen loaders en feature 2 con contratos fijados. No hay nuevas APIs ni servicios externos.
- **edge_cases:** valid_image=true si al menos una imagen nítida, relevante y usable muestra el objeto o pieza reclamada con suficiente contexto para revisar la condición. wrong_angle se trata como flag de calidad/reviewabilidad: si wrong_angle es el único problema pero otra imagen relevante permite evaluar la pieza, valid_image sigue true; si todas las imágenes relevantes tienen wrong_angle y no permiten inspeccionar la condición reclamada, valid_image=false. En sets multi-imagen, risk_flags visuales se emiten aunque afecten solo parte del set, pero no fuerzan valid_image=false si queda al menos una imagen usable para la pieza reclamada. valid_image=false solo cuando ninguna imagen cargada permite evaluar el objeto/parte reclamada. Los risk_flags multi-imagen se fusionan como unión ordenada de enums canónicos separados por punto y coma, sin prefijos por image_id; el detalle por imagen puede quedar en evidence_standard_met_reason o claim_status_justification como texto humano.
- **ui_states:** No hay interfaz de usuario. La salida es output.csv y métricas en evaluation_report.md.

<!-- harness:6 -->
## 6 · Refinamiento de deteccion de contradicted

Mejorar la precision de claim_status=contradicted, que en la evaluacion de feature 4 mostro el patron de error mas critico (contradicted predicho como supported). Introducir un post-proceso determinista que valide contradicted contra risk_flags y ejemplos few-shot en el prompt.

### Scope aprobado

  - `prompts/system_prompt_v3.txt`
  - `code/prompt_builder.py`
  - `code/parser_validator.py`
  - `code/pipeline.py`
  - `tests/test_parser_validator.py`
  - `tests/test_pipeline.py`
  - `evaluation/evaluation_report.md`
  - `docs/ARCHITECTURE.md`
  - `docs/DECISIONS.md`
  - `spec/**`
  - `progress/**`

### Contexto técnico

- **data_model:** pendiente
- **external_contracts:** pendiente
- **edge_cases:** pendiente
- **ui_states:** pendiente

