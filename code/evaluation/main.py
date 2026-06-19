"""Evaluation script: compares pipeline v1 vs v2 on sample_claims.csv.

Usage:
    python code/evaluation/main.py [--version v1|v2|both]

Requires GEMINI_API_KEY and GEMINI_MODEL environment variables.
Results are written to evaluation/evaluation_report.md.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = REPO_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from io_data import ClaimLoader, EvidenceRequirements, ImageLoader, UserHistoryLoader, enrich_claims
from model_client import GeminiModelClient
from pipeline import SingleClaimPipeline
from profile_data import main as profile_main
from prompt_builder import PROMPT_VERSION


DATASET_DIR = REPO_ROOT / "dataset"
EVAL_DIR = REPO_ROOT / "evaluation"
REPORT_PATH = EVAL_DIR / "evaluation_report.md"

SAMPLE_CLAIMS_PATH = DATASET_DIR / "sample_claims.csv"
USER_HISTORY_PATH = DATASET_DIR / "user_history.csv"
EVIDENCE_REQUIREMENTS_PATH = DATASET_DIR / "evidence_requirements.csv"


def _load_sample_ground_truth() -> dict[str, dict]:
    """Load sample_claims.csv rows keyed by user_id for accuracy comparison."""
    gt: dict[str, dict] = {}
    if not SAMPLE_CLAIMS_PATH.exists():
        return gt
    with SAMPLE_CLAIMS_PATH.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            gt[row.get("user_id", "")] = row
    return gt


def _run_pipeline_on_sample(prompt_version: str) -> list[dict[str, str]]:
    model = GeminiModelClient()
    image_loader = ImageLoader(DATASET_DIR)
    evidence = EvidenceRequirements(EVIDENCE_REQUIREMENTS_PATH)
    pipeline = SingleClaimPipeline(
        model_client=model,
        image_loader=image_loader,
        evidence_requirements=evidence,
    )

    claims = ClaimLoader(SAMPLE_CLAIMS_PATH).load()
    histories = UserHistoryLoader(USER_HISTORY_PATH).load()
    enriched = enrich_claims(claims, histories)

    results = []
    for item in enriched:
        row = pipeline.process_claim(item.claim, item.history)
        row["_prompt_version"] = prompt_version
        results.append(row)
    return results


def _accuracy(predictions: list[dict], ground_truth: dict[str, dict], field: str) -> tuple[float, dict]:
    correct = 0
    total = 0
    confusion: dict[tuple[str, str], int] = Counter()
    for pred in predictions:
        user_id = pred.get("user_id", "")
        gt_row = ground_truth.get(user_id)
        if gt_row is None or field not in gt_row:
            continue
        expected = gt_row[field].strip().lower()
        actual = pred.get(field, "").strip().lower()
        confusion[(expected, actual)] += 1
        if expected == actual:
            correct += 1
        total += 1
    acc = correct / total if total else 0.0
    return acc, dict(confusion)


def _write_report(v1_results: list[dict] | None, v2_results: list[dict], ground_truth: dict) -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Evaluation Report — Multi-Modal Evidence Review",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Active prompt_version: {PROMPT_VERSION}",
        "",
        "## Dataset",
        f"- sample_claims.csv: {len(v2_results)} rows processed",
        "",
    ]

    for label, results in [("v1 (baseline)", v1_results), (f"v2 (current — {PROMPT_VERSION})", v2_results)]:
        if results is None:
            continue
        lines += [f"## Results — {label}", ""]
        for field in ("claim_status", "issue_type", "object_part"):
            acc, confusion = _accuracy(results, ground_truth, field)
            lines += [
                f"### {field} accuracy: {acc:.1%} ({sum(1 for r in results if r.get(field) == ground_truth.get(r.get('user_id', ''), {}).get(field, ''))}/{len(results)})",
                "",
            ]
            if field == "claim_status" and confusion:
                lines += ["Confusion matrix (expected → predicted):"]
                for (exp, pred_val), count in sorted(confusion.items()):
                    lines.append(f"- {exp} → {pred_val}: {count}")
                lines.append("")

        supporting_mismatch = sum(
            1 for r in results
            if r.get("supporting_image_ids") == "none" and r.get("claim_status") == "supported"
        )
        lines += [
            "### supporting_image_ids coherence",
            f"- supported rows with supporting_image_ids=none (incoherent): {supporting_mismatch}",
            "",
        ]

    if v1_results and v2_results:
        v1_acc, _ = _accuracy(v1_results, ground_truth, "claim_status")
        v2_acc, _ = _accuracy(v2_results, ground_truth, "claim_status")
        delta = v2_acc - v1_acc
        lines += [
            "## v1 vs v2 comparison",
            f"- claim_status accuracy v1: {v1_acc:.1%}",
            f"- claim_status accuracy v2: {v2_acc:.1%}",
            f"- delta: {delta:+.1%}",
            "",
            "**Verdict:** " + (
                "v2 meets or exceeds v1 accuracy."
                if delta >= 0
                else f"v2 accuracy is lower than v1 by {abs(delta):.1%}. See worst-case analysis below."
            ),
            "",
        ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to {REPORT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pipeline evaluation on sample_claims.csv")
    parser.add_argument("--version", choices=["v1", "v2", "both"], default="v2")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set. Cannot run evaluation against real model.", file=sys.stderr)
        sys.exit(1)

    ground_truth = _load_sample_ground_truth()
    v1_results = None
    v2_results = None

    if args.version in ("v1", "both"):
        print("Running pipeline with v1 prompt...")
        v1_results = _run_pipeline_on_sample("v1")

    if args.version in ("v2", "both"):
        print(f"Running pipeline with {PROMPT_VERSION} prompt...")
        v2_results = _run_pipeline_on_sample(PROMPT_VERSION)

    if v2_results is None and v1_results is not None:
        v2_results = v1_results
        v1_results = None

    _write_report(v1_results, v2_results or [], ground_truth)


if __name__ == "__main__":
    main()
