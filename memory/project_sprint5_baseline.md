---
name: project_sprint5_baseline
description: Resultados de evaluación del pipeline tras el sprint 5 (evidence_and_risk_rules) — baseline para comparar en sprints posteriores
metadata:
  type: project
---

Evaluación ejecutada el 2026-06-19 sobre `dataset/sample_claims.csv` (20 claims) con prompt v2 y Gemini 2.5 Flash.

**Why:** El usuario quiere comparar estos números en el siguiente sprint para medir regresiones o mejoras.

**How to apply:** Cuando se ejecute evaluación en sprints futuros, comparar contra estas métricas y destacar cambios significativos (>5% en accuracy, cambios en distribución de risk_flags).

## Métricas sprint 5

| Métrica | Valor |
|---|---|
| claim_status accuracy | 75.0% (15/20) |
| issue_type accuracy | 45.0% (9/20) |
| object_part accuracy | 90.0% (18/20) |
| supporting_image_ids incoherent | 0/20 |
| evidence_standard_met=true | 17/20 (85%) |
| evidence_standard_met=false | 3/20 (15%) |
| valid_image=false | 1/20 (5%) |

## Confusión matrix — claim_status

- contradicted → contradicted: 1 ✓
- contradicted → not_enough_information: 2 ✗
- contradicted → supported: 2 ✗
- not_enough_information → not_enough_information: 1 ✓
- not_enough_information → supported: 1 ✗
- supported → supported: 13 ✓

## risk_flags frecuencia

- none: 10
- user_history_risk: 7
- damage_not_visible: 2
- wrong_object: 2
- blurry_image: 1
- low_light_or_glare: 1
- manual_review_required: 1
- text_instruction_present: 1
- wrong_angle: 1

## Puntos débiles observados

- `issue_type` accuracy es el punto más débil (45%) — puede ser objetivo de mejora en sprints futuros
- El modelo confunde `contradicted` con `supported` (2 casos) y con `not_enough_information` (2 casos)
