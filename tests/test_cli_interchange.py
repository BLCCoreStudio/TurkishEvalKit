from __future__ import annotations

import json
from pathlib import Path

import pytest

from turkishevalkit.cli import main


def test_convert_command_writes_jsonl(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "text.jsonl"

    assert (
        main(
            [
                "convert",
                "examples/text-evaluation.json",
                str(destination),
                "--output-format",
                "jsonl",
            ]
        )
        == 0
    )

    line = json.loads(destination.read_text(encoding="utf-8"))
    assert line["task_id"] == "text-demo-001"
    assert "converted 1 record(s)" in capsys.readouterr().out


def test_import_dry_run_then_import_then_deduplicate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"

    assert (
        main(
            [
                "import",
                "examples/text-evaluation.json",
                "--workspace",
                str(workspace),
                "--dry-run",
            ]
        )
        == 0
    )
    assert "would import 1/1 record(s)" in capsys.readouterr().out
    assert not (workspace / "evaluations").exists()

    assert (
        main(
            [
                "import",
                "examples/text-evaluation.json",
                "--workspace",
                str(workspace),
            ]
        )
        == 0
    )
    assert "imported 1/1 record(s)" in capsys.readouterr().out

    assert (
        main(
            [
                "import",
                "examples/text-evaluation.json",
                "--workspace",
                str(workspace),
            ]
        )
        == 0
    )
    assert "imported 0/1 record(s) · 1 duplicate(s)" in capsys.readouterr().out


def test_export_command_writes_canonical_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    destination = tmp_path / "bundle.json"

    assert (
        main(
            [
                "import",
                "examples/text-evaluation.json",
                "--workspace",
                str(workspace),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "export",
                "--workspace",
                str(workspace),
                "--output",
                str(destination),
            ]
        )
        == 0
    )

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema"] == "turkishevalkit.evaluation-dataset"
    assert payload["record_count"] == 1
    assert "exported 1 record(s)" in capsys.readouterr().out


def test_convert_rejects_invalid_evaluation(tmp_path: Path) -> None:
    source = tmp_path / "bad.json"
    destination = tmp_path / "out.json"
    source.write_text('{"task_id":"bad"}', encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(["convert", str(source), str(destination)])

    assert exc_info.value.code == 2
    assert not destination.exists()


def test_export_rejects_empty_workspace(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "export",
                "--workspace",
                str(tmp_path),
                "--output",
                str(tmp_path / "empty.json"),
            ]
        )

    assert exc_info.value.code == 2
