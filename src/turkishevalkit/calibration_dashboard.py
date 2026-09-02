"""Local calibration dashboard and append-only calibration history."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .calibration import (
    EvaluatorSubmission,
    build_calibration_report,
    calibration_report_to_dict,
)
from .rubrics import BUILTIN_RUBRICS
from .serialization import record_from_dict, workflow_from_dict

if TYPE_CHECKING:
    from flask import Blueprint

_FILENAME_SAFE = re.compile(r"[^\w.-]+", flags=re.UNICODE)


def _evaluation_dir(workspace: Path) -> Path:
    return workspace / "evaluations"


def _workflow_dir(workspace: Path) -> Path:
    return workspace / "workflows"


def _calibration_dir(workspace: Path) -> Path:
    return workspace / "calibrations"


def _safe_task_id(task_id: str) -> str:
    cleaned = _FILENAME_SAFE.sub("-", task_id.strip()).strip("._-")
    return (cleaned or "calibration")[:80]


def _valid_json_artifact_id(artifact_id: str) -> bool:
    return artifact_id == Path(artifact_id).name and artifact_id.endswith(".json")


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {label} JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain one JSON object")
    return data


def _load_saved_record(workspace: Path, artifact_id: str) -> tuple[Any, dict[str, Any]]:
    if not _valid_json_artifact_id(artifact_id):
        raise FileNotFoundError(artifact_id)
    path = _evaluation_dir(workspace) / artifact_id
    if not path.is_file():
        raise FileNotFoundError(artifact_id)

    saved_result = _load_json_object(path, label="evaluation artifact")
    raw_record = saved_result.get("payload")
    if not isinstance(raw_record, dict):
        raise ValueError("evaluation artifact does not contain a valid payload record")
    return record_from_dict(raw_record), saved_result


def _load_evaluator_id(workspace: Path, artifact_id: str) -> str | None:
    workflow_name = f"{artifact_id[:-5]}.workflow.json"
    path = _workflow_dir(workspace) / workflow_name
    if not path.is_file():
        return None
    workflow = workflow_from_dict(_load_json_object(path, label="workflow artifact"))
    evaluator_id = workflow.session.evaluator_id.strip()
    return evaluator_id or None


def _compatibility_key(raw_record: dict[str, Any]) -> str:
    identity = {
        "task_id": raw_record.get("task_id"),
        "evaluation_type": raw_record.get("evaluation_type"),
        "rubric_id": raw_record.get("rubric_id"),
        "rubric_version": raw_record.get("rubric_version"),
        "source": raw_record.get("source"),
    }
    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def list_calibration_candidates(workspace: Path) -> list[dict[str, Any]]:
    """Return saved evaluations with evaluator identity and compatibility metadata."""

    directory = _evaluation_dir(workspace)
    if not directory.exists():
        return []

    items: list[dict[str, Any]] = []
    paths = sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in paths:
        try:
            saved_result = _load_json_object(path, label="evaluation artifact")
            raw_record = saved_result.get("payload")
            if not isinstance(raw_record, dict):
                continue
            record = record_from_dict(raw_record)
            evaluator_id = _load_evaluator_id(workspace, path.name)
        except (OSError, TypeError, ValueError):
            continue

        items.append(
            {
                "filename": path.name,
                "task_id": record.task_id,
                "evaluation_type": record.evaluation_type.value,
                "rubric_id": record.rubric_id,
                "rubric_version": record.rubric_version,
                "evaluator_id": evaluator_id,
                "calibration_ready": evaluator_id is not None,
                "compatibility_key": _compatibility_key(raw_record),
                "normalized_score": saved_result.get("normalized_score"),
                "preference_score": saved_result.get("preference_score"),
                "overall_preference": saved_result.get("overall_preference"),
                "saved_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
            }
        )
    return items


def _save_calibration(
    workspace: Path,
    report: Any,
    source_artifacts: list[dict[str, str]],
) -> Path:
    directory = _calibration_dir(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC)
    destination = directory / (
        f"{_safe_task_id(report.task_id)}-{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}"
        ".calibration.json"
    )
    payload = {
        "schema_version": "1.0",
        "created_at": timestamp.isoformat(),
        "source_artifacts": source_artifacts,
        "report": calibration_report_to_dict(report),
    }
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def _load_calibration(workspace: Path, artifact_id: str) -> dict[str, Any]:
    if not _valid_json_artifact_id(artifact_id) or not artifact_id.endswith(".calibration.json"):
        raise FileNotFoundError(artifact_id)
    path = _calibration_dir(workspace) / artifact_id
    if not path.is_file():
        raise FileNotFoundError(artifact_id)
    return _load_json_object(path, label="calibration artifact")


def list_calibration_history(workspace: Path) -> list[dict[str, Any]]:
    """Return saved calibration reports newest first."""

    directory = _calibration_dir(workspace)
    if not directory.exists():
        return []

    items: list[dict[str, Any]] = []
    paths = sorted(
        directory.glob("*.calibration.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for path in paths:
        try:
            payload = _load_json_object(path, label="calibration artifact")
        except (OSError, ValueError):
            continue
        report = payload.get("report")
        if not isinstance(report, dict):
            continue
        source_artifacts = payload.get("source_artifacts")
        items.append(
            {
                "filename": path.name,
                "task_id": str(report.get("task_id", "")),
                "evaluation_type": str(report.get("evaluation_type", "")),
                "rubric_id": str(report.get("rubric_id", "")),
                "rubric_version": str(report.get("rubric_version", "")),
                "evaluator_count": report.get("evaluator_count"),
                "exact_criterion_agreement_rate": report.get(
                    "exact_criterion_agreement_rate"
                ),
                "aggregate_score_spread": report.get("aggregate_score_spread"),
                "created_at": str(payload.get("created_at", "")),
                "source_artifact_count": (
                    len(source_artifacts) if isinstance(source_artifacts, list) else 0
                ),
            }
        )
    return items


def create_calibration_blueprint(workspace: Path) -> Blueprint:
    """Create calibration routes bound to one resolved workbench workspace."""

    try:
        from flask import Blueprint, abort, jsonify, render_template, request, send_from_directory
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'The calibration dashboard requires the workbench dependency. '
            'Install with: python -m pip install "turkishevalkit[workbench]"'
        ) from exc

    blueprint = Blueprint("calibration_dashboard", __name__)

    @blueprint.get("/calibration")
    def calibration_page() -> str:
        return render_template("calibration.html")

    @blueprint.get("/api/calibrations/candidates")
    def calibration_candidates() -> Any:
        return jsonify({"items": list_calibration_candidates(workspace)})

    @blueprint.get("/api/calibrations")
    def calibration_history() -> Any:
        return jsonify({"items": list_calibration_history(workspace)})

    @blueprint.post("/api/calibrations")
    def create_calibration() -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "request body must be a JSON object"}), 400

        raw_filenames = payload.get("filenames")
        if not isinstance(raw_filenames, list) or len(raw_filenames) < 2:
            return jsonify({"error": "filenames must contain at least two artifacts"}), 400
        if not all(isinstance(item, str) and item for item in raw_filenames):
            return jsonify({"error": "filenames must contain non-empty strings"}), 400
        filenames = [str(item) for item in raw_filenames]
        if len(filenames) != len(set(filenames)):
            return jsonify({"error": "filenames must be unique"}), 400

        raw_tolerance = payload.get("annotation_tolerance_ms", 250)
        if isinstance(raw_tolerance, bool) or not isinstance(raw_tolerance, int):
            return jsonify({"error": "annotation_tolerance_ms must be an integer"}), 400
        if not 0 <= raw_tolerance <= 5000:
            return jsonify({"error": "annotation_tolerance_ms must be between 0 and 5000"}), 400

        try:
            submissions: list[EvaluatorSubmission] = []
            source_artifacts: list[dict[str, str]] = []
            for filename in filenames:
                record, _ = _load_saved_record(workspace, filename)
                evaluator_id = _load_evaluator_id(workspace, filename)
                if evaluator_id is None:
                    raise ValueError(
                        f"{filename} has no evaluator identity; create it with a workflow session"
                    )
                submissions.append(EvaluatorSubmission(evaluator_id=evaluator_id, record=record))
                source_artifacts.append(
                    {"filename": filename, "evaluator_id": evaluator_id}
                )

            first_record = submissions[0].record
            rubric = BUILTIN_RUBRICS.get(first_record.rubric_id)
            if rubric is None:
                raise ValueError(f"unknown rubric: {first_record.rubric_id}")
            report = build_calibration_report(
                tuple(submissions),
                rubric,
                annotation_tolerance_ms=raw_tolerance,
            )
            destination = _save_calibration(workspace, report, source_artifacts)
        except FileNotFoundError:
            abort(404)
        except (OSError, TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return (
            jsonify(
                {
                    "filename": destination.name,
                    "report": calibration_report_to_dict(report),
                    "source_artifacts": source_artifacts,
                }
            ),
            201,
        )

    @blueprint.get("/api/calibrations/<filename>/details")
    def calibration_details(filename: str) -> Any:
        try:
            return jsonify(_load_calibration(workspace, filename))
        except FileNotFoundError:
            abort(404)
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    @blueprint.get("/api/calibrations/<filename>/download")
    def calibration_download(filename: str) -> Any:
        try:
            _load_calibration(workspace, filename)
        except FileNotFoundError:
            abort(404)
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return send_from_directory(_calibration_dir(workspace), filename, as_attachment=True)

    return blueprint
