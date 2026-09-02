"""Local browser workbench backed by the core evaluation engine."""

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

from .evaluation import EvaluationResult, evaluate_submission
from .models import PairwiseEvaluationRecord
from .pairwise import PairwiseEvaluationResult, evaluate_pairwise_submission
from .rubrics import BUILTIN_RUBRICS
from .serialization import record_from_dict, result_to_dict

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


def _safe_task_id(task_id: str) -> str:
    cleaned = _FILENAME_SAFE.sub("-", task_id.strip()).strip("._-")
    return (cleaned or "evaluation")[:80]


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


def list_history(workspace: Path) -> list[dict[str, Any]]:
    """Return recent saved evaluations, newest first."""

    directory = _evaluation_dir(workspace)
    if not directory.exists():
        return []

    entries: list[dict[str, Any]] = []
    paths = sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        record = payload.get("payload")
        record_payload = record if isinstance(record, dict) else {}
        saved_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
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
            }
        )
    return entries


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

    @app.get("/")
    def index() -> str:
        return render_template("workbench.html")

    @app.get("/api/config")
    def config() -> Any:
        return jsonify(
            {
                "rubrics": rubric_payload(),
                "workspace": str(resolved_workspace),
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

        try:
            record = record_from_dict(payload)
            rubric = BUILTIN_RUBRICS.get(record.rubric_id)
            if rubric is None:
                raise ValueError(f"unknown rubric: {record.rubric_id}")
            if isinstance(record, PairwiseEvaluationRecord):
                result: SavedResult = evaluate_pairwise_submission(record, rubric)
            else:
                result = evaluate_submission(record, rubric)
            destination = save_result(resolved_workspace, result)
        except (OSError, TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return (
            jsonify(
                {
                    "filename": destination.name,
                    "result": result_to_dict(result),
                }
            ),
            201,
        )

    @app.get("/api/history/<filename>")
    def download_history(filename: str) -> Any:
        if filename != Path(filename).name or not filename.endswith(".json"):
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

    app.run(
        host="127.0.0.1",
        port=port,
        debug=False,
        use_reloader=False,
    )
