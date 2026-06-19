from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from io_data import EvidenceLookupResult, UserHistory
from schema import RISK_FLAGS


INVALIDATING_IMAGE_FLAGS = {
    "blurry_image",
    "cropped_or_obstructed",
    "low_light_or_glare",
    "wrong_angle",
    "wrong_object",
    "wrong_object_part",
    "damage_not_visible",
}


@dataclass(frozen=True)
class EvidenceRuleContext:
    evidence: EvidenceLookupResult
    claim_object: str
    issue_type: str
    valid_image_ids: set[str]
    image_errors: list[str]


def apply_evidence_rules(row: dict[str, str], context: EvidenceRuleContext) -> dict[str, str]:
    """Apply deterministic evidence and image-usability rules to a normalized output row."""
    updated = dict(row)
    flags = _risk_flag_list(updated.get("risk_flags", "none"))

    if context.image_errors:
        flags.append("manual_review_required")
        updated["evidence_standard_met_reason"] = _append_reason(
            updated.get("evidence_standard_met_reason", ""),
            "Partial image set; one or more images failed to load.",
        )

    updated["risk_flags"] = merge_risk_flags(flags)
    evidence_met, reason = compute_evidence_standard_met(updated, context)
    updated["evidence_standard_met"] = "true" if evidence_met else "false"
    if reason:
        updated["evidence_standard_met_reason"] = reason
    updated["valid_image"] = "true" if compute_valid_image(updated, context) else "false"

    if updated["valid_image"] == "false" and updated["evidence_standard_met"] == "true":
        updated["evidence_standard_met"] = "false"
        updated["evidence_standard_met_reason"] = _append_reason(
            updated.get("evidence_standard_met_reason", ""),
            "No usable image remains for automated review.",
        )

    return updated


def compute_evidence_standard_met(row: dict[str, str], context: EvidenceRuleContext) -> tuple[bool, str]:
    """Preserve the model boolean unless structured evidence rules invalidate it."""
    existing_reason = row.get("evidence_standard_met_reason", "").strip()
    if not context.evidence.requirements:
        prefix = (
            "No matching evidence requirement found for "
            f"claim_object={context.claim_object} issue_type={context.issue_type}."
        )
        return False, _append_reason(prefix, existing_reason)

    evidence_met = row.get("evidence_standard_met") == "true"
    if not evidence_met:
        return False, existing_reason

    if not context.valid_image_ids:
        return False, _append_reason(existing_reason, "No usable images were loaded.")

    if row.get("valid_image") == "false":
        return False, _append_reason(existing_reason, "Model marked the image set as not usable.")

    if row.get("claim_status") in {"supported", "contradicted"} and row.get("supporting_image_ids") == "none":
        return False, _append_reason(existing_reason, "No valid supporting image IDs remain for this decision.")

    if context.image_errors and row.get("supporting_image_ids") == "none":
        return False, _append_reason(existing_reason, "Partial image set prevents verifying the claim.")

    return True, existing_reason


def compute_valid_image(row: dict[str, str], context: EvidenceRuleContext) -> bool:
    """Return whether the image set has at least one usable relevant image."""
    if not context.valid_image_ids:
        return False
    if row.get("valid_image") == "true":
        return True
    if row.get("valid_image") == "false":
        return False
    flags = set(_risk_flag_list(row.get("risk_flags", "none")))
    return not flags.intersection(INVALIDATING_IMAGE_FLAGS)


def compute_history_risk_flags(history: UserHistory) -> list[str]:
    """Return canonical risk flags derived from CSV history flags and conservative thresholds."""
    explicit = _risk_flag_list(history.history_flags)
    if explicit:
        return explicit

    flags: list[str] = []
    if (
        history.rejected_claim >= 2
        or history.last_90_days_claim_count >= 4
        or (history.manual_review_claim >= 2 and history.past_claim_count >= 5)
    ):
        flags.append("user_history_risk")
    if history.rejected_claim >= 3 or history.last_90_days_claim_count >= 5 or history.manual_review_claim >= 3:
        flags.append("manual_review_required")
    return flags


def apply_history_risk_flags(row: dict[str, str], history: UserHistory) -> dict[str, str]:
    updated = dict(row)
    updated["risk_flags"] = merge_risk_flags(_risk_flag_list(updated.get("risk_flags", "none")) + compute_history_risk_flags(history))
    history_flags = compute_history_risk_flags(history)
    if history_flags:
        updated["claim_status_justification"] = _append_reason(
            updated.get("claim_status_justification", ""),
            f"History risk flags applied: {', '.join(history_flags)}.",
        )
    return updated


def merge_risk_flags(flags: Iterable[str]) -> str:
    values = {flag for flag in flags if flag in RISK_FLAGS and flag != "none"}
    ordered = [flag for flag in RISK_FLAGS if flag in values and flag != "none"]
    return ";".join(ordered) if ordered else "none"


def _risk_flag_list(value: str | Iterable[str]) -> list[str]:
    if isinstance(value, str):
        parts = [part.strip().lower() for part in value.split(";") if part.strip()]
    else:
        parts = [str(part).strip().lower() for part in value if str(part).strip()]
    return [part for part in parts if part in RISK_FLAGS and part != "none"]


def _append_reason(current: str, addition: str) -> str:
    current = (current or "").strip()
    addition = (addition or "").strip()
    if not current:
        return addition
    if not addition or addition in current:
        return current
    separator = "" if current.endswith((".", "!", "?")) else "."
    return f"{current}{separator} {addition}"
