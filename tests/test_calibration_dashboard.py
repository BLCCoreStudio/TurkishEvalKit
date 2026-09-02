from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from turkishevalkit.workbench import create_app


def _text_payload(
    *,
    evaluator_id: str | None,
    session_id: str = "calibration-session",
    scores: tuple[int, int, int, int, int] = (5, 5, 5, 4, 5),
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": "dashboard-calibration-001",
        "evaluation_type": "text",
        "rubric_id": "tr-text-quality",
        "rubric_version": "1.0",
        "source": {
            "prompt": "Parola yöneticisinin neden yararlı olduğunu kısa biçimde açıkla.",
            "response": (
                "Parola yöneticisi her hesap için güçlü ve benzersiz parola kullanmayı "
                "kolaylaştırır ve aynı parolayı tekrar kullanma ihtiyacını azaltır."
            ),
        },
        "ratings": [
            {"criterion_id": "fluency", "score": scores[0], "note": "Akıcı."},
            {
                "criterion_id": "instruction_following",
                "score": scores[1],
                "note": "İstenen kapsamı izliyor.",
            },
            {"criterion_id": "factuality", "score": scores[2], "note": "Doğru."},
            {"criterion_id": "helpfulness", "score": scores[3], "note": "Yararlı."},
            {"criterion_id": "locale_fit", "score": scores[4], "note": "Doğal Türkçe."},
        ],
        "evaluator_note": "Bağımsız insan değerlendirmesi.",
        "justification_en": "The answer is concise and directly addresses the requested security benefit.",
        "metadata": {"test_fixture": True},
    }
    if evaluator_id is not None:
        payload["workflow_context"] = {
            "session_id": session_id,
            "evaluator_id": evaluator_id,
        }
    return payload


def _create_evaluation(client: Any, payload: dict[str, Any]) -> str:
    response = client.post("/api/evaluations", json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert isinstance(body, dict)
    filename = body.get("filename")
    assert isinstance(filename, str)
    return filename


def test_calibration_dashboard_page_and_assets(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()

    page = client.get("/calibration")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert "Multi-evaluator calibration" in text
    assert "calibration.js" in text
    assert "calibration.css" in text
    assert "universal acceptance threshold" in text

    index = client.get("/").get_data(as_text=True)
    assert 'href="/calibration"' in index


def test_calibration_dashboard_creates_append_only_history(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    first = _create_evaluation(
        client,
        _text_payload(evaluator_id="evaluator-a", scores=(5, 5, 5, 4, 5)),
    )
    second = _create_evaluation(
        client,
        _text_payload(evaluator_id="evaluator-b", scores=(5, 4, 5, 4, 4)),
    )

    candidates_response = client.get("/api/calibrations/candidates")
    assert candidates_response.status_code == 200
    candidates = candidates_response.get_json()["items"]
    assert len(candidates) == 2
    assert {item["evaluator_id"] for item in candidates} == {"evaluator-a", "evaluator-b"}
    assert all(item["calibration_ready"] for item in candidates)
    assert len({item["compatibility_key"] for item in candidates}) == 1

    evaluation_dir = tmp_path / "evaluations"
    before = {path.name: path.read_bytes() for path in evaluation_dir.glob("*.json")}

    response = client.post(
        "/api/calibrations",
        json={"filenames": [first, second], "annotation_tolerance_ms": 250},
    )
    assert response.status_code == 201
    created = response.get_json()
    assert created["filename"].endswith(".calibration.json")
    report = created["report"]
    assert report["task_id"] == "dashboard-calibration-001"
    assert report["evaluator_count"] == 2
    assert report["evaluator_pair_count"] == 1
    assert report["within_one_criterion_agreement_rate"] == 1.0
    assert report["exact_criterion_agreement_rate"] == 0.6
    assert set(report["aggregate_scores"]) == {"evaluator-a", "evaluator-b"}

    after = {path.name: path.read_bytes() for path in evaluation_dir.glob("*.json")}
    assert after == before

    history_response = client.get("/api/calibrations")
    assert history_response.status_code == 200
    history = history_response.get_json()["items"]
    assert len(history) == 1
    assert history[0]["filename"] == created["filename"]
    assert history[0]["evaluator_count"] == 2
    assert history[0]["source_artifact_count"] == 2

    details_response = client.get(
        f"/api/calibrations/{created['filename']}/details"
    )
    assert details_response.status_code == 200
    details = details_response.get_json()
    assert details["schema_version"] == "1.0"
    assert details["report"] == report
    assert {item["filename"] for item in details["source_artifacts"]} == {first, second}

    download_response = client.get(
        f"/api/calibrations/{created['filename']}/download"
    )
    assert download_response.status_code == 200
    exported = json.loads(download_response.get_data(as_text=True))
    assert exported["report"]["task_id"] == "dashboard-calibration-001"

    calibration_files = list((tmp_path / "calibrations").glob("*.calibration.json"))
    assert len(calibration_files) == 1


def test_calibration_dashboard_rejects_missing_identity_and_invalid_selection(
    tmp_path: Path,
) -> None:
    client = create_app(tmp_path).test_client()
    identified = _create_evaluation(client, _text_payload(evaluator_id="evaluator-a"))
    anonymous = _create_evaluation(client, _text_payload(evaluator_id=None))

    candidates = client.get("/api/calibrations/candidates").get_json()["items"]
    by_filename = {item["filename"]: item for item in candidates}
    assert by_filename[identified]["calibration_ready"] is True
    assert by_filename[anonymous]["calibration_ready"] is False

    missing_identity = client.post(
        "/api/calibrations",
        json={"filenames": [identified, anonymous]},
    )
    assert missing_identity.status_code == 400
    assert "no evaluator identity" in missing_identity.get_json()["error"]

    duplicate = client.post(
        "/api/calibrations",
        json={"filenames": [identified, identified]},
    )
    assert duplicate.status_code == 400
    assert duplicate.get_json()["error"] == "filenames must be unique"

    invalid_tolerance = client.post(
        "/api/calibrations",
        json={"filenames": [identified, anonymous], "annotation_tolerance_ms": 6000},
    )
    assert invalid_tolerance.status_code == 400
    assert "between 0 and 5000" in invalid_tolerance.get_json()["error"]

    assert client.get("/api/calibrations/../details").status_code == 404
