from __future__ import annotations

import pytest

from turkishevalkit.evaluation import evaluate_submission
from turkishevalkit.models import EvaluationRecord, EvaluationType, Rating
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC


def _record(*ratings: Rating) -> EvaluationRecord:
    return EvaluationRecord(
        task_id="case-001",
        evaluation_type=EvaluationType.TEXT,
        rubric_id=TEXT_QUALITY_RUBRIC.id,
        rubric_version=TEXT_QUALITY_RUBRIC.version,
        ratings=ratings,
    )


def test_perfect_score_normalizes_to_100() -> None:
    record = _record(
        *(Rating(criterion.id, 5) for criterion in TEXT_QUALITY_RUBRIC.criteria)
    )

    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)

    assert result.weighted_score == 5.0
    assert result.normalized_score == 100.0


def test_lowest_score_normalizes_to_zero() -> None:
    record = _record(
        *(Rating(criterion.id, 1) for criterion in TEXT_QUALITY_RUBRIC.criteria)
    )

    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)

    assert result.weighted_score == 1.0
    assert result.normalized_score == 0.0


def test_missing_rating_is_rejected() -> None:
    ratings = tuple(Rating(criterion.id, 4) for criterion in TEXT_QUALITY_RUBRIC.criteria[:-1])

    with pytest.raises(ValueError, match="missing ratings"):
        evaluate_submission(_record(*ratings), TEXT_QUALITY_RUBRIC)


def test_duplicate_rating_is_rejected() -> None:
    ratings = [Rating(criterion.id, 4) for criterion in TEXT_QUALITY_RUBRIC.criteria]
    ratings.append(Rating(TEXT_QUALITY_RUBRIC.criteria[0].id, 5))

    with pytest.raises(ValueError, match="only be rated once"):
        evaluate_submission(_record(*ratings), TEXT_QUALITY_RUBRIC)


def test_rating_bounds_are_enforced() -> None:
    with pytest.raises(ValueError, match="between 1 and 5"):
        Rating("fluency", 6)
