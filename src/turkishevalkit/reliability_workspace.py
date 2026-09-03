"""Local browser adapter for repeated-task population reliability."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .calibration import EvaluatorSubmission
from .reliability import (
    PopulationReliabilitySpec,
    ReliabilityTask,
    build_population_reliability_report,
    population_reliability_report_to_dict,
)
from .rubrics import BUILTIN_RUBRICS
from .workspace_evaluations import (
    WorkspaceEvaluation,
    list_workspace_evaluations,
    load_evaluator_id,
    load_saved_record,
)

if TYPE_CHECKING:
    from flask import Blueprint

_MAX_TASK_GROUPS = 250
_MAX_FILENAMES_PER_GROUP = 100


@dataclass(frozen=True, slots=True)
class ReliabilityCandidateGroup:
    """One same-stimulus workspace group that may form a reliability task unit."""

    compatibility_key: str
    dataset_key: str
    task_id: str
    evaluation_type: str
    rubric_id: str
    rubric_version: str
    artifacts: tuple[WorkspaceEvaluation, ...]
    ready: bool
    reasons: tuple[str, ...]


def _dataset_key(item: WorkspaceEvaluation) -> str:
    identity = {
        "evaluation_type": item.record.evaluation_type.value,
        "rubric_id": item.record.rubric_id,
        "rubric_version": item.record.rubric_version,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _group_reasons(items: Sequence[WorkspaceEvaluation]) -> tuple[str, ...]:
    reasons: list[str] = []
    unattributed = sum(item.evaluator_id is None for item in items)
    if unattributed:
        reasons.append(
            f"{unattributed} evaluation(s) have no trusted evaluator attribution"
        )

    evaluator_ids = [item.evaluator_id for item in items if item.evaluator_id is not None]
    duplicates = sorted(
        evaluator_id
        for evaluator_id, count in Counter(evaluator_ids).items()
        if count > 1
    )
    if duplicates:
        reasons.append(
            "duplicate evaluator attribution in this task group: " + ", ".join(duplicates)
        )

    if len(items) < 2:
        reasons.append("reliability task groups require at least two evaluations")
    elif len(evaluator_ids) < 2:
        reasons.append("reliability task groups require at least two attributed evaluators")
    return tuple(reasons)


def list_reliability_candidate_groups(
    workspace: Path,
) -> list[ReliabilityCandidateGroup]:
    """Group local evaluations by same-stimulus compatibility for browser selection."""

    grouped: dict[str, list[WorkspaceEvaluation]] = defaultdict(list)
    for item in list_workspace_evaluations(workspace):
        grouped[item.compatibility_key].append(item)

    groups: list[ReliabilityCandidateGroup] = []
    for compatibility_key, items in grouped.items():
        first = items[0]
        reasons = _group_reasons(items)
        groups.append(
            ReliabilityCandidateGroup(
                compatibility_key=compatibility_key,
                dataset_key=_dataset_key(first),
                task_id=first.record.task_id,
                evaluation_type=first.record.evaluation_type.value,
                rubric_id=first.record.rubric_id,
                rubric_version=first.record.rubric_version,
                artifacts=tuple(items),
                ready=not reasons,
                reasons=reasons,
            )
        )

    groups.sort(
        key=lambda group: (
            not group.ready,
            group.evaluation_type,
            group.rubric_id,
            group.task_id.casefold(),
            group.compatibility_key,
        )
    )
    return groups


def reliability_candidate_group_to_dict(
    group: ReliabilityCandidateGroup,
) -> dict[str, Any]:
    """Serialize one candidate group without exposing evaluator record payloads."""

    return {
        "compatibility_key": group.compatibility_key,
        "dataset_key": group.dataset_key,
        "task_id": group.task_id,
        "evaluation_type": group.evaluation_type,
        "rubric_id": group.rubric_id,
        "rubric_version": group.rubric_version,
        "evaluator_count": len(
            {item.evaluator_id for item in group.artifacts if item.evaluator_id is not None}
        ),
        "artifact_count": len(group.artifacts),
        "ready": group.ready,
        "reasons": list(group.reasons),
        "artifacts": [
            {
                "filename": item.filename,
                "evaluator_id": item.evaluator_id,
                "saved_at": item.saved_at,
                "normalized_score": item.saved_result.get("normalized_score"),
                "preference_score": item.saved_result.get("preference_score"),
                "overall_preference": item.saved_result.get("overall_preference"),
            }
            for item in group.artifacts
        ],
    }


def _filenames_from_group(raw_group: Any, *, index: int) -> tuple[str, ...]:
    if not isinstance(raw_group, dict):
        raise ValueError(f"group {index} must be an object")
    raw_filenames = raw_group.get("filenames")
    if not isinstance(raw_filenames, list):
        raise ValueError(f"group {index} filenames must be a list")
    if not 2 <= len(raw_filenames) <= _MAX_FILENAMES_PER_GROUP:
        raise ValueError(
            f"group {index} must contain between 2 and {_MAX_FILENAMES_PER_GROUP} filenames"
        )
    if not all(isinstance(value, str) and value.strip() for value in raw_filenames):
        raise ValueError(f"group {index} filenames must contain non-empty strings")
    filenames = tuple(str(value).strip() for value in raw_filenames)
    if len(filenames) != len(set(filenames)):
        raise ValueError(f"group {index} filenames must be unique")
    return filenames


def _build_task_from_filenames(
    workspace: Path,
    filenames: Sequence[str],
) -> ReliabilityTask:
    submissions: list[EvaluatorSubmission] = []
    evaluator_ids: set[str] = set()
    for filename in filenames:
        record, _ = load_saved_record(workspace, filename)
        evaluator_id = load_evaluator_id(workspace, filename)
        if evaluator_id is None:
            raise ValueError(
                f"{filename} has no trusted evaluator identity; create it with a workflow session"
            )
        if evaluator_id in evaluator_ids:
            raise ValueError(
                "each reliability task requires unique evaluator identities; "
                f"duplicate evaluator_id: {evaluator_id}"
            )
        evaluator_ids.add(evaluator_id)
        submissions.append(EvaluatorSubmission(evaluator_id=evaluator_id, record=record))
    return ReliabilityTask(submissions=tuple(submissions))


def build_workspace_reliability_report(
    workspace: Path,
    *,
    minimum_task_count: int,
    groups: Sequence[Any],
) -> dict[str, Any]:
    """Rebuild selected canonical task groups and invoke the existing reliability core."""

    if minimum_task_count < 3:
        raise ValueError("minimum_task_count must be at least 3")
    if not minimum_task_count <= len(groups) <= _MAX_TASK_GROUPS:
        raise ValueError(
            "selected groups must satisfy minimum_task_count and contain at most "
            f"{_MAX_TASK_GROUPS} task groups"
        )

    all_filenames: set[str] = set()
    tasks: list[ReliabilityTask] = []
    for index, raw_group in enumerate(groups, start=1):
        filenames = _filenames_from_group(raw_group, index=index)
        overlap = all_filenames.intersection(filenames)
        if overlap:
            raise ValueError(
                "the same evaluation artifact cannot be reused across reliability task groups: "
                + ", ".join(sorted(overlap))
            )
        all_filenames.update(filenames)
        tasks.append(_build_task_from_filenames(workspace, filenames))

    spec = PopulationReliabilitySpec(
        minimum_task_count=minimum_task_count,
        tasks=tuple(tasks),
    )
    first_record = tasks[0].submissions[0].record
    rubric = BUILTIN_RUBRICS.get(first_record.rubric_id)
    if rubric is None:
        raise ValueError(f"unknown rubric: {first_record.rubric_id}")
    report = build_population_reliability_report(spec, rubric)
    return population_reliability_report_to_dict(report)


def create_reliability_blueprint(workspace: Path) -> Blueprint:
    """Create reliability workspace routes bound to one local workbench workspace."""

    try:
        from flask import Blueprint, abort, jsonify, render_template, request
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'The reliability workspace requires the workbench dependency. '
            'Install with: python -m pip install "turkishevalkit[workbench]"'
        ) from exc

    blueprint = Blueprint("reliability_workspace", __name__)

    @blueprint.get("/reliability")
    def reliability_page() -> str:
        return render_template("reliability.html")

    @blueprint.get("/api/reliability/candidates")
    def reliability_candidates() -> Any:
        groups = list_reliability_candidate_groups(workspace)
        return jsonify(
            {
                "groups": [reliability_candidate_group_to_dict(group) for group in groups],
                "minimum_task_count_floor": 3,
            }
        )

    @blueprint.post("/api/reliability/analyze")
    def reliability_analyze() -> tuple[Any, int] | Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "request body must be a JSON object"}), 400

        raw_minimum = payload.get("minimum_task_count", 3)
        if isinstance(raw_minimum, bool) or not isinstance(raw_minimum, int):
            return jsonify({"error": "minimum_task_count must be an integer"}), 400
        raw_groups = payload.get("groups")
        if not isinstance(raw_groups, list):
            return jsonify({"error": "groups must be a list"}), 400

        try:
            report = build_workspace_reliability_report(
                workspace,
                minimum_task_count=raw_minimum,
                groups=raw_groups,
            )
        except FileNotFoundError:
            abort(404)
        except (OSError, TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"report": report})

    return blueprint
