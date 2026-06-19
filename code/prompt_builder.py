from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from io_data import ClaimRecord, EvidenceLookupResult, ImagePayload, UserHistory
from schema import OBJECT_PARTS


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "system_prompt.txt"


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str
    images: list[ImagePayload]


def load_system_prompt(path: Path = PROMPT_PATH) -> str:
    return path.read_text(encoding="utf-8")


def build_user_prompt(
    claim: ClaimRecord,
    history: UserHistory,
    evidence: EvidenceLookupResult,
    images: list[ImagePayload],
    image_errors: list[str] | None = None,
) -> str:
    requirements = "\n".join(
        f"- {item.requirement_id}: {item.minimum_image_evidence}"
        for item in evidence.requirements
    ) or "- No matching evidence requirement found; use general visual review."
    image_summary = "\n".join(
        f"- {image.image_id}: {image.source_path}, {image.media_type}, {image.width}x{image.height}"
        for image in images
    ) or "- No usable images loaded."
    errors = "\n".join(f"- {error}" for error in (image_errors or [])) or "- none"
    object_parts = ", ".join(OBJECT_PARTS[claim.claim_object])

    return "\n".join(
        [
            "Review exactly one claim.",
            "",
            f"user_id: {claim.user_id}",
            f"claim_object: {claim.claim_object}",
            f"allowed_object_parts: {object_parts}",
            f"image_ids: {', '.join(claim.image_ids)}",
            "",
            "user_claim transcript:",
            claim.user_claim,
            "",
            "loaded_images:",
            image_summary,
            "",
            "image_load_errors:",
            errors,
            "",
            "user_history:",
            f"- past_claim_count: {history.past_claim_count}",
            f"- accept_claim: {history.accept_claim}",
            f"- manual_review_claim: {history.manual_review_claim}",
            f"- rejected_claim: {history.rejected_claim}",
            f"- last_90_days_claim_count: {history.last_90_days_claim_count}",
            f"- history_flags: {history.history_flags}",
            f"- history_summary: {history.history_summary}",
            "",
            f"evidence_requirements_matched_rule: {evidence.matched_rule}",
            "evidence_requirements:",
            requirements,
            "",
            "Return only the strict JSON object.",
        ]
    )


def build_prompt_bundle(
    claim: ClaimRecord,
    history: UserHistory,
    evidence: EvidenceLookupResult,
    images: list[ImagePayload],
    image_errors: list[str] | None = None,
) -> PromptBundle:
    return PromptBundle(
        system_prompt=load_system_prompt(),
        user_prompt=build_user_prompt(claim, history, evidence, images, image_errors),
        images=images,
    )
