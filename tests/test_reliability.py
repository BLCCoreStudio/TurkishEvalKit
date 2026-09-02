from __future__ import annotations

from pathlib import Path

import pytest

from turkishevalkit.calibration import EvaluatorSubmission
from turkishevalkit.models import (
    EvaluationRecord,
    EvaluationType,
    PairwiseEvaluationRecord,
    PairwiseJudgment,
    Preference,
    Rating,
    Rubric,
    RubricCriterion,
)
from turkishevalkit.reliability import (
    PopulationReliabilitySpec,
    ReliabilityTask,
    build_population_reliability_report,
    load_reliability_spec,
    population_reliability_report_to_dict,
    reliability_spec_from_dict,
    write_population_reliability_report,
)

SCALAR_RUBRIC = Rubric(
    id="test-scalar",
    version="1.0",
    title="Test scalar",
    evaluation_type=EvaluationType.TEXT,
    criteria=(RubricCriterion("quality", "Quality", "Overall quality"),),
)

PAIRWISE_RUBRIC = Rubric(
    id="test-pairwise",
    version="1.0",
    title="Test pairwise",
    evaluation_type=EvaluationType.PAIRWISE,
    criteria=(RubricCriterion("quality", "Quality", "Which response is better"),),
)


def _scalar_task(task_id: str, values: dict[str, int]) -> ReliabilityTask:
    source = {"prompt": f"prompt for {task_id}"}
    return ReliabilityTask(
        submissions=tuple(
            EvaluatorSubmission(
                evaluator_id,
                EvaluationRecord(
                    task_id=task_id,
                    evaluation_type=EvaluationType.TEXT,
                    rubric_id=SCALAR_RUBRIC.id,
                    rubric_version=SCALAR_RUBRIC.version,
                    ratings=(Rating("quality", score),),
                    source=source,
                ),
            )
            for evaluator_id, score in values.items()
        )
    )


def _pairwise_task(
    task_id: str,
    values: dict[str, Preference],
    *,
    strength: int,
) -> ReliabilityTask:
    source = {
        "prompt": f"prompt for {task_id}",
        "response_a": "A",
        "response_b": "B",
    }
    return ReliabilityTask(
        submissions=tuple(
            EvaluatorSubmission(
                evaluator_id,
                PairwiseEvaluationRecord(
                    task_id=task_id,
                    rubric_id=PAIRWISE_RUBRIC.id,
                    rubric_version=PAIRWISE_RUBRIC.version,
                    judgments=(PairwiseJudgment("quality", preference),),
                    overall_preference=preference,
                    preference_strength=strength,
                    source=source,
                ),
            )
            for evaluator_id, preference in values.items()
        )
    )


def test_scalar_reliability_supports_variable_panels_with_ordinal_alpha() -> None:
    spec = PopulationReliabilitySpec(
        minimum_task_count=3,
        tasks=(
            _scalar_task("t1", {"a": 1, "b": 1}),
            _scalar_task("t2", {"a": 2, "b": 2, "c": 2}),
            _scalar_task("t3", {"b": 3, "c": 3}),
        ),
    )

    report = build_population_reliability_report(spec, SCALAR_RUBRIC)

    assert report.task_count == 3
    assert report.min_evaluators_per_task == 2
    assert report.max_evaluators_per_task == 3
    assert report.fixed_rater_count is False
    assert report.fixed_evaluator_panel is False
    criterion = report.criterion_reliability["quality"]
    assert criterion.krippendorff_alpha.applicable is True
    assert criterion.krippendorff_alpha.value == 1.0
    assert criterion.fleiss_kappa.applicable is False
    assert criterion.icc_a1.applicable is False
    assert report.aggregate_score_icc_a1.applicable is False


def test_scalar_fixed_panel_reports_icc_a1_absolute_agreement() -> None:
    spec = PopulationReliabilitySpec(
        minimum_task_count=3,
        tasks=(
            _scalar_task("t1", {"a": 1, "b": 2}),
            _scalar_task("t2", {"a": 2, "b": 3}),
            _scalar_task("t3", {"a": 3, "b": 4}),
            _scalar_task("t4", {"a": 4, "b": 5}),
        ),
    )

    report = build_population_reliability_report(spec, SCALAR_RUBRIC)

    assert report.fixed_rater_count is True
    assert report.fixed_evaluator_panel is True
    criterion_icc = report.criterion_reliability["quality"].icc_a1
    assert criterion_icc.applicable is True
    assert criterion_icc.value == 0.7692
    assert report.aggregate_score_icc_a1.applicable is True
    assert report.aggregate_score_icc_a1.value == 0.7692


def test_pairwise_reliability_reports_nominal_alpha_and_fleiss_kappa() -> None:
    spec = PopulationReliabilitySpec(
        minimum_task_count=3,
        tasks=(
            _pairwise_task(
                "t1",
                {"a": Preference.A, "b": Preference.A, "c": Preference.A},
                strength=1,
            ),
            _pairwise_task(
                "t2",
                {"a": Preference.A, "b": Preference.A, "c": Preference.B},
                strength=2,
            ),
            _pairwise_task(
                "t3",
                {"a": Preference.B, "b": Preference.B, "c": Preference.B},
                strength=3,
            ),
        ),
    )

    report = build_population_reliability_report(spec, PAIRWISE_RUBRIC)

    criterion = report.criterion_reliability["quality"]
    assert criterion.krippendorff_alpha.value == 0.6
    assert criterion.fleiss_kappa.value == 0.55
    assert criterion.icc_a1.applicable is False
    assert report.overall_preference_krippendorff_alpha.value == 0.6
    assert report.overall_preference_fleiss_kappa.value == 0.55
    assert report.preference_strength_krippendorff_alpha.value == 1.0
    assert report.aggregate_score_icc_a1.applicable is False


def test_fleiss_kappa_is_not_applied_to_unbalanced_pairwise_panels() -> None:
    spec = PopulationReliabilitySpec(
        minimum_task_count=3,
        tasks=(
            _pairwise_task("t1", {"a": Preference.A, "b": Preference.A}, strength=1),
            _pairwise_task(
                "t2",
                {"a": Preference.A, "b": Preference.B, "c": Preference.B},
                strength=2,
            ),
            _pairwise_task("t3", {"b": Preference.B, "c": Preference.B}, strength=3),
        ),
    )

    report = build_population_reliability_report(spec, PAIRWISE_RUBRIC)

    estimate = report.criterion_reliability["quality"].fleiss_kappa
    assert estimate.applicable is False
    assert estimate.reason is not None
    assert "same number" in estimate.reason
    assert report.criterion_reliability["quality"].krippendorff_alpha.applicable is True


def test_zero_expected_disagreement_is_explicitly_not_applicable() -> None:
    spec = PopulationReliabilitySpec(
        minimum_task_count=3,
        tasks=(
            _scalar_task("t1", {"a": 3, "b": 3}),
            _scalar_task("t2", {"a": 3, "b": 3}),
            _scalar_task("t3", {"a": 3, "b": 3}),
        ),
    )

    report = build_population_reliability_report(spec, SCALAR_RUBRIC)

    alpha = report.criterion_reliability["quality"].krippendorff_alpha
    assert alpha.applicable is False
    assert alpha.reason is not None
    assert "expected disagreement" in alpha.reason
    assert report.aggregate_score_icc_a1.applicable is False


def test_spec_requires_explicit_minimum_and_enough_tasks() -> None:
    tasks = (
        _scalar_task("t1", {"a": 1, "b": 1}),
        _scalar_task("t2", {"a": 2, "b": 2}),
    )

    with pytest.raises(ValueError, match="at least 3"):
        PopulationReliabilitySpec(minimum_task_count=2, tasks=tasks)

    with pytest.raises(ValueError, match="declared minimum"):
        PopulationReliabilitySpec(minimum_task_count=3, tasks=tasks)


def test_population_rejects_duplicate_task_ids() -> None:
    spec = PopulationReliabilitySpec(
        minimum_task_count=3,
        tasks=(
            _scalar_task("duplicate", {"a": 1, "b": 1}),
            _scalar_task("duplicate", {"a": 2, "b": 2}),
            _scalar_task("t3", {"a": 3, "b": 3}),
        ),
    )

    with pytest.raises(ValueError, match="task_id values must be unique"):
        build_population_reliability_report(spec, SCALAR_RUBRIC)


def test_reliability_spec_from_dict_and_load(tmp_path: Path) -> None:
    payload = {
        "minimum_task_count": 3,
        "tasks": [
            {
                "submissions": [
                    {
                        "evaluator_id": evaluator_id,
                        "evaluation": {
                            "task_id": task_id,
                            "evaluation_type": "text",
                            "rubric_id": "test-scalar",
                            "rubric_version": "1.0",
                            "ratings": [{"criterion_id": "quality", "score": score}],
                            "source": {"prompt": task_id},
                        },
                    }
                    for evaluator_id, score in (("a", 4), ("b", 4))
                ]
            }
            for task_id in ("t1", "t2", "t3")
        ],
    }

    parsed = reliability_spec_from_dict(payload)
    assert parsed.minimum_task_count == 3
    assert [task.task_id for task in parsed.tasks] == ["t1", "t2", "t3"]

    path = tmp_path / "reliability.json"
    import json

    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_reliability_spec(path)
    assert loaded == parsed


def test_reliability_report_serializes_and_writes(tmp_path: Path) -> None:
    spec = PopulationReliabilitySpec(
        minimum_task_count=3,
        tasks=(
            _scalar_task("t1", {"a": 1, "b": 2}),
            _scalar_task("t2", {"a": 2, "b": 3}),
            _scalar_task("t3", {"a": 3, "b": 4}),
        ),
    )
    report = build_population_reliability_report(spec, SCALAR_RUBRIC)

    payload = population_reliability_report_to_dict(report)
    assert payload["evaluation_type"] == "text"
    assert payload["criterion_reliability"]["quality"]["icc_a1"]["metric"] == (
        "icc_a1_absolute_agreement"
    )

    destination = tmp_path / "report.json"
    write_population_reliability_report(destination, report)
    rendered = destination.read_text(encoding="utf-8")
    assert '"task_count": 3' in rendered
    assert '"declared_minimum_task_count": 3' in rendered


def test_reliability_spec_rejects_invalid_minimum_type() -> None:
    with pytest.raises(ValueError, match="must be an integer"):
        reliability_spec_from_dict({"minimum_task_count": True, "tasks": []})
