from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from evidence_rules import (  # noqa: E402
    EvidenceRuleContext,
    apply_evidence_rules,
    apply_history_risk_flags,
    compute_history_risk_flags,
    merge_risk_flags,
)
from io_data import EvidenceLookupResult, EvidenceRequirement, UserHistory  # noqa: E402


def requirement_result(requirements=True) -> EvidenceLookupResult:
    items = []
    if requirements:
        items.append(
            EvidenceRequirement(
                requirement_id="REQ1",
                claim_object="car",
                applies_to="dent or scratch",
                minimum_image_evidence="Clear image of the damaged car panel.",
            )
        )
    return EvidenceLookupResult(requirements=items, matched_rule="object_exact" if items else "none")


def context(requirements=True, image_errors=None) -> EvidenceRuleContext:
    return EvidenceRuleContext(
        evidence=requirement_result(requirements),
        claim_object="car",
        issue_type="dent",
        valid_image_ids={"img_1"},
        image_errors=image_errors or [],
    )


def row(**overrides) -> dict[str, str]:
    data = {
        "evidence_standard_met": "true",
        "evidence_standard_met_reason": "Model says the image is clear.",
        "risk_flags": "none",
        "issue_type": "dent",
        "object_part": "door",
        "claim_status": "supported",
        "claim_status_justification": "img_1 shows damage.",
        "supporting_image_ids": "img_1",
        "valid_image": "true",
        "severity": "low",
    }
    data.update(overrides)
    return data


def history(**overrides) -> UserHistory:
    data = {
        "user_id": "user_1",
        "past_claim_count": 0,
        "accept_claim": 0,
        "manual_review_claim": 0,
        "rejected_claim": 0,
        "last_90_days_claim_count": 0,
        "history_flags": "none",
        "history_summary": "No history available",
    }
    data.update(overrides)
    return UserHistory(**data)


def test_empty_requirements_forces_false_with_stable_reason_prefix():
    result = apply_evidence_rules(row(), context(requirements=False))

    assert result["evidence_standard_met"] == "false"
    assert result["evidence_standard_met_reason"].startswith(
        "No matching evidence requirement found for claim_object=car issue_type=dent."
    )


def test_requirements_present_and_model_true_preserves_true():
    result = apply_evidence_rules(row(), context())

    assert result["evidence_standard_met"] == "true"
    assert result["valid_image"] == "true"


def test_requirements_present_but_image_not_usable_forces_false():
    result = apply_evidence_rules(row(valid_image="false"), context())

    assert result["valid_image"] == "false"
    assert result["evidence_standard_met"] == "false"


def test_history_flags_none_under_threshold_returns_no_flags():
    assert compute_history_risk_flags(history(past_claim_count=4, manual_review_claim=1, rejected_claim=1)) == []


def test_history_flags_none_over_threshold_derives_flags():
    flags = compute_history_risk_flags(history(past_claim_count=8, manual_review_claim=3, rejected_claim=3))

    assert flags == ["user_history_risk", "manual_review_required"]


def test_explicit_history_flags_are_propagated_and_invalid_flags_dropped():
    flags = compute_history_risk_flags(history(history_flags="user_history_risk;bad_flag;manual_review_required"))

    assert flags == ["user_history_risk", "manual_review_required"]


def test_multi_image_partial_quality_keeps_valid_image_true_and_merges_flags():
    result = apply_evidence_rules(row(risk_flags="blurry_image;none"), context(image_errors=["missing.jpg"]))

    assert result["valid_image"] == "true"
    assert result["evidence_standard_met"] == "true"
    assert result["risk_flags"] == "blurry_image;manual_review_required"
    assert "Partial image set" in result["evidence_standard_met_reason"]


def test_merge_risk_flags_uses_canonical_order_and_deduplicates():
    assert merge_risk_flags(["manual_review_required", "blurry_image", "manual_review_required"]) == (
        "blurry_image;manual_review_required"
    )


def test_apply_history_flags_never_changes_status_or_evidence():
    result = apply_history_risk_flags(
        row(claim_status="not_enough_information", evidence_standard_met="false"),
        history(rejected_claim=3),
    )

    assert result["claim_status"] == "not_enough_information"
    assert result["evidence_standard_met"] == "false"
    assert result["risk_flags"] == "user_history_risk;manual_review_required"
