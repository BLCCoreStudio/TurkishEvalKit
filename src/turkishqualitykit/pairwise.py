"""Validation and scoring for pairwise human-preference evaluations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .models import PairwiseEvaluationRecord, Preference, Rubric


@dataclass(frozen=True, slots=True)
class PairwiseEvaluationResult:
    """Validated aggregate result for one A/B preference evaluation."""

    task_id: str
    rubric_id: str
    rubric_version: str
    overall_preference: Preference
    preference_strength: int
    preference_score: float
    criterion_preferences: dict[str, str]
    preference_counts: dict[str, int]
    payload: dict[str, Any]


def evaluate_pairwise_submission(
    record: PairwiseEvaluationRecord,
    rubric: Rubric,
) -> PairwiseEvaluationResult:
    """Validate a pairwise record and calculate a deterministic A↔B preference score."""

    if record.rubric_id != rubric.id or record.rubric_version != rubric.version:
        raise ValueError("record rubric id/version does not match the supplied rubric")
    if record.evaluation_type is not rubric.evaluation_type:
        raise ValueError("record evaluation_type does not match the supplied rubric")

    criterion_by_id = {criterion.id: criterion for criterion in rubric.criteria}
    judgment_by_id = {judgment.criterion_id: judgment for judgment in record.judgments}

    if len(judgment_by_id) != len(record.judgments):
        raise ValueError("a criterion may only be judged once")

    expected = set(criterion_by_id)
    actual = set(judgment_by_id)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        problems: list[str] = []
        if missing:
            problems.append(f"missing judgments: {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown judgments: {', '.join(unknown)}")
        raise ValueError("; ".join(problems))

    preference_value = {
        Preference.A: 1.0,
        Preference.B: -1.0,
        Preference.TIE: 0.0,
    }
    total_weight = sum(criterion.weight for criterion in rubric.criteria)
    weighted_sum = sum(
        preference_value[judgment_by_id[criterion.id].preference] * criterion.weight
        for criterion in rubric.criteria
    )
    preference_score = (weighted_sum / total_weight) * 100.0

    counts = {
        Preference.A.value: 0,
        Preference.B.value: 0,
        Preference.TIE.value: 0,
    }
    for judgment in record.judgments:
        counts[judgment.preference.value] += 1

    return PairwiseEvaluationResult(
        task_id=record.task_id,
        rubric_id=rubric.id,
        rubric_version=rubric.version,
        overall_preference=record.overall_preference,
        preference_strength=record.preference_strength,
        preference_score=round(preference_score, 2),
        criterion_preferences={
            criterion.id: judgment_by_id[criterion.id].preference.value
            for criterion in rubric.criteria
        },
        preference_counts=counts,
        payload=asdict(record),
    )
