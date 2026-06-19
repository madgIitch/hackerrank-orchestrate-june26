import csv
from pathlib import Path
import sys

import pytest
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from io_data import (  # noqa: E402
    ClaimLoader,
    EvidenceRequirements,
    ImageLoader,
    OutputWriter,
    UserHistory,
    UserHistoryLoader,
    enrich_claims,
    issue_family_for_issue_type,
    missing_history,
)
from schema import OUTPUT_COLUMNS  # noqa: E402


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def output_row(**overrides):
    row = {
        "user_id": "user_1",
        "image_paths": "images/sample/case_001/img_1.jpg",
        "user_claim": "Claim text",
        "claim_object": "car",
        "evidence_standard_met": True,
        "evidence_standard_met_reason": "Visible",
        "risk_flags": ["none"],
        "issue_type": "dent",
        "object_part": "door",
        "claim_status": "supported",
        "claim_status_justification": "Image supports claim.",
        "supporting_image_ids": ["img_1"],
        "valid_image": True,
        "severity": "low",
    }
    row.update(overrides)
    return row


def test_claim_loader_parses_paths_preserves_order_and_ids(tmp_path):
    path = tmp_path / "claims.csv"
    write_csv(
        path,
        ["user_id", "image_paths", "user_claim", "claim_object"],
        [
            {"user_id": "u1", "image_paths": "a/img_1.jpg; b/img_2.png ;", "user_claim": "first", "claim_object": "car"},
            {"user_id": "u2", "image_paths": "x/img_3.jpg", "user_claim": "second", "claim_object": "package"},
        ],
    )

    claims = ClaimLoader(path).load()

    assert [claim.user_id for claim in claims] == ["u1", "u2"]
    assert claims[0].image_paths == ["a/img_1.jpg", "b/img_2.png"]
    assert claims[0].image_ids == ["img_1", "img_2"]


def test_user_history_enrichment_uses_deterministic_missing_history(tmp_path):
    claims_path = tmp_path / "claims.csv"
    history_path = tmp_path / "user_history.csv"
    write_csv(
        claims_path,
        ["user_id", "image_paths", "user_claim", "claim_object"],
        [{"user_id": "missing", "image_paths": "img_1.jpg", "user_claim": "claim", "claim_object": "laptop"}],
    )
    write_csv(
        history_path,
        [
            "user_id",
            "past_claim_count",
            "accept_claim",
            "manual_review_claim",
            "rejected_claim",
            "last_90_days_claim_count",
            "history_flags",
            "history_summary",
        ],
        [],
    )

    enriched = enrich_claims(ClaimLoader(claims_path).load(), UserHistoryLoader(history_path).load())

    assert enriched[0].history == missing_history("missing")
    assert isinstance(enriched[0].history, UserHistory)


def test_evidence_requirements_lookup_precedence_and_no_match(tmp_path):
    path = tmp_path / "evidence_requirements.csv"
    write_csv(
        path,
        ["requirement_id", "claim_object", "applies_to", "minimum_image_evidence"],
        [
            {"requirement_id": "ALL_GENERAL", "claim_object": "all", "applies_to": "general claim review", "minimum_image_evidence": "general"},
            {"requirement_id": "ALL_DENT", "claim_object": "all", "applies_to": "dent or scratch", "minimum_image_evidence": "all dent"},
            {"requirement_id": "CAR_DENT_1", "claim_object": "car", "applies_to": "dent or scratch", "minimum_image_evidence": "car dent 1"},
            {"requirement_id": "CAR_DENT_2", "claim_object": "car", "applies_to": "dent or scratch", "minimum_image_evidence": "car dent 2"},
        ],
    )
    requirements = EvidenceRequirements(path)

    result = requirements.lookup("car", issue_type="scratch")
    assert result.matched_rule == "object_exact"
    assert [item.requirement_id for item in result.requirements] == ["CAR_DENT_1", "CAR_DENT_2"]
    assert issue_family_for_issue_type("water_damage") == "water damage or stain"

    no_match = requirements.lookup("package", issue_family="impossible")
    assert no_match.matched_rule == "all_general"
    assert [item.requirement_id for item in no_match.requirements] == ["ALL_GENERAL"]

    empty_path = tmp_path / "empty_requirements.csv"
    write_csv(empty_path, ["requirement_id", "claim_object", "applies_to", "minimum_image_evidence"], [])
    empty = EvidenceRequirements(empty_path).lookup("car", issue_type="dent")
    assert empty.matched_rule == "none"
    assert empty.requirements == []


def test_image_loader_payload_and_missing_image(tmp_path):
    dataset_dir = tmp_path / "dataset"
    small_path = dataset_dir / "images/sample/case_001/img_1.jpg"
    small_path.parent.mkdir(parents=True)
    Image.new("RGB", (10, 8), "red").save(small_path)

    payload = ImageLoader(dataset_dir).load("images/sample/case_001/img_1.jpg")

    assert payload.image_id == "img_1"
    assert payload.media_type == "image/jpeg"
    assert payload.width == 10
    assert payload.height == 8
    assert payload.original_width == 10
    assert payload.resized is False
    assert not payload.base64_data.startswith("data:")

    large_path = dataset_dir / "large.png"
    Image.new("RGB", (1200, 600), "blue").save(large_path)
    large_payload = ImageLoader(dataset_dir, max_dimension=1024).load("large.png")
    assert large_payload.resized is True
    assert large_payload.width == 1024
    assert large_payload.height == 512
    assert large_payload.original_width == 1200
    assert large_payload.media_type == "image/jpeg"

    with pytest.raises(FileNotFoundError):
        ImageLoader(dataset_dir).load("missing.jpg")


def test_output_writer_round_trip_and_soft_enum_correction(tmp_path):
    path = tmp_path / "out.csv"

    OutputWriter(path).write(
        [
            output_row(
                claim_status="bad",
                issue_type="bad",
                severity="bad",
                risk_flags=["blurry_image", "bad_flag"],
                evidence_standard_met="bad_bool",
                valid_image="true",
                supporting_image_ids=[],
            )
        ]
    )

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0].keys() == set(OUTPUT_COLUMNS)
    assert list(rows[0].keys()) == OUTPUT_COLUMNS
    assert rows[0]["claim_status"] == "not_enough_information"
    assert rows[0]["issue_type"] == "unknown"
    assert rows[0]["severity"] == "unknown"
    assert rows[0]["risk_flags"] == "blurry_image"
    assert rows[0]["evidence_standard_met"] == "false"
    assert rows[0]["supporting_image_ids"] == "none"


def test_output_writer_rejects_structural_errors(tmp_path):
    with pytest.raises(ValueError):
        OutputWriter(tmp_path / "out.csv").write([output_row(claim_object="bad")])
    with pytest.raises(ValueError):
        OutputWriter(tmp_path / "out.csv").write([output_row(object_part="screen")])


def test_smoke_loads_real_dataset_and_image():
    claims = ClaimLoader(REPO_ROOT / "dataset/claims.csv").load()
    histories = UserHistoryLoader(REPO_ROOT / "dataset/user_history.csv").load()
    enriched = enrich_claims(claims[:2], histories)
    assert len(enriched) == 2

    result = EvidenceRequirements(REPO_ROOT / "dataset/evidence_requirements.csv").lookup("car", issue_type="dent")
    assert result.requirements

    payload = ImageLoader(REPO_ROOT / "dataset").load("images/sample/case_001/img_1.jpg")
    assert payload.image_id == "img_1"
    assert payload.width > 0
