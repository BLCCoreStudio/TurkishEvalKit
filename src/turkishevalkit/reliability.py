"""Repeated-task reliability-study validation and structural eligibility diagnostics."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .evaluation import evaluate_submission
from .models import EvaluationRecord, EvaluationType, PairwiseEvaluationRecord, Rubric
from .pairwise import evaluate_pairwise_submission
from .serialization import record_from_dict


@dataclass(frozen=True, slots=True)
class ReliabilityObservation:
    """One evaluator's complete judgment for one repeated-task study item."""

    evaluator_id: str
    record: EvaluationRecord | PairwiseEvaluationRecord
    artifact_id: str | None = None

    def __post_init__(self) -> None:
        if not self.evaluator_id.strip():
            raise ValueError("evaluator_id must not be empty")
        if self.artifact_id is not None and not self.artifact_id.strip():
            raise ValueError("artifact_id must not be empty when provided")


@dataclass(frozen=True, slots=True)
class TaskCoverage:
    """Observed evaluator coverage for one study task."""

    task_id: str
    evaluator_ids: tuple[str, ...]
    observation_count: int
    source_signature: str
    comparable: bool


@dataclass(frozen=True, slots=True)
class EvaluatorCoverage:
    """Observed task coverage for one evaluator."""

    evaluator_id: str
    task_ids: tuple[str, ...]
    observation_count: int
    coverage_rate: float


@dataclass(frozen=True, slots=True)
class MetricEligibility:
    """Structural readiness for one future reliability statistic."""

    metric_id: str
    structurally_eligible: bool
    blocked_reasons: tuple[str, ...]
    required_decisions: tuple[str, ...]
    assumptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReliabilityStudyReport:
    """Validated repeated-task study structure without claiming a reliability score."""

    study_id: str
    evaluation_type: EvaluationType
    rubric_id: str
    rubric_version: str
    task_count: int
    comparable_task_count: int
    evaluator_count: int
    observation_count: int
    expected_panel_cells: int
    missing_panel_cells: int
    coverage_rate: float
    balanced_panel: bool
    min_raters_per_task: int
    max_raters_per_task: int
    task_coverage: tuple[TaskCoverage, ...]
    evaluator_coverage: tuple[EvaluatorCoverage, ...]
    metric_eligibility: tuple[MetricEligibility, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReliabilityStudySpec:
    """Parsed study input with explicit study identity and observations."""

    study_id: str
    observations: tuple[ReliabilityObservation, ...]

    def __post_init__(self) -> None:
        if not self.study_id.strip():
            raise ValueError("study_id must not be empty")
        if not self.observations:
            raise ValueError("reliability study must contain observations")


def _source_signature(source: dict[str, Any]) -> str:
    canonical = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_record(record: EvaluationRecord | PairwiseEvaluationRecord, rubric: Rubric) -> None:
    if isinstance(record, PairwiseEvaluationRecord):
        evaluate_pairwise_submission(record, rubric)
    else:
        evaluate_submission(record, rubric)


def _study_shape(
    observations: tuple[ReliabilityObservation, ...],
    rubric: Rubric,
) -> tuple[
    EvaluationType,
    dict[str, list[ReliabilityObservation]],
    tuple[str, ...],
    dict[str, str],
]:
    first = observations[0].record
    evaluation_type = first.evaluation_type
    if rubric.id != first.rubric_id or rubric.version != first.rubric_version:
        raise ValueError("study rubric does not match the first observation")
    if rubric.evaluation_type is not evaluation_type:
        raise ValueError("study rubric evaluation_type does not match observations")

    by_task: dict[str, list[ReliabilityObservation]] = defaultdict(list)
    task_sources: dict[str, str] = {}
    seen_evaluator_task: set[tuple[str, str]] = set()
    evaluator_ids: set[str] = set()

    for observation in observations:
        record = observation.record
        if record.evaluation_type is not evaluation_type:
            raise ValueError("all reliability observations must use one evaluation_type")
        if record.rubric_id != rubric.id or record.rubric_version != rubric.version:
            raise ValueError("all reliability observations must use the same rubric id/version")
        _validate_record(record, rubric)

        identity = (observation.evaluator_id, record.task_id)
        if identity in seen_evaluator_task:
            raise ValueError(
                "reliability study cannot contain multiple observations for the same evaluator/task"
            )
        seen_evaluator_task.add(identity)
        evaluator_ids.add(observation.evaluator_id)

        signature = _source_signature(record.source)
        previous = task_sources.get(record.task_id)
        if previous is not None and previous != signature:
            raise ValueError(
                f"task_id '{record.task_id}' maps to multiple source stimuli in one study"
            )
        task_sources[record.task_id] = signature
        by_task[record.task_id].append(observation)

    if len(by_task) < 2:
        raise ValueError("reliability study requires at least two distinct task_id values")
    if len(evaluator_ids) < 2:
        raise ValueError("reliability study requires at least two unique evaluators")

    return evaluation_type, by_task, tuple(sorted(evaluator_ids)), task_sources


def _eligibility(
    *,
    evaluation_type: EvaluationType,
    task_count: int,
    comparable_task_count: int,
    evaluator_count: int,
    balanced_panel: bool,
    min_raters: int,
    max_raters: int,
) -> tuple[MetricEligibility, ...]:
    scalar = evaluation_type is not EvaluationType.PAIRWISE
    enough_comparable_tasks = comparable_task_count >= 2

    cohen_reasons: list[str] = []
    if evaluator_count != 2:
        cohen_reasons.append("requires exactly two evaluators")
    if not balanced_panel:
        cohen_reasons.append("requires both evaluators to rate every included task")
    if task_count < 2:
        cohen_reasons.append("requires at least two repeated tasks")
    if not enough_comparable_tasks:
        cohen_reasons.append("requires at least two tasks with two or more ratings")

    fleiss_reasons: list[str] = []
    if not enough_comparable_tasks:
        fleiss_reasons.append("requires at least two tasks with two or more ratings")
    if min_raters != max_raters:
        fleiss_reasons.append("classic Fleiss kappa requires a constant rating count per task")
    if min_raters < 2:
        fleiss_reasons.append("requires at least two ratings per included task")

    alpha_reasons: list[str] = []
    if not enough_comparable_tasks:
        alpha_reasons.append("requires at least two tasks with two or more ratings")

    icc_reasons: list[str] = []
    if not scalar:
        icc_reasons.append("ICC is not defined here for A/Tie/B pairwise preference categories")
    if not balanced_panel:
        icc_reasons.append("the supported future ICC designs require a complete evaluator/task panel")
    if evaluator_count < 2 or task_count < 2:
        icc_reasons.append("requires at least two evaluators and two tasks")

    if scalar:
        cohen_decisions = (
            "choose weighted-kappa weighting (linear or quadratic) for ordinal 1..5 ratings",
            "predefine how confidence intervals will be estimated",
        )
        fleiss_decisions = (
            "decide whether treating ordinal 1..5 ratings as nominal categories is acceptable",
            "predefine the inference/uncertainty method",
        )
        alpha_decisions = (
            "choose ordinal distance for Krippendorff alpha",
            "predefine missing-data inclusion and uncertainty policy",
        )
    else:
        cohen_decisions = (
            "choose nominal or explicitly justified ordinal treatment for A/Tie/B",
            "predefine how confidence intervals will be estimated",
        )
        fleiss_decisions = (
            "confirm A/Tie/B is treated as nominal for classic Fleiss kappa",
            "predefine the inference/uncertainty method",
        )
        alpha_decisions = (
            "choose nominal or explicitly justified ordinal distance for A/Tie/B",
            "predefine missing-data inclusion and uncertainty policy",
        )

    return (
        MetricEligibility(
            metric_id="cohen_kappa",
            structurally_eligible=not cohen_reasons,
            blocked_reasons=tuple(cohen_reasons),
            required_decisions=cohen_decisions,
            assumptions=(
                "criterion-level categories are compared across the same repeated tasks",
                "structural eligibility does not imply adequate sample size or stable inference",
            ),
        ),
        MetricEligibility(
            metric_id="fleiss_kappa",
            structurally_eligible=not fleiss_reasons,
            blocked_reasons=tuple(fleiss_reasons),
            required_decisions=fleiss_decisions,
            assumptions=(
                "classic Fleiss kappa expects a fixed number of ratings per task",
                "structural eligibility does not imply adequate sample size or stable inference",
            ),
        ),
        MetricEligibility(
            metric_id="krippendorff_alpha",
            structurally_eligible=not alpha_reasons,
            blocked_reasons=tuple(alpha_reasons),
            required_decisions=alpha_decisions,
            assumptions=(
                "alpha may tolerate an unbalanced panel, but each analyzed unit needs usable ratings",
                "distance/measurement level must be selected before computation",
            ),
        ),
        MetricEligibility(
            metric_id="icc",
            structurally_eligible=not icc_reasons,
            blocked_reasons=tuple(icc_reasons),
            required_decisions=(
                "select the ICC model (one-way/two-way and random/mixed effects)",
                "select consistency versus absolute-agreement target",
                "select single-measure versus average-measure reporting",
            ),
            assumptions=(
                "ICC treats criterion ratings as numeric measurements",
                "the intended population and rater effects must be defined before interpretation",
            ),
        ),
    )


def build_reliability_study_report(
    study_id: str,
    observations: tuple[ReliabilityObservation, ...],
    rubric: Rubric,
) -> ReliabilityStudyReport:
    """Validate a repeated-task dataset and report coverage/metric readiness."""

    if not study_id.strip():
        raise ValueError("study_id must not be empty")
    if not observations:
        raise ValueError("reliability study must contain observations")

    evaluation_type, by_task, evaluator_ids, task_sources = _study_shape(observations, rubric)
    task_ids = tuple(sorted(by_task))
    task_count = len(task_ids)
    evaluator_count = len(evaluator_ids)

    task_coverage: list[TaskCoverage] = []
    evaluator_tasks: dict[str, set[str]] = {evaluator_id: set() for evaluator_id in evaluator_ids}
    raters_per_task: list[int] = []
    for task_id in task_ids:
        task_evaluators = tuple(sorted(item.evaluator_id for item in by_task[task_id]))
        raters_per_task.append(len(task_evaluators))
        for evaluator_id in task_evaluators:
            evaluator_tasks[evaluator_id].add(task_id)
        task_coverage.append(
            TaskCoverage(
                task_id=task_id,
                evaluator_ids=task_evaluators,
                observation_count=len(task_evaluators),
                source_signature=task_sources[task_id],
                comparable=len(task_evaluators) >= 2,
            )
        )

    observation_count = len(observations)
    expected_cells = task_count * evaluator_count
    missing_cells = expected_cells - observation_count
    coverage_rate = observation_count / expected_cells
    balanced_panel = missing_cells == 0
    min_raters = min(raters_per_task)
    max_raters = max(raters_per_task)
    comparable_task_count = sum(1 for count in raters_per_task if count >= 2)

    evaluator_coverage = tuple(
        EvaluatorCoverage(
            evaluator_id=evaluator_id,
            task_ids=tuple(sorted(evaluator_tasks[evaluator_id])),
            observation_count=len(evaluator_tasks[evaluator_id]),
            coverage_rate=len(evaluator_tasks[evaluator_id]) / task_count,
        )
        for evaluator_id in evaluator_ids
    )

    warnings: list[str] = []
    single_rater = [task_id for task_id, items in by_task.items() if len(items) < 2]
    if single_rater:
        warnings.append(
            "single-rater tasks cannot contribute pairwise reliability evidence: "
            + ", ".join(sorted(single_rater))
        )
    if not balanced_panel:
        warnings.append(
            "study panel is unbalanced; missing evaluator/task cells must be handled explicitly"
        )
    if min_raters != max_raters:
        warnings.append("rating counts vary across tasks")

    sources_to_tasks: dict[str, list[str]] = defaultdict(list)
    for task_id, signature in task_sources.items():
        sources_to_tasks[signature].append(task_id)
    duplicated_sources = [
        tuple(sorted(ids)) for ids in sources_to_tasks.values() if len(ids) > 1
    ]
    for ids in sorted(duplicated_sources):
        warnings.append(
            "identical source stimulus appears under multiple task_id values: " + ", ".join(ids)
        )

    return ReliabilityStudyReport(
        study_id=study_id.strip(),
        evaluation_type=evaluation_type,
        rubric_id=rubric.id,
        rubric_version=rubric.version,
        task_count=task_count,
        comparable_task_count=comparable_task_count,
        evaluator_count=evaluator_count,
        observation_count=observation_count,
        expected_panel_cells=expected_cells,
        missing_panel_cells=missing_cells,
        coverage_rate=coverage_rate,
        balanced_panel=balanced_panel,
        min_raters_per_task=min_raters,
        max_raters_per_task=max_raters,
        task_coverage=tuple(task_coverage),
        evaluator_coverage=evaluator_coverage,
        metric_eligibility=_eligibility(
            evaluation_type=evaluation_type,
            task_count=task_count,
            comparable_task_count=comparable_task_count,
            evaluator_count=evaluator_count,
            balanced_panel=balanced_panel,
            min_raters=min_raters,
            max_raters=max_raters,
        ),
        warnings=tuple(warnings),
    )


def reliability_report_to_dict(report: ReliabilityStudyReport) -> dict[str, Any]:
    """Convert a reliability-study report to JSON-compatible data."""

    return asdict(report)


def load_reliability_study_spec(path: Path) -> ReliabilityStudySpec:
    """Load a repeated-task reliability study JSON specification."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("reliability study file must contain one JSON object")
    study_id = data.get("study_id")
    raw_observations = data.get("observations")
    if not isinstance(study_id, str) or not study_id.strip():
        raise ValueError("reliability study requires a non-empty study_id")
    if not isinstance(raw_observations, list) or not raw_observations:
        raise ValueError("reliability study requires a non-empty observations list")

    observations: list[ReliabilityObservation] = []
    for index, raw in enumerate(raw_observations, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"observation {index} must be an object")
        evaluator_id = raw.get("evaluator_id")
        raw_record = raw.get("evaluation")
        artifact_id = raw.get("artifact_id")
        if not isinstance(evaluator_id, str) or not evaluator_id.strip():
            raise ValueError(f"observation {index} requires evaluator_id")
        if not isinstance(raw_record, dict):
            raise ValueError(f"observation {index} requires an evaluation object")
        if artifact_id is not None and not isinstance(artifact_id, str):
            raise ValueError(f"observation {index} artifact_id must be a string when provided")
        observations.append(
            ReliabilityObservation(
                evaluator_id=evaluator_id,
                record=record_from_dict(raw_record),
                artifact_id=artifact_id,
            )
        )
    return ReliabilityStudySpec(study_id=study_id, observations=tuple(observations))
