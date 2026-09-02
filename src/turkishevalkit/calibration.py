"""Agreement and calibration metrics for independent human evaluations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any, TypeAlias

from .evaluation import EvaluationResult, evaluate_submission
from .models import AudioAnnotation, EvaluationRecord, EvaluationType, PairwiseEvaluationRecord, Rubric
from .pairwise import PairwiseEvaluationResult, evaluate_pairwise_submission
from .serialization import record_from_dict

SubmissionRecord: TypeAlias = EvaluationRecord | PairwiseEvaluationRecord
SubmissionResult: TypeAlias = EvaluationResult | PairwiseEvaluationResult


@dataclass(frozen=True, slots=True)
class EvaluatorSubmission:
    """One evaluator identity paired with one immutable evaluation submission."""

    evaluator_id: str
    record: SubmissionRecord

    def __post_init__(self) -> None:
        if not self.evaluator_id.strip():
            raise ValueError("evaluator_id must not be empty")


@dataclass(frozen=True, slots=True)
class CriterionAgreement:
    """Observed agreement statistics for one rubric criterion."""

    criterion_id: str
    exact_agreement_rate: float
    observations: dict[str, int]
    mean_absolute_difference: float | None = None
    min_rating: int | None = None
    max_rating: int | None = None


@dataclass(frozen=True, slots=True)
class AudioAnnotationPairAgreement:
    """Localized annotation alignment for one pair of evaluators."""

    evaluator_a: str
    evaluator_b: str
    annotation_count_a: int
    annotation_count_b: int
    matched_count: int
    f1: float
    severity_agreement_rate: float | None
    mean_temporal_similarity: float | None


@dataclass(frozen=True, slots=True)
class AudioAnnotationAgreement:
    """Aggregate timestamped-audio alignment across all evaluator pairs."""

    tolerance_ms: int
    mean_pairwise_f1: float
    severity_agreement_rate: float | None
    mean_temporal_similarity: float | None
    pair_agreements: tuple[AudioAnnotationPairAgreement, ...]


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """Auditable agreement report for two or more independent evaluators."""

    task_id: str
    evaluation_type: EvaluationType
    rubric_id: str
    rubric_version: str
    evaluator_ids: tuple[str, ...]
    evaluator_count: int
    evaluator_pair_count: int
    exact_criterion_agreement_rate: float
    aggregate_scores: dict[str, float]
    aggregate_score_scale: str
    aggregate_score_spread: float
    criterion_agreement: dict[str, CriterionAgreement]
    within_one_criterion_agreement_rate: float | None = None
    mean_absolute_rating_difference: float | None = None
    max_rating_difference: int | None = None
    overall_preference_agreement_rate: float | None = None
    mean_absolute_preference_strength_difference: float | None = None
    max_preference_strength_difference: int | None = None
    audio_annotation_agreement: AudioAnnotationAgreement | None = None


def _round_rate(value: float) -> float:
    return round(value, 4)


def _validate_submissions(
    submissions: tuple[EvaluatorSubmission, ...],
    rubric: Rubric,
) -> None:
    if len(submissions) < 2:
        raise ValueError("calibration requires at least two evaluator submissions")

    evaluator_ids = [submission.evaluator_id for submission in submissions]
    if len(evaluator_ids) != len(set(evaluator_ids)):
        raise ValueError("evaluator_id values must be unique within one calibration report")

    first = submissions[0].record
    for submission in submissions:
        record = submission.record
        if record.task_id != first.task_id:
            raise ValueError("all calibration submissions must use the same task_id")
        if record.evaluation_type is not first.evaluation_type:
            raise ValueError("all calibration submissions must use the same evaluation_type")
        if record.rubric_id != first.rubric_id or record.rubric_version != first.rubric_version:
            raise ValueError("all calibration submissions must use the same rubric id/version")
        if record.source != first.source:
            raise ValueError("all calibration submissions must reference the same source stimulus")

    if first.rubric_id != rubric.id or first.rubric_version != rubric.version:
        raise ValueError("calibration rubric id/version does not match the supplied rubric")
    if first.evaluation_type is not rubric.evaluation_type:
        raise ValueError("calibration evaluation_type does not match the supplied rubric")


def _score_submissions(
    submissions: tuple[EvaluatorSubmission, ...],
    rubric: Rubric,
) -> tuple[SubmissionResult, ...]:
    results: list[SubmissionResult] = []
    for submission in submissions:
        record = submission.record
        if isinstance(record, PairwiseEvaluationRecord):
            results.append(evaluate_pairwise_submission(record, rubric))
        else:
            results.append(evaluate_submission(record, rubric))
    return tuple(results)


def _scalar_criterion_agreement(
    submissions: tuple[EvaluatorSubmission, ...],
    rubric: Rubric,
) -> tuple[dict[str, CriterionAgreement], list[int]]:
    pair_differences: list[int] = []
    agreement: dict[str, CriterionAgreement] = {}

    for criterion in rubric.criteria:
        scores = [
            next(rating.score for rating in submission.record.ratings if rating.criterion_id == criterion.id)
            for submission in submissions
            if isinstance(submission.record, EvaluationRecord)
        ]
        differences = [abs(left - right) for left, right in combinations(scores, 2)]
        pair_differences.extend(differences)
        observations = {str(score): scores.count(score) for score in sorted(set(scores))}
        agreement[criterion.id] = CriterionAgreement(
            criterion_id=criterion.id,
            exact_agreement_rate=_round_rate(sum(diff == 0 for diff in differences) / len(differences)),
            observations=observations,
            mean_absolute_difference=round(mean(differences), 3),
            min_rating=min(scores),
            max_rating=max(scores),
        )

    return agreement, pair_differences


def _pairwise_criterion_agreement(
    submissions: tuple[EvaluatorSubmission, ...],
    rubric: Rubric,
) -> tuple[dict[str, CriterionAgreement], list[bool]]:
    pair_matches: list[bool] = []
    agreement: dict[str, CriterionAgreement] = {}

    for criterion in rubric.criteria:
        preferences = [
            next(
                judgment.preference.value
                for judgment in submission.record.judgments
                if judgment.criterion_id == criterion.id
            )
            for submission in submissions
            if isinstance(submission.record, PairwiseEvaluationRecord)
        ]
        matches = [left == right for left, right in combinations(preferences, 2)]
        pair_matches.extend(matches)
        observations = {
            preference: preferences.count(preference) for preference in sorted(set(preferences))
        }
        agreement[criterion.id] = CriterionAgreement(
            criterion_id=criterion.id,
            exact_agreement_rate=_round_rate(sum(matches) / len(matches)),
            observations=observations,
        )

    return agreement, pair_matches


def _distance_to_interval(point_ms: int, start_ms: int, end_ms: int) -> int:
    if start_ms <= point_ms <= end_ms:
        return 0
    return min(abs(point_ms - start_ms), abs(point_ms - end_ms))


def _annotation_temporal_similarity(
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


def _match_audio_annotations(
    left: tuple[AudioAnnotation, ...],
    right: tuple[AudioAnnotation, ...],
    tolerance_ms: int,
) -> tuple[tuple[int, int, float], ...]:
    candidates: list[tuple[float, int, int]] = []
    for left_index, left_annotation in enumerate(left):
        for right_index, right_annotation in enumerate(right):
            similarity = _annotation_temporal_similarity(
                left_annotation,
                right_annotation,
                tolerance_ms,
            )
            if similarity is not None:
                candidates.append((similarity, left_index, right_index))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_left: set[int] = set()
    used_right: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for similarity, left_index, right_index in candidates:
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        matches.append((left_index, right_index, similarity))
    return tuple(matches)


def _audio_annotation_agreement(
    submissions: tuple[EvaluatorSubmission, ...],
    tolerance_ms: int,
) -> AudioAnnotationAgreement:
    pair_reports: list[AudioAnnotationPairAgreement] = []
    severity_matches = 0
    matched_total = 0
    temporal_similarities: list[float] = []

    for left_submission, right_submission in combinations(submissions, 2):
        left_record = left_submission.record
        right_record = right_submission.record
        if not isinstance(left_record, EvaluationRecord) or not isinstance(
            right_record, EvaluationRecord
        ):
            raise TypeError("audio annotation agreement requires scalar audio records")

        left = left_record.audio_annotations
        right = right_record.audio_annotations
        matches = _match_audio_annotations(left, right, tolerance_ms)
        matched_count = len(matches)
        denominator = len(left) + len(right)
        f1 = 1.0 if denominator == 0 else (2.0 * matched_count) / denominator

        pair_severity_matches = sum(
            left[left_index].severity is right[right_index].severity
            for left_index, right_index, _ in matches
        )
        pair_similarities = [similarity for _, _, similarity in matches]

        severity_matches += pair_severity_matches
        matched_total += matched_count
        temporal_similarities.extend(pair_similarities)
        pair_reports.append(
            AudioAnnotationPairAgreement(
                evaluator_a=left_submission.evaluator_id,
                evaluator_b=right_submission.evaluator_id,
                annotation_count_a=len(left),
                annotation_count_b=len(right),
                matched_count=matched_count,
                f1=_round_rate(f1),
                severity_agreement_rate=(
                    None
                    if matched_count == 0
                    else _round_rate(pair_severity_matches / matched_count)
                ),
                mean_temporal_similarity=(
                    None if not pair_similarities else _round_rate(mean(pair_similarities))
                ),
            )
        )

    return AudioAnnotationAgreement(
        tolerance_ms=tolerance_ms,
        mean_pairwise_f1=_round_rate(mean(report.f1 for report in pair_reports)),
        severity_agreement_rate=(
            None if matched_total == 0 else _round_rate(severity_matches / matched_total)
        ),
        mean_temporal_similarity=(
            None if not temporal_similarities else _round_rate(mean(temporal_similarities))
        ),
        pair_agreements=tuple(pair_reports),
    )


def build_calibration_report(
    submissions: tuple[EvaluatorSubmission, ...],
    rubric: Rubric,
    *,
    annotation_tolerance_ms: int = 250,
) -> CalibrationReport:
    """Validate independent submissions and calculate transparent agreement metrics."""

    if annotation_tolerance_ms < 0:
        raise ValueError("annotation_tolerance_ms must be non-negative")

    _validate_submissions(submissions, rubric)
    results = _score_submissions(submissions, rubric)
    first = submissions[0].record
    evaluator_ids = tuple(submission.evaluator_id for submission in submissions)
    evaluator_pair_count = len(tuple(combinations(submissions, 2)))

    if first.evaluation_type is EvaluationType.PAIRWISE:
        if not all(isinstance(result, PairwiseEvaluationResult) for result in results):
            raise TypeError("pairwise calibration produced an unexpected scalar result")
        pairwise_results = tuple(
            result for result in results if isinstance(result, PairwiseEvaluationResult)
        )
        criterion_agreement, pair_matches = _pairwise_criterion_agreement(submissions, rubric)
        overall_preferences = [result.overall_preference.value for result in pairwise_results]
        overall_matches = [left == right for left, right in combinations(overall_preferences, 2)]
        strengths = [result.preference_strength for result in pairwise_results]
        strength_differences = [abs(left - right) for left, right in combinations(strengths, 2)]
        aggregate_scores = {
            evaluator_id: result.preference_score
            for evaluator_id, result in zip(evaluator_ids, pairwise_results, strict=True)
        }
        score_values = list(aggregate_scores.values())

        return CalibrationReport(
            task_id=first.task_id,
            evaluation_type=first.evaluation_type,
            rubric_id=first.rubric_id,
            rubric_version=first.rubric_version,
            evaluator_ids=evaluator_ids,
            evaluator_count=len(submissions),
            evaluator_pair_count=evaluator_pair_count,
            exact_criterion_agreement_rate=_round_rate(sum(pair_matches) / len(pair_matches)),
            aggregate_scores=aggregate_scores,
            aggregate_score_scale="-100..100 signed A↔B criterion preference",
            aggregate_score_spread=round(max(score_values) - min(score_values), 2),
            criterion_agreement=criterion_agreement,
            overall_preference_agreement_rate=_round_rate(
                sum(overall_matches) / len(overall_matches)
            ),
            mean_absolute_preference_strength_difference=round(
                mean(strength_differences), 3
            ),
            max_preference_strength_difference=max(strength_differences),
        )

    if not all(isinstance(result, EvaluationResult) for result in results):
        raise TypeError("scalar calibration produced an unexpected pairwise result")
    scalar_results = tuple(result for result in results if isinstance(result, EvaluationResult))
    criterion_agreement, rating_differences = _scalar_criterion_agreement(submissions, rubric)
    aggregate_scores = {
        evaluator_id: result.normalized_score
        for evaluator_id, result in zip(evaluator_ids, scalar_results, strict=True)
    }
    score_values = list(aggregate_scores.values())

    return CalibrationReport(
        task_id=first.task_id,
        evaluation_type=first.evaluation_type,
        rubric_id=first.rubric_id,
        rubric_version=first.rubric_version,
        evaluator_ids=evaluator_ids,
        evaluator_count=len(submissions),
        evaluator_pair_count=evaluator_pair_count,
        exact_criterion_agreement_rate=_round_rate(
            sum(diff == 0 for diff in rating_differences) / len(rating_differences)
        ),
        aggregate_scores=aggregate_scores,
        aggregate_score_scale="0..100 normalized scalar score",
        aggregate_score_spread=round(max(score_values) - min(score_values), 2),
        criterion_agreement=criterion_agreement,
        within_one_criterion_agreement_rate=_round_rate(
            sum(diff <= 1 for diff in rating_differences) / len(rating_differences)
        ),
        mean_absolute_rating_difference=round(mean(rating_differences), 3),
        max_rating_difference=max(rating_differences),
        audio_annotation_agreement=(
            _audio_annotation_agreement(submissions, annotation_tolerance_ms)
            if first.evaluation_type is EvaluationType.AUDIO
            else None
        ),
    )


def calibration_spec_from_dict(data: dict[str, Any]) -> tuple[EvaluatorSubmission, ...]:
    """Build evaluator submissions from a portable calibration-spec mapping."""

    raw_submissions = data.get("submissions")
    if not isinstance(raw_submissions, list):
        raise ValueError("calibration spec submissions must be a list")

    submissions: list[EvaluatorSubmission] = []
    for item in raw_submissions:
        if not isinstance(item, dict):
            raise ValueError("each calibration submission must be an object")
        raw_evaluation = item.get("evaluation")
        if not isinstance(raw_evaluation, dict):
            raise ValueError("each calibration submission evaluation must be an object")
        submissions.append(
            EvaluatorSubmission(
                evaluator_id=str(item.get("evaluator_id", "")),
                record=record_from_dict(raw_evaluation),
            )
        )
    return tuple(submissions)


def load_calibration_spec(path: Path) -> tuple[EvaluatorSubmission, ...]:
    """Load a UTF-8 calibration spec containing two or more evaluator submissions."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("calibration file must contain one JSON object")
    return calibration_spec_from_dict(data)


def calibration_report_to_dict(report: CalibrationReport) -> dict[str, Any]:
    """Convert a calibration report into JSON-compatible data."""

    return asdict(report)


def write_calibration_report(path: Path, report: CalibrationReport) -> None:
    """Write a calibration report through a temporary file before replacement."""

    payload = json.dumps(calibration_report_to_dict(report), ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
