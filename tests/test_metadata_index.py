from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import turkishevalkit.workbench as workbench
from turkishevalkit.evaluation import evaluate_submission
from turkishevalkit.metadata_index import (
    METADATA_INDEX_SCHEMA_VERSION,
    MetadataIndexState,
    clear_metadata_index,
    load_indexed_history,
    metadata_index_path,
    metadata_index_status,
    rebuild_metadata_index,
    workspace_metadata_fingerprint,
)
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC
from turkishevalkit.serialization import load_record


def _save_text_result(workspace: Path) -> Path:
    record = load_record(Path("examples/text-evaluation.json"))
    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)
    return workbench.save_result(workspace, result)


def _rebuild(workspace: Path) -> object:
    fingerprint, source_file_count = workspace_metadata_fingerprint(workspace)
    entries = workbench.scan_history(workspace)
    return rebuild_metadata_index(
        workspace,
        entries,
        expected_source_fingerprint=fingerprint,
        expected_source_file_count=source_file_count,
    )


def test_index_is_opt_in_and_absent_by_default(tmp_path: Path) -> None:
    _save_text_result(tmp_path)

    assert workbench.list_history(tmp_path)
    assert not metadata_index_path(tmp_path).exists()

    status = metadata_index_status(tmp_path)
    assert status.state is MetadataIndexState.ABSENT
    assert status.record_count == 0
    assert status.source_file_count == 1


def test_rebuild_creates_fresh_equivalent_history_snapshot(tmp_path: Path) -> None:
    _save_text_result(tmp_path)
    canonical = workbench.scan_history(tmp_path)

    status = _rebuild(tmp_path)
    indexed = load_indexed_history(tmp_path)

    assert status.state is MetadataIndexState.FRESH
    assert status.schema_version == METADATA_INDEX_SCHEMA_VERSION
    assert status.record_count == 1
    assert indexed == canonical
    assert workbench.list_history(tmp_path) == canonical


def test_fresh_index_avoids_canonical_history_scan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _save_text_result(tmp_path)
    canonical = workbench.scan_history(tmp_path)
    _rebuild(tmp_path)

    def fail_scan(_workspace: Path) -> list[dict[str, object]]:
        raise AssertionError("fresh metadata index should avoid canonical JSON history scan")

    monkeypatch.setattr(workbench, "scan_history", fail_scan)

    assert workbench.list_history(tmp_path) == canonical


def test_rebuild_rejects_source_snapshot_change(tmp_path: Path) -> None:
    _save_text_result(tmp_path)
    fingerprint, source_file_count = workspace_metadata_fingerprint(tmp_path)
    entries = workbench.scan_history(tmp_path)
    _save_text_result(tmp_path)

    with pytest.raises(ValueError, match="canonical history changed"):
        rebuild_metadata_index(
            tmp_path,
            entries,
            expected_source_fingerprint=fingerprint,
            expected_source_file_count=source_file_count,
        )

    assert metadata_index_status(tmp_path).state is MetadataIndexState.ABSENT


def test_source_change_marks_index_stale_and_history_falls_back(tmp_path: Path) -> None:
    _save_text_result(tmp_path)
    _rebuild(tmp_path)
    assert metadata_index_status(tmp_path).state is MetadataIndexState.FRESH

    _save_text_result(tmp_path)

    status = metadata_index_status(tmp_path)
    assert status.state is MetadataIndexState.STALE
    assert load_indexed_history(tmp_path) is None
    assert len(workbench.list_history(tmp_path)) == 2


def test_workflow_change_marks_index_stale(tmp_path: Path) -> None:
    evaluation = _save_text_result(tmp_path)
    workflow = workbench.create_workflow(
        artifact_id=evaluation.name,
        task_id="text-demo-001",
        session_id="session-index",
        evaluator_id="evaluator-index",
    )
    workbench.save_workflow(tmp_path, workflow)
    _rebuild(tmp_path)
    assert metadata_index_status(tmp_path).state is MetadataIndexState.FRESH

    submitted = workbench.submit_workflow(workflow, actor_id="evaluator-index")
    workbench.save_workflow(tmp_path, submitted)

    assert metadata_index_status(tmp_path).state is MetadataIndexState.STALE
    history = workbench.list_history(tmp_path)
    assert history[0]["workflow_state"] == "submitted"


def test_schema_mismatch_is_stale_and_never_read_as_history(tmp_path: Path) -> None:
    _save_text_result(tmp_path)
    canonical = workbench.scan_history(tmp_path)
    _rebuild(tmp_path)
    path = metadata_index_path(tmp_path)

    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
            (str(METADATA_INDEX_SCHEMA_VERSION + 1),),
        )
        connection.commit()

    status = metadata_index_status(tmp_path)

    assert status.state is MetadataIndexState.STALE
    assert status.schema_version == METADATA_INDEX_SCHEMA_VERSION + 1
    assert load_indexed_history(tmp_path) is None
    assert workbench.list_history(tmp_path) == canonical


def test_corrupt_index_never_hides_canonical_history(tmp_path: Path) -> None:
    _save_text_result(tmp_path)
    path = metadata_index_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not-a-sqlite-database")

    status = metadata_index_status(tmp_path)

    assert status.state is MetadataIndexState.CORRUPT
    assert load_indexed_history(tmp_path) is None
    assert len(workbench.list_history(tmp_path)) == 1


def test_clear_removes_only_rebuildable_index(tmp_path: Path) -> None:
    evaluation = _save_text_result(tmp_path)
    _rebuild(tmp_path)

    assert clear_metadata_index(tmp_path) is True
    assert metadata_index_status(tmp_path).state is MetadataIndexState.ABSENT
    assert evaluation.exists()
    assert len(workbench.list_history(tmp_path)) == 1
    assert clear_metadata_index(tmp_path) is False
