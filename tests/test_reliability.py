from __future__ import annotations

import json
from pathlib import Path

import pytest

from turkishevalkit.models import (
    EvaluationRecord,
    EvaluationType,
    PairwiseEvaluationRecord,
    PairwiseJudgment,
    Preference,
    Rating,
)
from turkishevalkit.reliability import (
    ReliabilityObservation,
    build_reliability_study_report,
    load_reliability_study_spec,
    reliability_report_to_dict,
)
from turkishevalkit.rubrics import PAIRWISE_QUALITY_RUBRIC, TEXT_QUALITY_RUBRIC


def _text_record(task_id: str, score: int, *, source_key: str | None = None) -> EvaluationRecord:
    return EvaluationRecord(
        task_id=task_id,
        evaluation_type=EvaluationType.TEXT,
        rubric_id=TEXT_QUALITY_RUBRIC.id,
        rubric_version=TEXT_QUALITY_RUBRIC.version,
        ratings=tuple(
            Rating(criterion_id=criterion.id, score=score, note=f"evidence {score}")
            for criterion in TEXT_QUALITY_RUBRIC.criteria
        ),
        evaluator_note="study fixture",
        source={
            "prompt": f"prompt-{source_key or task_id}",
            "response": f"response-{source_key or task_id}",
        },
    )


def _pairwise_record(task_id: str, preference: Preference) -> PairwiseEvaluationRecord:
    return PairwiseEvaluationRecord(
        task_id=task_id,
        rubric_id=PAIRWISE_QUALITY_RUBRIC.id,
        rubric_version=PAIRWISE_QUALITY_RUBRIC.version,
        judgments=tuple(
            PairwiseJudgment(
                criterion_id=criterion.id,
                preference=preference,
                note="pairwise evidence",
            )
            for criterion in PAIRWISE_QUALITY_RUBRIC.criteria
        ),
        overall_preference=preference,
        preference_strength=2,
        source={
            "prompt": f"prompt-{task_id}",
            "response_a": f"a-{task_id}",
            "response_b": f"b-{task_id}",
        },
    )


def _observation(evaluator: str, record: EvaluationRecord | PairwiseEvaluationRecord):
    return ReliabilityObservation(evaluator_id=evaluator, record=record)


def _eligibility(report, metric_id: str):
    return next(item for item in report.metric_eligibility if item.metric_id == metric_id)


def test_balanced_two_evaluator_scalar_panel_is_structurally_ready() -> None:
    observations = tuple(
        _observation(evaluator, _text_record(task_id, score))
        for task_id, scores in (
            ("task-01", (5, 4)),
            ("task-02", (4, 4)),
            ("task-03", (3, 2)),
        )
        for evaluator, score in zip(("eval-a", "eval-b"), scores, strict=True)
    )

    report = build_reliability_study_report(
        "balanced-study",
        observations,
        TEXT_QUALITY_RUBRIC,
    )

    assert report.task_count == 3
    assert report.comparable_task_count == 3
    assert report.evaluator_count == 2
    assert report.observation_count == 6
    assert report.expected_panel_cells == 6
    assert report.missing_panel_cells == 0
    assert report.coverage_rate == 1.0
    assert report.balanced_panel is True
    assert report.min_raters_per_task == 2
    assert report.max_raters_per_task == 2
    assert report.warnings == ()
    assert all(item.structurally_eligible for item in report.metric_eligibility)

    cohen = _eligibility(report, "cohen_kappa")
    assert "weighted-kappa" in cohen.required_decisions[0]
    icc = _eligibility(report, "icc")
    assert "select the ICC model" in icc.required_decisions[0]


def test_unbalanced_panel_exposes_missingness_without_hiding_usable_tasks() -> None:
    observations = (
        _observation("eval-a", _text_record("task-01", 5)),
        _observation("eval-b", _text_record("task-01", 4)),
        _observation("eval-c", _text_record("task-01", 4)),
        _observation("eval-a", _text_record("task-02", 3)),
        _observation("eval-b", _text_record("task-02", 3)),
        _observation("eval-a", _text_record("task-03", 2)),
    )

    report = build_reliability_study_report(
        "unbalanced-study",
        observations,
        TEXT_QUALITY_RUBRIC,
    )

    assert report.task_count == 3
    assert report.comparable_task_count == 2
    assert report.evaluator_count == 3
    assert report.expected_panel_cells == 9
    assert report.missing_panel_cells == 3
    assert report.coverage_rate == pytest.approx(2 / 3)
    assert report.balanced_panel is False
    assert report.min_raters_per_task == 1
    assert report.max_raters_per_task == 3
    assert report.task_coverage[-1].task_id == "task-03"
    assert report.task_coverage[-1].comparable is False
    assert any("single-rater tasks" in warning for warning in report.warnings)
    assert any("unbalanced" in warning for warning in report.warnings)
    assert any("vary across tasks" in warning for warning in report.warnings)

    assert _eligibility(report, "cohen_kappa").structurally_eligible is False
    assert _eligibility(report, "fleiss_kappa").structurally_eligible is False
    assert _eligibility(report, "krippendorff_alpha").structurally_eligible is True
    assert _eligibility(report, "icc").structurally_eligible is False


def test_pairwise_panel_blocks_icc_but_preserves_categorical_candidates() -> None:
    observations = tuple(
        _observation(evaluator, _pairwise_record(task_id, preference))
        for task_id, preferences in (
            ("pair-01", (Preference.A, Preference.TIE)),
            ("pair-02", (Preference.B, Preference.B)),
        )
        for evaluator, preference in zip(("eval-a", "eval-b"), preferences, strict=True)
    )

    report = build_reliability_study_report(
        "pairwise-study",
        observations,
        PAIRWISE_QUALITY_RUBRIC,
    )

    assert report.evaluation_type is EvaluationType.PAIRWISE
    assert _eligibility(report, "cohen_kappa").structurally_eligible is True
    assert _eligibility(report, "fleiss_kappa").structurally_eligible is True
    assert _eligibility(report, "krippendorff_alpha").structurally_eligible is True
    icc = _eligibility(report, "icc")
    assert icc.structurally_eligible is False
    assert "A/Tie/B" in icc.blocked_reasons[0]


def test_duplicate_evaluator_task_is_rejected() -> None:
    observations = (
        _observation("eval-a", _text_record("task-01", 5)),
        _observation("eval-a", _text_record("task-01", 4)),
        _observation("eval-b", _text_record("task-02", 4)),
    )

    with pytest.raises(ValueError, match="same evaluator/task"):
        build_reliability_study_report("duplicate", observations, TEXT_QUALITY_RUBRIC)


def test_same_task_id_cannot_hide_different_source_stimuli() -> None:
    observations = (
        _observation("eval-a", _text_record("task-01", 5, source_key="a")),
        _observation("eval-b", _text_record("task-01", 4, source_key="b")),
        _observation("eval-a", _text_record("task-02", 4)),
        _observation("eval-b", _text_record("task-02", 4)),
    )

    with pytest.raises(ValueError, match="multiple source stimuli"):
        build_reliability_study_report("source-mismatch", observations, TEXT_QUALITY_RUBRIC)


def test_duplicate_stimulus_under_multiple_task_ids_is_visible_warning() -> None:
    observations = (
        _observation("eval-a", _text_record("task-01", 5, source_key="same")),
        _observation("eval-b", _text_record("task-01", 4, source_key="same")),
        _observation("eval-a", _text_record("task-02", 4, source_key="same")),
        _observation("eval-b", _text_record("task-02", 4, source_key="same")),
    )

    report = build_reliability_study_report(
        "duplicate-stimulus",
        observations,
        TEXT_QUALITY_RUBRIC,
    )

    assert report.balanced_panel is True
    assert len(report.warnings) == 1
    assert "identical source stimulus" in report.warnings[0]
    assert "task-01" in report.warnings[0]
    assert "task-02" in report.warnings[0]


def test_study_requires_multiple_tasks_and_evaluators() -> None:
    with pytest.raises(ValueError, match="two distinct task_id"):
        build_reliability_study_report(
            "one-task",
            (
                _observation("eval-a", _text_record("task-01", 5)),
                _observation("eval-b", _text_record("task-01", 4)),
            ),
            TEXT_QUALITY_RUBRIC,
        )

    with pytest.raises(ValueError, match="two unique evaluators"):
        build_reliability_study_report(
            "one-evaluator",
            (
                _observation("eval-a", _text_record("task-01", 5)),
                _observation("eval-a", _text_record("task-02", 4)),
            ),
            TEXT_QUALITY_RUBRIC,
        )


def test_report_serialization_is_json_native() -> None:
    report = build_reliability_study_report(
        "serialize-study",
        (
            _observation("eval-a", _text_record("task-01", 5)),
            _observation("eval-b", _text_record("task-01", 4)),
            _observation("eval-a", _text_record("task-02", 4)),
            _observation("eval-b", _text_record("task-02", 4)),
        ),
        TEXT_QUALITY_RUBRIC,
    )

    payload = reliability_report_to_dict(report)
    assert payload["evaluation_type"] == "text"
    assert payload["balanced_panel"] is True
    assert payload["metric_eligibility"][0]["metric_id"] == "cohen_kappa"


def test_load_reliability_study_spec_roundtrips_records(tmp_path: Path) -> None:
    record_a = _text_record("task-01", 5)
    record_b = _text_record("task-02", 4)
    from turkishevalkit.serialization import record_to_dict

    path = tmp_path / "study.json"
    path.write_text(
        json.dumps(
            {
                "study_id": "spec-study",
                "observations": [
                    {
                        "evaluator_id": "eval-a",
                        "artifact_id": "a.json",
                        "evaluation": record_to_dict(record_a),
                    },
                    {
                        "evaluator_id": "eval-b",
                        "evaluation": record_to_dict(record_b),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    spec = load_reliability_study_spec(path)
    assert spec.study_id == "spec-study"
    assert len(spec.observations) == 2
    assert spec.observations[0].artifact_id == "a.json"
    assert spec.observations[0].record.task_id == "task-01"


def test_load_reliability_study_spec_rejects_invalid_shapes(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="one JSON object"):
        load_reliability_study_spec(path)

    path.write_text(json.dumps({"study_id": "x", "observations": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty observations"):
        load_reliability_study_spec(path)
