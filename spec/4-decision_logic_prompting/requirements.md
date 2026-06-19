# 4 · Prompting y logica de decision — Requisitos

- name: `decision_logic_prompting` · priority: P1 · sdd: true
- aprobado por: peorr · 2026-06-19T11:13:04.648Z

## Contexto

Mejorar la calidad de las decisiones para issue_type, object_part, supporting_image_ids, severity y claim_status, priorizando evidencia visual sobre historial.

## Requisitos funcionales

R1. El prompt mejorado vive en prompts/system_prompt_v2.txt, conserva prompts/system_prompt.txt como baseline v1, define PROMPT_VERSION="v2" en codigo y registra prompt_version en PipelineLog por cada ejecucion; la version no se anade a output.csv.
R2. El prompt instruye al modelo a referenciar image_ids especificos en claim_status_justification y a incluir solo image_ids pertenecientes al ClaimRecord de entrada en supporting_image_ids; el post-proceso elimina IDs ajenos y fuerza not_enough_information si supported/contradicted queda sin image_id valido.
R3. claim_status distingue supported, contradicted y not_enough_information con reglas explicitas: supported requiere evidencia visual del dano reclamado en objeto/parte correctos; contradicted requiere evidencia visual suficiente de ausencia o discrepancia verificable; not_enough_information cubre evidencia insuficiente, imagen no usable o incertidumbre.
R4. El post-proceso fuerza claim_status=not_enough_information, evidence_standard_met=false y supporting_image_ids=none cuando evidence_standard_met normalizado es false, incluso si el modelo devuelve supported o contradicted; no usa patrones de texto de evidence_standard_met_reason como condicion logica.
R5. pipeline.py elimina el hardcode de issue_family_for_issue_type("unknown") antes de conocer issue_type e implementa un flujo de maximo dos pasadas: triage/extraccion multimodal breve, lookup de requirements exactos, y decision final con transcript, imagenes, resumen de triage, requirements e historial.
R6. Si la primera pasada falla o devuelve issue_type/object_part inutilizables, el pipeline cae a requirements generales y la decision final debe poder devolver una fila valida not_enough_information sin abortar el batch.
R7. La evaluacion sobre sample_claims.csv compara v2 contra el baseline v1 y reporta accuracy de claim_status como metrica primaria, mas issue_type, object_part y coherencia de supporting_image_ids; v2 debe tener claim_status accuracy mayor o igual que v1, o documentar categorias de error restantes sin empeorar issue_type/object_part frente al baseline.
R8. Los tests existentes siguen cubriendo fallback, validacion de enums y escritura a tmp_path; pueden actualizarse solo para el comportamiento documentado. Se anaden tests unitarios deterministas sin modelo real para supported+evidence false -> not_enough_information, contradicted+evidence false -> not_enough_information, not_enough_information+evidence true se preserva, IDs ajenos se descartan, e historial no puede elevar not_enough_information a supported/contradicted.
R9. La historia del usuario puede anadir risk_flags como user_history_risk y enriquecer claim_status_justification, pero nunca cambia claim_status por si sola; la evidencia visual mantiene precedencia sobre historial.

## Restricciones

- **error_states:** evidence_standard_met=false tiene precedencia absoluta sobre supported y contradicted. Si no se cumple la evidencia mínima, el post-proceso fuerza claim_status=not_enough_information y, si no hay imagen suficiente, supporting_image_ids=none; evidence_standard_met permanece false. contradicted solo es válido cuando hay evidencia visual suficiente para verificar una ausencia o discrepancia concreta del daño reclamado; sin esa suficiencia, el resultado correcto es not_enough_information, no contradicted.
- **auth_secrets:** Heredado de feature 3: credenciales solo desde variables de entorno (GEMINI_API_KEY, GEMINI_MODEL). Feature 4 no añade nuevas integraciones externas ni secretos adicionales.
- **rollback_compat:** Los tests existentes pueden actualizarse solo cuando el nuevo comportamiento esté documentado, pero no deben perder cobertura de fallback, validación de enums ni escritura a tmp_path. No se requiere preservar un artefacto baseline previo si aún no existe; para comparar, la evaluación debe poder ejecutar o documentar el baseline v1 usando prompts/system_prompt.txt y guardar resultados bajo evaluation/. El pipeline v2 no puede romper los contratos de salida (14 columnas, enums existentes).

