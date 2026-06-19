from __future__ import annotations

import base64
import csv
import mimetypes
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from schema import (
    BOOLEAN_VALUES,
    CLAIM_OBJECTS,
    CLAIM_STATUS,
    ENUMS,
    ISSUE_TYPES,
    OBJECT_PARTS,
    OUTPUT_COLUMNS,
    RISK_FLAGS,
    SEVERITY,
)


CLAIM_COLUMNS = ["user_id", "image_paths", "user_claim", "claim_object"]
USER_HISTORY_COLUMNS = [
    "user_id",
    "past_claim_count",
    "accept_claim",
    "manual_review_claim",
    "rejected_claim",
    "last_90_days_claim_count",
    "history_flags",
    "history_summary",
]
EVIDENCE_COLUMNS = ["requirement_id", "claim_object", "applies_to", "minimum_image_evidence"]
MAX_IMAGE_DIMENSION = 1024


@dataclass(frozen=True)
class ClaimRecord:
    user_id: str
    image_paths: list[str]
    image_ids: list[str]
    user_claim: str
    claim_object: str


@dataclass(frozen=True)
class UserHistory:
    user_id: str
    past_claim_count: int
    accept_claim: int
    manual_review_claim: int
    rejected_claim: int
    last_90_days_claim_count: int
    history_flags: str
    history_summary: str


@dataclass(frozen=True)
class EnrichedClaim:
    claim: ClaimRecord
    history: UserHistory


@dataclass(frozen=True)
class EvidenceRequirement:
    requirement_id: str
    claim_object: str
    applies_to: str
    minimum_image_evidence: str


@dataclass(frozen=True)
class EvidenceLookupResult:
    requirements: list[EvidenceRequirement]
    matched_rule: str


@dataclass(frozen=True)
class ImagePayload:
    image_id: str
    source_path: str
    media_type: str
    width: int
    height: int
    base64_data: str
    resized: bool
    original_width: int
    original_height: int
    byte_size: int


def read_csv_rows(path: Path, required_columns: Iterable[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        missing = [column for column in required_columns if column not in columns]
        if missing:
            raise ValueError(f"{path}: missing required columns {', '.join(missing)}")
        return list(reader)


def split_image_paths(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def image_id_from_path(image_path: str) -> str:
    return Path(image_path.replace("\\", "/")).stem


def missing_history(user_id: str) -> UserHistory:
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


def _to_int(value: str) -> int:
    return int((value or "0").strip() or "0")


class ClaimLoader:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[ClaimRecord]:
        claims: list[ClaimRecord] = []
        for index, row in enumerate(read_csv_rows(self.path, CLAIM_COLUMNS), start=2):
            claim_object = (row.get("claim_object") or "").strip().lower()
            if claim_object not in CLAIM_OBJECTS:
                raise ValueError(f"{self.path}:{index}: invalid claim_object {claim_object!r}")
            image_paths = split_image_paths(row.get("image_paths", ""))
            if not image_paths:
                raise ValueError(f"{self.path}:{index}: image_paths is empty")
            claims.append(
                ClaimRecord(
                    user_id=(row.get("user_id") or "").strip(),
                    image_paths=image_paths,
                    image_ids=[image_id_from_path(path) for path in image_paths],
                    user_claim=row.get("user_claim") or "",
                    claim_object=claim_object,
                )
            )
        return claims


class UserHistoryLoader:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> dict[str, UserHistory]:
        history: dict[str, UserHistory] = {}
        for row in read_csv_rows(self.path, USER_HISTORY_COLUMNS):
            user_id = (row.get("user_id") or "").strip()
            history[user_id] = UserHistory(
                user_id=user_id,
                past_claim_count=_to_int(row.get("past_claim_count", "0")),
                accept_claim=_to_int(row.get("accept_claim", "0")),
                manual_review_claim=_to_int(row.get("manual_review_claim", "0")),
                rejected_claim=_to_int(row.get("rejected_claim", "0")),
                last_90_days_claim_count=_to_int(row.get("last_90_days_claim_count", "0")),
                history_flags=(row.get("history_flags") or "none").strip() or "none",
                history_summary=(row.get("history_summary") or "").strip(),
            )
        return history


def enrich_claims(claims: Iterable[ClaimRecord], histories: dict[str, UserHistory]) -> list[EnrichedClaim]:
    return [EnrichedClaim(claim=claim, history=histories.get(claim.user_id, missing_history(claim.user_id))) for claim in claims]


def issue_family_for_issue_type(issue_type: str) -> str:
    normalized = (issue_type or "").strip().lower()
    if normalized in {"dent", "scratch"}:
        return "dent or scratch"
    if normalized in {"crack", "glass_shatter", "broken_part", "missing_part"}:
        return "crack, broken, or missing part"
    if normalized in {"torn_packaging", "crushed_packaging"}:
        return "torn or crushed packaging"
    if normalized in {"water_damage", "stain"}:
        return "water damage or stain"
    return "general claim review"


class EvidenceRequirements:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.requirements = [
            EvidenceRequirement(
                requirement_id=row["requirement_id"],
                claim_object=row["claim_object"].strip().lower(),
                applies_to=row["applies_to"].strip().lower(),
                minimum_image_evidence=row["minimum_image_evidence"],
            )
            for row in read_csv_rows(self.path, EVIDENCE_COLUMNS)
        ]

    def lookup(self, claim_object: str, issue_family: str | None = None, issue_type: str | None = None) -> EvidenceLookupResult:
        normalized_object = (claim_object or "").strip().lower()
        family = (issue_family or issue_family_for_issue_type(issue_type or "")).strip().lower()
        levels = [
            ("object_exact", lambda item: item.claim_object == normalized_object and item.applies_to == family),
            ("all_exact", lambda item: item.claim_object == "all" and item.applies_to == family),
            ("object_general", lambda item: item.claim_object == normalized_object and item.applies_to == "general claim review"),
            ("all_general", lambda item: item.claim_object == "all" and item.applies_to == "general claim review"),
        ]
        for name, predicate in levels:
            matches = [item for item in self.requirements if predicate(item)]
            if matches:
                return EvidenceLookupResult(requirements=matches, matched_rule=name)
        return EvidenceLookupResult(requirements=[], matched_rule="none")


class ImageLoader:
    def __init__(self, dataset_dir: Path, max_dimension: int = MAX_IMAGE_DIMENSION):
        self.dataset_dir = Path(dataset_dir)
        self.max_dimension = max_dimension

    def resolve(self, image_path: str) -> Path:
        candidate = self.dataset_dir / image_path
        if candidate.exists():
            return candidate
        candidate = self.dataset_dir / image_path.replace("\\", "/")
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Missing image: {image_path}")

    def load(self, image_path: str) -> ImagePayload:
        source = self.resolve(image_path)
        original_bytes = source.read_bytes()
        with Image.open(source) as image:
            original_width, original_height = image.size
            media_type = mimetypes.guess_type(source.name)[0] or Image.MIME.get(image.format, "application/octet-stream")
            if original_width <= self.max_dimension and original_height <= self.max_dimension:
                payload_bytes = original_bytes
                width, height = original_width, original_height
                resized = False
            else:
                resized_image = image.convert("RGB")
                resized_image.thumbnail((self.max_dimension, self.max_dimension), Image.Resampling.LANCZOS)
                buffer = BytesIO()
                resized_image.save(buffer, format="JPEG", quality=85)
                payload_bytes = buffer.getvalue()
                width, height = resized_image.size
                media_type = "image/jpeg"
                resized = True
        return ImagePayload(
            image_id=image_id_from_path(image_path),
            source_path=image_path,
            media_type=media_type,
            width=width,
            height=height,
            base64_data=base64.b64encode(payload_bytes).decode("ascii"),
            resized=resized,
            original_width=original_width,
            original_height=original_height,
            byte_size=len(payload_bytes),
        )


class OutputWriter:
    def __init__(self, path: Path):
        self.path = Path(path)

    def write(self, rows: Iterable[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(self.normalize_row(row))

    def normalize_row(self, row: dict[str, Any]) -> dict[str, str]:
        missing = [column for column in OUTPUT_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"Output row missing columns: {', '.join(missing)}")
        claim_object = str(row["claim_object"]).strip().lower()
        if claim_object not in CLAIM_OBJECTS:
            raise ValueError(f"Invalid claim_object: {claim_object}")
        object_part = str(row["object_part"]).strip().lower() or "unknown"
        if object_part not in OBJECT_PARTS[claim_object]:
            raise ValueError(f"Invalid object_part {object_part!r} for {claim_object}")

        out = {column: "" for column in OUTPUT_COLUMNS}
        for column in OUTPUT_COLUMNS:
            out[column] = self._stringify(row[column])

        out["claim_object"] = claim_object
        out["evidence_standard_met"] = self._boolean(row["evidence_standard_met"])
        out["risk_flags"] = self._risk_flags(row["risk_flags"])
        out["issue_type"] = self._enum(row["issue_type"], ISSUE_TYPES, "unknown")
        out["object_part"] = object_part
        out["claim_status"] = self._enum(row["claim_status"], CLAIM_STATUS, "not_enough_information")
        out["supporting_image_ids"] = self._list(row["supporting_image_ids"], fallback="none")
        out["valid_image"] = self._boolean(row["valid_image"])
        out["severity"] = self._enum(row["severity"], SEVERITY, "unknown")
        return out

    def _stringify(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return ";".join(str(item).strip() for item in value if str(item).strip())
        return str(value)

    def _enum(self, value: Any, allowed: list[str], fallback: str) -> str:
        normalized = str(value).strip().lower()
        return normalized if normalized in allowed else fallback

    def _boolean(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        normalized = str(value).strip().lower()
        return normalized if normalized in BOOLEAN_VALUES else "false"

    def _list(self, value: Any, fallback: str) -> str:
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(";") if part.strip()]
        else:
            parts = [str(part).strip() for part in value if str(part).strip()]
        return ";".join(parts) if parts else fallback

    def _risk_flags(self, value: Any) -> str:
        flags = [flag for flag in self._list(value, fallback="none").split(";") if flag in RISK_FLAGS and flag != "none"]
        return ";".join(flags) if flags else "none"
