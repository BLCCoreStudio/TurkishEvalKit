from __future__ import annotations

import pytest

from turkishevalkit.models import (
    EvaluationRecord,
    EvaluationType,
    Rating,
    Rubric,
    RubricCriterion,
)


def test_rating_requires_criterion_id() -> None:
    with pytest.raises(ValueError, match="criterion_id must not be empty"):
        Rating("   ", 3)


def test_rubric_criterion_validates_identity_and_weight() -> None:
    with pytest.raises(ValueError, match="criterion id must not be empty"):
        RubricCriterion("", "Fluency", "Description")

    with pytest.raises(ValueError, match="criterion label must not be empty"):
        RubricCriterion("fluency", " ", "Description")

    with pytest.raises(ValueError, match="criterion weight must be positive"):
        RubricCriterion("fluency", "Fluency", "Description", weight=0)


def test_rubric_requires_identity_criteria_and_unique_ids() -> None:
    criterion = RubricCriterion("fluency", "Fluency", "Description")

    with pytest.raises(ValueError, match="rubric id, version, and title must not be empty"):
        Rubric("", "1.0", "Title", (criterion,))

    with pytest.raises(ValueError, match="at least one criterion"):
        Rubric("rubric", "1.0", "Title", ())

    duplicate = RubricCriterion("fluency", "Fluency duplicate", "Description")
    with pytest.raises(ValueError, match="criterion ids must be unique"):
        Rubric("rubric", "1.0", "Title", (criterion, duplicate))


def test_evaluation_record_validates_required_fields() -> None:
    rating = Rating("fluency", 4)

    with pytest.raises(ValueError, match="task_id must not be empty"):
        EvaluationRecord("", EvaluationType.TEXT, "rubric", "1.0", (rating,))

    with pytest.raises(ValueError, match="rubric id and version must not be empty"):
        EvaluationRecord("task", EvaluationType.TEXT, "", "1.0", (rating,))

    with pytest.raises(ValueError, match="at least one rating"):
        EvaluationRecord("task", EvaluationType.TEXT, "rubric", "1.0", ())
