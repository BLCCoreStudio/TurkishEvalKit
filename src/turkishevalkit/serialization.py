"""Portable JSON serialization helpers for evaluation records and results."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .evaluation import EvaluationResult
from .models import EvaluationRecord, EvaluationType, Rating


def record_from_dict(data: dict[str, Any]) -> EvaluationRecord:
    """Build a validated EvaluationRecord from a JSON-compatible mapping."""

    raw_ratings = data.get("ratings")
    if not isinstance(raw_ratings, list):
        raise ValueError("ratings must be a list")

    ratings: list[Rating] = []
    for item in raw_ratings:
        if not isinstance(item, dict):
            raise ValueError("each rating must be an object")
        ratings.append(
            Rating(
                criterion_id=str(item.get("criterion_id", "")),
                score=int(item.get("score", 0)),
                note=str(item.get("note", "")),
            )
        )

    source = data.get("source", {})
    metadata = data.get("metadata", {})
    if not isinstance(source, dict) or not isinstance(metadata, dict):
        raise ValueError("source and metadata must be objects")

    try:
        evaluation_type = EvaluationType(str(data.get("evaluation_type", "")))
    except ValueError as exc:
        supported = ", ".join(item.value for item in EvaluationType)
        raise ValueError(f"evaluation_type must be one of: {supported}") from exc

    return EvaluationRecord(
        task_id=str(data.get("task_id", "")),
        evaluation_type=evaluation_type,
        rubric_id=str(data.get("rubric_id", "")),
        rubric_version=str(data.get("rubric_version", "")),
        ratings=tuple(ratings),
        evaluator_note=str(data.get("evaluator_note", "")),
        justification_en=str(data.get("justification_en", "")),
        source=source,
        metadata=metadata,
    )


def load_record(path: Path) -> EvaluationRecord:
    """Load an evaluation record from UTF-8 JSON."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("evaluation file must contain one JSON object")
    return record_from_dict(data)


def result_to_dict(result: EvaluationResult) -> dict[str, Any]:
    """Convert a result to a stable JSON-compatible mapping."""

    return asdict(result)


def write_result(path: Path, result: EvaluationResult) -> None:
    """Write a result atomically enough for local evaluator workflows."""

    payload = json.dumps(result_to_dict(result), ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
