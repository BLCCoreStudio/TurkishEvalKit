"""Immutable revision-lineage primitives for superseding evaluation artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .workflow import utc_now_iso


@dataclass(frozen=True, slots=True)
class RevisionLineage:
    """Server-owned relationship between a new evaluation and the artifact it supersedes."""

    schema_version: int
    artifact_id: str
    task_id: str
    root_artifact_id: str
    supersedes_artifact_id: str
    revision_number: int
    requested_by: str
    created_by: str
    request_note: str
    created_at: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported revision lineage schema_version")
        for field_name, value in (
            ("artifact_id", self.artifact_id),
            ("task_id", self.task_id),
            ("root_artifact_id", self.root_artifact_id),
            ("supersedes_artifact_id", self.supersedes_artifact_id),
            ("requested_by", self.requested_by),
            ("created_by", self.created_by),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.artifact_id == self.supersedes_artifact_id:
            raise ValueError("a revision cannot supersede itself")
        if self.revision_number < 1:
            raise ValueError("revision_number must be positive")
        if not self.request_note.strip():
            raise ValueError("request_note must explain why a revision was requested")
        _validate_timestamp(self.created_at)


def create_revision_lineage(
    *,
    artifact_id: str,
    task_id: str,
    supersedes_artifact_id: str,
    requested_by: str,
    created_by: str,
    request_note: str,
    parent_lineage: RevisionLineage | None = None,
    occurred_at: str | None = None,
) -> RevisionLineage:
    """Create the next immutable lineage record in a linear revision chain."""

    if parent_lineage is not None and parent_lineage.artifact_id != supersedes_artifact_id:
        raise ValueError("parent lineage does not describe the superseded artifact")
    root_artifact_id = (
        parent_lineage.root_artifact_id if parent_lineage is not None else supersedes_artifact_id
    )
    revision_number = parent_lineage.revision_number + 1 if parent_lineage is not None else 1
    return RevisionLineage(
        schema_version=1,
        artifact_id=artifact_id,
        task_id=task_id,
        root_artifact_id=root_artifact_id,
        supersedes_artifact_id=supersedes_artifact_id,
        revision_number=revision_number,
        requested_by=requested_by,
        created_by=created_by,
        request_note=request_note.strip(),
        created_at=occurred_at or utc_now_iso(),
    )


def revision_to_dict(lineage: RevisionLineage) -> dict[str, object]:
    """Convert lineage to stable JSON-native data."""

    return {
        "schema_version": lineage.schema_version,
        "artifact_id": lineage.artifact_id,
        "task_id": lineage.task_id,
        "root_artifact_id": lineage.root_artifact_id,
        "supersedes_artifact_id": lineage.supersedes_artifact_id,
        "revision_number": lineage.revision_number,
        "requested_by": lineage.requested_by,
        "created_by": lineage.created_by,
        "request_note": lineage.request_note,
        "created_at": lineage.created_at,
    }


def revision_from_dict(data: dict[str, Any]) -> RevisionLineage:
    """Reconstruct and validate one persisted lineage record."""

    return RevisionLineage(
        schema_version=int(data.get("schema_version", 0)),
        artifact_id=str(data.get("artifact_id", "")),
        task_id=str(data.get("task_id", "")),
        root_artifact_id=str(data.get("root_artifact_id", "")),
        supersedes_artifact_id=str(data.get("supersedes_artifact_id", "")),
        revision_number=int(data.get("revision_number", 0)),
        requested_by=str(data.get("requested_by", "")),
        created_by=str(data.get("created_by", "")),
        request_note=str(data.get("request_note", "")),
        created_at=str(data.get("created_at", "")),
    )


def _validate_timestamp(value: str) -> None:
    if not value.strip():
        raise ValueError("created_at must not be empty")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("created_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("created_at must include a timezone")
