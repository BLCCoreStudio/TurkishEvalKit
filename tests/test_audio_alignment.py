from __future__ import annotations

import pytest

from turkishevalkit.audio_alignment import (
    AudioAnnotationMatch,
    annotation_temporal_similarity,
    match_audio_annotations,
)
from turkishevalkit.models import (
    AudioAnnotation,
    AudioIssueCategory,
    AudioIssueSeverity,
)


def _annotation(
    start_ms: int,
    end_ms: int,
    *,
    category: AudioIssueCategory = AudioIssueCategory.INTONATION,
) -> AudioAnnotation:
    return AudioAnnotation(
        start_ms=start_ms,
        end_ms=end_ms,
        category=category,
        severity=AudioIssueSeverity.MINOR,
        note="test evidence",
    )


def test_point_similarity_uses_tolerance_and_category() -> None:
    left = _annotation(1000, 1000)
    exact = _annotation(1000, 1000)
    nearby = _annotation(1100, 1100)
    different_category = _annotation(
        1000,
        1000,
        category=AudioIssueCategory.NOISE,
    )

    assert annotation_temporal_similarity(left, exact, 250) == 1.0
    assert annotation_temporal_similarity(left, nearby, 250) == pytest.approx(1.0 - 100 / 251)
    assert annotation_temporal_similarity(left, different_category, 250) is None
    assert annotation_temporal_similarity(left, nearby, 50) is None


def test_point_interval_similarity_uses_distance_to_interval() -> None:
    interval = _annotation(1000, 1400)
    inside = _annotation(1200, 1200)
    outside = _annotation(900, 900)

    assert annotation_temporal_similarity(inside, interval, 100) == 1.0
    assert annotation_temporal_similarity(interval, inside, 100) == 1.0
    assert annotation_temporal_similarity(outside, interval, 100) == pytest.approx(1.0 - 100 / 101)
    assert annotation_temporal_similarity(outside, interval, 99) is None


def test_interval_similarity_preserves_overlap_and_near_gap_rules() -> None:
    left = _annotation(1000, 2000)
    overlapping = _annotation(1500, 2500)
    touching = _annotation(2000, 2600)
    nearby = _annotation(2100, 2600)
    distant = _annotation(2300, 2600)

    assert annotation_temporal_similarity(left, overlapping, 250) == pytest.approx(500 / 1500)
    assert annotation_temporal_similarity(left, touching, 250) == 0.25
    assert annotation_temporal_similarity(left, nearby, 250) == pytest.approx(
        0.25 * (1.0 - 100 / 251)
    )
    assert annotation_temporal_similarity(left, distant, 250) is None


def test_matching_is_one_to_one_and_deterministic_for_equal_candidates() -> None:
    left = (_annotation(0, 0), _annotation(100, 100))
    right = (_annotation(50, 50),)

    matches = match_audio_annotations(left, right, 100)

    assert len(matches) == 1
    assert matches[0].left_index == 0
    assert matches[0].right_index == 0
    assert matches[0].temporal_similarity == pytest.approx(1.0 - 50 / 101)


def test_matching_prefers_highest_similarity_before_stable_indexes() -> None:
    left = (_annotation(0, 0), _annotation(100, 100))
    right = (_annotation(90, 90), _annotation(10, 10))

    matches = match_audio_annotations(left, right, 100)

    assert [(match.left_index, match.right_index) for match in matches] == [(0, 1), (1, 0)]
    assert all(match.temporal_similarity == pytest.approx(1.0 - 10 / 101) for match in matches)


def test_matching_ignores_cross_category_candidates_and_supports_empty_sequences() -> None:
    left = (_annotation(1000, 1000),)
    right = (
        _annotation(1000, 1000, category=AudioIssueCategory.NOISE),
        _annotation(1000, 1000),
    )

    matches = match_audio_annotations(left, right, 0)

    assert [(match.left_index, match.right_index) for match in matches] == [(0, 1)]
    assert match_audio_annotations((), (), 250) == ()


def test_alignment_rejects_invalid_tolerance_and_match_values() -> None:
    annotation = _annotation(0, 0)

    with pytest.raises(ValueError, match="non-negative"):
        annotation_temporal_similarity(annotation, annotation, -1)
    with pytest.raises(TypeError, match="integer"):
        match_audio_annotations((annotation,), (annotation,), True)
    with pytest.raises(ValueError, match="indexes"):
        AudioAnnotationMatch(-1, 0, 1.0)
    with pytest.raises(ValueError, match="between 0 and 1"):
        AudioAnnotationMatch(0, 0, 1.1)
