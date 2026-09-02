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
    task_id: str = "dashboard-calibration-001",
    response_text: str = (
        "A password manager makes it easier to use a strong unique password "
        "for each account and reduces password reuse."
    ),
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": task_id,
        "evaluation_type": "text",
        "rubric_id": "tr-text-quality",
        "rubric_version": "1.0",
        "source": {
            "prompt": "Explain briefly why a password manager is useful.",
            "response": response_text,
        },
        "ratings": [
            {"criterion_id": "fluency", "score": scores[0], "note": "Natural."},
            {
                "criterion_id": "instruction_following",
                "score": scores[1],
                "note": "Follows scope.",
            },
            {"criterion_id": "factuality", "score": scores[2], "note": "Accurate."},
            {"criterion_id": "helpfulness", "score": scores[3], "note": "Useful."},
            {
                "criterion_id": "locale_fit",
                "score": scores[4],
                "note": "Locale fit checked.",
            },
        ],
        "evaluator_note": "Independent human evaluation fixture.",
        "justification_en": (
            "The answer is concise and directly addresses the requested "
            "security benefit."
        ),
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


def _create_two_compatible(client: Any) -> tuple[str, str]:
    first = _create_evaluation(
        client,
        _text_payload(evaluator_id="evaluator-a", scores=(5, 5, 5, 4, 5)),
    )
    second = _create_evaluation(
        client,
        _text_payload(evaluator_id="evaluator-b", scores=(5, 4, 5, 4, 4)),
    )
    return first, second


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

    assert client.get("/static/calibration.css").status_code == 200
    assert client.get("/static/calibration.js").status_code == 200


def test_calibration_dashboard_creates_append_only_history(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    first, second = _create_two_compatible(client)

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

    details_response = client.get(f"/api/calibrations/{created['filename']}/details")
    assert details_response.status_code == 200
    details = details_response.get_json()
    assert details["schema_version"] == "1.0"
    assert details["report"] == report
    assert {item["filename"] for item in details["source_artifacts"]} == {first, second}

    download_response = client.get(f"/api/calibrations/{created['filename']}/download")
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


def test_calibration_dashboard_validates_request_shape_and_compatibility(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    first, second = _create_two_compatible(client)
    incompatible = _create_evaluation(
        client,
        _text_payload(
            evaluator_id="evaluator-c",
            response_text="A different source response must not be mixed into calibration.",
        ),
    )

    not_json = client.post(
        "/api/calibrations",
        data="not-json",
        content_type="text/plain",
    )
    assert not_json.status_code == 400
    assert not_json.get_json()["error"] == "request body must be a JSON object"

    one_file = client.post("/api/calibrations", json={"filenames": [first]})
    assert one_file.status_code == 400
    assert "at least two" in one_file.get_json()["error"]

    invalid_filename_type = client.post(
        "/api/calibrations",
        json={"filenames": [first, 123]},
    )
    assert invalid_filename_type.status_code == 400
    assert "non-empty strings" in invalid_filename_type.get_json()["error"]

    bool_tolerance = client.post(
        "/api/calibrations",
        json={"filenames": [first, second], "annotation_tolerance_ms": True},
    )
    assert bool_tolerance.status_code == 400
    assert "must be an integer" in bool_tolerance.get_json()["error"]

    missing = client.post(
        "/api/calibrations",
        json={"filenames": [first, "missing-evaluation.json"]},
    )
    assert missing.status_code == 404

    mismatch = client.post(
        "/api/calibrations",
        json={"filenames": [first, incompatible]},
    )
    assert mismatch.status_code == 400
    assert "same source" in mismatch.get_json()["error"]


def test_calibration_candidates_and_history_skip_corrupt_artifacts(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    identified = _create_evaluation(client, _text_payload(evaluator_id="evaluator-a"))

    evaluation_dir = tmp_path / "evaluations"
    (evaluation_dir / "broken.json").write_text("{broken", encoding="utf-8")
    (evaluation_dir / "array.json").write_text("[]", encoding="utf-8")
    (evaluation_dir / "missing-payload.json").write_text("{}", encoding="utf-8")

    workflow_path = tmp_path / "workflows" / f"{identified[:-5]}.workflow.json"
    workflow_path.write_text("{broken", encoding="utf-8")

    candidates = client.get("/api/calibrations/candidates").get_json()["items"]
    assert len(candidates) == 1
    assert candidates[0]["filename"] == identified
    assert candidates[0]["calibration_ready"] is False
    assert candidates[0]["evaluator_id"] is None

    calibration_dir = tmp_path / "calibrations"
    calibration_dir.mkdir()
    (calibration_dir / "broken.calibration.json").write_text("{broken", encoding="utf-8")
    (calibration_dir / "missing-report.calibration.json").write_text(
        json.dumps({"created_at": "2026-09-02T00:00:00+00:00"}),
        encoding="utf-8",
    )
    assert client.get("/api/calibrations").get_json()["items"] == []


def test_calibration_details_reject_missing_and_corrupt_artifacts(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    assert client.get("/api/calibrations/missing.calibration.json/details").status_code == 404
    assert client.get("/api/calibrations/missing.calibration.json/download").status_code == 404

    calibration_dir = tmp_path / "calibrations"
    calibration_dir.mkdir()
    broken = calibration_dir / "broken.calibration.json"
    broken.write_text("{broken", encoding="utf-8")

    details = client.get(f"/api/calibrations/{broken.name}/details")
    assert details.status_code == 400
    assert "invalid calibration artifact JSON" in details.get_json()["error"]

    download = client.get(f"/api/calibrations/{broken.name}/download")
    assert download.status_code == 400
    assert "invalid calibration artifact JSON" in download.get_json()["error"]
