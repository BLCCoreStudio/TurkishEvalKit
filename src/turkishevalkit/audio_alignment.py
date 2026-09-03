"""Deterministic timestamp alignment primitives for localized audio evidence."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import AudioAnnotation


@dataclass(frozen=True, slots=True)
class AudioAnnotationMatch:
    """One deterministic one-to-one correspondence between two annotation sequences."""

    left_index: int
    right_index: int
    temporal_similarity: float

    def __post_init__(self) -> None:
        if self.left_index < 0 or self.right_index < 0:
            raise ValueError("audio annotation match indexes must be non-negative")
        if not 0.0 <= self.temporal_similarity <= 1.0:
            raise ValueError("temporal_similarity must be between 0 and 1")


def _validate_tolerance(tolerance_ms: int) -> None:
    if isinstance(tolerance_ms, bool) or not isinstance(tolerance_ms, int):
        raise TypeError("tolerance_ms must be an integer")
    if tolerance_ms < 0:
        raise ValueError("tolerance_ms must be non-negative")


def _distance_to_interval(point_ms: int, start_ms: int, end_ms: int) -> int:
    if start_ms <= point_ms <= end_ms:
        return 0
    return min(abs(point_ms - start_ms), abs(point_ms - end_ms))


def _temporal_similarity_unchecked(
    left: AudioAnnotation,
    right: AudioAnnotation,
    tolerance_ms: int,
) -> float | None:
    if left.category is not right.category:
        return None

    left_point = left.start_ms == left.end_ms
    right_point = right.start_ms == right.end_ms

    if left_point and right_point:
        distance = abs(left.start_ms - right.start_ms)
        if distance > tolerance_ms:
            return None
        return max(0.0, 1.0 - (distance / (tolerance_ms + 1)))

    if left_point != right_point:
        point = left if left_point else right
        interval = right if left_point else left
        distance = _distance_to_interval(point.start_ms, interval.start_ms, interval.end_ms)
        if distance > tolerance_ms:
            return None
        return max(0.0, 1.0 - (distance / (tolerance_ms + 1)))

    overlap = max(0, min(left.end_ms, right.end_ms) - max(left.start_ms, right.start_ms))
    if overlap > 0:
        union = max(left.end_ms, right.end_ms) - min(left.start_ms, right.start_ms)
        return overlap / union

    gap = max(left.start_ms, right.start_ms) - min(left.end_ms, right.end_ms)
    if gap > tolerance_ms:
        return None
    return 0.25 * max(0.0, 1.0 - (gap / (tolerance_ms + 1)))


def annotation_temporal_similarity(
    left: AudioAnnotation,
    right: AudioAnnotation,
    tolerance_ms: int,
) -> float | None:
    """Return category-aware temporal similarity, or None when annotations cannot match.

    The function preserves TurkishEvalKit's established calibration semantics:
    point/point and point/interval proximity use the configured tolerance, overlapping
    intervals use overlap-over-union, and separated intervals receive a small proximity
    score only while their gap remains inside the tolerance.
    """

    _validate_tolerance(tolerance_ms)
    return _temporal_similarity_unchecked(left, right, tolerance_ms)


def match_audio_annotations(
    left: Sequence[AudioAnnotation],
    right: Sequence[AudioAnnotation],
    tolerance_ms: int,
) -> tuple[AudioAnnotationMatch, ...]:
    """Greedily create deterministic one-to-one matches ordered by best similarity.

    Candidate pairs are ranked by descending temporal similarity, then by their original
    left/right indexes. Each annotation may participate in at most one returned match.
    This intentionally preserves the existing calibration/disagreement matching behavior;
    it is not a global assignment optimizer.
    """

    _validate_tolerance(tolerance_ms)
    candidates: list[tuple[float, int, int]] = []
    for left_index, left_annotation in enumerate(left):
        for right_index, right_annotation in enumerate(right):
            similarity = _temporal_similarity_unchecked(
                left_annotation,
                right_annotation,
                tolerance_ms,
            )
            if similarity is not None:
                candidates.append((similarity, left_index, right_index))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_left: set[int] = set()
    used_right: set[int] = set()
    matches: list[AudioAnnotationMatch] = []
    for similarity, left_index, right_index in candidates:
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        matches.append(
            AudioAnnotationMatch(
                left_index=left_index,
                right_index=right_index,
                temporal_similarity=similarity,
            )
        )
    return tuple(matches)
