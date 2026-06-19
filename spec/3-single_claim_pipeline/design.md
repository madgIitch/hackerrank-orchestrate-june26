# 3 · Pipeline vertical de una reclamacion — Diseño

## Scope (archivos que puede tocar)

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

## Enfoque

- **data_model:** El modelo produce un JSON candidato con exactamente 10 campos de decision: evidence_standard_met, evidence_standard_met_reason, risk_flags, issue_type, object_part, claim_status, claim_status_justification, supporting_image_ids, valid_image, severity. Los campos de entrada user_id, image_paths, user_claim y claim_object se preservan desde ClaimRecord sin pasar por el modelo. Normalizacion via schema.py/OutputWriter: enums invalidos a unknown/none/not_enough_information segun el campo, booleanos invalidos a false, listas invalidas filtradas.
- **external_contracts:** Gemini por defecto (coste), capa ModelClient aislada y configurable por env vars. GEMINI_API_KEY para la key, GEMINI_MODEL para el modelo con default Gemini Flash documentado en README. JSON estricto forzado con mecanismo nativo del proveedor. Transcript proviene del campo user_claim de ClaimRecord; no hay archivo separado.
- **edge_cases:** Fallo parcial de imagenes: continuar con las restantes, marcar manual_review_required en risk_flags, reflejar evidencia parcial en evidence_standard_met_reason y claim_status_justification; si la imagen faltante impide verificar, claim_status=not_enough_information y evidence_standard_met=false. Sin imagenes usables: fila fallback con valid_image=false, evidence_standard_met=false, risk_flags=manual_review_required, supporting_image_ids=none, claim_status=not_enough_information.
- **ui_states:** Sin UI. Salida es OutputRow/dict validado por claim. Coherente con el resto del proyecto.

## Decisiones de la entrevista

- **adv-496fec98f9:** No se omite la fila ni se aborta el batch. Cualquier fallo de llamada, timeout, respuesta vacia o JSON no parseable produce una fila fallback valida con claim_status=not_enough_information, evidence_standard_met=false, valid_image=false, risk_flags=manual_review_required, supporting_image_ids=none y severity=unknown.
- **adv-b00af563ea:** Esta feature no escribe output.csv en la raiz. El pipeline devuelve una OutputRow/dict validado y solo escribe CSV si recibe un path explicito; los tests usan tmp_path. La generacion de output.csv final queda para final_submission_package.
- **adv-b28570c402:** Los gates normales usan tests deterministas con mock del modelo, sin credenciales ni coste. Puede existir un test real opcional contra Gemini, saltado por defecto, que solo corre con RUN_MODEL_TESTS=1 y GEMINI_API_KEY.
- **adv-c543ae58d3:** El criterio debe producir siempre tres filas para tres ClaimRecords. Si una llamada al modelo falla para una claim, esa claim produce su fila fallback valida en lugar de saltarse.
- **adv-6d31ccdc92:** El proveedor de esta feature queda fijado a Gemini mediante ModelClient. El modelo exacto es configurable por GEMINI_MODEL, pero el mecanismo verificable de JSON estricto es el response MIME JSON o equivalente soportado por el SDK de Gemini.
- **data_model:** El modelo debe producir un JSON candidato con todos los campos de decision del contrato de salida: evidence_standard_met, evidence_standard_met_reason, risk_flags, issue_type, object_part, claim_status, claim_status_justification, supporting_image_ids, valid_image y severity. Los campos de entrada user_id, image_paths, user_claim y claim_object se preservan desde ClaimRecord. El codigo no debe inventar una segunda logica de decision en esta feature, pero si debe validar, normalizar y degradar valores invalidos con schema.py/OutputWriter: enums invalidos a unknown/none/not_enough_information segun corresponda, booleanos invalidos a false y listas invalidas filtradas. En features posteriores se podran mover evidence_standard_met, valid_image o risk_flags a reglas deterministas, pero aqui el objetivo es el pipeline vertical con validacion.
- **error_states:** No se omite la fila. Para una respuesta no parseable, respuesta vacia, timeout, error HTTP o exceso de tokens, el pipeline debe devolver una fila fallback valida: evidence_standard_met=false, evidence_standard_met_reason describiendo el fallo del modelo, risk_flags=manual_review_required, issue_type=unknown, object_part=unknown, claim_status=not_enough_information, claim_status_justification indicando que la revision automatica no pudo completarse, supporting_image_ids=none, valid_image=false y severity=unknown. El error debe registrarse de forma local sin incluir secretos.
- **edge_cases:** Si falla una imagen pero hay otras imagenes cargables, el pipeline continua con las restantes y marca manual_review_required en risk_flags; la razon de evidence_standard_met y la justificacion de claim_status deben reflejar que la evidencia fue parcial. Si la imagen faltante impide verificar la reclamacion, claim_status debe terminar en not_enough_information y evidence_standard_met=false. Si no queda ninguna imagen usable, se devuelve una fila fallback valida con valid_image=false, evidence_standard_met=false, risk_flags=manual_review_required, supporting_image_ids=none y claim_status=not_enough_information.
- **external_contracts:** Usar Gemini por defecto por coste, mediante una capa ModelClient aislada y configurable por variables de entorno. La API key se lee de GEMINI_API_KEY y el modelo de GEMINI_MODEL, con un valor por defecto de la familia Gemini Flash documentado en README para poder cambiarlo sin tocar codigo. La llamada debe forzar JSON estricto con el mecanismo nativo disponible del proveedor. El transcript proviene del campo user_claim de sample_claims.csv/claims.csv; no hay archivo separado ni transcript sintetico para runtime. Los tests unitarios pueden usar transcripts fixture derivados del propio user_claim.
- **rollback_compat:** Esta feature no debe escribir output.csv en la raiz. El pipeline debe poder devolver una OutputRow/dict validado para una claim y, si se necesita persistir durante pruebas o demos, escribir solo en un path explicito pasado por parametro o en tmp_path desde tests. La generacion de output.csv final queda reservada para la feature final_submission_package.
- **tests:** Los tests obligatorios deben ser deterministas y mockear la respuesta del modelo, sin credenciales reales ni coste en pytest/CI. Puede existir un test de integracion real opcional, saltado por defecto, que solo corre si RUN_MODEL_TESTS=1 y GEMINI_API_KEY estan definidos; ese test no debe bloquear los gates normales. Los fixtures deben cubrir car, laptop y package, respuesta valida, JSON no parseable/fallo de llamada, valores invalidos degradados e imagen faltante/parcial.

