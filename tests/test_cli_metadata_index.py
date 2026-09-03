from __future__ import annotations

import json
from pathlib import Path

import pytest

from turkishevalkit.cli import main
from turkishevalkit.evaluation import evaluate_submission
from turkishevalkit.metadata_index import MetadataIndexState, metadata_index_status
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC
from turkishevalkit.serialization import load_record
from turkishevalkit.workbench import save_result


def _populate_workspace(workspace: Path) -> None:
    record = load_record(Path("examples/text-evaluation.json"))
    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)
    save_result(workspace, result)


def test_index_status_rebuild_and_clear_commands(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    _populate_workspace(workspace)

    assert main(["index", "status", "--workspace", str(workspace), "--json"]) == 0
    status_payload = json.loads(capsys.readouterr().out)
    assert status_payload["state"] == "absent"
    assert status_payload["source_file_count"] == 1

    assert main(["index", "rebuild", "--workspace", str(workspace)]) == 0
    assert "rebuilt metadata index: 1 record(s)" in capsys.readouterr().out
    assert metadata_index_status(workspace).state is MetadataIndexState.FRESH

    assert main(["index", "status", "--workspace", str(workspace)]) == 0
    assert "fresh: 1 indexed record(s)" in capsys.readouterr().out

    assert main(["index", "clear", "--workspace", str(workspace)]) == 0
    assert "metadata index cleared" in capsys.readouterr().out
    assert metadata_index_status(workspace).state is MetadataIndexState.ABSENT

    assert main(["index", "clear", "--workspace", str(workspace)]) == 0
    assert "already absent" in capsys.readouterr().out


def test_index_rebuild_skips_invalid_canonical_evaluation_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    _populate_workspace(workspace)
    evaluations = workspace / "evaluations"
    (evaluations / "broken.json").write_text("{bad-json", encoding="utf-8")

    assert main(["index", "rebuild", "--workspace", str(workspace)]) == 0

    output = capsys.readouterr().out
    assert "1 record(s)" in output
    assert "2 canonical source file(s)" in output
