from __future__ import annotations

import json
from typing import Any

from io_data import OutputWriter
from schema import CLAIM_STATUS, ISSUE_TYPES, OBJECT_PARTS, OUTPUT_COLUMNS, RISK_FLAGS, SEVERITY


DECISION_FIELDS = [
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


def parse_model_json(raw: str) -> dict[str, Any]:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Model JSON must be an object")
    return parsed


def fallback_decision(reason: str) -> dict[str, Any]:
    clean_reason = reason.strip() or "Automated review could not be completed."
    return {
        "evidence_standard_met": False,
        "evidence_standard_met_reason": clean_reason,
        "risk_flags": ["manual_review_required"],
        "issue_type": "unknown",
        "object_part": "unknown",
        "claim_status": "not_enough_information",
        "claim_status_justification": clean_reason,
        "supporting_image_ids": ["none"],
        "valid_image": False,
        "severity": "unknown",
    }


def merge_output_row(base_row: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    row = dict(base_row)
    for field in DECISION_FIELDS:
        row[field] = decision.get(field, fallback_decision("Missing model field.")[field])
    row["claim_status"] = _enum(row["claim_status"], CLAIM_STATUS, "not_enough_information")
    row["issue_type"] = _enum(row["issue_type"], ISSUE_TYPES, "unknown")
    row["severity"] = _enum(row["severity"], SEVERITY, "unknown")
    row["risk_flags"] = _valid_risk_flags(row["risk_flags"])
    row["object_part"] = _valid_object_part(row["object_part"], str(base_row.get("claim_object", "")))
    return row


def validate_output_row(row: dict[str, Any]) -> dict[str, str]:
    return OutputWriter.__new__(OutputWriter).normalize_row(row)


def apply_evidence_precedence(row: dict[str, str]) -> dict[str, str]:
    """Force not_enough_information when evidence_standard_met is false."""
    if row.get("evidence_standard_met") == "false":
        row["claim_status"] = "not_enough_information"
        row["supporting_image_ids"] = "none"
    return row


def filter_supporting_image_ids(row: dict[str, str], valid_ids: set[str]) -> dict[str, str]:
    """Remove foreign image IDs; force not_enough_information if none remain for supported/contradicted."""
    raw = row.get("supporting_image_ids", "none")
    if raw == "none":
        return row
    ids = [id_.strip() for id_ in raw.split(";") if id_.strip() and id_.strip() != "none"]
    filtered = [id_ for id_ in ids if id_ in valid_ids]
    if not filtered:
        row["supporting_image_ids"] = "none"
        if row.get("claim_status") in ("supported", "contradicted"):
            row["claim_status"] = "not_enough_information"
    else:
        row["supporting_image_ids"] = ";".join(filtered)
    return row


def parse_and_validate_output(base_row: dict[str, Any], raw_json: str) -> dict[str, str]:
    try:
        decision = parse_model_json(raw_json)
    except (TypeError, json.JSONDecodeError, ValueError) as exc:
        decision = fallback_decision(f"Model returned invalid JSON: {type(exc).__name__}.")
    return validate_output_row(merge_output_row(base_row, decision))


def assert_output_columns(row: dict[str, Any]) -> None:
    missing = [column for column in OUTPUT_COLUMNS if column not in row]
    if missing:
        raise ValueError(f"Output row missing columns: {', '.join(missing)}")


def _enum(value: Any, allowed: list[str], fallback: str) -> str:
    normalized = str(value).strip().lower()
    return normalized if normalized in allowed else fallback


def _valid_object_part(value: Any, claim_object: str) -> str:
    normalized = str(value).strip().lower()
    allowed = OBJECT_PARTS.get(claim_object.strip().lower(), [])
    return normalized if normalized in allowed else "unknown"


def _valid_risk_flags(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = [part.strip().lower() for part in value.split(";") if part.strip()]
    else:
        try:
            parts = [str(part).strip().lower() for part in value if str(part).strip()]
        except TypeError:
            parts = []
    flags = [flag for flag in parts if flag in RISK_FLAGS and flag != "none"]
    return flags or ["none"]
