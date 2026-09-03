"""Versioned local-first import/export for evaluator-authored evaluation datasets."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .evaluation import EvaluationResult, evaluate_submission
from .models import PairwiseEvaluationRecord
from .pairwise import PairwiseEvaluationResult, evaluate_pairwise_submission
from .rubrics import BUILTIN_RUBRICS
from .serialization import SubmissionRecord, record_from_dict, result_to_dict

INTERCHANGE_SCHEMA = "turkishevalkit.evaluation-dataset"
INTERCHANGE_SCHEMA_VERSION = "1.0"
InputFormat = Literal["auto", "json", "jsonl"]
OutputFormat = Literal["bundle", "array", "jsonl"]
ScoredResult = EvaluationResult | PairwiseEvaluationResult

_FILENAME_SAFE = re.compile(r"[^\w.-]+", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class WorkspaceImportSummary:
    """Outcome of importing evaluator records into a local workspace."""

    total_records: int
    imported_count: int
    duplicate_count: int
    artifact_ids: tuple[str, ...]
    dry_run: bool


def _safe_task_id(task_id: str) -> str:
    cleaned = _FILENAME_SAFE.sub("-", task_id.strip()).strip("._-")
    return (cleaned or "evaluation")[:80]


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _record_dict(record: SubmissionRecord) -> dict[str, Any]:
    data = asdict(record)
    if not isinstance(data, dict):
        raise TypeError("evaluation record serialization must produce an object")
    return data


def record_digest(record: SubmissionRecord) -> str:
    """Return a stable SHA-256 digest for the evaluator-authored record only."""

    return hashlib.sha256(_canonical_json(_record_dict(record)).encode("utf-8")).hexdigest()


def _score_record(record: SubmissionRecord) -> ScoredResult:
    rubric = BUILTIN_RUBRICS.get(record.rubric_id)
    if rubric is None:
        available = ", ".join(sorted(BUILTIN_RUBRICS))
        raise ValueError(
            f"unknown rubric '{record.rubric_id}'; available rubrics: {available}"
        )
    if isinstance(record, PairwiseEvaluationRecord):
        return evaluate_pairwise_submission(record, rubric)
    return evaluate_submission(record, rubric)


def _validated_record(data: dict[str, Any]) -> SubmissionRecord:
    record = record_from_dict(data)
    _score_record(record)
    return record


def _unwrap_record_object(data: dict[str, Any]) -> dict[str, Any]:
    raw_payload = data.get("payload")
    if isinstance(raw_payload, dict):
        return raw_payload
    return data


def _records_from_json_value(value: Any) -> tuple[SubmissionRecord, ...]:
    if isinstance(value, list):
        raw_records = value
    elif isinstance(value, dict) and value.get("schema") == INTERCHANGE_SCHEMA:
        if value.get("schema_version") != INTERCHANGE_SCHEMA_VERSION:
            raise ValueError(
                "unsupported interchange schema_version: "
                f"{value.get('schema_version')!r}; expected {INTERCHANGE_SCHEMA_VERSION!r}"
            )
        raw_records = value.get("records")
        if not isinstance(raw_records, list):
            raise ValueError("interchange bundle records must be a list")
        raw_count = value.get("record_count")
        if isinstance(raw_count, bool) or not isinstance(raw_count, int):
            raise ValueError("interchange bundle record_count must be an integer")
        if raw_count != len(raw_records):
            raise ValueError("interchange bundle record_count does not match records")
    elif isinstance(value, dict):
        raw_records = [value]
    else:
        raise ValueError("interchange JSON must be an object or array")

    records: list[SubmissionRecord] = []
    for index, item in enumerate(raw_records, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"record {index} must be a JSON object")
        try:
            records.append(_validated_record(_unwrap_record_object(item)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"record {index}: {exc}") from exc
    if not records:
        raise ValueError("interchange input must contain at least one evaluation record")
    return tuple(records)


def _records_from_jsonl(text: str) -> tuple[SubmissionRecord, ...]:
    records: list[SubmissionRecord] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line {line_number} must contain one JSON object")
        if value.get("schema") == INTERCHANGE_SCHEMA:
            raise ValueError("JSONL lines must contain records, not dataset bundles")
        try:
            records.append(_validated_record(_unwrap_record_object(value)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"JSONL line {line_number}: {exc}") from exc
    if not records:
        raise ValueError("interchange input must contain at least one evaluation record")
    return tuple(records)


def parse_interchange_text(
    text: str,
    *,
    input_format: InputFormat = "auto",
) -> tuple[SubmissionRecord, ...]:
    """Parse and validate JSON, canonical bundle JSON, or JSONL evaluator records."""

    if input_format not in {"auto", "json", "jsonl"}:
        raise ValueError("input_format must be one of: auto, json, jsonl")
    if not text.strip():
        raise ValueError("interchange input must not be empty")

    if input_format == "jsonl":
        return _records_from_jsonl(text)

    try:
        value = json.loads(text)
    except json.JSONDecodeError as json_error:
        if input_format == "json":
            raise ValueError(f"invalid JSON: {json_error.msg}") from json_error
        try:
            return _records_from_jsonl(text)
        except ValueError as jsonl_error:
            raise ValueError(
                f"input is neither valid JSON nor valid JSONL: {jsonl_error}"
            ) from json_error
    return _records_from_json_value(value)


def load_interchange_records(
    path: Path,
    *,
    input_format: InputFormat = "auto",
) -> tuple[SubmissionRecord, ...]:
    """Load evaluator records from a portable UTF-8 interchange file."""

    text = path.read_text(encoding="utf-8")
    resolved_format = input_format
    if input_format == "auto" and path.suffix.lower() in {".jsonl", ".ndjson"}:
        resolved_format = "jsonl"
    return parse_interchange_text(text, input_format=resolved_format)


def interchange_payload(records: Sequence[SubmissionRecord]) -> dict[str, Any]:
    """Build the canonical versioned JSON dataset envelope."""

    if not records:
        raise ValueError("interchange output requires at least one evaluation record")
    canonical_records = [_record_dict(record) for record in records]
    return {
        "schema": INTERCHANGE_SCHEMA,
        "schema_version": INTERCHANGE_SCHEMA_VERSION,
        "record_count": len(canonical_records),
        "records": canonical_records,
    }


def render_interchange(
    records: Sequence[SubmissionRecord],
    *,
    output_format: OutputFormat = "bundle",
) -> str:
    """Render validated evaluator records in a supported portable representation."""

    if output_format not in {"bundle", "array", "jsonl"}:
        raise ValueError("output_format must be one of: bundle, array, jsonl")
    if not records:
        raise ValueError("interchange output requires at least one evaluation record")

    if output_format == "bundle":
        payload: Any = interchange_payload(records)
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    record_dicts = [_record_dict(record) for record in records]
    if output_format == "array":
        return json.dumps(record_dicts, ensure_ascii=False, indent=2) + "\n"
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in record_dicts
    )


def write_interchange_records(
    path: Path,
    records: Sequence[SubmissionRecord],
    *,
    output_format: OutputFormat = "bundle",
) -> None:
    """Atomically write a portable evaluation dataset."""

    payload = render_interchange(records, output_format=output_format)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def _load_workspace_record(path: Path) -> SubmissionRecord:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name}: invalid evaluation JSON: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: evaluation artifact must contain one JSON object")
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: evaluation artifact has no evaluator payload")
    try:
        return _validated_record(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path.name}: {exc}") from exc


def load_workspace_records(workspace: Path) -> tuple[SubmissionRecord, ...]:
    """Read and validate all evaluator-authored records in a local workspace."""

    directory = workspace.expanduser().resolve() / "evaluations"
    if not directory.exists():
        return ()
    records = [_load_workspace_record(path) for path in sorted(directory.glob("*.json"))]
    return tuple(records)


def export_workspace(
    workspace: Path,
    output: Path,
    *,
    output_format: OutputFormat = "bundle",
) -> int:
    """Export evaluator-authored records without workflow/revision process metadata."""

    records = load_workspace_records(workspace)
    if not records:
        raise ValueError("workspace contains no evaluation records to export")
    write_interchange_records(output, records, output_format=output_format)
    return len(records)


def _existing_workspace_digests(workspace: Path) -> set[str]:
    directory = workspace / "evaluations"
    if not directory.exists():
        return set()
    return {
        record_digest(_load_workspace_record(path))
        for path in sorted(directory.glob("*.json"))
    }


def _import_destination(
    directory: Path,
    record: SubmissionRecord,
    digest: str,
) -> Path:
    stem = f"{_safe_task_id(record.task_id)}-import-{digest[:24]}"
    candidate = directory / f"{stem}.json"
    if not candidate.exists():
        return candidate
    existing = _load_workspace_record(candidate)
    if record_digest(existing) == digest:
        return candidate
    return directory / f"{_safe_task_id(record.task_id)}-import-{digest}.json"


def import_workspace_records(
    workspace: Path,
    records: Sequence[SubmissionRecord],
    *,
    dry_run: bool = False,
) -> WorkspaceImportSummary:
    """Import validated records as untracked scored artifacts with content deduplication."""

    if not records:
        raise ValueError("workspace import requires at least one evaluation record")

    resolved_workspace = workspace.expanduser().resolve()
    scored: list[tuple[SubmissionRecord, ScoredResult, str]] = []
    for record in records:
        scored.append((record, _score_record(record), record_digest(record)))

    existing_digests = _existing_workspace_digests(resolved_workspace)
    seen_digests = set(existing_digests)
    pending: list[tuple[SubmissionRecord, ScoredResult, str]] = []
    duplicate_count = 0
    for item in scored:
        digest = item[2]
        if digest in seen_digests:
            duplicate_count += 1
            continue
        seen_digests.add(digest)
        pending.append(item)

    directory = resolved_workspace / "evaluations"
    planned_paths = [
        _import_destination(directory, record, digest)
        for record, _, digest in pending
    ]
    if dry_run:
        return WorkspaceImportSummary(
            total_records=len(records),
            imported_count=len(pending),
            duplicate_count=duplicate_count,
            artifact_ids=tuple(path.name for path in planned_paths),
            dry_run=True,
        )

    directory.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for (_record, result, digest), destination in zip(
            pending,
            planned_paths,
            strict=True,
        ):
            if destination.exists():
                existing = _load_workspace_record(destination)
                if record_digest(existing) == digest:
                    duplicate_count += 1
                    continue
                raise ValueError(f"import destination collision: {destination.name}")
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_text(
                json.dumps(result_to_dict(result), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(destination)
            created.append(destination)
    except (OSError, TypeError, ValueError):
        for path in created:
            path.unlink(missing_ok=True)
        raise

    return WorkspaceImportSummary(
        total_records=len(records),
        imported_count=len(created),
        duplicate_count=duplicate_count,
        artifact_ids=tuple(path.name for path in created),
        dry_run=False,
    )


def import_workspace_file(
    workspace: Path,
    input_path: Path,
    *,
    input_format: InputFormat = "auto",
    dry_run: bool = False,
) -> WorkspaceImportSummary:
    """Load a portable dataset and import it into a local workspace."""

    records = load_interchange_records(input_path, input_format=input_format)
    return import_workspace_records(workspace, records, dry_run=dry_run)
