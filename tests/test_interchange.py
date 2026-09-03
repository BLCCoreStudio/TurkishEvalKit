from __future__ import annotations

import json
from pathlib import Path

import pytest

from turkishevalkit.evaluation import evaluate_submission
from turkishevalkit.interchange import (
    INTERCHANGE_SCHEMA,
    INTERCHANGE_SCHEMA_VERSION,
    export_workspace,
    import_workspace_file,
    import_workspace_records,
    load_interchange_records,
    parse_interchange_text,
    record_digest,
    render_interchange,
)
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC
from turkishevalkit.serialization import load_record, write_result


def _text_record() -> object:
    return load_record(Path("examples/text-evaluation.json"))


def test_bundle_round_trip_preserves_record() -> None:
    record = _text_record()
    rendered = render_interchange((record,), output_format="bundle")

    payload = json.loads(rendered)
    assert payload["schema"] == INTERCHANGE_SCHEMA
    assert payload["schema_version"] == INTERCHANGE_SCHEMA_VERSION
    assert payload["record_count"] == 1

    loaded = parse_interchange_text(rendered)
    assert len(loaded) == 1
    assert record_digest(loaded[0]) == record_digest(record)


def test_jsonl_round_trip_ignores_blank_lines() -> None:
    record = _text_record()
    rendered = render_interchange((record,), output_format="jsonl")

    loaded = parse_interchange_text(f"\n{rendered}\n", input_format="jsonl")

    assert len(loaded) == 1
    assert record_digest(loaded[0]) == record_digest(record)


def test_plain_array_is_accepted() -> None:
    record = _text_record()
    rendered = render_interchange((record,), output_format="array")

    loaded = parse_interchange_text(rendered)

    assert len(loaded) == 1
    assert loaded[0].task_id == "text-demo-001"


def test_scored_result_wrapper_is_unwrapped() -> None:
    record = load_record(Path("examples/text-evaluation.json"))
    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)
    wrapped = json.dumps(
        {
            "task_id": result.task_id,
            "rubric_id": result.rubric_id,
            "rubric_version": result.rubric_version,
            "normalized_score": result.normalized_score,
            "payload": result.payload,
        },
        ensure_ascii=False,
    )

    loaded = parse_interchange_text(wrapped)

    assert len(loaded) == 1
    assert loaded[0].task_id == result.task_id


def test_bundle_rejects_unsupported_schema_version() -> None:
    record = _text_record()
    payload = json.loads(render_interchange((record,), output_format="bundle"))
    payload["schema_version"] = "999.0"

    with pytest.raises(ValueError, match="unsupported interchange schema_version"):
        parse_interchange_text(json.dumps(payload))


def test_bundle_rejects_mismatched_record_count() -> None:
    record = _text_record()
    payload = json.loads(render_interchange((record,), output_format="bundle"))
    payload["record_count"] = 2

    with pytest.raises(ValueError, match="record_count does not match"):
        parse_interchange_text(json.dumps(payload))


def test_interchange_revalidates_rubric_semantics() -> None:
    record = _text_record()
    payload = json.loads(render_interchange((record,), output_format="array"))
    payload[0]["ratings"] = payload[0]["ratings"][:-1]

    with pytest.raises(ValueError, match="missing ratings"):
        parse_interchange_text(json.dumps(payload))


def test_import_is_exact_content_deduplicated(tmp_path: Path) -> None:
    record = _text_record()

    first = import_workspace_records(tmp_path, (record,))
    second = import_workspace_records(tmp_path, (record,))

    assert first.total_records == 1
    assert first.imported_count == 1
    assert first.duplicate_count == 0
    assert second.total_records == 1
    assert second.imported_count == 0
    assert second.duplicate_count == 1
    assert len(list((tmp_path / "evaluations").glob("*.json"))) == 1
    assert not (tmp_path / "workflows").exists()


def test_import_deduplicates_repeated_records_inside_input(tmp_path: Path) -> None:
    record = _text_record()

    summary = import_workspace_records(tmp_path, (record, record))

    assert summary.total_records == 2
    assert summary.imported_count == 1
    assert summary.duplicate_count == 1


def test_dry_run_does_not_write_workspace(tmp_path: Path) -> None:
    record = _text_record()

    summary = import_workspace_records(tmp_path, (record,), dry_run=True)

    assert summary.dry_run is True
    assert summary.imported_count == 1
    assert len(summary.artifact_ids) == 1
    assert not (tmp_path / "evaluations").exists()


def test_export_workspace_writes_only_evaluator_records(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    evaluations = workspace / "evaluations"
    evaluations.mkdir(parents=True)
    record = load_record(Path("examples/text-evaluation.json"))
    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)
    write_result(evaluations / "saved.json", result)

    workflow_dir = workspace / "workflows"
    workflow_dir.mkdir()
    (workflow_dir / "saved.workflow.json").write_text(
        '{"server_owned":"must-not-export"}\n',
        encoding="utf-8",
    )
    destination = tmp_path / "export.json"

    count = export_workspace(workspace, destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert count == 1
    assert payload["record_count"] == 1
    assert "server_owned" not in destination.read_text(encoding="utf-8")
    assert payload["records"][0]["task_id"] == "text-demo-001"


def test_import_file_accepts_jsonl_extension_auto_detection(tmp_path: Path) -> None:
    record = _text_record()
    source = tmp_path / "dataset.ndjson"
    source.write_text(render_interchange((record,), output_format="jsonl"), encoding="utf-8")

    summary = import_workspace_file(tmp_path / "workspace", source)

    assert summary.imported_count == 1


def test_load_rejects_empty_file(tmp_path: Path) -> None:
    source = tmp_path / "empty.json"
    source.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="must not be empty"):
        load_interchange_records(source)
