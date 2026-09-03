"""Evidence-level disagreement drill-down for saved calibration inputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Any

from .audio_alignment import match_audio_annotations
from .calibration import EvaluatorSubmission, build_calibration_report
from .models import (
    AudioAnnotation,
    EvaluationRecord,
    EvaluationType,
    PairwiseEvaluationRecord,
    Rubric,
)

_PREFERENCE_POSITION = {"b": -1, "tie": 0, "a": 1}


@dataclass(frozen=True, slots=True)
class EvaluatorObservation:
    """One evaluator's criterion observation and optional human evidence note."""

    evaluator_id: str
    value: str
    note: str


@dataclass(frozen=True, slots=True)
class CriterionPairDisagreement:
    """One evaluator pair that disagrees on a rubric criterion."""

    evaluator_a: str
    evaluator_b: str
    value_a: str
    value_b: str
    gap: int | None
    note_a: str
    note_b: str


@dataclass(frozen=True, slots=True)
class CriterionDisagreement:
    """Criterion-level observations plus only the evaluator pairs that differ."""

    criterion_id: str
    criterion_label: str
    exact_agreement_rate: float
    disagreement_pair_count: int
    total_pair_count: int
    observations: tuple[EvaluatorObservation, ...]
    pair_disagreements: tuple[CriterionPairDisagreement, ...]


@dataclass(frozen=True, slots=True)
class OverallPreferenceDifference:
    """Pairwise-task difference in holistic preference and/or preference strength."""

    evaluator_a: str
    evaluator_b: str
    preference_a: str
    preference_b: str
    strength_a: int
    strength_b: int
    preference_changed: bool
    strength_gap: int


@dataclass(frozen=True, slots=True)
class AudioEvidence:
    """One timestamped annotation with evaluator attribution."""

    evaluator_id: str
    start_ms: int
    end_ms: int
    category: str
    severity: str
    note: str


@dataclass(frozen=True, slots=True)
class MatchedAudioVariance:
    """Matched audio evidence that differs in timing and/or severity."""

    left: AudioEvidence
    right: AudioEvidence
    temporal_similarity: float
    severity_match: bool


@dataclass(frozen=True, slots=True)
class AudioPairDisagreement:
    """Evidence-level differences for one pair of audio evaluators."""

    evaluator_a: str
    evaluator_b: str
    unmatched_a: tuple[AudioEvidence, ...]
    unmatched_b: tuple[AudioEvidence, ...]
    matched_variances: tuple[MatchedAudioVariance, ...]


@dataclass(frozen=True, slots=True)
class DisagreementReport:
    """Derived drill-down over the same immutable submissions used for calibration."""

    task_id: str
    evaluation_type: EvaluationType
    rubric_id: str
    rubric_version: str
    evaluator_ids: tuple[str, ...]
    evaluator_count: int
    criterion_count: int
    disputed_criterion_count: int
    disputed_criterion_pair_count: int
    criteria: tuple[CriterionDisagreement, ...]
    overall_preference_differences: tuple[OverallPreferenceDifference, ...] = ()
    audio_pair_disagreements: tuple[AudioPairDisagreement, ...] = ()


def _rating(record: EvaluationRecord, criterion_id: str) -> tuple[int, str]:
    for rating in record.ratings:
        if rating.criterion_id == criterion_id:
            return rating.score, rating.note
    raise ValueError(f"missing rating for criterion {criterion_id}")


def _preference(record: PairwiseEvaluationRecord, criterion_id: str) -> tuple[str, str]:
    for judgment in record.judgments:
        if judgment.criterion_id == criterion_id:
            return judgment.preference.value, judgment.note
    raise ValueError(f"missing pairwise judgment for criterion {criterion_id}")


def _criterion_drilldown(
    submissions: tuple[EvaluatorSubmission, ...],
    rubric: Rubric,
    exact_rates: dict[str, float],
) -> tuple[CriterionDisagreement, ...]:
    total_pair_count = len(tuple(combinations(submissions, 2)))
    rows: list[tuple[int, CriterionDisagreement]] = []

    for rubric_index, criterion in enumerate(rubric.criteria):
        observations: list[EvaluatorObservation] = []
        values: dict[str, tuple[str, str]] = {}
        for submission in submissions:
            record = submission.record
            if isinstance(record, PairwiseEvaluationRecord):
                value, note = _preference(record, criterion.id)
            else:
                score, note = _rating(record, criterion.id)
                value = str(score)
            values[submission.evaluator_id] = (value, note)
            observations.append(
                EvaluatorObservation(
                    evaluator_id=submission.evaluator_id,
                    value=value,
                    note=note,
                )
            )

        pair_disagreements: list[CriterionPairDisagreement] = []
        for left, right in combinations(submissions, 2):
            value_a, note_a = values[left.evaluator_id]
            value_b, note_b = values[right.evaluator_id]
            if value_a == value_b:
                continue
            gap: int | None
            if isinstance(left.record, PairwiseEvaluationRecord):
                gap = abs(_PREFERENCE_POSITION[value_a] - _PREFERENCE_POSITION[value_b])
            else:
                gap = abs(int(value_a) - int(value_b))
            pair_disagreements.append(
                CriterionPairDisagreement(
                    evaluator_a=left.evaluator_id,
                    evaluator_b=right.evaluator_id,
                    value_a=value_a,
                    value_b=value_b,
                    gap=gap,
                    note_a=note_a,
                    note_b=note_b,
                )
            )

        row = CriterionDisagreement(
            criterion_id=criterion.id,
            criterion_label=criterion.label,
            exact_agreement_rate=exact_rates[criterion.id],
            disagreement_pair_count=len(pair_disagreements),
            total_pair_count=total_pair_count,
            observations=tuple(observations),
            pair_disagreements=tuple(pair_disagreements),
        )
        rows.append((rubric_index, row))

    rows.sort(key=lambda item: (-item[1].disagreement_pair_count, item[0]))
    return tuple(row for _, row in rows)


def _overall_pairwise_differences(
    submissions: tuple[EvaluatorSubmission, ...],
) -> tuple[OverallPreferenceDifference, ...]:
    differences: list[OverallPreferenceDifference] = []
    for left, right in combinations(submissions, 2):
        if not isinstance(left.record, PairwiseEvaluationRecord) or not isinstance(
            right.record, PairwiseEvaluationRecord
        ):
            continue
        preference_a = left.record.overall_preference.value
        preference_b = right.record.overall_preference.value
        strength_a = left.record.preference_strength
        strength_b = right.record.preference_strength
        if preference_a == preference_b and strength_a == strength_b:
            continue
        differences.append(
            OverallPreferenceDifference(
                evaluator_a=left.evaluator_id,
                evaluator_b=right.evaluator_id,
                preference_a=preference_a,
                preference_b=preference_b,
                strength_a=strength_a,
                strength_b=strength_b,
                preference_changed=preference_a != preference_b,
                strength_gap=abs(strength_a - strength_b),
            )
        )
    return tuple(differences)


def _audio_evidence(evaluator_id: str, annotation: AudioAnnotation) -> AudioEvidence:
    return AudioEvidence(
        evaluator_id=evaluator_id,
        start_ms=annotation.start_ms,
        end_ms=annotation.end_ms,
        category=annotation.category.value,
        severity=annotation.severity.value,
        note=annotation.note,
    )


def _audio_pair_drilldown(
    submissions: tuple[EvaluatorSubmission, ...],
    tolerance_ms: int,
) -> tuple[AudioPairDisagreement, ...]:
    pairs: list[AudioPairDisagreement] = []
    for left, right in combinations(submissions, 2):
        if not isinstance(left.record, EvaluationRecord) or not isinstance(
            right.record, EvaluationRecord
        ):
            raise TypeError("audio disagreement drill-down requires scalar audio records")
        left_annotations = left.record.audio_annotations
        right_annotations = right.record.audio_annotations
        matches = match_audio_annotations(left_annotations, right_annotations, tolerance_ms)
        matched_left = {match.left_index for match in matches}
        matched_right = {match.right_index for match in matches}

        variances: list[MatchedAudioVariance] = []
        for match in matches:
            left_annotation = left_annotations[match.left_index]
            right_annotation = right_annotations[match.right_index]
            severity_match = left_annotation.severity is right_annotation.severity
            if severity_match and abs(match.temporal_similarity - 1.0) < 1e-12:
                continue
            variances.append(
                MatchedAudioVariance(
                    left=_audio_evidence(left.evaluator_id, left_annotation),
                    right=_audio_evidence(right.evaluator_id, right_annotation),
                    temporal_similarity=round(match.temporal_similarity, 4),
                    severity_match=severity_match,
                )
            )

        unmatched_a = tuple(
            _audio_evidence(left.evaluator_id, annotation)
            for index, annotation in enumerate(left_annotations)
            if index not in matched_left
        )
        unmatched_b = tuple(
            _audio_evidence(right.evaluator_id, annotation)
            for index, annotation in enumerate(right_annotations)
            if index not in matched_right
        )
        if unmatched_a or unmatched_b or variances:
            pairs.append(
                AudioPairDisagreement(
                    evaluator_a=left.evaluator_id,
                    evaluator_b=right.evaluator_id,
                    unmatched_a=unmatched_a,
                    unmatched_b=unmatched_b,
                    matched_variances=tuple(variances),
                )
            )
    return tuple(pairs)


def build_disagreement_report(
    submissions: tuple[EvaluatorSubmission, ...],
    rubric: Rubric,
    *,
    annotation_tolerance_ms: int = 250,
) -> DisagreementReport:
    """Build evidence-level disagreement details without deciding who is correct."""

    calibration = build_calibration_report(
        submissions,
        rubric,
        annotation_tolerance_ms=annotation_tolerance_ms,
    )
    exact_rates = {
        criterion_id: agreement.exact_agreement_rate
        for criterion_id, agreement in calibration.criterion_agreement.items()
    }
    criteria = _criterion_drilldown(submissions, rubric, exact_rates)
    disputed = tuple(item for item in criteria if item.disagreement_pair_count > 0)
    first = submissions[0].record

    return DisagreementReport(
        task_id=calibration.task_id,
        evaluation_type=calibration.evaluation_type,
        rubric_id=calibration.rubric_id,
        rubric_version=calibration.rubric_version,
        evaluator_ids=calibration.evaluator_ids,
        evaluator_count=calibration.evaluator_count,
        criterion_count=len(criteria),
        disputed_criterion_count=len(disputed),
        disputed_criterion_pair_count=sum(
            item.disagreement_pair_count for item in disputed
        ),
        criteria=criteria,
        overall_preference_differences=(
            _overall_pairwise_differences(submissions)
            if first.evaluation_type is EvaluationType.PAIRWISE
            else ()
        ),
        audio_pair_disagreements=(
            _audio_pair_drilldown(submissions, annotation_tolerance_ms)
            if first.evaluation_type is EvaluationType.AUDIO
            else ()
        ),
    )


def disagreement_report_to_dict(report: DisagreementReport) -> dict[str, Any]:
    """Convert a disagreement report to JSON-compatible data."""

    return asdict(report)
