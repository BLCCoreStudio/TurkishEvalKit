from __future__ import annotations

from pathlib import Path

import pytest

from turkishevalkit.evaluation import evaluate_submission
from turkishevalkit.models import EvaluationType
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC
from turkishevalkit.serialization import load_record, write_result


def test_load_example_and_write_result(tmp_path: Path) -> None:
    record = load_record(Path("examples/text-evaluation.json"))

    assert record.evaluation_type is EvaluationType.TEXT
    assert record.rubric_id == TEXT_QUALITY_RUBRIC.id

    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)
    output = tmp_path / "result.json"
    write_result(output, result)

    rendered = output.read_text(encoding="utf-8")
    assert '"task_id": "text-demo-001"' in rendered
    assert '"normalized_score"' in rendered
    assert "İki faktörlü" in rendered


def test_invalid_json_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSON"):
        load_record(path)


def test_unknown_evaluation_type_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unknown.json"
    path.write_text(
        '{"task_id":"x","evaluation_type":"video","rubric_id":"x","rubric_version":"1","ratings":[]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="evaluation_type must be one of"):
        load_record(path)
