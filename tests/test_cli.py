from __future__ import annotations

import json
from pathlib import Path

import pytest

from turkishevalkit.cli import main


def test_rubrics_command_lists_builtins(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["rubrics"]) == 0
    output = capsys.readouterr().out
    assert "tr-text-quality@1.0" in output
    assert "tr-audio-quality@1.0" in output


def test_evaluate_command_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["evaluate", "examples/text-evaluation.json", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["task_id"] == "text-demo-001"
    assert payload["normalized_score"] == 95.0


def test_evaluate_command_can_write_output(tmp_path: Path) -> None:
    destination = tmp_path / "scored.json"
    assert (
        main(
            [
                "evaluate",
                "examples/audio-evaluation.json",
                "--output",
                str(destination),
            ]
        )
        == 0
    )
    assert destination.exists()
    assert '"task_id": "audio-demo-001"' in destination.read_text(encoding="utf-8")


def test_evaluate_command_rejects_missing_file() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["evaluate", "does-not-exist.json"])
    assert exc_info.value.code == 2
