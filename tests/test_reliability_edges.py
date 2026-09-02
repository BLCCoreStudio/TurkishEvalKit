from __future__ import annotations

from pathlib import Path

import pytest

from turkishevalkit.calibration import EvaluatorSubmission
from turkishevalkit.models import EvaluationRecord, EvaluationType, Rating
from turkishevalkit.reliability import (
    PopulationReliabilitySpec,
    ReliabilityEstimate,
    ReliabilityTask,
    build_population_reliability_report,
    load_reliability_spec,
    reliability_spec_from_dict,
)
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC


def _text_submission(task_id: str, evaluator_id: str, score: int) -> EvaluatorSubmission:
    return EvaluatorSubmission(
        evaluator_id=evaluator_id,
        record=EvaluationRecord(
            task_id=task_id,
            evaluation_type=EvaluationType.TEXT,
            rubric_id=TEXT_QUALITY_RUBRIC.id,
            rubric_version=TEXT_QUALITY_RUBRIC.version,
            ratings=tuple(
                Rating(criterion.id, score)
                for criterion in TEXT_QUALITY_RUBRIC.criteria
            ),
            source={"prompt": task_id, "response": f"response-{task_id}"},
        ),
    )


def _task(task_id: str, scores: dict[str, int]) -> ReliabilityTask:
    return ReliabilityTask(
        tuple(
            _text_submission(task_id, evaluator_id, score)
            for evaluator_id, score in scores.items()
        )
    )


def test_reliability_task_rejects_single_submission() -> None:
    with pytest.raises(ValueError, match="at least two"):
        ReliabilityTask((_text_submission("t1", "a", 3),))


def test_reliability_estimate_invariants_are_enforced() -> None:
    assumptions = ("test assumption",)

    with pytest.raises(ValueError, match="require a value"):
        ReliabilityEstimate("metric", None, True, None, assumptions)

    with pytest.raises(ValueError, match="require a reason"):
        ReliabilityEstimate("metric", None, False, None, assumptions)


def test_equal_rater_counts_do_not_imply_fixed_evaluator_panel() -> None:
    spec = PopulationReliabilitySpec(
        minimum_task_count=3,
        tasks=(
            _task("t1", {"a": 1, "b": 2}),
            _task("t2", {"a": 2, "c": 3}),
            _task("t3", {"b": 3, "c": 4}),
        ),
    )

    report = build_population_reliability_report(spec, TEXT_QUALITY_RUBRIC)

    assert report.fixed_rater_count is True
    assert report.fixed_evaluator_panel is False
    assert report.aggregate_score_icc_a1.applicable is False
    assert report.aggregate_score_icc_a1.reason is not None
    assert "same evaluator identities" in report.aggregate_score_icc_a1.reason


def test_negative_icc_is_preserved_instead_of_clipped() -> None:
    spec = PopulationReliabilitySpec(
        minimum_task_count=4,
        tasks=(
            _task("t1", {"a": 1, "b": 5}),
            _task("t2", {"a": 5, "b": 1}),
            _task("t3", {"a": 1, "b": 5}),
            _task("t4", {"a": 5, "b": 1}),
        ),
    )

    report = build_population_reliability_report(spec, TEXT_QUALITY_RUBRIC)
    estimate = report.aggregate_score_icc_a1

    assert estimate.applicable is True
    assert estimate.value is not None
    assert estimate.value < 0


def test_reliability_spec_rejects_non_list_tasks() -> None:
    with pytest.raises(ValueError, match="tasks must be a list"):
        reliability_spec_from_dict({"minimum_task_count": 3, "tasks": {}})


def test_reliability_spec_rejects_non_object_task() -> None:
    with pytest.raises(ValueError, match="task must be an object"):
        reliability_spec_from_dict(
            {"minimum_task_count": 3, "tasks": [[], [], []]}
        )


def test_load_reliability_spec_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSON"):
        load_reliability_spec(path)


def test_load_reliability_spec_rejects_non_object_root(tmp_path: Path) -> None:
    path = tmp_path / "invalid-root.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="one JSON object"):
        load_reliability_spec(path)
