from __future__ import annotations

from pathlib import Path

import pytest

from turkishevalkit.calibration import load_calibration_spec
from turkishevalkit.disagreement import build_disagreement_report, disagreement_report_to_dict
from turkishevalkit.rubrics import (
    AUDIO_QUALITY_RUBRIC,
    PAIRWISE_QUALITY_RUBRIC,
    TEXT_QUALITY_RUBRIC,
)


def test_text_disagreement_exposes_rating_pairs_and_notes() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-text.json"))

    report = build_disagreement_report(submissions, TEXT_QUALITY_RUBRIC)

    assert report.task_id == "text-calibration-001"
    assert report.criterion_count == 5
    assert report.disputed_criterion_count == 2
    assert report.disputed_criterion_pair_count == 2
    assert [item.criterion_id for item in report.criteria[:2]] == [
        "instruction_following",
        "locale_fit",
    ]

    instruction = report.criteria[0]
    assert instruction.exact_agreement_rate == 0.0
    assert instruction.disagreement_pair_count == 1
    assert instruction.total_pair_count == 1
    assert [(item.evaluator_id, item.value) for item in instruction.observations] == [
        ("evaluator-a", "5"),
        ("evaluator-b", "4"),
    ]
    pair = instruction.pair_disagreements[0]
    assert pair.gap == 1
    assert pair.note_a == "İstenen kapsamı doğrudan karşılıyor."
    assert pair.note_b == "İsteği karşılıyor; biraz daha kısa olabilirdi."

    unanimous = next(item for item in report.criteria if item.criterion_id == "fluency")
    assert unanimous.disagreement_pair_count == 0
    assert unanimous.exact_agreement_rate == 1.0


def test_pairwise_disagreement_keeps_criterion_and_holistic_differences_separate() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-pairwise.json"))

    report = build_disagreement_report(submissions, PAIRWISE_QUALITY_RUBRIC)

    assert report.disputed_criterion_count == 1
    assert report.disputed_criterion_pair_count == 1
    helpfulness = report.criteria[0]
    assert helpfulness.criterion_id == "helpfulness"
    pair = helpfulness.pair_disagreements[0]
    assert (pair.value_a, pair.value_b, pair.gap) == ("b", "tie", 1)

    assert len(report.overall_preference_differences) == 1
    overall = report.overall_preference_differences[0]
    assert overall.preference_a == "a"
    assert overall.preference_b == "a"
    assert overall.preference_changed is False
    assert overall.strength_a == 2
    assert overall.strength_b == 1
    assert overall.strength_gap == 1
    assert report.audio_pair_disagreements == ()


def test_audio_disagreement_exposes_unmatched_and_temporal_evidence() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-audio.json"))

    report = build_disagreement_report(
        submissions,
        AUDIO_QUALITY_RUBRIC,
        annotation_tolerance_ms=250,
    )

    assert report.disputed_criterion_count == 2
    assert [item.criterion_id for item in report.criteria[:2]] == [
        "pronunciation",
        "intonation",
    ]
    assert len(report.audio_pair_disagreements) == 1
    pair = report.audio_pair_disagreements[0]
    assert pair.evaluator_a == "evaluator-a"
    assert pair.evaluator_b == "evaluator-b"
    assert pair.unmatched_a == ()
    assert len(pair.unmatched_b) == 1
    assert pair.unmatched_b[0].category == "noise"
    assert pair.unmatched_b[0].start_ms == 7000
    assert "gürültü" in pair.unmatched_b[0].note

    assert len(pair.matched_variances) == 2
    by_category = {item.left.category: item for item in pair.matched_variances}
    assert by_category["emphasis"].severity_match is True
    assert by_category["emphasis"].temporal_similarity == 0.8571
    assert by_category["intonation"].severity_match is True
    assert by_category["intonation"].temporal_similarity == 0.6016


def test_audio_tolerance_changes_unmatched_evidence_consistently() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-audio.json"))

    report = build_disagreement_report(
        submissions,
        AUDIO_QUALITY_RUBRIC,
        annotation_tolerance_ms=50,
    )

    pair = report.audio_pair_disagreements[0]
    assert {item.category for item in pair.unmatched_a} == {"intonation"}
    assert {item.category for item in pair.unmatched_b} == {"intonation", "noise"}
    assert len(pair.matched_variances) == 1
    assert pair.matched_variances[0].left.category == "emphasis"


def test_disagreement_report_serializes_to_json_native_shape() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-text.json"))
    report = build_disagreement_report(submissions, TEXT_QUALITY_RUBRIC)

    payload = disagreement_report_to_dict(report)

    assert payload["evaluation_type"] == "text"
    assert payload["disputed_criterion_count"] == 2
    assert payload["criteria"][0]["pair_disagreements"][0]["gap"] == 1


def test_disagreement_report_reuses_calibration_validation() -> None:
    submissions = load_calibration_spec(Path("examples/calibration-audio.json"))

    with pytest.raises(ValueError, match="non-negative"):
        build_disagreement_report(
            submissions,
            AUDIO_QUALITY_RUBRIC,
            annotation_tolerance_ms=-1,
        )
