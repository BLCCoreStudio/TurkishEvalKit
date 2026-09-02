from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import turkishevalkit.review_queue_app as queue_app


def _payload(*, evaluator_id: str = "eval-01", session_id: str = "session-01") -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        Path("examples/text-evaluation.json").read_text(encoding="utf-8")
    )
    payload["workflow_context"] = {
        "evaluator_id": evaluator_id,
        "session_id": session_id,
    }
    return payload


def test_queue_page_and_empty_api(tmp_path: Path) -> None:
    app = queue_app.create_review_queue_app(tmp_path)
    app.testing = True
    client = app.test_client()

    page = client.get("/queue")
    assert page.status_code == 200
    assert b"Review queue" in page.data
    assert b"Find the evaluation that needs attention next" in page.data

    response = client.get("/api/review-queue")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["items"] == []
    assert payload["summary"]["workspace_total"] == 0
    assert payload["summary"]["actionable_total"] == 0


def test_queue_api_rejects_invalid_query_values(tmp_path: Path) -> None:
    app = queue_app.create_review_queue_app(tmp_path)
    app.testing = True
    client = app.test_client()

    assert client.get("/api/review-queue?action=nope").status_code == 400
    assert client.get("/api/review-queue?sort=nope").status_code == 400
    assert client.get("/api/review-queue?page=0").status_code == 400
    assert client.get("/api/review-queue?page=abc").status_code == 400
    assert client.get("/api/review-queue?per_page=101").status_code == 400


def test_queue_tracks_review_and_adjudication_lifecycle(tmp_path: Path) -> None:
    app = queue_app.create_review_queue_app(tmp_path)
    app.testing = True
    client = app.test_client()

    created = client.post("/api/evaluations", json=_payload())
    assert created.status_code == 201
    filename = created.get_json()["filename"]

    draft = client.get("/api/review-queue?action=draft").get_json()
    assert draft["total"] == 1
    assert draft["items"][0]["queue_action"] == "draft"
    assert draft["items"][0]["evaluator_id"] == "eval-01"

    submitted = client.post(
        f"/api/workflows/{filename}/submit",
        json={"actor_id": "eval-01", "note": "Ready."},
    )
    assert submitted.status_code == 200

    review_queue = client.get("/api/review-queue?action=awaiting_review").get_json()
    assert review_queue["total"] == 1
    assert review_queue["items"][0]["filename"] == filename
    assert review_queue["summary"]["by_action"]["awaiting_review"] == 1

    escalated = client.post(
        f"/api/workflows/{filename}/review",
        json={
            "actor_id": "reviewer-01",
            "outcome": "escalate",
            "note": "Evidence needs independent resolution.",
        },
    )
    assert escalated.status_code == 200

    adjudication_queue = client.get(
        "/api/review-queue?action=awaiting_adjudication&evaluator_id=eval-01"
    ).get_json()
    assert adjudication_queue["total"] == 1
    assert adjudication_queue["items"][0]["review_outcome"] == "escalate"

    adjudicated = client.post(
        f"/api/workflows/{filename}/adjudicate",
        json={
            "actor_id": "adjudicator-01",
            "outcome": "evaluation_upheld",
            "note": "Independent evidence supports the evaluation.",
        },
    )
    assert adjudicated.status_code == 200

    complete = client.get("/api/review-queue?action=complete").get_json()
    assert complete["total"] == 1
    assert complete["items"][0]["queue_action"] == "complete"
    assert complete["summary"]["actionable_total"] == 0


def test_queue_search_filters_and_pagination_use_saved_history(tmp_path: Path) -> None:
    app = queue_app.create_review_queue_app(tmp_path)
    app.testing = True
    client = app.test_client()

    for index, evaluator in enumerate(("alice", "alice", "bob"), start=1):
        payload = _payload(evaluator_id=evaluator, session_id=f"session-{index}")
        payload["task_id"] = f"queue-task-{index}"
        response = client.post("/api/evaluations", json=payload)
        assert response.status_code == 201

    response = client.get(
        "/api/review-queue?q=queue-task&evaluator_id=alice&sort=task&per_page=1&page=2"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 2
    assert body["pages"] == 2
    assert body["page"] == 2
    assert body["items"][0]["task_id"] == "queue-task-2"
    assert {facet["value"] for facet in body["facets"]["evaluator_id"]} == {"alice", "bob"}


def test_run_review_queue_binds_loopback_and_opens_queue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: dict[str, Any] = {}

    class FakeApp:
        def run(self, **kwargs: Any) -> None:
            calls["run"] = kwargs

    class FakeTimer:
        daemon = False

        def __init__(self, interval: float, function: Any, args: tuple[str, ...]) -> None:
            calls["timer"] = (interval, function, args)

        def start(self) -> None:
            calls["timer_started"] = True

    monkeypatch.setattr(queue_app, "create_review_queue_app", lambda workspace: FakeApp())
    monkeypatch.setattr(queue_app.threading, "Timer", FakeTimer)

    queue_app.run_review_queue(tmp_path, port=9876, open_browser=True)

    assert calls["run"] == {
        "host": "127.0.0.1",
        "port": 9876,
        "debug": False,
        "use_reloader": False,
    }
    assert calls["timer"][2] == ("http://127.0.0.1:9876/queue",)
    assert calls["timer_started"] is True

    with pytest.raises(ValueError, match="port must be between"):
        queue_app.run_review_queue(tmp_path, port=0)
