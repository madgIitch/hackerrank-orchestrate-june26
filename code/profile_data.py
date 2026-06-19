from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from schema import CLAIM_OBJECTS, ENUMS, ISSUE_TYPES, OUTPUT_COLUMNS, assert_unique_enums


DATASET_FILES = {
    "sample_claims": "sample_claims.csv",
    "claims": "claims.csv",
    "user_history": "user_history.csv",
    "evidence_requirements": "evidence_requirements.csv",
}

REQUIRED_COLUMNS = {
    "sample_claims": OUTPUT_COLUMNS,
    "claims": ["user_id", "image_paths", "user_claim", "claim_object"],
    "user_history": [
        "user_id",
        "past_claim_count",
        "accept_claim",
        "manual_review_claim",
        "rejected_claim",
        "last_90_days_claim_count",
        "history_flags",
        "history_summary",
    ],
    "evidence_requirements": [
        "requirement_id",
        "claim_object",
        "applies_to",
        "minimum_image_evidence",
    ],
}


@dataclass
class CsvProfile:
    name: str
    path: Path
    row_count: int
    columns: list[str]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def csv_columns(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        return next(reader)


def split_image_paths(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def resolve_dataset_path(dataset_dir: Path, image_path: str) -> Path:
    candidate = dataset_dir / image_path
    if candidate.exists():
        return candidate
    return dataset_dir / image_path.replace("\\", "/")


def distribution(rows: list[dict[str, str]], field: str, expected: list[str]) -> dict[str, object]:
    total_rows = len(rows)
    values = [(row.get(field) or "").strip().lower() for row in rows]
    empty_count = sum(1 for value in values if not value)
    non_empty = [value for value in values if value]
    counts = Counter(non_empty)
    denominator = len(non_empty) or 1
    items = [
        {
            "value": value,
            "count": count,
            "percent": round((count / denominator) * 100, 2),
        }
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    unexpected = sorted(value for value in counts if value not in set(expected))
    return {
        "field": field,
        "total_rows": total_rows,
        "non_empty_rows": len(non_empty),
        "empty_rows": empty_count,
        "unexpected_values": unexpected,
        "items": items,
    }


def validate_columns(profiles: dict[str, CsvProfile]) -> list[str]:
    incidents: list[str] = []
    for name, required in REQUIRED_COLUMNS.items():
        missing = [column for column in required if column not in profiles[name].columns]
        if missing:
            incidents.append(f"{name}: missing required columns {', '.join(missing)}")
    return incidents


def validate_sample_images(dataset_dir: Path, sample_rows: list[dict[str, str]]) -> tuple[int, list[str]]:
    checked = 0
    incidents: list[str] = []
    for row_number, row in enumerate(sample_rows, start=2):
        paths = split_image_paths(row.get("image_paths", ""))
        if not paths:
            incidents.append(f"sample_claims row {row_number}: image_paths is empty")
            continue
        for image_path in paths:
            checked += 1
            if not resolve_dataset_path(dataset_dir, image_path).exists():
                incidents.append(f"sample_claims row {row_number}: missing image {image_path}")
    return checked, incidents


def load_profiles(repo_root: Path) -> tuple[dict[str, CsvProfile], dict[str, list[dict[str, str]]]]:
    dataset_dir = repo_root / "dataset"
    rows_by_name: dict[str, list[dict[str, str]]] = {}
    profiles: dict[str, CsvProfile] = {}
    for name, filename in DATASET_FILES.items():
        path = dataset_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing required CSV: {path}")
        rows = read_csv(path)
        rows_by_name[name] = rows
        profiles[name] = CsvProfile(
            name=name,
            path=path,
            row_count=len(rows),
            columns=csv_columns(path),
        )
    return profiles, rows_by_name


def render_distribution(section: dict[str, object]) -> list[str]:
    lines = [
        f"### {section['field']}",
        "",
        f"- total_rows: {section['total_rows']}",
        f"- non_empty_rows: {section['non_empty_rows']}",
        f"- empty_rows: {section['empty_rows']}",
        f"- unexpected_values: {', '.join(section['unexpected_values']) if section['unexpected_values'] else 'none'}",
        "",
        "| value | count | percent |",
        "|---|---:|---:|",
    ]
    for item in section["items"]:
        lines.append(f"| {item['value']} | {item['count']} | {item['percent']:.2f}% |")
    lines.append("")
    return lines


def build_report(repo_root: Path) -> tuple[str, list[str]]:
    assert_unique_enums()
    profiles, rows_by_name = load_profiles(repo_root)
    incidents = validate_columns(profiles)
    checked_images, image_incidents = validate_sample_images(repo_root / "dataset", rows_by_name["sample_claims"])
    incidents.extend(image_incidents)

    sample_rows = rows_by_name["sample_claims"]
    distributions = [
        distribution(sample_rows, "claim_status", ENUMS["claim_status"]),
        distribution(sample_rows, "claim_object", CLAIM_OBJECTS),
        distribution(sample_rows, "issue_type", ISSUE_TYPES),
    ]
    for section in distributions:
        for value in section["unexpected_values"]:
            incidents.append(f"sample_claims {section['field']}: unexpected value {value}")

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# Data Profile",
        "",
        f"Generated: {timestamp}",
        "",
        "## CSV Summary",
        "",
        "| dataset | path | rows | columns |",
        "|---|---|---:|---|",
    ]
    for profile in profiles.values():
        relative = profile.path.relative_to(repo_root).as_posix()
        lines.append(f"| {profile.name} | `{relative}` | {profile.row_count} | {', '.join(profile.columns)} |")
    lines.extend(["", "## Output Contract", ""])
    lines.append("Columns, in order:")
    lines.append("")
    for index, column in enumerate(OUTPUT_COLUMNS, start=1):
        lines.append(f"{index}. `{column}`")
    lines.extend(["", "## Sample Distributions", ""])
    for section in distributions:
        lines.extend(render_distribution(section))
    lines.extend(
        [
            "## Image Path Validation",
            "",
            f"- sample image paths checked: {checked_images}",
            f"- missing sample image paths: {len(image_incidents)}",
            "",
            "## Incidents and Warnings",
            "",
        ]
    )
    if incidents:
        lines.extend(f"- {incident}" for incident in incidents)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines), incidents


def write_report(repo_root: Path) -> Path:
    report, incidents = build_report(repo_root)
    output_path = repo_root / "evaluation" / "data_profile.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    if incidents:
        raise SystemExit("Data profile found contract incidents; see evaluation/data_profile.md")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile HackerRank Orchestrate datasets.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    output_path = write_report(args.repo_root.resolve())
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
