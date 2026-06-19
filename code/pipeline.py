from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from evidence_rules import EvidenceRuleContext, apply_evidence_rules, apply_history_risk_flags
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
from schema import ISSUE_TYPES

log = logging.getLogger("pipeline")


@dataclass
class PipelineLog:
    errors: list[str] = field(default_factory=list)
    prompt_version: str = PROMPT_VERSION

    def record(self, message: str) -> None:
        self.errors.append(message)
        log.warning("pipeline_event: %s", message)


@dataclass
class SingleClaimPipeline:
    model_client: ModelClient
    image_loader: ImageLoader
    evidence_requirements: EvidenceRequirements
    log: PipelineLog = field(default_factory=PipelineLog)

    def process_claim(self, claim: ClaimRecord, history: UserHistory) -> dict[str, str]:
        log.info("[%s] start claim_object=%s images=%s", claim.user_id, claim.claim_object, claim.image_ids)

        images, image_errors = self._load_images(claim)
        base_row = self._base_row(claim)

        if not images:
            log.warning("[%s] no usable images → fallback", claim.user_id)
            return validate_output_row(
                merge_output_row(base_row, fallback_decision("No usable images were loaded for automated review."))
            )

        if image_errors:
            log.warning("[%s] partial image errors: %s", claim.user_id, image_errors)

        # Pass 1: triage — identify issue_type and object_part from visual evidence
        log.info("[%s] pass-1 triage start (%d images)", claim.user_id, len(images))
        triage = self._triage_pass(claim, images)
        issue_type = "unknown"
        visual_summary = ""
        if triage:
            raw_issue = str(triage.get("issue_type", "unknown")).strip().lower()
            issue_type = raw_issue if raw_issue in ISSUE_TYPES else "unknown"
            visual_summary = str(triage.get("visual_summary", ""))
            log.info(
                "[%s] triage → issue_type=%s object_part=%s relevant_ids=%s summary=%r",
                claim.user_id, issue_type,
                triage.get("object_part", "?"),
                triage.get("relevant_image_ids", []),
                visual_summary[:120],
            )
        else:
            log.warning("[%s] triage failed → using general requirements", claim.user_id)

        # Lookup exact requirements based on triage issue_type
        evidence = self.evidence_requirements.lookup(
            claim.claim_object,
            issue_family=issue_family_for_issue_type(issue_type),
        )
        log.info("[%s] evidence lookup → matched_rule=%s requirements=%d", claim.user_id, evidence.matched_rule, len(evidence.requirements))

        # Pass 2: full decision with requirements, history, and triage context
        log.info("[%s] pass-2 decision start (prompt_version=%s)", claim.user_id, self.log.prompt_version)
        bundle = build_prompt_bundle(claim, history, evidence, images, image_errors, triage_summary=visual_summary)
        try:
            raw_json = self.model_client.generate_json(bundle.system_prompt, bundle.user_prompt, bundle.images)
        except (ModelClientError, RuntimeError, TimeoutError, ValueError) as exc:
            self.log.record(f"model_error: {type(exc).__name__}: {exc}")
            log.error("[%s] decision call failed: %s", claim.user_id, exc)
            return validate_output_row(
                merge_output_row(base_row, fallback_decision("Automated model review failed; manual review is required."))
            )

        try:
            decision = json.loads(raw_json)
        except Exception as exc:
            self.log.record(f"model_parse_error: {type(exc).__name__}: {exc}")
            log.error("[%s] decision JSON parse failed: %s | raw=%r", claim.user_id, exc, raw_json[:200])
            return validate_output_row(
                merge_output_row(base_row, fallback_decision("Model returned invalid JSON; manual review is required."))
            )

        log.debug("[%s] raw decision: %s", claim.user_id, json.dumps(decision))

        row = validate_output_row(merge_output_row(base_row, decision))

        before_ids = row.get("supporting_image_ids")
        row = filter_supporting_image_ids(row, set(claim.image_ids))
        if row.get("supporting_image_ids") != before_ids:
            log.info("[%s] image_id filter: %r → %r", claim.user_id, before_ids, row["supporting_image_ids"])

        before_evidence = row.get("evidence_standard_met")
        row = apply_evidence_rules(
            row,
            EvidenceRuleContext(
                evidence=evidence,
                claim_object=claim.claim_object,
                issue_type=row.get("issue_type", "unknown"),
                valid_image_ids={image.image_id for image in images},
                image_errors=image_errors,
            ),
        )
        if row.get("evidence_standard_met") != before_evidence:
            log.info(
                "[%s] evidence_rules override: evidence_standard_met %s → %s",
                claim.user_id, before_evidence, row.get("evidence_standard_met"),
            )

        before_status = row.get("claim_status")
        row = apply_evidence_precedence(row)
        if row.get("claim_status") != before_status:
            log.info(
                "[%s] evidence_precedence override: claim_status %s → %s (evidence_standard_met=%s)",
                claim.user_id, before_status, row["claim_status"], row.get("evidence_standard_met"),
            )

        row = apply_history_risk_flags(row, history)

        log.info(
            "[%s] done → claim_status=%s issue_type=%s object_part=%s severity=%s evidence_met=%s risk_flags=%s",
            claim.user_id,
            row.get("claim_status"), row.get("issue_type"), row.get("object_part"),
            row.get("severity"), row.get("evidence_standard_met"), row.get("risk_flags"),
        )
        return row

    def write_rows(self, rows: Iterable[dict[str, str]], path: Path) -> None:
        OutputWriter(path).write(rows)

    def _triage_pass(self, claim: ClaimRecord, images: list[ImagePayload]) -> dict[str, Any] | None:
        bundle = build_triage_bundle(claim, images)
        try:
            raw = self.model_client.generate_json(bundle.system_prompt, bundle.user_prompt, bundle.images)
            log.debug("[%s] triage raw response: %r", claim.user_id, raw[:300])
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            self.log.record("triage_error: response was not a JSON object")
            return None
        except Exception as exc:
            self.log.record(f"triage_error: {type(exc).__name__}: {exc}")
            log.error("[%s] triage exception: %s", claim.user_id, exc)
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
