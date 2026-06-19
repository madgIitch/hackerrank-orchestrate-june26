# Evaluation Report — Multi-Modal Evidence Review

Generated: 2026-06-19T18:16:11.275726+00:00
Active prompt_version: v2

## Dataset
- sample_claims.csv: 20 rows processed

## Results — v2 (current — v2)

### claim_status accuracy: 75.0% (15/20)

Confusion matrix (expected → predicted):
- contradicted → contradicted: 1
- contradicted → not_enough_information: 2
- contradicted → supported: 2
- not_enough_information → not_enough_information: 1
- not_enough_information → supported: 1
- supported → supported: 13

### issue_type accuracy: 45.0% (9/20)

### object_part accuracy: 90.0% (18/20)

### supporting_image_ids coherence
- supported rows with supporting_image_ids=none (incoherent): 0

### evidence/risk diagnostics
- evidence_standard_met distribution:
  - false: 3 (15.0%)
  - true: 17 (85.0%)
- risk_flags frequency:
  - none: 10
  - user_history_risk: 7
  - damage_not_visible: 2
  - wrong_object: 2
  - blurry_image: 1
  - low_light_or_glare: 1
  - manual_review_required: 1
  - text_instruction_present: 1
  - wrong_angle: 1
- valid_image=false ratio: 1/20 (5.0%)
- Ground-truth comparable fields present: evidence_standard_met, risk_flags, valid_image.
