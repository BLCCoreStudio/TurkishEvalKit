"""Optional rebuildable SQLite metadata index for local evaluation history."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

METADATA_INDEX_SCHEMA_VERSION = 1
_INDEX_DIRECTORY = "indexes"
_INDEX_FILENAME = "metadata.sqlite3"
_TRACKED_GLOBS = (
    ("evaluations", "*.json"),
    ("workflows", "*.workflow.json"),
    ("revisions", "*.revision.json"),
)


class MetadataIndexState(StrEnum):
    """Observable state of the optional rebuildable metadata index."""

    ABSENT = "absent"
    FRESH = "fresh"
    STALE = "stale"
    CORRUPT = "corrupt"


@dataclass(frozen=True, slots=True)
class MetadataIndexStatus:
    """Status snapshot for one workspace metadata index."""

    state: MetadataIndexState
    path: str
    record_count: int
    source_file_count: int
    schema_version: int | None
    built_at: str | None
    reason: str | None = None


def metadata_index_path(workspace: Path) -> Path:
    """Return the deterministic cache path for a workspace metadata index."""

    return workspace.expanduser().resolve() / _INDEX_DIRECTORY / _INDEX_FILENAME


def _tracked_files(workspace: Path) -> list[Path]:
    resolved = workspace.expanduser().resolve()
    files: list[Path] = []
    for directory_name, pattern in _TRACKED_GLOBS:
        directory = resolved / directory_name
        if not directory.exists():
            continue
        files.extend(sorted(directory.glob(pattern), key=lambda path: path.name))
    return sorted(files, key=lambda path: path.relative_to(resolved).as_posix())


def workspace_metadata_fingerprint(workspace: Path) -> tuple[str, int]:
    """Hash cheap file metadata for canonical history sources without parsing JSON."""

    resolved = workspace.expanduser().resolve()
    digest = hashlib.sha256()
    source_file_count = 0
    for path in _tracked_files(resolved):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        source_file_count += 1
        relative = path.relative_to(resolved).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), source_file_count


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _metadata(connection: sqlite3.Connection) -> dict[str, str]:
    rows = connection.execute("SELECT key, value FROM metadata").fetchall()
    return {str(key): str(value) for key, value in rows}


def _history_count(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) FROM history").fetchone()
    if row is None:
        raise sqlite3.DatabaseError("metadata index history count is unavailable")
    return int(row[0])


def _status_from_connection(
    workspace: Path,
    path: Path,
    connection: sqlite3.Connection,
) -> MetadataIndexStatus:
    metadata = _metadata(connection)
    raw_schema = metadata.get("schema_version")
    try:
        schema_version = int(raw_schema) if raw_schema is not None else None
    except ValueError:
        schema_version = None
    current_fingerprint, source_file_count = workspace_metadata_fingerprint(workspace)

    if schema_version != METADATA_INDEX_SCHEMA_VERSION:
        return MetadataIndexStatus(
            state=MetadataIndexState.STALE,
            path=str(path),
            record_count=0,
            source_file_count=source_file_count,
            schema_version=schema_version,
            built_at=metadata.get("built_at"),
            reason="metadata index schema version does not match the current reader",
        )

    record_count = _history_count(connection)
    if metadata.get("source_fingerprint") != current_fingerprint:
        return MetadataIndexStatus(
            state=MetadataIndexState.STALE,
            path=str(path),
            record_count=record_count,
            source_file_count=source_file_count,
            schema_version=schema_version,
            built_at=metadata.get("built_at"),
            reason="canonical evaluation/workflow/revision files changed after rebuild",
        )

    return MetadataIndexStatus(
        state=MetadataIndexState.FRESH,
        path=str(path),
        record_count=record_count,
        source_file_count=source_file_count,
        schema_version=schema_version,
        built_at=metadata.get("built_at"),
    )


def metadata_index_status(workspace: Path) -> MetadataIndexStatus:
    """Inspect the optional index without treating it as authoritative state."""

    path = metadata_index_path(workspace)
    if not path.exists():
        _, source_file_count = workspace_metadata_fingerprint(workspace)
        return MetadataIndexStatus(
            state=MetadataIndexState.ABSENT,
            path=str(path),
            record_count=0,
            source_file_count=source_file_count,
            schema_version=None,
            built_at=None,
            reason="metadata index has not been built",
        )

    try:
        with closing(_connect_read_only(path)) as connection:
            return _status_from_connection(workspace, path, connection)
    except (OSError, sqlite3.DatabaseError, ValueError) as exc:
        _, source_file_count = workspace_metadata_fingerprint(workspace)
        return MetadataIndexStatus(
            state=MetadataIndexState.CORRUPT,
            path=str(path),
            record_count=0,
            source_file_count=source_file_count,
            schema_version=None,
            built_at=None,
            reason=str(exc),
        )


def metadata_index_status_to_dict(status: MetadataIndexStatus) -> dict[str, Any]:
    """Serialize an index status for CLI/UI adapters."""

    payload = asdict(status)
    payload["state"] = status.state.value
    return payload


def _history_row(entry: dict[str, Any], position: int) -> tuple[Any, ...]:
    return (
        position,
        str(entry.get("filename") or ""),
        str(entry.get("task_id") or ""),
        str(entry.get("evaluation_type") or ""),
        str(entry.get("rubric_id") or ""),
        str(entry.get("rubric_version") or ""),
        entry.get("weighted_score"),
        entry.get("normalized_score"),
        entry.get("preference_score"),
        entry.get("overall_preference"),
        entry.get("preference_strength"),
        str(entry.get("saved_at") or ""),
        entry.get("workflow_state"),
        entry.get("session_id"),
        entry.get("evaluator_id"),
        entry.get("review_outcome"),
        entry.get("adjudication_outcome"),
        int(entry.get("revision_number") or 0),
        entry.get("root_artifact_id"),
        entry.get("supersedes_artifact_id"),
        entry.get("superseded_by"),
    )


def _initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        PRAGMA synchronous=FULL;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE history (
            position INTEGER NOT NULL UNIQUE,
            filename TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            evaluation_type TEXT NOT NULL,
            rubric_id TEXT NOT NULL,
            rubric_version TEXT NOT NULL,
            weighted_score REAL,
            normalized_score REAL,
            preference_score REAL,
            overall_preference TEXT,
            preference_strength INTEGER,
            saved_at TEXT NOT NULL,
            workflow_state TEXT,
            session_id TEXT,
            evaluator_id TEXT,
            review_outcome TEXT,
            adjudication_outcome TEXT,
            revision_number INTEGER NOT NULL,
            root_artifact_id TEXT,
            supersedes_artifact_id TEXT,
            superseded_by TEXT
        );

        CREATE INDEX history_saved_at_idx ON history(saved_at DESC);
        CREATE INDEX history_task_idx ON history(task_id);
        CREATE INDEX history_type_idx ON history(evaluation_type);
        CREATE INDEX history_rubric_idx ON history(rubric_id);
        CREATE INDEX history_evaluator_idx ON history(evaluator_id);
        CREATE INDEX history_workflow_state_idx ON history(workflow_state);
        """
    )


def rebuild_metadata_index(
    workspace: Path,
    entries: Sequence[dict[str, Any]],
) -> MetadataIndexStatus:
    """Atomically rebuild the cache from a canonical history scan."""

    resolved = workspace.expanduser().resolve()
    path = metadata_index_path(resolved)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    Path(f"{temporary}-journal").unlink(missing_ok=True)

    source_fingerprint, source_file_count = workspace_metadata_fingerprint(resolved)
    built_at = datetime.now(UTC).isoformat()

    try:
        with closing(sqlite3.connect(temporary)) as connection:
            _initialize_schema(connection)
            connection.executemany(
                """
                INSERT INTO history (
                    position,
                    filename,
                    task_id,
                    evaluation_type,
                    rubric_id,
                    rubric_version,
                    weighted_score,
                    normalized_score,
                    preference_score,
                    overall_preference,
                    preference_strength,
                    saved_at,
                    workflow_state,
                    session_id,
                    evaluator_id,
                    review_outcome,
                    adjudication_outcome,
                    revision_number,
                    root_artifact_id,
                    supersedes_artifact_id,
                    superseded_by
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [_history_row(dict(entry), position) for position, entry in enumerate(entries)],
            )
            connection.executemany(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                (
                    ("schema_version", str(METADATA_INDEX_SCHEMA_VERSION)),
                    ("source_fingerprint", source_fingerprint),
                    ("source_file_count", str(source_file_count)),
                    ("built_at", built_at),
                ),
            )
            connection.commit()
        temporary.replace(path)
    except (OSError, sqlite3.DatabaseError, TypeError, ValueError):
        temporary.unlink(missing_ok=True)
        Path(f"{temporary}-journal").unlink(missing_ok=True)
        raise

    return MetadataIndexStatus(
        state=MetadataIndexState.FRESH,
        path=str(path),
        record_count=len(entries),
        source_file_count=source_file_count,
        schema_version=METADATA_INDEX_SCHEMA_VERSION,
        built_at=built_at,
    )


def load_indexed_history(workspace: Path) -> list[dict[str, Any]] | None:
    """Return cached history only when the index is readable and demonstrably fresh."""

    path = metadata_index_path(workspace)
    if not path.exists():
        return None

    try:
        with closing(_connect_read_only(path)) as connection:
            status = _status_from_connection(workspace, path, connection)
            if status.state is not MetadataIndexState.FRESH:
                return None
            rows = connection.execute(
                """
                SELECT
                    filename,
                    task_id,
                    evaluation_type,
                    rubric_id,
                    rubric_version,
                    weighted_score,
                    normalized_score,
                    preference_score,
                    overall_preference,
                    preference_strength,
                    saved_at,
                    workflow_state,
                    session_id,
                    evaluator_id,
                    review_outcome,
                    adjudication_outcome,
                    revision_number,
                    root_artifact_id,
                    supersedes_artifact_id,
                    superseded_by
                FROM history
                ORDER BY position ASC
                """
            ).fetchall()
    except (OSError, sqlite3.DatabaseError, ValueError):
        return None

    keys = (
        "filename",
        "task_id",
        "evaluation_type",
        "rubric_id",
        "rubric_version",
        "weighted_score",
        "normalized_score",
        "preference_score",
        "overall_preference",
        "preference_strength",
        "saved_at",
        "workflow_state",
        "session_id",
        "evaluator_id",
        "review_outcome",
        "adjudication_outcome",
        "revision_number",
        "root_artifact_id",
        "supersedes_artifact_id",
        "superseded_by",
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


def clear_metadata_index(workspace: Path) -> bool:
    """Delete only rebuildable index files and leave canonical artifacts untouched."""

    path = metadata_index_path(workspace)
    temporary = path.with_suffix(path.suffix + ".tmp")
    removed = False
    for candidate in (
        path,
        Path(f"{path}-journal"),
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        temporary,
        Path(f"{temporary}-journal"),
        Path(f"{temporary}-wal"),
        Path(f"{temporary}-shm"),
    ):
        if candidate.exists():
            candidate.unlink()
            removed = True
    return removed
