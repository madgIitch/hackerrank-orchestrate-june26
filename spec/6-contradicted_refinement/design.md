# 6 · Refinamiento de deteccion de contradicted — Diseño

## Scope (archivos que puede tocar)

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

## Enfoque

- **data_model:** pendiente
- **external_contracts:** pendiente
- **edge_cases:** pendiente
- **ui_states:** pendiente

## Decisiones de la entrevista

- **data_model:** El contrato de 14 columnas no cambia. El post-proceso solo reasigna claim_status entre valores ya existentes del enum (contradicted → not_enough_information). PROMPT_VERSION='v3' es una constante interna del código, no una columna de output.csv. No se añade ningún campo nuevo ni se modifica el schema.py.
- **error_states:** Paso explícito al FINAL del pipeline, después de apply_history_risk_flags — así ve los risk_flags definitivos incluyendo los de historial. La función apply_contradicted_refinement vive en parser_validator.py (al lado de apply_evidence_precedence y filter_supporting_image_ids) y se llama desde pipeline.py como el último paso. En ese punto los risk_flags ya son string semicolon-separado (el pipeline normaliza todo a strings con validate_output_row y los pasos posteriores mantienen ese formato), de modo que la función usa el mismo patrón de parsing con split(';') que usa _risk_flag_list en evidence_rules.py.
- **edge_cases:** Sí en ambos casos. El patrón ya está establecido en el código: _risk_flag_list excluye explícitamente 'none' del conjunto de flags activos, así que risk_flags='none' equivale a lista vacía — ningún flag de discrepancia presente → contradicted degrada. Y sí debe existir un test explícito para contradicted + solo blurry_image: es el caso más probable de error silencioso porque blurry_image es un flag visualmente relacionado con la imagen pero NO es de discrepancia, y un implementador podría confundirlo con claim_mismatch/damage_not_visible.
- **auth_secrets:** Sin nuevas credenciales ni secretos. Se heredan exactamente GEMINI_API_KEY y GEMINI_MODEL de las features anteriores. El nuevo system_prompt_v3.txt es texto estático versionado, no contiene secretos ni datos de usuario.
- **external_contracts:** Texto plano descriptivo hipotético. El prompt de sistema se carga como string estático desde el archivo y no embebe imágenes reales: (1) las imágenes reales viajan en el user_prompt junto al claim específico, no en el system_prompt; (2) embeber base64 de imágenes reales en el system_prompt multiplicaría el coste de cada llamada y rompería el patrón establecido en build_prompt_bundle; (3) los few-shot descriptivos son suficientes para guiar al modelo sobre el criterio de contradicted sin necesitar evidencia visual real en el prompt de sistema.
- **ui_states:** Sin UI. La salida sigue siendo output.csv (14 columnas, misma estructura) y evaluation/evaluation_report.md. No hay cambio de formato ni estados de interfaz nuevos.
- **rollback_compat:** Sí en ambos casos. El orden final del pipeline queda: merge/validate → filter_supporting_image_ids → apply_evidence_rules → apply_evidence_precedence → apply_history_risk_flags → apply_contradicted_refinement. Si apply_evidence_precedence ya degradó contradicted a not_enough_information (por evidence_standard_met=false), la nueva función recibe not_enough_information y no hace nada — sin conflicto. Y sí debe actualizarse claim_status_justification con un texto específico cuando aplica la degradación (p.ej. "contradicted invalidated: no discrepancy risk_flag present") para que sea distinguible del downgrade de feature 4 y trazable en los logs y en evaluation_report.
- **tests:** Verificar el cambio de claim_status es suficiente como aserción principal en todos los casos. Adicionalmente, exactamente UN test (el caso canónico: contradicted sin ningún flag de discrepancia) debe también verificar que claim_status_justification contiene algún substring indicativo de la causa (p.ej. "discrepancy" o "contradicted invalidated"), sin fijar el string exacto. Esto garantiza trazabilidad sin acoplar los tests a la redacción exacta del mensaje.
- **adv-7eeaa1c40e:** ### [adv-39ea056476] El comportamiento para risk_flags=[] (lista vacía) no está especificado: solo se define que risk_flags=['none'] se trata como ausencia de flags de discrepancia, pero una lista vacía puede representar lo mismo o un estado distinto según la implementación, afectando si contradicted se degrada o se preserva.

**R:**
- **adv-34ef38c857:** ### [adv-011a6a6b5d] La distribución de degradaciones contradicted→not_enough_information debe reportarse 'con y sin prompt v3', pero no se especifica qué baseline es 'sin v3': ¿ejecución con v2, sin post-proceso, o con post-proceso pero sin v3? Dos implementaciones razonables producen métricas distintas e incomparables.

**R:**
- **adv-24739a54ad:** ### [adv-de3715dd22] Los tests existentes de features 3, 4 y 5 pueden modificar sus aserciones de claim_status si el cambio está 'explícitamente documentado', pero no se especifica dónde ni en qué formato debe constar esa documentación (comentario en el test, entrada en DECISIONS.md, mensaje de commit), lo que impide verificar si una modificación es válida o no.

**R:**

