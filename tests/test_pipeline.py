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
from prompt_builder import build_user_prompt  # noqa: E402


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
    pipeline, dataset_dir = pipeline_factory([valid_model_json("door"), valid_model_json("screen"), valid_model_json("box")])
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
    pipeline, dataset_dir = pipeline_factory([ModelClientError("timeout")])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")

    row = pipeline.process_claim(claim("car"), history("user_car"))

    assert row["claim_status"] == "not_enough_information"
    assert row["evidence_standard_met"] == "false"
    assert row["valid_image"] == "false"
    assert row["risk_flags"] == "manual_review_required"
    assert row["supporting_image_ids"] == "none"
    assert pipeline.log.errors


def test_partial_missing_image_continues_and_marks_manual_review(pipeline_factory):
    pipeline, dataset_dir = pipeline_factory([valid_model_json("door")])
    make_image(dataset_dir, "images/sample/car/img_1.jpg")
    item = claim("car", ["images/sample/car/img_1.jpg", "images/sample/car/missing.jpg"])

    row = pipeline.process_claim(item, history("user_car"))

    assert row["claim_status"] == "supported"
    assert "manual_review_required" in row["risk_flags"]
    assert row["evidence_standard_met"] == "false"
    assert "Partial image set" in row["evidence_standard_met_reason"]


def test_no_usable_images_returns_fallback_without_model_call(pipeline_factory):
    pipeline, _dataset_dir = pipeline_factory([valid_model_json("door")])

    row = pipeline.process_claim(claim("car", ["images/sample/car/missing.jpg"]), history("user_car"))

    assert row["claim_status"] == "not_enough_information"
    assert row["risk_flags"] == "manual_review_required"
    assert row["valid_image"] == "false"
    assert pipeline.model_client.calls == []


def test_write_rows_requires_explicit_path_and_uses_tmp_path(pipeline_factory, tmp_path):
    pipeline, dataset_dir = pipeline_factory([valid_model_json("door")])
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
