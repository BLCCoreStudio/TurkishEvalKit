from __future__ import annotations

from pathlib import Path

import pytest

from turkishevalkit.evaluation import evaluate_submission
from turkishevalkit.models import EvaluationType, PairwiseEvaluationRecord, Preference
from turkishevalkit.pairwise import evaluate_pairwise_submission
from turkishevalkit.rubrics import PAIRWISE_QUALITY_RUBRIC, TEXT_QUALITY_RUBRIC
from turkishevalkit.serialization import load_record, write_result


def test_load_example_and_write_result(tmp_path: Path) -> None:
    record = load_record(Path("examples/text-evaluation.json"))

    assert record.evaluation_type is EvaluationType.TEXT
    assert record.rubric_id == TEXT_QUALITY_RUBRIC.id
    assert not isinstance(record, PairwiseEvaluationRecord)

    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)
    output = tmp_path / "result.json"
    write_result(output, result)

    rendered = output.read_text(encoding="utf-8")
    assert '"task_id": "text-demo-001"' in rendered
    assert '"normalized_score"' in rendered
    assert "İki faktörlü" in rendered


def test_load_pairwise_example_and_write_result(tmp_path: Path) -> None:
    record = load_record(Path("examples/pairwise-evaluation.json"))

    assert isinstance(record, PairwiseEvaluationRecord)
    assert record.evaluation_type is EvaluationType.PAIRWISE
    assert record.overall_preference is Preference.A
    assert record.preference_strength == 2

    result = evaluate_pairwise_submission(record, PAIRWISE_QUALITY_RUBRIC)
    output = tmp_path / "pairwise-result.json"
    write_result(output, result)

    rendered = output.read_text(encoding="utf-8")
    assert '"task_id": "pairwise-demo-001"' in rendered
    assert '"preference_score": 40.0' in rendered
    assert '"overall_preference": "a"' in rendered
    assert '"response_a"' in rendered
    assert '"response_b"' in rendered


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
