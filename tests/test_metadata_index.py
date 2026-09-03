from __future__ import annotations

from pathlib import Path

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
)
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC
from turkishevalkit.serialization import load_record


def _save_text_result(workspace: Path) -> Path:
    record = load_record(Path("examples/text-evaluation.json"))
    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)
    return workbench.save_result(workspace, result)


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

    status = rebuild_metadata_index(tmp_path, canonical)
    indexed = load_indexed_history(tmp_path)

    assert status.state is MetadataIndexState.FRESH
    assert status.schema_version == METADATA_INDEX_SCHEMA_VERSION
    assert status.record_count == 1
    assert indexed == canonical
    assert workbench.list_history(tmp_path) == canonical


def test_source_change_marks_index_stale_and_history_falls_back(tmp_path: Path) -> None:
    _save_text_result(tmp_path)
    rebuild_metadata_index(tmp_path, workbench.scan_history(tmp_path))
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
    rebuild_metadata_index(tmp_path, workbench.scan_history(tmp_path))
    assert metadata_index_status(tmp_path).state is MetadataIndexState.FRESH

    submitted = workbench.submit_workflow(workflow, actor_id="evaluator-index")
    workbench.save_workflow(tmp_path, submitted)

    assert metadata_index_status(tmp_path).state is MetadataIndexState.STALE
    history = workbench.list_history(tmp_path)
    assert history[0]["workflow_state"] == "submitted"


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
    rebuild_metadata_index(tmp_path, workbench.scan_history(tmp_path))

    assert clear_metadata_index(tmp_path) is True
    assert metadata_index_status(tmp_path).state is MetadataIndexState.ABSENT
    assert evaluation.exists()
    assert len(workbench.list_history(tmp_path)) == 1
    assert clear_metadata_index(tmp_path) is False
