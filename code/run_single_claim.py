from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from io_data import ClaimLoader, EvidenceRequirements, ImageLoader, UserHistoryLoader, enrich_claims
from model_client import GeminiModelClient
from pipeline import SingleClaimPipeline


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the single-claim Gemini pipeline.")
    parser.add_argument("--claims", default="dataset/sample_claims.csv", help="Claims CSV path.")
    parser.add_argument("--index", type=int, default=0, help="Zero-based claim row index.")
    parser.add_argument("--write", help="Optional staging CSV path. Never defaults to output.csv.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")

    claims_path = REPO_ROOT / args.claims
    claims = ClaimLoader(claims_path).load()
    if args.index < 0 or args.index >= len(claims):
        raise IndexError(f"--index must be between 0 and {len(claims) - 1}")

    histories = UserHistoryLoader(REPO_ROOT / "dataset/user_history.csv").load()
    enriched = enrich_claims([claims[args.index]], histories)[0]

    pipeline = SingleClaimPipeline(
        model_client=GeminiModelClient(),
        image_loader=ImageLoader(REPO_ROOT / "dataset"),
        evidence_requirements=EvidenceRequirements(REPO_ROOT / "dataset/evidence_requirements.csv"),
    )
    row = pipeline.process_claim(enriched.claim, enriched.history)

    if args.write:
        pipeline.write_rows([row], REPO_ROOT / args.write)

    print(json.dumps(row, indent=2, ensure_ascii=False))
    if pipeline.log.errors:
        print("\nPipeline log:", file=sys.stderr)
        for error in pipeline.log.errors:
            print(f"- {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
