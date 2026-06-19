# 6 · Refinamiento de deteccion de contradicted — Requisitos

- name: `contradicted_refinement` · priority: P1 · sdd: true
- aprobado por: peorr · 2026-06-19T18:46:02.725Z

## Contexto

Mejorar la precision de claim_status=contradicted, que en la evaluacion de feature 4 mostro el patron de error mas critico (contradicted predicho como supported). Introducir un post-proceso determinista que valide contradicted contra risk_flags y ejemplos few-shot en el prompt.

## Requisitos funcionales

R1. system_prompt_v3.txt contiene al menos 2 ejemplos few-shot de claim_status=contradicted (texto descriptivo de situación + imagen, indicando la discrepancia verificable) y al menos 1 ejemplo de not_enough_information que un modelo sin contexto confundiría con contradicted; system_prompt_v2.txt se preserva sin modificar.
R2. PROMPT_VERSION='v3' en código; el pipeline usa v3 por defecto tras esta feature.
R3. El post-proceso de contradicted se ejecuta como último paso del pipeline, después de apply_history_risk_flags, operando sobre risk_flags en formato lista/set Python (no string CSV); el paso queda documentado en el orden oficial de DECISIONS.md.
R4. El post-proceso invalida claim_status=contradicted → not_enough_information si y solo si ninguno de {claim_mismatch, damage_not_visible, wrong_object, wrong_object_part} está presente en los risk_flags finales; risk_flags=['none'] se trata como ausencia de flags de discrepancia.
R5. El post-proceso no modifica claim_status=supported ni claim_status=not_enough_information bajo ninguna condición.
R6. Cuando ocurre la degradación contradicted→not_enough_information por esta regla, claim_status_justification se actualiza con una nota que indica la causa (e.g., 'contradicted invalidated: no discrepancy risk_flag present').
R7. Tests unitarios deterministas sin modelo real en tests/test_parser_validator.py cubren: (a) contradicted sin flag de discrepancia → not_enough_information, (b) contradicted + claim_mismatch → se preserva, (c) contradicted + solo blurry_image (sin flag de discrepancia) → not_enough_information, (d) contradicted + risk_flags=['none'] → not_enough_information, (e) supported + cualquier risk_flag → no cambia, (f) not_enough_information → no cambia.
R8. La evaluación sobre sample_claims.csv documenta en evaluation_report.md: accuracy de claim_status >= 80% (igual o mejor que feature 4), cuenta de casos contradicted→supported = 0, y distribución de degradaciones contradicted→not_enough_information con y sin prompt v3.
R9. Los tests existentes de features 3, 4 y 5 pasan sin modificación de sus aserciones de claim_status salvo actualización explícita documentada.

## Restricciones

- **error_states:** pendiente
- **auth_secrets:** pendiente
- **rollback_compat:** pendiente

