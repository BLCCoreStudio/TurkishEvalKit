from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from turkishevalkit.workbench import create_app


def _evaluation_from_calibration_example(
    example_path: str,
    index: int,
    *,
    session_id: str,
) -> dict[str, Any]:
    payload = json.loads(Path(example_path).read_text(encoding="utf-8"))
    item = payload["submissions"][index]
    evaluation = dict(item["evaluation"])
    evaluation["workflow_context"] = {
        "session_id": session_id,
        "evaluator_id": item["evaluator_id"],
    }
    return evaluation


def _create(client: Any, payload: dict[str, Any]) -> str:
    response = client.post("/api/evaluations", json=payload)
    assert response.status_code == 201
    filename = response.get_json()["filename"]
    assert isinstance(filename, str)
    return filename


def _create_calibration(client: Any, filenames: list[str], *, tolerance: int = 250) -> str:
    response = client.post(
        "/api/calibrations",
        json={"filenames": filenames, "annotation_tolerance_ms": tolerance},
    )
    assert response.status_code == 201
    filename = response.get_json()["filename"]
    assert isinstance(filename, str)
    return filename


def test_saved_text_calibration_exposes_disagreement_drilldown(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    first = _create(
        client,
        _evaluation_from_calibration_example(
            "examples/calibration-text.json", 0, session_id="session-a"
        ),
    )
    second = _create(
        client,
        _evaluation_from_calibration_example(
            "examples/calibration-text.json", 1, session_id="session-b"
        ),
    )
    calibration = _create_calibration(client, [first, second])

    response = client.get(f"/api/calibrations/{calibration}/disagreements")

    assert response.status_code == 200
    report = response.get_json()
    assert report["task_id"] == "text-calibration-001"
    assert report["disputed_criterion_count"] == 2
    assert report["disputed_criterion_pair_count"] == 2
    assert [item["criterion_id"] for item in report["criteria"][:2]] == [
        "instruction_following",
        "locale_fit",
    ]
    pair = report["criteria"][0]["pair_disagreements"][0]
    assert pair["evaluator_a"] == "evaluator-a"
    assert pair["evaluator_b"] == "evaluator-b"
    assert pair["gap"] == 1
    assert pair["note_a"]
    assert pair["note_b"]


def test_disagreement_route_uses_saved_audio_tolerance(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    first = _create(
        client,
        _evaluation_from_calibration_example(
            "examples/calibration-audio.json", 0, session_id="session-a"
        ),
    )
    second = _create(
        client,
        _evaluation_from_calibration_example(
            "examples/calibration-audio.json", 1, session_id="session-b"
        ),
    )
    calibration = _create_calibration(client, [first, second], tolerance=50)

    response = client.get(f"/api/calibrations/{calibration}/disagreements")

    assert response.status_code == 200
    report = response.get_json()
    pair = report["audio_pair_disagreements"][0]
    assert {item["category"] for item in pair["unmatched_a"]} == {"intonation"}
    assert {item["category"] for item in pair["unmatched_b"]} == {
        "intonation",
        "noise",
    }


def test_disagreement_route_reports_missing_source_without_hiding_calibration(
    tmp_path: Path,
) -> None:
    client = create_app(tmp_path).test_client()
    first = _create(
        client,
        _evaluation_from_calibration_example(
            "examples/calibration-text.json", 0, session_id="session-a"
        ),
    )
    second = _create(
        client,
        _evaluation_from_calibration_example(
            "examples/calibration-text.json", 1, session_id="session-b"
        ),
    )
    calibration = _create_calibration(client, [first, second])
    (tmp_path / "evaluations" / second).unlink()

    response = client.get(f"/api/calibrations/{calibration}/disagreements")

    assert response.status_code == 409
    assert second in response.get_json()["error"]
    assert client.get(f"/api/calibrations/{calibration}/details").status_code == 200


def test_disagreement_route_rejects_tampered_saved_attribution(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    first = _create(
        client,
        _evaluation_from_calibration_example(
            "examples/calibration-text.json", 0, session_id="session-a"
        ),
    )
    second = _create(
        client,
        _evaluation_from_calibration_example(
            "examples/calibration-text.json", 1, session_id="session-b"
        ),
    )
    calibration = _create_calibration(client, [first, second])
    path = tmp_path / "calibrations" / calibration
    artifact = json.loads(path.read_text(encoding="utf-8"))
    artifact["source_artifacts"][1]["evaluator_id"] = "tampered-evaluator"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    response = client.get(f"/api/calibrations/{calibration}/disagreements")

    assert response.status_code == 400
    assert "attribution" in response.get_json()["error"]


def test_disagreement_route_rejects_invalid_or_missing_calibration(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    assert (
        client.get("/api/calibrations/missing.calibration.json/disagreements").status_code
        == 404
    )

    calibration_dir = tmp_path / "calibrations"
    calibration_dir.mkdir()
    path = calibration_dir / "broken.calibration.json"
    path.write_text("{broken", encoding="utf-8")
    response = client.get(f"/api/calibrations/{path.name}/disagreements")
    assert response.status_code == 400
    assert "invalid calibration artifact JSON" in response.get_json()["error"]
