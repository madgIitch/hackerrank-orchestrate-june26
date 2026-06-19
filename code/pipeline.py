from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from io_data import ClaimRecord, EvidenceRequirements, ImageLoader, ImagePayload, OutputWriter, UserHistory, issue_family_for_issue_type
from model_client import ModelClient, ModelClientError
from parser_validator import (
    apply_evidence_precedence,
    fallback_decision,
    filter_supporting_image_ids,
    merge_output_row,
    validate_output_row,
)
from prompt_builder import PROMPT_VERSION, build_prompt_bundle, build_triage_bundle
from schema import ISSUE_TYPES, RISK_FLAGS


@dataclass
class PipelineLog:
    errors: list[str] = field(default_factory=list)
    prompt_version: str = PROMPT_VERSION

    def record(self, message: str) -> None:
        self.errors.append(message)


@dataclass
class SingleClaimPipeline:
    model_client: ModelClient
    image_loader: ImageLoader
    evidence_requirements: EvidenceRequirements
    log: PipelineLog = field(default_factory=PipelineLog)

    def process_claim(self, claim: ClaimRecord, history: UserHistory) -> dict[str, str]:
        images, image_errors = self._load_images(claim)
        base_row = self._base_row(claim)

        if not images:
            return validate_output_row(
                merge_output_row(base_row, fallback_decision("No usable images were loaded for automated review."))
            )

        # Pass 1: triage — identify issue_type and object_part from visual evidence
        triage = self._triage_pass(claim, images)
        issue_type = "unknown"
        visual_summary = ""
        if triage:
            raw_issue = str(triage.get("issue_type", "unknown")).strip().lower()
            issue_type = raw_issue if raw_issue in ISSUE_TYPES else "unknown"
            visual_summary = str(triage.get("visual_summary", ""))

        # Lookup exact requirements based on triage issue_type
        evidence = self.evidence_requirements.lookup(
            claim.claim_object,
            issue_family=issue_family_for_issue_type(issue_type),
        )

        # Pass 2: full decision with requirements, history, and triage context
        bundle = build_prompt_bundle(claim, history, evidence, images, image_errors, triage_summary=visual_summary)
        try:
            raw_json = self.model_client.generate_json(bundle.system_prompt, bundle.user_prompt, bundle.images)
        except (ModelClientError, RuntimeError, TimeoutError, ValueError) as exc:
            self.log.record(f"model_error: {type(exc).__name__}: {exc}")
            return validate_output_row(
                merge_output_row(base_row, fallback_decision("Automated model review failed; manual review is required."))
            )

        try:
            decision = json.loads(raw_json)
        except Exception as exc:
            self.log.record(f"model_parse_error: {type(exc).__name__}: {exc}")
            return validate_output_row(
                merge_output_row(base_row, fallback_decision("Model returned invalid JSON; manual review is required."))
            )

        row = validate_output_row(merge_output_row(base_row, decision))
        row = filter_supporting_image_ids(row, set(claim.image_ids))
        row = apply_evidence_precedence(row)
        row = _apply_history_risk(row, history)

        if image_errors:
            row = self._mark_partial_image_review(row)

        return row

    def write_rows(self, rows: Iterable[dict[str, str]], path: Path) -> None:
        OutputWriter(path).write(rows)

    def _triage_pass(self, claim: ClaimRecord, images: list[ImagePayload]) -> dict[str, Any] | None:
        bundle = build_triage_bundle(claim, images)
        try:
            raw = self.model_client.generate_json(bundle.system_prompt, bundle.user_prompt, bundle.images)
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            self.log.record("triage_error: response was not a JSON object")
            return None
        except Exception as exc:
            self.log.record(f"triage_error: {type(exc).__name__}: {exc}")
            return None

    def _base_row(self, claim: ClaimRecord) -> dict[str, object]:
        return {
            "user_id": claim.user_id,
            "image_paths": claim.image_paths,
            "user_claim": claim.user_claim,
            "claim_object": claim.claim_object,
        }

    def _load_images(self, claim: ClaimRecord) -> tuple[list[ImagePayload], list[str]]:
        images: list[ImagePayload] = []
        errors: list[str] = []
        for image_path in claim.image_paths:
            try:
                images.append(self.image_loader.load(image_path))
            except (FileNotFoundError, OSError) as exc:
                message = f"{image_path}: {type(exc).__name__}"
                errors.append(message)
                self.log.record(f"image_load_error: {message}")
        return images, errors

    def _mark_partial_image_review(self, row: dict[str, str]) -> dict[str, str]:
        flags = [flag for flag in row["risk_flags"].split(";") if flag and flag != "none"]
        if "manual_review_required" not in flags:
            flags.append("manual_review_required")
        row["risk_flags"] = ";".join(flags) if flags else "manual_review_required"
        if "partial" not in row["evidence_standard_met_reason"].lower():
            row["evidence_standard_met_reason"] = (
                f"{row['evidence_standard_met_reason']} Partial image set; one or more images failed to load."
            )
        if row["evidence_standard_met"] == "true":
            row["evidence_standard_met"] = "false"
        return row


def _apply_history_risk(row: dict[str, str], history: UserHistory) -> dict[str, str]:
    """Add user_history_risk risk flag when history indicates elevated risk. Never changes claim_status."""
    history_flags = (history.history_flags or "").strip().lower()
    risky = (
        (history_flags and history_flags != "none")
        or history.rejected_claim > 1
        or history.last_90_days_claim_count > 3
    )
    if not risky:
        return row
    current = row.get("risk_flags", "none")
    if "user_history_risk" in current:
        return row
    row["risk_flags"] = current + ";user_history_risk" if current != "none" else "user_history_risk"
    return row
