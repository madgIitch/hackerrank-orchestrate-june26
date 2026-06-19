from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from io_data import ClaimRecord, EvidenceRequirements, ImageLoader, OutputWriter, UserHistory, issue_family_for_issue_type
from model_client import ModelClient, ModelClientError
from parser_validator import fallback_decision, merge_output_row, validate_output_row
from prompt_builder import build_prompt_bundle


@dataclass
class PipelineLog:
    errors: list[str] = field(default_factory=list)

    def record(self, message: str) -> None:
        self.errors.append(message)


@dataclass
class SingleClaimPipeline:
    model_client: ModelClient
    image_loader: ImageLoader
    evidence_requirements: EvidenceRequirements
    log: PipelineLog = field(default_factory=PipelineLog)

    def process_claim(self, claim: ClaimRecord, history: UserHistory) -> dict[str, str]:
        images = []
        image_errors = []
        for image_path in claim.image_paths:
            try:
                images.append(self.image_loader.load(image_path))
            except (FileNotFoundError, OSError) as exc:
                message = f"{image_path}: {type(exc).__name__}"
                image_errors.append(message)
                self.log.record(f"image_load_error: {message}")

        base_row = self._base_row(claim)
        if not images:
            return validate_output_row(
                merge_output_row(base_row, fallback_decision("No usable images were loaded for automated review."))
            )

        evidence = self.evidence_requirements.lookup(
            claim.claim_object,
            issue_family=issue_family_for_issue_type("unknown"),
        )
        bundle = build_prompt_bundle(claim, history, evidence, images, image_errors)

        try:
            raw_json = self.model_client.generate_json(bundle.system_prompt, bundle.user_prompt, bundle.images)
        except (ModelClientError, RuntimeError, TimeoutError, ValueError) as exc:
            self.log.record(f"model_error: {type(exc).__name__}: {exc}")
            return validate_output_row(
                merge_output_row(base_row, fallback_decision("Automated model review failed; manual review is required."))
            )

        try:
            row = validate_output_row(merge_output_row(base_row, json.loads(raw_json)))
        except Exception as exc:
            self.log.record(f"model_parse_error: {type(exc).__name__}: {exc}")
            row = validate_output_row(
                merge_output_row(base_row, fallback_decision("Model returned invalid JSON; manual review is required."))
            )

        if image_errors:
            row = self._mark_partial_image_review(row)
        return row

    def write_rows(self, rows: Iterable[dict[str, str]], path: Path) -> None:
        OutputWriter(path).write(rows)

    def _base_row(self, claim: ClaimRecord) -> dict[str, object]:
        return {
            "user_id": claim.user_id,
            "image_paths": claim.image_paths,
            "user_claim": claim.user_claim,
            "claim_object": claim.claim_object,
        }

    def _mark_partial_image_review(self, row: dict[str, str]) -> dict[str, str]:
        flags = [flag for flag in row["risk_flags"].split(";") if flag and flag != "none"]
        if "manual_review_required" not in flags:
            flags.append("manual_review_required")
        row["risk_flags"] = ";".join(flags) if flags else "manual_review_required"
        if "partial" not in row["evidence_standard_met_reason"].lower():
            row["evidence_standard_met_reason"] = f"{row['evidence_standard_met_reason']} Partial image set; one or more images failed to load."
        if row["evidence_standard_met"] == "true":
            row["evidence_standard_met"] = "false"
        return row
