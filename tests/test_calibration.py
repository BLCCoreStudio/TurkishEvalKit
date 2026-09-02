from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from turkishevalkit.calibration import (
    EvaluatorSubmission,
    build_calibration_report,
    calibration_report_to_dict,
    load_calibration_spec,
    write_calibration_report,
)
from turkishevalkit.models import EvaluationRecord, Rating
from turkishevalkit.rubrics import (
    AUDIO_QUALITY_RUBRIC,
    PAIRWISE_QUALITY_RUBRIC,
    TEXT_QUALITY_RUBRIC,
)


def test_text_calibration_reports_scalar_agreement() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-text.json"))

    report = build_calibration_report(submissions, TEXT_QUALITY_RUBRIC)

    assert report.evaluator_count == 2
    assert report.evaluator_pair_count == 1
    assert report.exact_criterion_agreement_rate == 0.6
    assert report.within_one_criterion_agreement_rate == 1.0
    assert report.mean_absolute_rating_difference == 0.4
    assert report.max_rating_difference == 1
    assert report.aggregate_scores == {"evaluator-a": 95.0, "evaluator-b": 85.0}
    assert report.aggregate_score_spread == 10.0
    assert report.criterion_agreement["fluency"].exact_agreement_rate == 1.0
    assert report.criterion_agreement["instruction_following"].mean_absolute_difference == 1.0
    assert report.audio_annotation_agreement is None


def test_pairwise_calibration_reports_preference_agreement() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-pairwise.json"))

    report = build_calibration_report(submissions, PAIRWISE_QUALITY_RUBRIC)

    assert report.exact_criterion_agreement_rate == 0.8
    assert report.overall_preference_agreement_rate == 1.0
    assert report.mean_absolute_preference_strength_difference == 1.0
    assert report.max_preference_strength_difference == 1
    assert report.aggregate_scores == {"evaluator-a": 40.0, "evaluator-b": 60.0}
    assert report.aggregate_score_spread == 20.0
    assert report.within_one_criterion_agreement_rate is None
    assert report.criterion_agreement["helpfulness"].observations == {"b": 1, "tie": 1}


def test_audio_calibration_matches_localized_annotations() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-audio.json"))

    report = build_calibration_report(submissions, AUDIO_QUALITY_RUBRIC)

    assert report.exact_criterion_agreement_rate == 0.6
    assert report.within_one_criterion_agreement_rate == 1.0
    assert report.aggregate_score_spread == 10.0
    assert report.audio_annotation_agreement is not None
    annotation = report.audio_annotation_agreement
    assert annotation.tolerance_ms == 250
    assert annotation.mean_pairwise_f1 == 0.8
    assert annotation.severity_agreement_rate == 1.0
    assert annotation.mean_temporal_similarity == 0.7294
    assert len(annotation.pair_agreements) == 1
    pair = annotation.pair_agreements[0]
    assert pair.matched_count == 2
    assert pair.annotation_count_a == 2
    assert pair.annotation_count_b == 3


def test_audio_annotation_tolerance_can_disable_nearby_point_match() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-audio.json"))

    report = build_calibration_report(
        submissions,
        AUDIO_QUALITY_RUBRIC,
        annotation_tolerance_ms=50,
    )

    assert report.audio_annotation_agreement is not None
    assert report.audio_annotation_agreement.pair_agreements[0].matched_count == 1
    assert report.audio_annotation_agreement.mean_pairwise_f1 == 0.4


def test_calibration_supports_more_than_two_evaluators() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-text.json"))
    second = submissions[1].record
    assert isinstance(second, EvaluationRecord)
    third_record = replace(
        second,
        ratings=tuple(
            Rating(rating.criterion_id, 5 if rating.criterion_id == "locale_fit" else rating.score)
            for rating in second.ratings
        ),
    )
    extended = (*submissions, EvaluatorSubmission("evaluator-c", third_record))

    report = build_calibration_report(extended, TEXT_QUALITY_RUBRIC)

    assert report.evaluator_count == 3
    assert report.evaluator_pair_count == 3
    assert set(report.aggregate_scores) == {"evaluator-a", "evaluator-b", "evaluator-c"}


def test_calibration_rejects_fewer_than_two_evaluators() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-text.json"))

    with pytest.raises(ValueError, match="at least two"):
        build_calibration_report((submissions[0],), TEXT_QUALITY_RUBRIC)


def test_calibration_rejects_duplicate_evaluator_ids() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-text.json"))
    duplicate = (
        submissions[0],
        EvaluatorSubmission(submissions[0].evaluator_id, submissions[1].record),
    )

    with pytest.raises(ValueError, match="unique"):
        build_calibration_report(duplicate, TEXT_QUALITY_RUBRIC)


def test_calibration_rejects_mixed_task_ids() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-text.json"))
    second = submissions[1].record
    assert isinstance(second, EvaluationRecord)
    mixed = (
        submissions[0],
        EvaluatorSubmission("evaluator-b", replace(second, task_id="different-task")),
    )

    with pytest.raises(ValueError, match="same task_id"):
        build_calibration_report(mixed, TEXT_QUALITY_RUBRIC)


def test_calibration_rejects_source_mismatch() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-text.json"))
    second = submissions[1].record
    assert isinstance(second, EvaluationRecord)
    mixed = (
        submissions[0],
        EvaluatorSubmission("evaluator-b", replace(second, source={"prompt": "different"})),
    )

    with pytest.raises(ValueError, match="same source stimulus"):
        build_calibration_report(mixed, TEXT_QUALITY_RUBRIC)


def test_calibration_rejects_negative_audio_tolerance() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-audio.json"))

    with pytest.raises(ValueError, match="non-negative"):
        build_calibration_report(
            submissions,
            AUDIO_QUALITY_RUBRIC,
            annotation_tolerance_ms=-1,
        )


def test_calibration_report_serializes_and_writes(tmp_path: Path) -> None:
    submissions = load_calibration_spec(Path("examples/calibration-text.json"))
    report = build_calibration_report(submissions, TEXT_QUALITY_RUBRIC)

    payload = calibration_report_to_dict(report)
    assert payload["evaluation_type"] == "text"
    assert payload["criterion_agreement"]["fluency"]["observations"] == {"5": 2}

    destination = tmp_path / "calibration.json"
    write_calibration_report(destination, report)
    rendered = destination.read_text(encoding="utf-8")
    assert '"evaluator_count": 2' in rendered
    assert '"exact_criterion_agreement_rate": 0.6' in rendered


def test_load_calibration_spec_rejects_invalid_shape(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"submissions": [{"evaluator_id": "a", "evaluation": []}]}', encoding="utf-8")

    with pytest.raises(ValueError, match="evaluation must be an object"):
        load_calibration_spec(path)
