"""Validation and scoring for human-authored evaluation records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .models import EvaluationRecord, Rubric


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Validated aggregate result for one evaluation record."""

    task_id: str
    rubric_id: str
    rubric_version: str
    weighted_score: float
    normalized_score: float
    criterion_scores: dict[str, int]
    payload: dict[str, Any]


def evaluate_submission(record: EvaluationRecord, rubric: Rubric) -> EvaluationResult:
    """Validate a record against a rubric and calculate deterministic aggregate scores."""

    if record.rubric_id != rubric.id or record.rubric_version != rubric.version:
        raise ValueError("record rubric id/version does not match the supplied rubric")

    criterion_by_id = {criterion.id: criterion for criterion in rubric.criteria}
    rating_by_id = {rating.criterion_id: rating for rating in record.ratings}

    if len(rating_by_id) != len(record.ratings):
        raise ValueError("a criterion may only be rated once")

    expected = set(criterion_by_id)
    actual = set(rating_by_id)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        problems: list[str] = []
        if missing:
            problems.append(f"missing ratings: {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown ratings: {', '.join(unknown)}")
        raise ValueError("; ".join(problems))

    total_weight = sum(criterion.weight for criterion in rubric.criteria)
    weighted_sum = sum(
        rating_by_id[criterion.id].score * criterion.weight for criterion in rubric.criteria
    )
    weighted_score = weighted_sum / total_weight
    normalized_score = ((weighted_score - 1.0) / 4.0) * 100.0

    return EvaluationResult(
        task_id=record.task_id,
        rubric_id=rubric.id,
        rubric_version=rubric.version,
        weighted_score=round(weighted_score, 3),
        normalized_score=round(normalized_score, 2),
        criterion_scores={criterion.id: rating_by_id[criterion.id].score for criterion in rubric.criteria},
        payload=asdict(record),
    )
