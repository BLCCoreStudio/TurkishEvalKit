"""Population-level inter-rater reliability over repeated evaluation tasks.

Repeated-task reliability is deliberately separate from single-task calibration.
A coefficient is calculated only when its documented design assumptions are met;
otherwise the report contains an explicit not-applicable estimate.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from math import isclose
from pathlib import Path
from typing import Any, TypeAlias

from .calibration import (
    CalibrationReport,
    EvaluatorSubmission,
    build_calibration_report,
    calibration_spec_from_dict,
)
from .models import EvaluationRecord, EvaluationType, PairwiseEvaluationRecord, Rubric

Category: TypeAlias = int | str
Distance: TypeAlias = Callable[[Category, Category], float]


@dataclass(frozen=True, slots=True)
class ReliabilityTask:
    """Independent evaluator submissions for one task/source unit."""

    submissions: tuple[EvaluatorSubmission, ...]

    def __post_init__(self) -> None:
        if len(self.submissions) < 2:
            raise ValueError(
                "each reliability task requires at least two evaluator submissions"
            )

    @property
    def task_id(self) -> str:
        return self.submissions[0].record.task_id


@dataclass(frozen=True, slots=True)
class PopulationReliabilitySpec:
    """Repeated-task dataset plus an explicitly declared task-count floor."""

    minimum_task_count: int
    tasks: tuple[ReliabilityTask, ...]

    def __post_init__(self) -> None:
        if self.minimum_task_count < 3:
            raise ValueError("minimum_task_count must be at least 3")
        if len(self.tasks) < self.minimum_task_count:
            raise ValueError(
                "reliability dataset does not satisfy its declared minimum_task_count"
            )


@dataclass(frozen=True, slots=True)
class ReliabilityEstimate:
    """One coefficient plus explicit applicability and assumptions."""

    metric: str
    value: float | None
    applicable: bool
    reason: str | None
    assumptions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.applicable and self.value is None:
            raise ValueError("applicable reliability estimates require a value")
        if not self.applicable and self.reason is None:
            raise ValueError("not-applicable reliability estimates require a reason")


@dataclass(frozen=True, slots=True)
class CriterionReliability:
    """Population reliability coefficients for one rubric criterion."""

    criterion_id: str
    krippendorff_alpha: ReliabilityEstimate
    fleiss_kappa: ReliabilityEstimate
    icc_a1: ReliabilityEstimate


@dataclass(frozen=True, slots=True)
class PopulationReliabilityReport:
    """Auditable repeated-task reliability report without pass/fail semantics."""

    evaluation_type: EvaluationType
    rubric_id: str
    rubric_version: str
    task_count: int
    declared_minimum_task_count: int
    evaluator_ids: tuple[str, ...]
    min_evaluators_per_task: int
    max_evaluators_per_task: int
    fixed_rater_count: bool
    fixed_evaluator_panel: bool
    criterion_reliability: dict[str, CriterionReliability]
    aggregate_score_icc_a1: ReliabilityEstimate
    overall_preference_krippendorff_alpha: ReliabilityEstimate
    overall_preference_fleiss_kappa: ReliabilityEstimate
    preference_strength_krippendorff_alpha: ReliabilityEstimate
    notes: tuple[str, ...]


_KRIPPENDORFF_BASE_ASSUMPTIONS = (
    "task units are independent for the intended population inference",
    "each included task has at least two independent human ratings",
    "chance disagreement is estimated from pooled observed marginals",
)

_FLEISS_ASSUMPTIONS = (
    "categories are treated as nominal",
    "every included task has the same number of ratings",
    "rater identities may vary by task",
    "chance agreement is estimated from pooled category marginals",
)

_ICC_A1_ASSUMPTIONS = (
    "the same evaluator panel rates every included task",
    "two-way random-effects ANOVA model",
    "absolute agreement rather than consistency",
    "single-measure reliability ICC(A,1)",
    "task and evaluator effects use the two-way ANOVA decomposition",
)


def _estimate(
    metric: str,
    value: float,
    assumptions: tuple[str, ...],
) -> ReliabilityEstimate:
    return ReliabilityEstimate(
        metric=metric,
        value=round(value, 4),
        applicable=True,
        reason=None,
        assumptions=assumptions,
    )


def _not_applicable(
    metric: str,
    reason: str,
    assumptions: tuple[str, ...],
) -> ReliabilityEstimate:
    return ReliabilityEstimate(
        metric=metric,
        value=None,
        applicable=False,
        reason=reason,
        assumptions=assumptions,
    )


def _nominal_distance(left: Category, right: Category) -> float:
    return 0.0 if left == right else 1.0


def _ordinal_distance(
    categories: Sequence[int],
    pooled_counts: Counter[Category],
) -> Distance:
    positions = {category: index for index, category in enumerate(categories)}

    def distance(left: Category, right: Category) -> float:
        if left == right:
            return 0.0
        if not isinstance(left, int) or not isinstance(right, int):
            raise TypeError("ordinal reliability requires integer categories")
        try:
            left_index = positions[left]
            right_index = positions[right]
        except KeyError as exc:
            raise ValueError(
                "ordinal observation is outside the declared category scale"
            ) from exc
        low, high = sorted((left_index, right_index))
        interval_mass = sum(
            pooled_counts.get(category, 0)
            for category in categories[low : high + 1]
        )
        endpoint_half_mass = (
            pooled_counts.get(categories[low], 0)
            + pooled_counts.get(categories[high], 0)
        ) / 2.0
        value = interval_mass - endpoint_half_mass
        return float(value * value)

    return distance


def _category_disagreement(
    counts: Counter[Category],
    distance: Distance,
) -> float:
    total = sum(counts.values())
    if total < 2:
        raise ValueError("disagreement requires at least two observations")
    numerator = sum(
        left_count * right_count * distance(left, right)
        for left, left_count in counts.items()
        for right, right_count in counts.items()
    )
    return numerator / (total * (total - 1))


def _krippendorff_alpha(
    units: Sequence[Sequence[Category]],
    *,
    scale: str,
    ordinal_categories: Sequence[int] = (),
) -> ReliabilityEstimate:
    metric = f"krippendorff_alpha_{scale}"
    valid_units = [tuple(unit) for unit in units if len(unit) >= 2]
    if not valid_units:
        return _not_applicable(
            metric,
            "no task contains at least two pairable observations",
            _KRIPPENDORFF_BASE_ASSUMPTIONS,
        )

    pooled = Counter(value for unit in valid_units for value in unit)
    if len(pooled) < 2:
        return _not_applicable(
            metric,
            "expected disagreement is zero because only one category is observed",
            _KRIPPENDORFF_BASE_ASSUMPTIONS,
        )

    if scale == "nominal":
        distance = _nominal_distance
        assumptions = (*_KRIPPENDORFF_BASE_ASSUMPTIONS, "categories are nominal")
    elif scale == "ordinal":
        if not ordinal_categories:
            raise ValueError("ordinal_categories are required for ordinal alpha")
        distance = _ordinal_distance(ordinal_categories, pooled)
        assumptions = (
            *_KRIPPENDORFF_BASE_ASSUMPTIONS,
            "categories are ordered and use Krippendorff ordinal distance",
        )
    else:
        raise ValueError(f"unsupported Krippendorff scale: {scale}")

    total_pairable_ratings = sum(len(unit) for unit in valid_units)
    observed = sum(
        _category_disagreement(Counter(unit), distance) * len(unit)
        for unit in valid_units
    ) / total_pairable_ratings
    expected = _category_disagreement(pooled, distance)
    if isclose(expected, 0.0, abs_tol=1e-12):
        return _not_applicable(
            metric,
            "expected disagreement is zero for the observed marginal distribution",
            assumptions,
        )
    return _estimate(metric, 1.0 - (observed / expected), assumptions)


def _fleiss_kappa(
    units: Sequence[Sequence[str]],
    *,
    categories: Sequence[str],
) -> ReliabilityEstimate:
    metric = "fleiss_kappa"
    if not units:
        return _not_applicable(metric, "no tasks are available", _FLEISS_ASSUMPTIONS)

    rater_counts = {len(unit) for unit in units}
    if len(rater_counts) != 1:
        return _not_applicable(
            metric,
            "Fleiss kappa requires the same number of ratings for every task",
            _FLEISS_ASSUMPTIONS,
        )
    rater_count = next(iter(rater_counts))
    if rater_count < 2:
        return _not_applicable(
            metric,
            "Fleiss kappa requires at least two ratings per task",
            _FLEISS_ASSUMPTIONS,
        )

    category_totals = Counter(value for unit in units for value in unit)
    total_ratings = len(units) * rater_count
    marginal_probabilities = {
        category: category_totals.get(category, 0) / total_ratings
        for category in categories
    }
    task_agreements: list[float] = []
    for unit in units:
        counts = Counter(unit)
        numerator = (
            sum(counts.get(category, 0) ** 2 for category in categories)
            - rater_count
        )
        task_agreements.append(numerator / (rater_count * (rater_count - 1)))

    observed = sum(task_agreements) / len(task_agreements)
    expected = sum(
        probability * probability
        for probability in marginal_probabilities.values()
    )
    if isclose(1.0 - expected, 0.0, abs_tol=1e-12):
        return _not_applicable(
            metric,
            "chance agreement is 1 because only one pooled category has probability mass",
            _FLEISS_ASSUMPTIONS,
        )
    return _estimate(
        metric,
        (observed - expected) / (1.0 - expected),
        _FLEISS_ASSUMPTIONS,
    )


def _icc_a1(rows: Sequence[dict[str, float]]) -> ReliabilityEstimate:
    metric = "icc_a1_absolute_agreement"
    if not rows:
        return _not_applicable(metric, "no tasks are available", _ICC_A1_ASSUMPTIONS)

    first_panel = tuple(sorted(rows[0]))
    if len(first_panel) < 2:
        return _not_applicable(
            metric,
            "ICC(A,1) requires at least two evaluators",
            _ICC_A1_ASSUMPTIONS,
        )
    if any(tuple(sorted(row)) != first_panel for row in rows[1:]):
        return _not_applicable(
            metric,
            "ICC(A,1) requires the same evaluator identities on every task",
            _ICC_A1_ASSUMPTIONS,
        )
    if len(rows) < 2:
        return _not_applicable(
            metric,
            "ICC(A,1) requires at least two tasks",
            _ICC_A1_ASSUMPTIONS,
        )

    matrix = [[row[evaluator_id] for evaluator_id in first_panel] for row in rows]
    task_count = len(matrix)
    evaluator_count = len(first_panel)
    grand_mean = sum(sum(row) for row in matrix) / (task_count * evaluator_count)
    task_means = [sum(row) / evaluator_count for row in matrix]
    evaluator_means = [
        sum(matrix[row_index][column_index] for row_index in range(task_count))
        / task_count
        for column_index in range(evaluator_count)
    ]

    task_ss = evaluator_count * sum((value - grand_mean) ** 2 for value in task_means)
    evaluator_ss = task_count * sum(
        (value - grand_mean) ** 2 for value in evaluator_means
    )
    residual_ss = sum(
        (
            matrix[row_index][column_index]
            - task_means[row_index]
            - evaluator_means[column_index]
            + grand_mean
        )
        ** 2
        for row_index in range(task_count)
        for column_index in range(evaluator_count)
    )

    task_ms = task_ss / (task_count - 1)
    evaluator_ms = evaluator_ss / (evaluator_count - 1)
    residual_ms = residual_ss / ((task_count - 1) * (evaluator_count - 1))
    denominator = (
        task_ms
        + ((evaluator_count - 1) * residual_ms)
        + (evaluator_count * (evaluator_ms - residual_ms) / task_count)
    )
    if isclose(denominator, 0.0, abs_tol=1e-12):
        return _not_applicable(
            metric,
            "ICC(A,1) denominator is zero for this dataset",
            _ICC_A1_ASSUMPTIONS,
        )
    return _estimate(
        metric,
        (task_ms - residual_ms) / denominator,
        _ICC_A1_ASSUMPTIONS,
    )


def _validate_population(
    spec: PopulationReliabilitySpec,
    rubric: Rubric,
) -> tuple[CalibrationReport, ...]:
    reports: list[CalibrationReport] = []
    task_ids: set[str] = set()
    evaluation_type: EvaluationType | None = None

    for task in spec.tasks:
        report = build_calibration_report(task.submissions, rubric)
        if report.task_id in task_ids:
            raise ValueError(
                "reliability task_id values must be unique across the dataset"
            )
        task_ids.add(report.task_id)
        if evaluation_type is None:
            evaluation_type = report.evaluation_type
        elif report.evaluation_type is not evaluation_type:
            raise ValueError("all reliability tasks must use the same evaluation_type")
        if report.rubric_id != rubric.id or report.rubric_version != rubric.version:
            raise ValueError(
                "all reliability tasks must use the supplied rubric id/version"
            )
        reports.append(report)
    return tuple(reports)


def _scalar_criterion_rows(
    spec: PopulationReliabilitySpec,
    criterion_id: str,
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for task in spec.tasks:
        row: dict[str, float] = {}
        for submission in task.submissions:
            record = submission.record
            if not isinstance(record, EvaluationRecord):
                raise TypeError("scalar reliability received a pairwise record")
            score = next(
                rating.score
                for rating in record.ratings
                if rating.criterion_id == criterion_id
            )
            row[submission.evaluator_id] = float(score)
        rows.append(row)
    return rows


def _scalar_criterion_units(
    spec: PopulationReliabilitySpec,
    criterion_id: str,
) -> list[list[Category]]:
    return [
        [int(value) for value in row.values()]
        for row in _scalar_criterion_rows(spec, criterion_id)
    ]


def _pairwise_criterion_units(
    spec: PopulationReliabilitySpec,
    criterion_id: str,
) -> list[list[str]]:
    units: list[list[str]] = []
    for task in spec.tasks:
        values: list[str] = []
        for submission in task.submissions:
            record = submission.record
            if not isinstance(record, PairwiseEvaluationRecord):
                raise TypeError("pairwise reliability received a scalar record")
            preference = next(
                judgment.preference.value
                for judgment in record.judgments
                if judgment.criterion_id == criterion_id
            )
            values.append(preference)
        units.append(values)
    return units


def _overall_preference_units(
    spec: PopulationReliabilitySpec,
) -> list[list[str]]:
    units: list[list[str]] = []
    for task in spec.tasks:
        values: list[str] = []
        for submission in task.submissions:
            record = submission.record
            if not isinstance(record, PairwiseEvaluationRecord):
                raise TypeError(
                    "overall preference reliability requires pairwise records"
                )
            values.append(record.overall_preference.value)
        units.append(values)
    return units


def _preference_strength_units(
    spec: PopulationReliabilitySpec,
) -> list[list[Category]]:
    units: list[list[Category]] = []
    for task in spec.tasks:
        values: list[Category] = []
        for submission in task.submissions:
            record = submission.record
            if not isinstance(record, PairwiseEvaluationRecord):
                raise TypeError(
                    "preference strength reliability requires pairwise records"
                )
            values.append(record.preference_strength)
        units.append(values)
    return units


def _aggregate_score_rows(
    reports: Sequence[CalibrationReport],
) -> list[dict[str, float]]:
    return [dict(report.aggregate_scores) for report in reports]


def build_population_reliability_report(
    spec: PopulationReliabilitySpec,
    rubric: Rubric,
) -> PopulationReliabilityReport:
    """Calculate repeated-task reliability under explicit metric assumptions."""

    reports = _validate_population(spec, rubric)
    first = reports[0]
    evaluator_sets = [set(report.evaluator_ids) for report in reports]
    evaluator_counts = [report.evaluator_count for report in reports]
    evaluator_ids = tuple(
        sorted(
            {
                evaluator_id
                for report in reports
                for evaluator_id in report.evaluator_ids
            }
        )
    )
    fixed_rater_count = len(set(evaluator_counts)) == 1
    fixed_evaluator_panel = all(
        panel == evaluator_sets[0] for panel in evaluator_sets[1:]
    )

    criterion_reports: dict[str, CriterionReliability] = {}
    if first.evaluation_type is EvaluationType.PAIRWISE:
        for criterion in rubric.criteria:
            units = _pairwise_criterion_units(spec, criterion.id)
            criterion_reports[criterion.id] = CriterionReliability(
                criterion_id=criterion.id,
                krippendorff_alpha=_krippendorff_alpha(
                    units,
                    scale="nominal",
                ),
                fleiss_kappa=_fleiss_kappa(
                    units,
                    categories=("a", "tie", "b"),
                ),
                icc_a1=_not_applicable(
                    "icc_a1_absolute_agreement",
                    "ICC(A,1) is not applied to categorical A/Tie/B judgments",
                    _ICC_A1_ASSUMPTIONS,
                ),
            )

        overall_units = _overall_preference_units(spec)
        overall_alpha = _krippendorff_alpha(overall_units, scale="nominal")
        overall_fleiss = _fleiss_kappa(
            overall_units,
            categories=("a", "tie", "b"),
        )
        strength_alpha = _krippendorff_alpha(
            _preference_strength_units(spec),
            scale="ordinal",
            ordinal_categories=(1, 2, 3),
        )
        aggregate_icc = _not_applicable(
            "icc_a1_absolute_agreement",
            "ICC(A,1) is not applied to the derived signed pairwise preference score",
            _ICC_A1_ASSUMPTIONS,
        )
    else:
        for criterion in rubric.criteria:
            units = _scalar_criterion_units(spec, criterion.id)
            criterion_reports[criterion.id] = CriterionReliability(
                criterion_id=criterion.id,
                krippendorff_alpha=_krippendorff_alpha(
                    units,
                    scale="ordinal",
                    ordinal_categories=(1, 2, 3, 4, 5),
                ),
                fleiss_kappa=_not_applicable(
                    "fleiss_kappa",
                    (
                        "scalar 1-5 ratings are ordinal; they are not silently "
                        "treated as nominal"
                    ),
                    _FLEISS_ASSUMPTIONS,
                ),
                icc_a1=_icc_a1(
                    _scalar_criterion_rows(spec, criterion.id)
                ),
            )

        overall_alpha = _not_applicable(
            "krippendorff_alpha_nominal",
            "overall A/Tie/B preference exists only for pairwise evaluations",
            (*_KRIPPENDORFF_BASE_ASSUMPTIONS, "categories are nominal"),
        )
        overall_fleiss = _not_applicable(
            "fleiss_kappa",
            "overall A/Tie/B preference exists only for pairwise evaluations",
            _FLEISS_ASSUMPTIONS,
        )
        strength_alpha = _not_applicable(
            "krippendorff_alpha_ordinal",
            "preference strength exists only for pairwise evaluations",
            (
                *_KRIPPENDORFF_BASE_ASSUMPTIONS,
                "categories are ordered and use Krippendorff ordinal distance",
            ),
        )
        aggregate_icc = _icc_a1(_aggregate_score_rows(reports))

    return PopulationReliabilityReport(
        evaluation_type=first.evaluation_type,
        rubric_id=first.rubric_id,
        rubric_version=first.rubric_version,
        task_count=len(spec.tasks),
        declared_minimum_task_count=spec.minimum_task_count,
        evaluator_ids=evaluator_ids,
        min_evaluators_per_task=min(evaluator_counts),
        max_evaluators_per_task=max(evaluator_counts),
        fixed_rater_count=fixed_rater_count,
        fixed_evaluator_panel=fixed_evaluator_panel,
        criterion_reliability=criterion_reports,
        aggregate_score_icc_a1=aggregate_icc,
        overall_preference_krippendorff_alpha=overall_alpha,
        overall_preference_fleiss_kappa=overall_fleiss,
        preference_strength_krippendorff_alpha=strength_alpha,
        notes=(
            (
                "Reliability coefficients describe consistency/agreement, "
                "not evaluator correctness."
            ),
            (
                "The declared minimum task count is an inclusion guardrail, "
                "not a universal claim of statistical sufficiency."
            ),
            (
                "No coefficient is automatically converted into a pass/fail "
                "threshold or evaluator rank."
            ),
        ),
    )


def reliability_spec_from_dict(data: dict[str, Any]) -> PopulationReliabilitySpec:
    """Build a repeated-task reliability spec from JSON-compatible data."""

    raw_minimum = data.get("minimum_task_count")
    if isinstance(raw_minimum, bool) or not isinstance(raw_minimum, int):
        raise ValueError("minimum_task_count must be an integer")
    raw_tasks = data.get("tasks")
    if not isinstance(raw_tasks, list):
        raise ValueError("reliability spec tasks must be a list")

    tasks: list[ReliabilityTask] = []
    for item in raw_tasks:
        if not isinstance(item, dict):
            raise ValueError("each reliability task must be an object")
        tasks.append(
            ReliabilityTask(
                submissions=calibration_spec_from_dict(item),
            )
        )
    return PopulationReliabilitySpec(
        minimum_task_count=raw_minimum,
        tasks=tuple(tasks),
    )


def load_reliability_spec(path: Path) -> PopulationReliabilitySpec:
    """Load a UTF-8 repeated-task reliability specification."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("reliability file must contain one JSON object")
    return reliability_spec_from_dict(data)


def population_reliability_report_to_dict(
    report: PopulationReliabilityReport,
) -> dict[str, Any]:
    """Convert a reliability report into JSON-compatible data."""

    return asdict(report)


def write_population_reliability_report(
    path: Path,
    report: PopulationReliabilityReport,
) -> None:
    """Atomically write a population reliability report as UTF-8 JSON."""

    payload = json.dumps(
        population_reliability_report_to_dict(report),
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
