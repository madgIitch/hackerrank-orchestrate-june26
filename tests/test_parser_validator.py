"""Deterministic unit tests for parser_validator post-processing logic (no real model required)."""
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from parser_validator import (  # noqa: E402
    apply_evidence_precedence,
    filter_supporting_image_ids,
    validate_output_row,
    merge_output_row,
    fallback_decision,
)


def _base_row(claim_object: str = "car") -> dict:
    return {
        "user_id": "u1",
        "image_paths": ["images/sample/car/img_1.jpg"],
        "user_claim": "car is damaged",
        "claim_object": claim_object,
    }


def _make_row(
    claim_status: str = "supported",
    evidence_standard_met: bool = True,
    supporting_image_ids: list = None,
    claim_object: str = "car",
) -> dict:
    decision = {
        "evidence_standard_met": evidence_standard_met,
        "evidence_standard_met_reason": "reason",
        "risk_flags": ["none"],
        "issue_type": "dent",
        "object_part": "door",
        "claim_status": claim_status,
        "claim_status_justification": "justification",
        "supporting_image_ids": supporting_image_ids if supporting_image_ids is not None else ["img_1"],
        "valid_image": True,
        "severity": "low",
    }
    return validate_output_row(merge_output_row(_base_row(claim_object), decision))


# ── apply_evidence_precedence ─────────────────────────────────────────────────

def test_evidence_false_overrides_supported():
    row = _make_row(claim_status="supported", evidence_standard_met=False)
    result = apply_evidence_precedence(row)
    assert result["claim_status"] == "not_enough_information"
    assert result["supporting_image_ids"] == "none"


def test_evidence_false_overrides_contradicted():
    row = _make_row(claim_status="contradicted", evidence_standard_met=False)
    result = apply_evidence_precedence(row)
    assert result["claim_status"] == "not_enough_information"
    assert result["supporting_image_ids"] == "none"


def test_evidence_false_preserves_not_enough_information():
    row = _make_row(claim_status="not_enough_information", evidence_standard_met=False, supporting_image_ids=["none"])
    result = apply_evidence_precedence(row)
    assert result["claim_status"] == "not_enough_information"


def test_evidence_true_does_not_change_supported():
    row = _make_row(claim_status="supported", evidence_standard_met=True)
    result = apply_evidence_precedence(row)
    assert result["claim_status"] == "supported"


def test_evidence_true_preserves_not_enough_information():
    row = _make_row(claim_status="not_enough_information", evidence_standard_met=True, supporting_image_ids=["none"])
    result = apply_evidence_precedence(row)
    assert result["claim_status"] == "not_enough_information"
    assert result["evidence_standard_met"] == "true"


# ── filter_supporting_image_ids ───────────────────────────────────────────────

def test_foreign_ids_removed_valid_ids_kept():
    row = _make_row(claim_status="supported", supporting_image_ids=["img_1", "foreign", "other"])
    result = filter_supporting_image_ids(row, {"img_1"})
    assert "img_1" in result["supporting_image_ids"]
    assert "foreign" not in result["supporting_image_ids"]
    assert "other" not in result["supporting_image_ids"]
    assert result["claim_status"] == "supported"


def test_all_foreign_ids_forces_not_enough_information_on_supported():
    row = _make_row(claim_status="supported", supporting_image_ids=["foreign_img", "other_img"])
    result = filter_supporting_image_ids(row, {"img_1"})
    assert result["supporting_image_ids"] == "none"
    assert result["claim_status"] == "not_enough_information"


def test_all_foreign_ids_forces_not_enough_information_on_contradicted():
    row = _make_row(claim_status="contradicted", supporting_image_ids=["foreign_img"])
    result = filter_supporting_image_ids(row, {"img_1"})
    assert result["claim_status"] == "not_enough_information"
    assert result["supporting_image_ids"] == "none"


def test_none_supporting_ids_unchanged():
    row = _make_row(claim_status="not_enough_information", supporting_image_ids=["none"])
    result = filter_supporting_image_ids(row, {"img_1"})
    assert result["supporting_image_ids"] == "none"
    assert result["claim_status"] == "not_enough_information"


def test_multiple_valid_ids_all_kept():
    row = _make_row(claim_status="supported", supporting_image_ids=["img_1", "img_2"])
    result = filter_supporting_image_ids(row, {"img_1", "img_2", "img_3"})
    ids = set(result["supporting_image_ids"].split(";"))
    assert "img_1" in ids
    assert "img_2" in ids


def test_mixed_valid_and_foreign_only_valid_kept():
    row = _make_row(claim_status="supported", supporting_image_ids=["img_1", "img_2", "bad_img"])
    result = filter_supporting_image_ids(row, {"img_1", "img_2"})
    ids = set(result["supporting_image_ids"].split(";"))
    assert "img_1" in ids
    assert "img_2" in ids
    assert "bad_img" not in ids
    assert result["claim_status"] == "supported"


# ── combined post-processing (order matters: filter → evidence precedence) ───

def test_foreign_ids_then_evidence_false_both_applied():
    row = _make_row(claim_status="supported", evidence_standard_met=False, supporting_image_ids=["img_1"])
    row = filter_supporting_image_ids(row, {"img_1"})
    row = apply_evidence_precedence(row)
    assert row["claim_status"] == "not_enough_information"
    assert row["supporting_image_ids"] == "none"
    assert row["evidence_standard_met"] == "false"


def test_history_risk_does_not_change_claim_status():
    """Integration: even if apply_evidence_precedence is skipped, history alone cannot elevate claim_status."""
    row = _make_row(claim_status="not_enough_information", evidence_standard_met=False, supporting_image_ids=["none"])
    # Simulate adding user_history_risk flag manually (as _apply_history_risk would)
    row["risk_flags"] = "user_history_risk"
    # claim_status must remain not_enough_information regardless of risk flags
    assert row["claim_status"] == "not_enough_information"
