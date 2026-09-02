from __future__ import annotations

import pytest

from turkishevalkit.models import (
    AudioAnnotation,
    AudioIssueCategory,
    AudioIssueSeverity,
    EvaluationRecord,
    EvaluationType,
    Rating,
    Rubric,
    RubricCriterion,
)


def _annotation() -> AudioAnnotation:
    return AudioAnnotation(
        start_ms=1200,
        end_ms=1800,
        category=AudioIssueCategory.PRONUNCIATION,
        severity=AudioIssueSeverity.MAJOR,
        note="The vowel duration is clearly unnatural for the spoken phrase.",
    )


def test_rating_requires_criterion_id() -> None:
    with pytest.raises(ValueError, match="criterion_id must not be empty"):
        Rating("   ", 3)


def test_audio_annotation_accepts_ranges_and_point_markers() -> None:
    ranged = _annotation()
    point = AudioAnnotation(
        start_ms=5100,
        end_ms=5100,
        category=AudioIssueCategory.INTONATION,
        severity=AudioIssueSeverity.MINOR,
        note="Sentence-final intonation becomes flat at this point.",
    )

    assert ranged.end_ms > ranged.start_ms
    assert point.start_ms == point.end_ms


def test_audio_annotation_rejects_invalid_timestamps_and_empty_note() -> None:
    with pytest.raises(ValueError, match="timestamps must be non-negative"):
        AudioAnnotation(
            start_ms=-1,
            end_ms=20,
            category=AudioIssueCategory.NOISE,
            severity=AudioIssueSeverity.MINOR,
            note="Background noise.",
        )
    with pytest.raises(ValueError, match="end_ms must be greater than or equal"):
        AudioAnnotation(
            start_ms=2000,
            end_ms=1000,
            category=AudioIssueCategory.PACE,
            severity=AudioIssueSeverity.MAJOR,
            note="Pace changes abruptly.",
        )
    with pytest.raises(ValueError, match="note must not be empty"):
        AudioAnnotation(
            start_ms=100,
            end_ms=200,
            category=AudioIssueCategory.OTHER,
            severity=AudioIssueSeverity.MINOR,
            note="   ",
        )


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
        Rubric("", "1.0", "Title", EvaluationType.TEXT, (criterion,))

    with pytest.raises(ValueError, match="at least one criterion"):
        Rubric("rubric", "1.0", "Title", EvaluationType.TEXT, ())

    duplicate = RubricCriterion("fluency", "Fluency duplicate", "Description")
    with pytest.raises(ValueError, match="criterion ids must be unique"):
        Rubric(
            "rubric",
            "1.0",
            "Title",
            EvaluationType.TEXT,
            (criterion, duplicate),
        )


def test_evaluation_record_validates_required_fields() -> None:
    rating = Rating("fluency", 4)

    with pytest.raises(ValueError, match="task_id must not be empty"):
        EvaluationRecord("", EvaluationType.TEXT, "rubric", "1.0", (rating,))

    with pytest.raises(ValueError, match="rubric id and version must not be empty"):
        EvaluationRecord("task", EvaluationType.TEXT, "", "1.0", (rating,))

    with pytest.raises(ValueError, match="at least one rating"):
        EvaluationRecord("task", EvaluationType.TEXT, "rubric", "1.0", ())


def test_audio_annotations_are_audio_only_and_duplicate_safe() -> None:
    rating = Rating("fluency", 4)
    annotation = _annotation()

    audio = EvaluationRecord(
        "audio-task",
        EvaluationType.AUDIO,
        "rubric",
        "1.0",
        (rating,),
        audio_annotations=(annotation,),
    )
    assert audio.audio_annotations == (annotation,)

    with pytest.raises(ValueError, match="only valid for audio evaluations"):
        EvaluationRecord(
            "text-task",
            EvaluationType.TEXT,
            "rubric",
            "1.0",
            (rating,),
            audio_annotations=(annotation,),
        )

    with pytest.raises(ValueError, match="must not contain exact duplicates"):
        EvaluationRecord(
            "audio-task",
            EvaluationType.AUDIO,
            "rubric",
            "1.0",
            (rating,),
            audio_annotations=(annotation, annotation),
        )
