"""Shared read-only access to saved evaluation artifacts and trusted evaluator attribution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .serialization import SubmissionRecord, record_from_dict, workflow_from_dict


@dataclass(frozen=True, slots=True)
class WorkspaceEvaluation:
    """One saved evaluation plus trusted local attribution and compatibility metadata."""

    filename: str
    record: SubmissionRecord
    saved_result: dict[str, Any]
    evaluator_id: str | None
    compatibility_key: str
    saved_at: str

    @property
    def attributed(self) -> bool:
        return self.evaluator_id is not None


def evaluation_dir(workspace: Path) -> Path:
    return workspace / "evaluations"


def workflow_dir(workspace: Path) -> Path:
    return workspace / "workflows"


def valid_json_artifact_id(artifact_id: str) -> bool:
    return artifact_id == Path(artifact_id).name and artifact_id.endswith(".json")


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {label} JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must contain one JSON object")
    return data


def load_saved_record(
    workspace: Path,
    artifact_id: str,
) -> tuple[SubmissionRecord, dict[str, Any]]:
    """Load one canonical evaluation artifact and reconstruct its typed record."""

    if not valid_json_artifact_id(artifact_id):
        raise FileNotFoundError(artifact_id)
    path = evaluation_dir(workspace) / artifact_id
    if not path.is_file():
        raise FileNotFoundError(artifact_id)

    saved_result = load_json_object(path, label="evaluation artifact")
    raw_record = saved_result.get("payload")
    if not isinstance(raw_record, dict):
        raise ValueError("evaluation artifact does not contain a valid payload record")
    return record_from_dict(raw_record), saved_result


def load_evaluator_id(workspace: Path, artifact_id: str) -> str | None:
    """Read evaluator identity only from a valid local workflow sidecar."""

    if not valid_json_artifact_id(artifact_id):
        raise FileNotFoundError(artifact_id)
    workflow_name = f"{artifact_id[:-5]}.workflow.json"
    path = workflow_dir(workspace) / workflow_name
    if not path.is_file():
        return None
    workflow = workflow_from_dict(load_json_object(path, label="workflow artifact"))
    if workflow.artifact_id != artifact_id:
        raise ValueError("workflow artifact id does not match evaluation filename")
    evaluator_id = workflow.session.evaluator_id.strip()
    return evaluator_id or None


def compatibility_key(raw_record: dict[str, Any]) -> str:
    """Return a stable same-stimulus compatibility key for local grouping only."""

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


def load_workspace_evaluation(workspace: Path, path: Path) -> WorkspaceEvaluation:
    """Load one evaluation path plus best-effort trusted local attribution."""

    record, saved_result = load_saved_record(workspace, path.name)
    raw_record = saved_result.get("payload")
    if not isinstance(raw_record, dict):
        raise ValueError("evaluation artifact does not contain a valid payload record")
    try:
        evaluator_id = load_evaluator_id(workspace, path.name)
    except (OSError, TypeError, ValueError):
        evaluator_id = None
    saved_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    return WorkspaceEvaluation(
        filename=path.name,
        record=record,
        saved_result=saved_result,
        evaluator_id=evaluator_id,
        compatibility_key=compatibility_key(raw_record),
        saved_at=saved_at,
    )


def list_workspace_evaluations(workspace: Path) -> list[WorkspaceEvaluation]:
    """Return readable saved evaluations newest first while isolating corrupt records."""

    directory = evaluation_dir(workspace)
    if not directory.exists():
        return []

    paths = sorted(
        directory.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    items: list[WorkspaceEvaluation] = []
    for path in paths:
        try:
            items.append(load_workspace_evaluation(workspace, path))
        except (OSError, TypeError, ValueError):
            continue
    return items
