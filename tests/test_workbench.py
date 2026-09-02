from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import turkishevalkit.workbench as workbench
from turkishevalkit.evaluation import evaluate_submission
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC
from turkishevalkit.serialization import load_record


def _text_payload() -> dict[str, Any]:
    return json.loads(Path("examples/text-evaluation.json").read_text(encoding="utf-8"))


def _pairwise_payload() -> dict[str, Any]:
    return json.loads(Path("examples/pairwise-evaluation.json").read_text(encoding="utf-8"))


def _with_workflow(
    payload: dict[str, Any],
    *,
    session_id: str = "session-001",
    evaluator_id: str = "eval-01",
) -> dict[str, Any]:
    payload["workflow_context"] = {
        "session_id": session_id,
        "evaluator_id": evaluator_id,
    }
    return payload


def test_default_workspace_honors_xdg_data_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if workbench.os.name == "nt" or workbench.sys.platform == "darwin":
        pytest.skip("XDG assertion is specific to Unix-like non-macOS runners")

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert workbench.default_workspace() == tmp_path / "turkishevalkit"


def test_rubric_payload_exposes_task_family() -> None:
    payload = workbench.rubric_payload()
    by_id = {item["id"]: item for item in payload}

    assert by_id["tr-text-quality"]["evaluation_type"] == "text"
    assert by_id["tr-audio-quality"]["evaluation_type"] == "audio"
    assert by_id["tr-pairwise-quality"]["evaluation_type"] == "pairwise"
    assert len(by_id["tr-text-quality"]["criteria"]) == 5
    assert len(by_id["tr-pairwise-quality"]["criteria"]) == 5


def test_history_storage_is_append_only_and_skips_invalid_files(tmp_path: Path) -> None:
    record = load_record(Path("examples/text-evaluation.json"))
    assert not hasattr(record, "judgments")
    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)

    first = workbench.save_result(tmp_path, result)
    second = workbench.save_result(tmp_path, result)

    assert first != second
    assert first.exists()
    assert second.exists()

    directory = tmp_path / "evaluations"
    (directory / "broken.json").write_text("{bad-json", encoding="utf-8")
    (directory / "array.json").write_text("[]", encoding="utf-8")

    history = workbench.list_history(tmp_path)
    assert len(history) == 2
    assert history[0]["task_id"] == "text-demo-001"
    assert history[0]["evaluation_type"] == "text"
    assert history[0]["normalized_score"] == 95.0
    assert history[0]["preference_score"] is None
    assert history[0]["workflow_state"] is None


def test_history_keeps_evaluation_visible_when_workflow_sidecar_is_invalid(tmp_path: Path) -> None:
    record = load_record(Path("examples/text-evaluation.json"))
    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)
    evaluation = workbench.save_result(tmp_path, result)

    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir()
    workflow_path = workflow_dir / f"{evaluation.stem}.workflow.json"
    workflow_path.write_text("{broken", encoding="utf-8")

    history = workbench.list_history(tmp_path)
    assert len(history) == 1
    assert history[0]["task_id"] == "text-demo-001"
    assert history[0]["workflow_state"] is None


def test_history_is_empty_before_workspace_is_created(tmp_path: Path) -> None:
    assert workbench.list_history(tmp_path) == []


def test_workbench_routes_validate_save_list_and_export(tmp_path: Path) -> None:
    app = workbench.create_app(tmp_path)
    app.testing = True
    client = app.test_client()

    index = client.get("/")
    assert index.status_code == 200
    assert b"TurkishEvalKit" in index.data
    assert b"Pairwise" in index.data

    config = client.get("/api/config")
    assert config.status_code == 200
    config_payload = config.get_json()
    assert config_payload["workspace"] == str(tmp_path.resolve())
    assert len(config_payload["rubrics"]) == 3
    assert config_payload["workflow"]["review_outcomes"] == ["accept", "escalate"]
    assert set(config_payload["workflow"]["adjudication_outcomes"]) == {
        "evaluation_upheld",
        "review_concern_upheld",
        "inconclusive",
    }

    empty_history = client.get("/api/history")
    assert empty_history.get_json() == {"items": []}

    invalid = client.post(
        "/api/evaluations",
        data="not-json",
        content_type="application/json",
    )
    assert invalid.status_code == 400
    assert "JSON object" in invalid.get_json()["error"]

    invalid_context = _text_payload()
    invalid_context["workflow_context"] = {"session_id": "session-only"}
    response = client.post("/api/evaluations", json=invalid_context)
    assert response.status_code == 400
    assert "requires session_id and evaluator_id" in response.get_json()["error"]

    unknown = _text_payload()
    unknown["rubric_id"] = "does-not-exist"
    response = client.post("/api/evaluations", json=unknown)
    assert response.status_code == 400
    assert "unknown rubric" in response.get_json()["error"]

    wrong_type = _text_payload()
    wrong_type["evaluation_type"] = "audio"
    response = client.post("/api/evaluations", json=wrong_type)
    assert response.status_code == 400
    assert "evaluation_type" in response.get_json()["error"]

    saved = client.post("/api/evaluations", json=_with_workflow(_text_payload()))
    assert saved.status_code == 201
    body = saved.get_json()
    assert body["result"]["task_id"] == "text-demo-001"
    assert body["result"]["normalized_score"] == 95.0
    assert body["workflow"]["state"] == "draft"
    assert body["workflow"]["session"]["session_id"] == "session-001"
    assert body["workflow"]["session"]["evaluator_id"] == "eval-01"

    pairwise_saved = client.post("/api/evaluations", json=_pairwise_payload())
    assert pairwise_saved.status_code == 201
    pairwise_body = pairwise_saved.get_json()
    assert pairwise_body["result"]["task_id"] == "pairwise-demo-001"
    assert pairwise_body["result"]["overall_preference"] == "a"
    assert pairwise_body["result"]["preference_score"] == 40.0
    assert pairwise_body["result"]["preference_counts"] == {"a": 3, "b": 1, "tie": 1}
    assert pairwise_body["workflow"] is None

    history = client.get("/api/history").get_json()["items"]
    assert len(history) == 2
    by_task = {item["task_id"]: item for item in history}
    assert by_task["text-demo-001"]["filename"] == body["filename"]
    assert by_task["text-demo-001"]["workflow_state"] == "draft"
    assert by_task["text-demo-001"]["session_id"] == "session-001"
    assert by_task["pairwise-demo-001"]["filename"] == pairwise_body["filename"]
    assert by_task["pairwise-demo-001"]["evaluation_type"] == "pairwise"
    assert by_task["pairwise-demo-001"]["overall_preference"] == "a"
    assert by_task["pairwise-demo-001"]["preference_score"] == 40.0
    assert by_task["pairwise-demo-001"]["workflow_state"] is None

    details = client.get(f"/api/history/{body['filename']}/details")
    assert details.status_code == 200
    details_payload = details.get_json()
    assert details_payload["evaluation"]["task_id"] == "text-demo-001"
    assert details_payload["workflow"]["state"] == "draft"

    download = client.get(f"/api/history/{body['filename']}")
    assert download.status_code == 200
    exported = json.loads(download.data)
    assert exported["task_id"] == "text-demo-001"

    pairwise_download = client.get(f"/api/history/{pairwise_body['filename']}")
    assert pairwise_download.status_code == 200
    pairwise_exported = json.loads(pairwise_download.data)
    assert pairwise_exported["task_id"] == "pairwise-demo-001"
    assert pairwise_exported["payload"]["source"]["response_a"]
    assert pairwise_exported["payload"]["source"]["response_b"]

    assert client.get("/api/history/missing.json").status_code == 404
    assert client.get("/api/history/not-json.txt").status_code == 404
    assert client.get("/api/history/../escape.json/details").status_code == 404


def test_review_and_adjudication_routes_preserve_evaluation_artifact(tmp_path: Path) -> None:
    app = workbench.create_app(tmp_path)
    app.testing = True
    client = app.test_client()

    created = client.post("/api/evaluations", json=_with_workflow(_text_payload()))
    assert created.status_code == 201
    filename = created.get_json()["filename"]
    evaluation_path = tmp_path / "evaluations" / filename
    original_evaluation = evaluation_path.read_bytes()

    wrong_submitter = client.post(
        f"/api/workflows/{filename}/submit",
        json={"actor_id": "not-the-evaluator"},
    )
    assert wrong_submitter.status_code == 400
    assert "only the session evaluator" in wrong_submitter.get_json()["error"]

    submitted = client.post(
        f"/api/workflows/{filename}/submit",
        json={"actor_id": "eval-01", "note": "Ready for review."},
    )
    assert submitted.status_code == 200
    assert submitted.get_json()["workflow"]["state"] == "submitted"

    self_review = client.post(
        f"/api/workflows/{filename}/review",
        json={"actor_id": "eval-01", "outcome": "accept"},
    )
    assert self_review.status_code == 400
    assert "different from the evaluator" in self_review.get_json()["error"]

    missing_escalation_note = client.post(
        f"/api/workflows/{filename}/review",
        json={"actor_id": "reviewer-01", "outcome": "escalate"},
    )
    assert missing_escalation_note.status_code == 400
    assert "require a note" in missing_escalation_note.get_json()["error"]

    reviewed = client.post(
        f"/api/workflows/{filename}/review",
        json={
            "actor_id": "reviewer-01",
            "outcome": "escalate",
            "note": "The factuality score conflicts with the cited evidence.",
        },
    )
    assert reviewed.status_code == 200
    reviewed_workflow = reviewed.get_json()["workflow"]
    assert reviewed_workflow["state"] == "reviewed"
    assert reviewed_workflow["events"][-1]["review_outcome"] == "escalate"

    non_independent = client.post(
        f"/api/workflows/{filename}/adjudicate",
        json={
            "actor_id": "reviewer-01",
            "outcome": "inconclusive",
            "note": "Cannot adjudicate own review.",
        },
    )
    assert non_independent.status_code == 400
    assert "must be independent" in non_independent.get_json()["error"]

    adjudicated = client.post(
        f"/api/workflows/{filename}/adjudicate",
        json={
            "actor_id": "adjudicator-01",
            "outcome": "review_concern_upheld",
            "note": "Independent evidence confirms the reviewer concern.",
        },
    )
    assert adjudicated.status_code == 200
    adjudicated_workflow = adjudicated.get_json()["workflow"]
    assert adjudicated_workflow["state"] == "adjudicated"
    assert adjudicated_workflow["events"][-1]["adjudication_outcome"] == (
        "review_concern_upheld"
    )
    assert [event["sequence"] for event in adjudicated_workflow["events"]] == [1, 2, 3, 4]

    assert evaluation_path.read_bytes() == original_evaluation

    history = client.get("/api/history").get_json()["items"]
    assert history[0]["workflow_state"] == "adjudicated"
    assert history[0]["review_outcome"] == "escalate"
    assert history[0]["adjudication_outcome"] == "review_concern_upheld"

    sidecars = list((tmp_path / "workflows").glob("*.workflow.json"))
    assert len(sidecars) == 1
    persisted = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert persisted["state"] == "adjudicated"
    assert len(persisted["events"]) == 4


def test_accepted_review_cannot_be_adjudicated(tmp_path: Path) -> None:
    app = workbench.create_app(tmp_path)
    app.testing = True
    client = app.test_client()

    created = client.post(
        "/api/evaluations",
        json=_with_workflow(_pairwise_payload(), session_id="session-02", evaluator_id="eval-02"),
    )
    filename = created.get_json()["filename"]

    assert client.post(
        f"/api/workflows/{filename}/submit", json={"actor_id": "eval-02"}
    ).status_code == 200
    accepted = client.post(
        f"/api/workflows/{filename}/review",
        json={"actor_id": "reviewer-02", "outcome": "accept"},
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["workflow"]["state"] == "reviewed"

    adjudicate = client.post(
        f"/api/workflows/{filename}/adjudicate",
        json={
            "actor_id": "adjudicator-02",
            "outcome": "evaluation_upheld",
            "note": "This should not be reachable for an accepted review.",
        },
    )
    assert adjudicate.status_code == 400
    assert "only escalated reviews" in adjudicate.get_json()["error"]


def test_run_workbench_binds_loopback_and_controls_browser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: dict[str, Any] = {}

    class FakeApp:
        def run(self, **kwargs: Any) -> None:
            calls["run"] = kwargs

    class FakeTimer:
        daemon = False

        def __init__(
            self,
            interval: float,
            function: Any,
            args: tuple[str, ...],
        ) -> None:
            calls["timer"] = (interval, function, args)

        def start(self) -> None:
            calls["timer_started"] = True

    monkeypatch.setattr(workbench, "create_app", lambda workspace: FakeApp())
    monkeypatch.setattr(workbench.threading, "Timer", FakeTimer)

    workbench.run_workbench(tmp_path, port=9999, open_browser=True)

    assert calls["run"] == {
        "host": "127.0.0.1",
        "port": 9999,
        "debug": False,
        "use_reloader": False,
    }
    assert calls["timer"][2] == ("http://127.0.0.1:9999/",)
    assert calls["timer_started"] is True

    with pytest.raises(ValueError, match="port must be between"):
        workbench.run_workbench(tmp_path, port=0)
