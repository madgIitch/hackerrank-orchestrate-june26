from pathlib import Path
import sys

import pytest
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from io_data import ClaimRecord, EvidenceRequirements, ImageLoader, OutputWriter, UserHistory  # noqa: E402
from model_client import GeminiModelClient, ModelClientError  # noqa: E402
from parser_validator import parse_and_validate_output  # noqa: E402
from pipeline import SingleClaimPipeline  # noqa: E402
from prompt_builder import build_user_prompt, PROMPT_VERSION  # noqa: E402


class FakeModelClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_json(self, system_prompt, user_prompt, images):
        self.calls.append((system_prompt, user_prompt, images))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def write_requirements(path: Path) -> None:
    path.write_text(
        "requirement_id,claim_object,applies_to,minimum_image_evidence\n"
        "REQ1,all,general claim review,At least one clear image of the claimed object.\n",
        encoding="utf-8",
    )


def make_image(dataset_dir: Path, relative: str, color: str = "red") -> None:
    path = dataset_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 12), color).save(path)


def claim(claim_object: str, image_paths=None) -> ClaimRecord:
    paths = image_paths or [f"images/sample/{claim_object}/img_1.jpg"]
    return ClaimRecord(
        user_id=f"user_{claim_object}",
        image_paths=paths,
        image_ids=[Path(path).stem for path in paths],
        user_claim=f"Customer says the {claim_object} is damaged.",
        claim_object=claim_object,
    )


def history(user_id="user_car") -> UserHistory:
    return UserHistory(
        user_id=user_id,
        past_claim_count=0,
        accept_claim=0,
        manual_review_claim=0,
        rejected_claim=0,
        last_90_days_claim_count=0,
        history_flags="none",
        history_summary="No history available",
    )


def valid_triage_json(object_part="door", issue_type="dent", image_id="img_1") -> str:
    return (
        "{"
        f'"issue_type": "{issue_type}",'
        f'"object_part": "{object_part}",'
        f'"relevant_image_ids": ["{image_id}"],'
        '"visual_summary": "Visible damage on the surface."'
        "}"
    )


def valid_model_json(object_part="door") -> str:
    return (
        "{"
        '"evidence_standard_met": true,'
        '"evidence_standard_met_reason": "The image is clear enough.",'
        '"risk_flags": ["none"],'
        '"issue_type": "dent",'
        f'"object_part": "{object_part}",'
        '"claim_status": "supported",'
        '"claim_status_justification": "img_1 shows the claimed damage.",'
        '"supporting_image_ids": ["img_1"],'
        '"valid_image": true,'
        '"severity": "low"'
        "}"
    )


@pytest.fixture
def pipeline_factory(tmp_path):
    dataset_dir = tmp_path / "dataset"
    requirements_path = tmp_path / "evidence_requirements.csv"
    write_requirements(requirements_path)

    def factory(responses):
        return SingleClaimPipeline(
            model_client=FakeModelClient(responses),
            image_loader=ImageLoader(dataset_dir),
            evidence_requirements=EvidenceRequirements(requirements_path),
        ), dataset_dir

    return factory


def test_build_user_prompt_contains_one_claim_and_loaded_images(tmp_path):
    dataset_dir = tmp_path / "dataset"
    make_image(dataset_dir, "images/sample/car/img_1.jpg")
    image = ImageLoader(dataset_dir).load("images/sample/car/img_1.jpg")
    requirements_path = tmp_path / "evidence_requirements.csv"
    write_requirements(requirements_path)
    item = claim("car")

    prompt = build_user_prompt(
        item,
        history(item.user_id),
        EvidenceRequirements(requirements_path).lookup("car"),
        [image],
    )

    assert item.user_claim in prompt
    assert "claim_object: car" in prompt
    assert "img_1" in prompt
    assert "user_laptop" not in prompt


def test_pipeline_produces_rows_for_car_laptop_and_package(pipeline_factory):
    # Two passes per claim: triage + decision
    responses = []
    for obj, part in [("car", "door"), ("laptop", "screen"), ("package", "box")]:
        responses.append(valid_triage_json(object_part=part))
        responses.append(valid_model_json(part))
    pipeline, dataset_dir = pipeline_factory(responses)
    for obj in ["car", "laptop", "package"]:
        make_image(dataset_dir, f"images/sample/{obj}/img_1.jpg")

    rows = [pipeline.process_claim(claim(obj), history(f"user_{obj}")) for obj in ["car", "laptop", "package"]]

    assert len(rows) == 3
    assert [row["claim_status"] for row in rows] == ["supported", "supported", "supported"]
    for row in rows:
        OutputWriter(Path("unused.csv")).normalize_row(row)


def test_parser_degrades_invalid_enums_to_soft_fallbacks():
    base = {
        "user_id": "u1",
        "image_paths": ["images/sample/car/img_1.jpg"],
        "user_claim": "claim",
        "claim_object": "car",
    }
    row = parse_and_validate_output(
        base,
        "{"
        '"evidence_standard_met": "bad",'
        '"evidence_standard_met_reason": "reason",'
        '"risk_flags": ["blurry_image", "bad_flag"],'
        '"issue_type": "bad",'
        '"object_part": "screen",'
        '"claim_status": "bad",'
        '"claim_status_justification": "why",'
        '"supporting_image_ids": [],'
        '"valid_image": "bad",'
        '"severity": "bad"'
        "}",
    )

    assert row["evidence_standard_met"] == "false"
    assert row["risk_flags"] == "blurry_image"
    assert row["issue_type"] == "unknown"
    assert row["object_part"] == "unknown"
    assert row["claim_status"] == "not_enough_information"
    assert row["supporting_image_ids"] == "none"
    assert row["valid_image"] == "false"
    assert row["severity"] == "unknown"


def test_model_failure_returns_valid_fallback_row(pipeline_factory):
    # Both triage and decision fail → fallback row
    pipeline, dataset_dir = pipeline_factory([ModelClientError("timeout"), ModelClientError("timeout")])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")

    row = pipeline.process_claim(claim("car"), history("user_car"))

    assert row["claim_status"] == "not_enough_information"
    assert row["evidence_standard_met"] == "false"
    assert row["valid_image"] == "false"
    assert row["risk_flags"] == "manual_review_required"
    assert row["supporting_image_ids"] == "none"
    assert pipeline.log.errors


def test_partial_missing_image_continues_and_marks_manual_review(pipeline_factory):
    # Two passes: triage + decision
    pipeline, dataset_dir = pipeline_factory([valid_triage_json("door"), valid_model_json("door")])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")
    item = claim("car", ["images/sample/car/img_1.jpg", "images/sample/car/missing.jpg"])

    row = pipeline.process_claim(item, history("user_car"))

    assert row["claim_status"] == "supported"
    assert "manual_review_required" in row["risk_flags"]
    assert row["valid_image"] == "true"
    assert row["evidence_standard_met"] == "true"
    assert "Partial image set" in row["evidence_standard_met_reason"]


def test_no_usable_images_returns_fallback_without_model_call(pipeline_factory):
    pipeline, _dataset_dir = pipeline_factory([valid_triage_json("door"), valid_model_json("door")])

    row = pipeline.process_claim(claim("car", ["images/sample/car/missing.jpg"]), history("user_car"))

    assert row["claim_status"] == "not_enough_information"
    assert row["risk_flags"] == "manual_review_required"
    assert row["valid_image"] == "false"
    assert pipeline.model_client.calls == []


def test_write_rows_requires_explicit_path_and_uses_tmp_path(pipeline_factory, tmp_path):
    pipeline, dataset_dir = pipeline_factory([valid_triage_json("door"), valid_model_json("door")])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")
    row = pipeline.process_claim(claim("car"), history("user_car"))
    output_path = tmp_path / "staging.csv"

    pipeline.write_rows([row], output_path)

    assert output_path.exists()
    assert not (REPO_ROOT / "output.csv").exists()


def test_gemini_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ModelClientError):
        GeminiModelClient()


# ── New tests for feature 4 post-processing behaviors ─────────────────────────

def test_supported_with_evidence_false_forces_not_enough_information(pipeline_factory):
    """evidence_standard_met=false must override claim_status=supported → not_enough_information."""
    decision_json = (
        "{"
        '"evidence_standard_met": false,'
        '"evidence_standard_met_reason": "Image too blurry.",'
        '"risk_flags": ["blurry_image"],'
        '"issue_type": "dent",'
        '"object_part": "door",'
        '"claim_status": "supported",'
        '"claim_status_justification": "img_1 shows damage.",'
        '"supporting_image_ids": ["img_1"],'
        '"valid_image": false,'
        '"severity": "low"'
        "}"
    )
    pipeline, dataset_dir = pipeline_factory([valid_triage_json("door"), decision_json])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")

    row = pipeline.process_claim(claim("car"), history("user_car"))

    assert row["claim_status"] == "not_enough_information"
    assert row["evidence_standard_met"] == "false"
    assert row["supporting_image_ids"] == "none"


def test_contradicted_with_evidence_false_forces_not_enough_information(pipeline_factory):
    """evidence_standard_met=false must override claim_status=contradicted → not_enough_information."""
    decision_json = (
        "{"
        '"evidence_standard_met": false,'
        '"evidence_standard_met_reason": "Image does not meet requirements.",'
        '"risk_flags": ["wrong_angle"],'
        '"issue_type": "none",'
        '"object_part": "door",'
        '"claim_status": "contradicted",'
        '"claim_status_justification": "img_1 shows no damage.",'
        '"supporting_image_ids": ["img_1"],'
        '"valid_image": false,'
        '"severity": "none"'
        "}"
    )
    pipeline, dataset_dir = pipeline_factory([valid_triage_json("door"), decision_json])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")

    row = pipeline.process_claim(claim("car"), history("user_car"))

    assert row["claim_status"] == "not_enough_information"
    assert row["evidence_standard_met"] == "false"
    assert row["supporting_image_ids"] == "none"


def test_not_enough_information_with_evidence_true_is_preserved(pipeline_factory):
    """not_enough_information with evidence_standard_met=true must remain unchanged."""
    decision_json = (
        "{"
        '"evidence_standard_met": true,'
        '"evidence_standard_met_reason": "Image is clear.",'
        '"risk_flags": ["none"],'
        '"issue_type": "unknown",'
        '"object_part": "unknown",'
        '"claim_status": "not_enough_information",'
        '"claim_status_justification": "Cannot determine damage area.",'
        '"supporting_image_ids": ["none"],'
        '"valid_image": true,'
        '"severity": "unknown"'
        "}"
    )
    pipeline, dataset_dir = pipeline_factory([valid_triage_json("door"), decision_json])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")

    row = pipeline.process_claim(claim("car"), history("user_car"))

    assert row["claim_status"] == "not_enough_information"
    assert row["evidence_standard_met"] == "true"


def test_foreign_image_ids_discarded_from_supporting(pipeline_factory):
    """Image IDs not belonging to the claim must be removed from supporting_image_ids."""
    decision_json = (
        "{"
        '"evidence_standard_met": true,'
        '"evidence_standard_met_reason": "Clear images.",'
        '"risk_flags": ["none"],'
        '"issue_type": "dent",'
        '"object_part": "door",'
        '"claim_status": "supported",'
        '"claim_status_justification": "img_1 and foreign_img show damage.",'
        '"supporting_image_ids": ["img_1", "foreign_img", "other_claim_img"],'
        '"valid_image": true,'
        '"severity": "low"'
        "}"
    )
    pipeline, dataset_dir = pipeline_factory([valid_triage_json("door"), decision_json])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")

    row = pipeline.process_claim(claim("car"), history("user_car"))

    assert "foreign_img" not in row["supporting_image_ids"]
    assert "other_claim_img" not in row["supporting_image_ids"]
    assert "img_1" in row["supporting_image_ids"]
    assert row["claim_status"] == "supported"


def test_supported_with_all_foreign_ids_becomes_not_enough_information(pipeline_factory):
    """supported with only foreign image IDs → not_enough_information after filtering."""
    decision_json = (
        "{"
        '"evidence_standard_met": true,'
        '"evidence_standard_met_reason": "Clear images.",'
        '"risk_flags": ["none"],'
        '"issue_type": "dent",'
        '"object_part": "door",'
        '"claim_status": "supported",'
        '"claim_status_justification": "foreign_img shows damage.",'
        '"supporting_image_ids": ["foreign_img", "other_img"],'
        '"valid_image": true,'
        '"severity": "low"'
        "}"
    )
    pipeline, dataset_dir = pipeline_factory([valid_triage_json("door"), decision_json])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")

    row = pipeline.process_claim(claim("car"), history("user_car"))

    assert row["claim_status"] == "not_enough_information"
    assert row["supporting_image_ids"] == "none"


def test_history_cannot_elevate_not_enough_information(pipeline_factory):
    """High-risk history adds user_history_risk flag but must not change claim_status."""
    decision_json = (
        "{"
        '"evidence_standard_met": false,'
        '"evidence_standard_met_reason": "Insufficient evidence.",'
        '"risk_flags": ["none"],'
        '"issue_type": "unknown",'
        '"object_part": "unknown",'
        '"claim_status": "not_enough_information",'
        '"claim_status_justification": "Cannot verify.",'
        '"supporting_image_ids": ["none"],'
        '"valid_image": false,'
        '"severity": "unknown"'
        "}"
    )
    pipeline, dataset_dir = pipeline_factory([valid_triage_json("door"), decision_json])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")
    risky_history = UserHistory(
        user_id="user_car",
        past_claim_count=5,
        accept_claim=0,
        manual_review_claim=2,
        rejected_claim=3,
        last_90_days_claim_count=4,
        history_flags="high_risk",
        history_summary="Multiple rejected claims.",
    )

    row = pipeline.process_claim(claim("car"), risky_history)

    assert row["claim_status"] == "not_enough_information"
    assert "user_history_risk" in row["risk_flags"]


def test_prompt_version_recorded_in_pipeline_log(pipeline_factory):
    """Pipeline log must record prompt_version."""
    pipeline, _dataset_dir = pipeline_factory([])

    assert pipeline.log.prompt_version == PROMPT_VERSION


def test_triage_failure_falls_back_to_general_requirements(pipeline_factory):
    """If triage fails, pipeline uses general requirements and proceeds to decision pass."""
    pipeline, dataset_dir = pipeline_factory([ModelClientError("triage_down"), valid_model_json("door")])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")

    row = pipeline.process_claim(claim("car"), history("user_car"))

    assert row["claim_status"] in ("supported", "not_enough_information", "contradicted")
    assert pipeline.log.errors  # triage error should be logged
