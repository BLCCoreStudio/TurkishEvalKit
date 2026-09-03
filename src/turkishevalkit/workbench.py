"""Local browser workbench backed by evaluation, review, revision, calibration, and reliability cores."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias

from .calibration_dashboard import create_calibration_blueprint
from .evaluation import EvaluationResult, evaluate_submission
from .metadata_index import load_indexed_history
from .models import PairwiseEvaluationRecord
from .pairwise import PairwiseEvaluationResult, evaluate_pairwise_submission
from .reliability_workspace import create_reliability_blueprint
from .revision import (
    RevisionLineage,
    create_revision_lineage,
    revision_from_dict,
    revision_to_dict,
)
from .rubrics import BUILTIN_RUBRICS
from .serialization import (
    record_from_dict,
    result_to_dict,
    workflow_from_dict,
    workflow_to_dict,
)
from .workflow import (
    AdjudicationOutcome,
    EvaluationWorkflow,
    ReviewOutcome,
    WorkflowState,
    adjudicate_workflow,
    create_workflow,
    mark_revision_created,
    review_workflow,
    submit_workflow,
)

if TYPE_CHECKING:
    from flask import Flask

_FILENAME_SAFE = re.compile(r"[^\w.-]+", flags=re.UNICODE)
SavedResult: TypeAlias = EvaluationResult | PairwiseEvaluationResult


def default_workspace() -> Path:
    """Return a platform-appropriate local data directory."""

    if os.name == "nt":
        configured = os.environ.get("LOCALAPPDATA")
        base = Path(configured) if configured else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        configured = os.environ.get("XDG_DATA_HOME")
        base = Path(configured) if configured else Path.home() / ".local" / "share"
    return base / "turkishevalkit"


def rubric_payload() -> list[dict[str, Any]]:
    """Return built-in rubrics in a stable JSON-friendly shape."""

    return [
        {
            "id": rubric.id,
            "version": rubric.version,
            "title": rubric.title,
            "evaluation_type": rubric.evaluation_type.value,
            "criteria": [
                {
                    "id": criterion.id,
                    "label": criterion.label,
                    "description": criterion.description,
                    "weight": criterion.weight,
                }
                for criterion in rubric.criteria
            ],
        }
        for rubric in BUILTIN_RUBRICS.values()
    ]


def _evaluation_dir(workspace: Path) -> Path:
    return workspace / "evaluations"


def _workflow_dir(workspace: Path) -> Path:
    return workspace / "workflows"


def _revision_dir(workspace: Path) -> Path:
    return workspace / "revisions"


def _safe_task_id(task_id: str) -> str:
    cleaned = _FILENAME_SAFE.sub("-", task_id.strip()).strip("._-")
    return (cleaned or "evaluation")[:80]


def _valid_artifact_id(artifact_id: str) -> bool:
    return artifact_id == Path(artifact_id).name and artifact_id.endswith(".json")


def _workflow_path(workspace: Path, artifact_id: str) -> Path:
    if not _valid_artifact_id(artifact_id):
        raise ValueError("invalid evaluation artifact id")
    return _workflow_dir(workspace) / f"{artifact_id[:-5]}.workflow.json"


def _revision_path(workspace: Path, artifact_id: str) -> Path:
    if not _valid_artifact_id(artifact_id):
        raise ValueError("invalid evaluation artifact id")
    return _revision_dir(workspace) / f"{artifact_id[:-5]}.revision.json"


def save_result(workspace: Path, result: SavedResult) -> Path:
    """Persist a scored result using an append-only filename."""

    directory = _evaluation_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = directory / f"{_safe_task_id(result.task_id)}-{timestamp}.json"
    temporary = destination.with_suffix(".json.tmp")
    payload = json.dumps(result_to_dict(result), ensure_ascii=False, indent=2) + "\n"
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(destination)
    return destination


def save_workflow(workspace: Path, workflow: EvaluationWorkflow) -> Path:
    """Atomically rewrite the workflow snapshot while preserving its full event chain."""

    destination = _workflow_path(workspace, workflow.artifact_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    payload = json.dumps(workflow_to_dict(workflow), ensure_ascii=False, indent=2) + "\n"
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_workflow(workspace: Path, artifact_id: str) -> EvaluationWorkflow | None:
    """Load and validate one workflow sidecar, returning None when it does not exist."""

    path = _workflow_path(workspace, artifact_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid workflow JSON for {artifact_id}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("workflow file must contain one JSON object")
    workflow = workflow_from_dict(payload)
    if workflow.artifact_id != artifact_id:
        raise ValueError("workflow artifact id does not match its filename")
    return workflow


def save_revision_lineage(workspace: Path, lineage: RevisionLineage) -> Path:
    """Persist one immutable revision sidecar for a newly created artifact."""

    destination = _revision_path(workspace, lineage.artifact_id)
    if destination.exists():
        raise ValueError("revision lineage already exists for this artifact")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    payload = json.dumps(revision_to_dict(lineage), ensure_ascii=False, indent=2) + "\n"
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_revision_lineage(workspace: Path, artifact_id: str) -> RevisionLineage | None:
    """Load one revision lineage sidecar, returning None for an original artifact."""

    path = _revision_path(workspace, artifact_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid revision JSON for {artifact_id}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("revision file must contain one JSON object")
    lineage = revision_from_dict(payload)
    if lineage.artifact_id != artifact_id:
        raise ValueError("revision artifact id does not match its filename")
    return lineage


def _revision_index(
    workspace: Path,
) -> tuple[dict[str, RevisionLineage], dict[str, str]]:
    """Return valid child lineages plus parent-to-child links, isolating corrupt sidecars."""

    by_artifact: dict[str, RevisionLineage] = {}
    child_by_parent: dict[str, str] = {}
    directory = _revision_dir(workspace)
    if not directory.exists():
        return by_artifact, child_by_parent
    for path in directory.glob("*.revision.json"):
        artifact_id = f"{path.name[:-14]}.json"
        try:
            lineage = load_revision_lineage(workspace, artifact_id)
        except (OSError, ValueError):
            continue
        if lineage is None or lineage.supersedes_artifact_id in child_by_parent:
            continue
        by_artifact[lineage.artifact_id] = lineage
        child_by_parent[lineage.supersedes_artifact_id] = lineage.artifact_id
    return by_artifact, child_by_parent


def _workflow_summary(workflow: EvaluationWorkflow | None) -> dict[str, Any]:
    if workflow is None:
        return {
            "workflow_state": None,
            "session_id": None,
            "evaluator_id": None,
            "review_outcome": None,
            "adjudication_outcome": None,
            "superseded_by": None,
        }
    return {
        "workflow_state": workflow.state.value,
        "session_id": workflow.session.session_id,
        "evaluator_id": workflow.session.evaluator_id,
        "review_outcome": (
            workflow.review_outcome.value if workflow.review_outcome is not None else None
        ),
        "adjudication_outcome": (
            workflow.adjudication_outcome.value
            if workflow.adjudication_outcome is not None
            else None
        ),
        "superseded_by": workflow.superseded_by,
    }


def _lineage_summary(
    lineage: RevisionLineage | None,
    *,
    superseded_by: str | None,
) -> dict[str, Any]:
    return {
        "revision_number": lineage.revision_number if lineage is not None else 0,
        "root_artifact_id": lineage.root_artifact_id if lineage is not None else None,
        "supersedes_artifact_id": (
            lineage.supersedes_artifact_id if lineage is not None else None
        ),
        "superseded_by": superseded_by,
    }


def scan_history(workspace: Path) -> list[dict[str, Any]]:
    """Scan canonical JSON artifacts and derive history metadata newest first."""

    directory = _evaluation_dir(workspace)
    if not directory.exists():
        return []
    lineages, child_by_parent = _revision_index(workspace)
    entries: list[dict[str, Any]] = []
    paths = sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        try:
            workflow = load_workflow(workspace, path.name)
        except (OSError, ValueError):
            workflow = None
        record = payload.get("payload")
        record_payload = record if isinstance(record, dict) else {}
        saved_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
        workflow_summary = _workflow_summary(workflow)
        superseded_by = child_by_parent.get(path.name) or workflow_summary["superseded_by"]
        entries.append(
            {
                "filename": path.name,
                "task_id": str(payload.get("task_id", "")),
                "evaluation_type": str(record_payload.get("evaluation_type", "")),
                "rubric_id": str(payload.get("rubric_id", "")),
                "rubric_version": str(payload.get("rubric_version", "")),
                "weighted_score": payload.get("weighted_score"),
                "normalized_score": payload.get("normalized_score"),
                "preference_score": payload.get("preference_score"),
                "overall_preference": payload.get("overall_preference"),
                "preference_strength": payload.get("preference_strength"),
                "saved_at": saved_at,
                **workflow_summary,
                **_lineage_summary(lineages.get(path.name), superseded_by=superseded_by),
            }
        )
    return entries


def list_history(workspace: Path) -> list[dict[str, Any]]:
    """Use a fresh optional index when available, otherwise scan canonical artifacts."""

    indexed = load_indexed_history(workspace)
    if indexed is not None:
        return indexed
    return scan_history(workspace)


def _read_evaluation(workspace: Path, artifact_id: str) -> dict[str, Any]:
    if not _valid_artifact_id(artifact_id):
        raise FileNotFoundError(artifact_id)
    path = _evaluation_dir(workspace) / artifact_id
    if not path.is_file():
        raise FileNotFoundError(artifact_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("evaluation artifact must contain one JSON object")
    return payload


def _workflow_context(payload: dict[str, Any]) -> tuple[str, str] | None:
    raw = payload.get("workflow_context")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("workflow_context must be an object")
    session_id = str(raw.get("session_id", "")).strip()
    evaluator_id = str(raw.get("evaluator_id", "")).strip()
    if not session_id or not evaluator_id:
        raise ValueError("workflow_context requires session_id and evaluator_id")
    return session_id, evaluator_id


def _score_record(record: Any) -> SavedResult:
    rubric = BUILTIN_RUBRICS.get(record.rubric_id)
    if rubric is None:
        raise ValueError(f"unknown rubric: {record.rubric_id}")
    if isinstance(record, PairwiseEvaluationRecord):
        return evaluate_pairwise_submission(record, rubric)
    return evaluate_submission(record, rubric)


def _saved_record(saved: dict[str, Any]) -> Any:
    raw = saved.get("payload")
    if not isinstance(raw, dict):
        raise ValueError("evaluation artifact does not contain a valid payload record")
    return record_from_dict(raw)


def _validate_revision_compatibility(parent: Any, revision: Any) -> None:
    checks = (
        (revision.task_id == parent.task_id, "task_id"),
        (revision.evaluation_type == parent.evaluation_type, "evaluation_type"),
        (revision.rubric_id == parent.rubric_id, "rubric_id"),
        (revision.rubric_version == parent.rubric_version, "rubric_version"),
        (revision.source == parent.source, "source stimulus"),
    )
    for matches, label in checks:
        if not matches:
            raise ValueError(f"revision must preserve the original {label}")


def _revision_request_note(workflow: EvaluationWorkflow) -> tuple[str, str]:
    for event in reversed(workflow.events):
        if event.review_outcome is ReviewOutcome.REQUEST_CHANGES:
            return event.actor_id, event.note
    raise ValueError("revision creation requires a request-changes review")


def create_app(workspace: Path | None = None) -> Flask:
    """Create the local Flask application without importing Flask at package import time."""

    try:
        from flask import Flask, abort, jsonify, render_template, request, send_from_directory
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'The local workbench requires the optional dependency. '
            'Install with: python -m pip install "turkishevalkit[workbench]"'
        ) from exc

    resolved_workspace = (workspace or default_workspace()).expanduser().resolve()
    app = Flask(__name__)
    app.register_blueprint(create_calibration_blueprint(resolved_workspace))
    app.register_blueprint(create_reliability_blueprint(resolved_workspace))

    @app.get("/")
    def index() -> str:
        return render_template("workbench.html")

    @app.get("/api/config")
    def config() -> Any:
        return jsonify(
            {
                "rubrics": rubric_payload(),
                "workspace": str(resolved_workspace),
                "workflow": {
                    "review_outcomes": [item.value for item in ReviewOutcome],
                    "adjudication_outcomes": [item.value for item in AdjudicationOutcome],
                },
            }
        )

    @app.get("/api/history")
    def history() -> Any:
        return jsonify({"items": list_history(resolved_workspace)})

    @app.post("/api/evaluations")
    def create_evaluation() -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "request body must be a JSON object"}), 400
        destination: Path | None = None
        try:
            context = _workflow_context(payload)
            record = record_from_dict(payload)
            result = _score_record(record)
            destination = save_result(resolved_workspace, result)
            workflow: EvaluationWorkflow | None = None
            if context is not None:
                session_id, evaluator_id = context
                workflow = create_workflow(
                    artifact_id=destination.name,
                    task_id=result.task_id,
                    session_id=session_id,
                    evaluator_id=evaluator_id,
                )
                try:
                    save_workflow(resolved_workspace, workflow)
                except OSError:
                    destination.unlink(missing_ok=True)
                    raise
        except (OSError, TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return (
            jsonify(
                {
                    "filename": destination.name,
                    "result": result_to_dict(result),
                    "workflow": workflow_to_dict(workflow) if workflow is not None else None,
                    "revision": None,
                }
            ),
            201,
        )

    @app.post("/api/evaluations/<filename>/revisions")
    def create_revision(filename: str) -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "request body must be a JSON object"}), 400
        destination: Path | None = None
        child_workflow_path: Path | None = None
        lineage_path: Path | None = None
        try:
            parent_saved = _read_evaluation(resolved_workspace, filename)
            parent_record = _saved_record(parent_saved)
            parent_workflow = load_workflow(resolved_workspace, filename)
            if parent_workflow is None:
                raise ValueError("revision base does not have a workflow sidecar")
            if parent_workflow.state is not WorkflowState.REVISION_REQUESTED:
                raise ValueError("revision base is not awaiting requested changes")
            if parent_workflow.superseded_by is not None:
                raise ValueError("revision base has already been superseded")
            _, child_by_parent = _revision_index(resolved_workspace)
            if filename in child_by_parent:
                raise ValueError("revision base already has a superseding artifact")

            context = _workflow_context(payload)
            if context is None:
                raise ValueError("revision requires workflow_context")
            session_id, evaluator_id = context
            if evaluator_id != parent_workflow.session.evaluator_id:
                raise ValueError("only the original evaluator can create the requested revision")

            revision_record = record_from_dict(payload)
            _validate_revision_compatibility(parent_record, revision_record)
            result = _score_record(revision_record)
            destination = save_result(resolved_workspace, result)

            child_workflow = create_workflow(
                artifact_id=destination.name,
                task_id=result.task_id,
                session_id=session_id,
                evaluator_id=evaluator_id,
            )
            child_workflow_path = save_workflow(resolved_workspace, child_workflow)

            requested_by, request_note = _revision_request_note(parent_workflow)
            parent_lineage = load_revision_lineage(resolved_workspace, filename)
            lineage = create_revision_lineage(
                artifact_id=destination.name,
                task_id=result.task_id,
                supersedes_artifact_id=filename,
                requested_by=requested_by,
                created_by=evaluator_id,
                request_note=request_note,
                parent_lineage=parent_lineage,
            )
            lineage_path = save_revision_lineage(resolved_workspace, lineage)
            updated_parent = mark_revision_created(
                parent_workflow,
                actor_id=evaluator_id,
                revised_artifact_id=destination.name,
            )
            save_workflow(resolved_workspace, updated_parent)
        except FileNotFoundError:
            if lineage_path is not None:
                lineage_path.unlink(missing_ok=True)
            if child_workflow_path is not None:
                child_workflow_path.unlink(missing_ok=True)
            if destination is not None:
                destination.unlink(missing_ok=True)
            abort(404)
        except (OSError, TypeError, ValueError) as exc:
            if lineage_path is not None:
                lineage_path.unlink(missing_ok=True)
            if child_workflow_path is not None:
                child_workflow_path.unlink(missing_ok=True)
            if destination is not None:
                destination.unlink(missing_ok=True)
            return jsonify({"error": str(exc)}), 400
        return (
            jsonify(
                {
                    "filename": destination.name,
                    "result": result_to_dict(result),
                    "workflow": workflow_to_dict(child_workflow),
                    "revision": revision_to_dict(lineage),
                    "superseded_workflow": workflow_to_dict(updated_parent),
                }
            ),
            201,
        )

    @app.get("/api/history/<filename>/details")
    def history_details(filename: str) -> Any:
        try:
            evaluation = _read_evaluation(resolved_workspace, filename)
            workflow = load_workflow(resolved_workspace, filename)
            lineage = load_revision_lineage(resolved_workspace, filename)
            _, child_by_parent = _revision_index(resolved_workspace)
        except FileNotFoundError:
            abort(404)
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(
            {
                "evaluation": evaluation,
                "workflow": workflow_to_dict(workflow) if workflow is not None else None,
                "revision": revision_to_dict(lineage) if lineage is not None else None,
                "superseded_by": child_by_parent.get(filename)
                or (workflow.superseded_by if workflow is not None else None),
            }
        )

    @app.post("/api/workflows/<filename>/submit")
    def submit(filename: str) -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "request body must be a JSON object"}), 400
        try:
            workflow = load_workflow(resolved_workspace, filename)
            if workflow is None:
                raise ValueError("evaluation does not have a workflow sidecar")
            updated = submit_workflow(
                workflow,
                actor_id=str(payload.get("actor_id", "")).strip(),
                note=str(payload.get("note", "")),
            )
            save_workflow(resolved_workspace, updated)
        except FileNotFoundError:
            abort(404)
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"workflow": workflow_to_dict(updated)}), 200

    @app.post("/api/workflows/<filename>/review")
    def review(filename: str) -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "request body must be a JSON object"}), 400
        try:
            workflow = load_workflow(resolved_workspace, filename)
            if workflow is None:
                raise ValueError("evaluation does not have a workflow sidecar")
            outcome = ReviewOutcome(str(payload.get("outcome", "")))
            updated = review_workflow(
                workflow,
                reviewer_id=str(payload.get("actor_id", "")).strip(),
                outcome=outcome,
                note=str(payload.get("note", "")),
            )
            save_workflow(resolved_workspace, updated)
        except FileNotFoundError:
            abort(404)
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"workflow": workflow_to_dict(updated)}), 200

    @app.post("/api/workflows/<filename>/adjudicate")
    def adjudicate(filename: str) -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "request body must be a JSON object"}), 400
        try:
            workflow = load_workflow(resolved_workspace, filename)
            if workflow is None:
                raise ValueError("evaluation does not have a workflow sidecar")
            outcome = AdjudicationOutcome(str(payload.get("outcome", "")))
            updated = adjudicate_workflow(
                workflow,
                adjudicator_id=str(payload.get("actor_id", "")).strip(),
                outcome=outcome,
                note=str(payload.get("note", "")),
            )
            save_workflow(resolved_workspace, updated)
        except FileNotFoundError:
            abort(404)
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"workflow": workflow_to_dict(updated)}), 200

    @app.get("/api/history/<filename>")
    def download_history(filename: str) -> Any:
        if not _valid_artifact_id(filename):
            abort(404)
        directory = _evaluation_dir(resolved_workspace)
        if not (directory / filename).is_file():
            abort(404)
        return send_from_directory(directory, filename, as_attachment=True)

    return app


def run_workbench(
    workspace: Path | None = None,
    *,
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Run the localhost-only workbench server."""

    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    app = create_app(workspace)
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        timer = threading.Timer(0.7, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
