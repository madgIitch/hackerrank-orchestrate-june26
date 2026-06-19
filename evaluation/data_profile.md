# Data Profile

Generated: 2026-06-19T09:08:08+00:00

## CSV Summary

| dataset | path | rows | columns |
|---|---|---:|---|
| sample_claims | `dataset/sample_claims.csv` | 20 | user_id, image_paths, user_claim, claim_object, evidence_standard_met, evidence_standard_met_reason, risk_flags, issue_type, object_part, claim_status, claim_status_justification, supporting_image_ids, valid_image, severity |
| claims | `dataset/claims.csv` | 44 | user_id, image_paths, user_claim, claim_object |
| user_history | `dataset/user_history.csv` | 47 | user_id, past_claim_count, accept_claim, manual_review_claim, rejected_claim, last_90_days_claim_count, history_flags, history_summary |
| evidence_requirements | `dataset/evidence_requirements.csv` | 11 | requirement_id, claim_object, applies_to, minimum_image_evidence |

## Output Contract

Columns, in order:

1. `user_id`
2. `image_paths`
3. `user_claim`
4. `claim_object`
5. `evidence_standard_met`
6. `evidence_standard_met_reason`
7. `risk_flags`
8. `issue_type`
9. `object_part`
10. `claim_status`
11. `claim_status_justification`
12. `supporting_image_ids`
13. `valid_image`
14. `severity`

## Sample Distributions

### claim_status

- total_rows: 20
- non_empty_rows: 20
- empty_rows: 0
- unexpected_values: none

| value | count | percent |
|---|---:|---:|
| supported | 13 | 65.00% |
| contradicted | 5 | 25.00% |
| not_enough_information | 2 | 10.00% |

### claim_object

- total_rows: 20
- non_empty_rows: 20
- empty_rows: 0
- unexpected_values: none

| value | count | percent |
|---|---:|---:|
| car | 8 | 40.00% |
| laptop | 6 | 30.00% |
| package | 6 | 30.00% |

### issue_type

- total_rows: 20
- non_empty_rows: 20
- empty_rows: 0
- unexpected_values: none

| value | count | percent |
|---|---:|---:|
| broken_part | 3 | 15.00% |
| crack | 3 | 15.00% |
| dent | 3 | 15.00% |
| unknown | 3 | 15.00% |
| none | 2 | 10.00% |
| scratch | 2 | 10.00% |
| crushed_packaging | 1 | 5.00% |
| stain | 1 | 5.00% |
| torn_packaging | 1 | 5.00% |
| water_damage | 1 | 5.00% |

## Image Path Validation

- sample image paths checked: 29
- missing sample image paths: 0

## Incidents and Warnings

- none
