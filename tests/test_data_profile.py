from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from profile_data import build_report, load_profiles, split_image_paths
from schema import CLAIM_OBJECTS, ENUMS, OBJECT_PARTS, OUTPUT_COLUMNS, assert_unique_enums


def test_output_contract_columns_are_exact():
    assert OUTPUT_COLUMNS == [
        "user_id",
        "image_paths",
        "user_claim",
        "claim_object",
        "evidence_standard_met",
        "evidence_standard_met_reason",
        "risk_flags",
        "issue_type",
        "object_part",
        "claim_status",
        "claim_status_justification",
        "supporting_image_ids",
        "valid_image",
        "severity",
    ]


def test_enums_are_unique_and_match_contract():
    assert_unique_enums()
    assert ENUMS["claim_status"] == ["supported", "contradicted", "not_enough_information"]
    assert CLAIM_OBJECTS == ["car", "laptop", "package"]
    assert OBJECT_PARTS["car"][-1] == "unknown"
    assert "manual_review_required" in ENUMS["risk_flags"]
    assert ENUMS["severity"] == ["none", "low", "medium", "high", "unknown"]


def test_canonical_csvs_load_and_have_required_columns():
    profiles, _ = load_profiles(REPO_ROOT)
    assert set(profiles) == {"sample_claims", "claims", "user_history", "evidence_requirements"}
    assert profiles["sample_claims"].columns == OUTPUT_COLUMNS
    assert profiles["claims"].columns == ["user_id", "image_paths", "user_claim", "claim_object"]


def test_sample_image_paths_exist():
    _, rows_by_name = load_profiles(REPO_ROOT)
    checked = 0
    for row in rows_by_name["sample_claims"]:
        paths = split_image_paths(row["image_paths"])
        assert paths
        for image_path in paths:
            checked += 1
            assert (REPO_ROOT / "dataset" / image_path).exists()
    assert checked > 0


def test_profile_report_contains_required_sections_without_incidents():
    report, incidents = build_report(REPO_ROOT)
    assert incidents == []
    assert "## CSV Summary" in report
    assert "## Output Contract" in report
    assert "### claim_status" in report
    assert "### claim_object" in report
    assert "### issue_type" in report
    assert "sample image paths checked:" in report
