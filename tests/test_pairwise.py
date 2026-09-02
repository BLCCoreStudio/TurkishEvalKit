from __future__ import annotations

import pytest

from turkishevalkit.models import (
    PairwiseEvaluationRecord,
    PairwiseJudgment,
    Preference,
)
from turkishevalkit.pairwise import evaluate_pairwise_submission
from turkishevalkit.rubrics import PAIRWISE_QUALITY_RUBRIC


def _record(*judgments: PairwiseJudgment) -> PairwiseEvaluationRecord:
    return PairwiseEvaluationRecord(
        task_id="pairwise-case-001",
        rubric_id=PAIRWISE_QUALITY_RUBRIC.id,
        rubric_version=PAIRWISE_QUALITY_RUBRIC.version,
        judgments=judgments,
        overall_preference=Preference.A,
        preference_strength=2,
    )


def test_all_a_preferences_score_positive_100() -> None:
    record = _record(
        *(PairwiseJudgment(criterion.id, Preference.A) for criterion in PAIRWISE_QUALITY_RUBRIC.criteria)
    )

    result = evaluate_pairwise_submission(record, PAIRWISE_QUALITY_RUBRIC)

    assert result.preference_score == 100.0
    assert result.preference_counts == {"a": 5, "b": 0, "tie": 0}
    assert result.overall_preference is Preference.A
    assert result.preference_strength == 2


def test_all_b_preferences_score_negative_100() -> None:
    record = PairwiseEvaluationRecord(
        task_id="pairwise-case-b",
        rubric_id=PAIRWISE_QUALITY_RUBRIC.id,
        rubric_version=PAIRWISE_QUALITY_RUBRIC.version,
        judgments=tuple(
            PairwiseJudgment(criterion.id, Preference.B)
            for criterion in PAIRWISE_QUALITY_RUBRIC.criteria
        ),
        overall_preference=Preference.B,
        preference_strength=3,
    )

    result = evaluate_pairwise_submission(record, PAIRWISE_QUALITY_RUBRIC)

    assert result.preference_score == -100.0
    assert result.preference_counts == {"a": 0, "b": 5, "tie": 0}


def test_mixed_preferences_compute_weighted_direction() -> None:
    preferences = [Preference.A, Preference.A, Preference.TIE, Preference.B, Preference.A]
    record = _record(
        *(
            PairwiseJudgment(criterion.id, preference)
            for criterion, preference in zip(PAIRWISE_QUALITY_RUBRIC.criteria, preferences, strict=True)
        )
    )

    result = evaluate_pairwise_submission(record, PAIRWISE_QUALITY_RUBRIC)

    assert result.preference_score == 40.0
    assert result.preference_counts == {"a": 3, "b": 1, "tie": 1}


def test_missing_pairwise_judgment_is_rejected() -> None:
    judgments = tuple(
        PairwiseJudgment(criterion.id, Preference.A)
        for criterion in PAIRWISE_QUALITY_RUBRIC.criteria[:-1]
    )

    with pytest.raises(ValueError, match="missing judgments"):
        evaluate_pairwise_submission(_record(*judgments), PAIRWISE_QUALITY_RUBRIC)


def test_duplicate_pairwise_judgment_is_rejected() -> None:
    judgments = [
        PairwiseJudgment(criterion.id, Preference.A)
        for criterion in PAIRWISE_QUALITY_RUBRIC.criteria
    ]
    judgments.append(PairwiseJudgment(PAIRWISE_QUALITY_RUBRIC.criteria[0].id, Preference.B))

    with pytest.raises(ValueError, match="only be judged once"):
        evaluate_pairwise_submission(_record(*judgments), PAIRWISE_QUALITY_RUBRIC)


def test_pairwise_record_validates_strength() -> None:
    judgments = tuple(
        PairwiseJudgment(criterion.id, Preference.TIE)
        for criterion in PAIRWISE_QUALITY_RUBRIC.criteria
    )

    with pytest.raises(ValueError, match="preference_strength must be between 1 and 3"):
        PairwiseEvaluationRecord(
            task_id="bad-strength",
            rubric_id=PAIRWISE_QUALITY_RUBRIC.id,
            rubric_version=PAIRWISE_QUALITY_RUBRIC.version,
            judgments=judgments,
            overall_preference=Preference.TIE,
            preference_strength=4,
        )
