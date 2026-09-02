from __future__ import annotations

import json
from pathlib import Path

from turkishevalkit.cli import main


def test_reliability_cli_json_output(capsys: object) -> None:
    exit_code = main(["reliability", "examples/reliability-text.json", "--json"])

    assert exit_code == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert payload["evaluation_type"] == "text"
    assert payload["task_count"] == 3
    assert payload["declared_minimum_task_count"] == 3
    assert payload["fixed_evaluator_panel"] is True
    assert payload["criterion_reliability"]["fluency"]["krippendorff_alpha"]["applicable"] is True


def test_reliability_cli_writes_report(tmp_path: Path, capsys: object) -> None:
    output = tmp_path / "reliability-report.json"

    exit_code = main(
        [
            "reliability",
            "examples/reliability-text.json",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert output.is_file()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["rubric_id"] == "tr-text-quality"
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "3 tasks" in captured.out
    assert "fluency" in captured.out
