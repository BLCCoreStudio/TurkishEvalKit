"""Portable JSON serialization helpers for evaluation records, results, and workflows."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypeAlias

from .evaluation import EvaluationResult
from .models import (
    EvaluationRecord,
    EvaluationType,
    PairwiseEvaluationRecord,
    PairwiseJudgment,
    Preference,
    Rating,
)
from .pairwise import PairwiseEvaluationResult
from .workflow import (
    ActorRole,
    AdjudicationOutcome,
    EvaluationSession,
    EvaluationWorkflow,
    ReviewOutcome,
    WorkflowEvent,
    WorkflowEventKind,
    WorkflowState,
)

SubmissionRecord: TypeAlias = EvaluationRecord | PairwiseEvaluationRecord
SubmissionResult: TypeAlias = EvaluationResult | PairwiseEvaluationResult


def _evaluation_type(data: dict[str, Any]) -> EvaluationType:
    try:
        return EvaluationType(str(data.get("evaluation_type", "")))
    except ValueError as exc:
        supported = ", ".join(item.value for item in EvaluationType)
        raise ValueError(f"evaluation_type must be one of: {supported}") from exc


def _source_and_metadata(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = data.get("source", {})
    metadata = data.get("metadata", {})
    if not isinstance(source, dict) or not isinstance(metadata, dict):
        raise ValueError("source and metadata must be objects")
    return source, metadata


def _preference(value: Any, field_name: str) -> Preference:
    try:
        return Preference(str(value))
    except ValueError as exc:
        supported = ", ".join(item.value for item in Preference)
        raise ValueError(f"{field_name} must be one of: {supported}") from exc


def _enum_value(enum_type: type[Any], value: Any, field_name: str) -> Any:
    try:
        return enum_type(str(value))
    except ValueError as exc:
        supported = ", ".join(str(item.value) for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {supported}") from exc


def record_from_dict(data: dict[str, Any]) -> SubmissionRecord:
    """Build a validated scalar or pairwise record from a JSON-compatible mapping."""

    evaluation_type = _evaluation_type(data)
    source, metadata = _source_and_metadata(data)

    if evaluation_type is EvaluationType.PAIRWISE:
        raw_judgments = data.get("judgments")
        if not isinstance(raw_judgments, list):
            raise ValueError("judgments must be a list")

        judgments: list[PairwiseJudgment] = []
        for item in raw_judgments:
            if not isinstance(item, dict):
                raise ValueError("each judgment must be an object")
            judgments.append(
                PairwiseJudgment(
                    criterion_id=str(item.get("criterion_id", "")),
                    preference=_preference(item.get("preference", ""), "preference"),
                    note=str(item.get("note", "")),
                )
            )

        return PairwiseEvaluationRecord(
            task_id=str(data.get("task_id", "")),
            rubric_id=str(data.get("rubric_id", "")),
            rubric_version=str(data.get("rubric_version", "")),
            judgments=tuple(judgments),
            overall_preference=_preference(
                data.get("overall_preference", ""), "overall_preference"
            ),
            preference_strength=int(data.get("preference_strength", 0)),
            evaluator_note=str(data.get("evaluator_note", "")),
            justification_en=str(data.get("justification_en", "")),
            source=source,
            metadata=metadata,
        )

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


def load_record(path: Path) -> SubmissionRecord:
    """Load an evaluation record from UTF-8 JSON."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("evaluation file must contain one JSON object")
    return record_from_dict(data)


def result_to_dict(result: SubmissionResult) -> dict[str, Any]:
    """Convert a result to a stable JSON-compatible mapping."""

    return asdict(result)


def write_result(path: Path, result: SubmissionResult) -> None:
    """Write a result atomically enough for local evaluator workflows."""

    payload = json.dumps(result_to_dict(result), ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def workflow_to_dict(workflow: EvaluationWorkflow) -> dict[str, Any]:
    """Convert a workflow snapshot and event chain into portable JSON data."""

    return asdict(workflow)


def workflow_from_dict(data: dict[str, Any]) -> EvaluationWorkflow:
    """Reconstruct and validate a persisted evaluator workflow snapshot."""

    raw_session = data.get("session")
    raw_events = data.get("events")
    if not isinstance(raw_session, dict):
        raise ValueError("workflow session must be an object")
    if not isinstance(raw_events, list):
        raise ValueError("workflow events must be a list")

    session = EvaluationSession(
        session_id=str(raw_session.get("session_id", "")),
        evaluator_id=str(raw_session.get("evaluator_id", "")),
        started_at=str(raw_session.get("started_at", "")),
    )

    events: list[WorkflowEvent] = []
    for item in raw_events:
        if not isinstance(item, dict):
            raise ValueError("each workflow event must be an object")

        raw_from_state = item.get("from_state")
        from_state = (
            None
            if raw_from_state is None
            else _enum_value(WorkflowState, raw_from_state, "from_state")
        )
        raw_review_outcome = item.get("review_outcome")
        review_outcome = (
            None
            if raw_review_outcome is None
            else _enum_value(ReviewOutcome, raw_review_outcome, "review_outcome")
        )
        raw_adjudication_outcome = item.get("adjudication_outcome")
        adjudication_outcome = (
            None
            if raw_adjudication_outcome is None
            else _enum_value(
                AdjudicationOutcome,
                raw_adjudication_outcome,
                "adjudication_outcome",
            )
        )

        events.append(
            WorkflowEvent(
                sequence=int(item.get("sequence", 0)),
                event_id=str(item.get("event_id", "")),
                kind=_enum_value(WorkflowEventKind, item.get("kind", ""), "kind"),
                from_state=from_state,
                to_state=_enum_value(WorkflowState, item.get("to_state", ""), "to_state"),
                actor_id=str(item.get("actor_id", "")),
                actor_role=_enum_value(ActorRole, item.get("actor_role", ""), "actor_role"),
                occurred_at=str(item.get("occurred_at", "")),
                note=str(item.get("note", "")),
                review_outcome=review_outcome,
                adjudication_outcome=adjudication_outcome,
            )
        )

    return EvaluationWorkflow(
        artifact_id=str(data.get("artifact_id", "")),
        task_id=str(data.get("task_id", "")),
        session=session,
        state=_enum_value(WorkflowState, data.get("state", ""), "state"),
        events=tuple(events),
    )
