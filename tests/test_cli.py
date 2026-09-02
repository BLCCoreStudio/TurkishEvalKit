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
    assert "tr-pairwise-quality@1.0" in output


def test_evaluate_command_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["evaluate", "examples/text-evaluation.json", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["task_id"] == "text-demo-001"
    assert payload["normalized_score"] == 95.0


def test_pairwise_evaluate_command_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["evaluate", "examples/pairwise-evaluation.json", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["task_id"] == "pairwise-demo-001"
    assert payload["overall_preference"] == "a"
    assert payload["preference_score"] == 40.0


def test_pairwise_evaluate_command_has_human_summary(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["evaluate", "examples/pairwise-evaluation.json"]) == 0
    output = capsys.readouterr().out
    assert "A preferred" in output
    assert "+40.00/100" in output
    assert "strength 2/3" in output


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


def test_workbench_command_delegates_to_local_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        workspace: Path | None = None,
        *,
        port: int = 8765,
        open_browser: bool = True,
    ) -> None:
        captured.update(
            {
                "workspace": workspace,
                "port": port,
                "open_browser": open_browser,
            }
        )

    monkeypatch.setattr("turkishevalkit.workbench.run_workbench", fake_run)

    assert (
        main(
            [
                "workbench",
                "--workspace",
                str(tmp_path),
                "--port",
                "9876",
                "--no-browser",
            ]
        )
        == 0
    )
    assert captured == {
        "workspace": tmp_path,
        "port": 9876,
        "open_browser": False,
    }


def test_workbench_command_rejects_invalid_port() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["workbench", "--port", "70000"])
    assert exc_info.value.code == 2
