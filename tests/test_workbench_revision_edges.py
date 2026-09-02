from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import turkishevalkit.workbench as workbench


def _payload(*, session: str = "session-001", evaluator: str = "eval-01") -> dict[str, Any]:
    data = json.loads(Path("examples/text-evaluation.json").read_text(encoding="utf-8"))
    data["workflow_context"] = {"session_id": session, "evaluator_id": evaluator}
    return data


def _requested_parent(client: Any) -> str:
    created = client.post("/api/evaluations", json=_payload())
    assert created.status_code == 201
    filename = created.get_json()["filename"]
    assert client.post(
        f"/api/workflows/{filename}/submit", json={"actor_id": "eval-01"}
    ).status_code == 200
    assert client.post(
        f"/api/workflows/{filename}/review",
        json={
            "actor_id": "reviewer-01",
            "outcome": "request_changes",
            "note": "Revise the evidence note.",
        },
    ).status_code == 200
    return filename


def test_revision_route_rejects_wrong_actor_stimulus_and_second_child(tmp_path: Path) -> None:
    app = workbench.create_app(tmp_path)
    app.testing = True
    client = app.test_client()
    parent = _requested_parent(client)

    wrong_actor = client.post(
        f"/api/evaluations/{parent}/revisions",
        json=_payload(session="session-r1", evaluator="eval-02"),
    )
    assert wrong_actor.status_code == 400
    assert "only the original evaluator" in wrong_actor.get_json()["error"]

    changed_source = _payload(session="session-r1")
    changed_source["source"]["response"] = "Different response"
    changed = client.post(f"/api/evaluations/{parent}/revisions", json=changed_source)
    assert changed.status_code == 400
    assert "preserve the original source stimulus" in changed.get_json()["error"]

    first = client.post(
        f"/api/evaluations/{parent}/revisions",
        json=_payload(session="session-r1"),
    )
    assert first.status_code == 201

    duplicate = client.post(
        f"/api/evaluations/{parent}/revisions",
        json=_payload(session="session-r1-duplicate"),
    )
    assert duplicate.status_code == 400
    assert "not awaiting requested changes" in duplicate.get_json()["error"]


def test_revision_chain_preserves_root_and_increments_number(tmp_path: Path) -> None:
    app = workbench.create_app(tmp_path)
    app.testing = True
    client = app.test_client()
    root = _requested_parent(client)

    first = client.post(
        f"/api/evaluations/{root}/revisions",
        json=_payload(session="session-r1"),
    )
    assert first.status_code == 201
    child = first.get_json()["filename"]

    assert client.post(
        f"/api/workflows/{child}/submit", json={"actor_id": "eval-01"}
    ).status_code == 200
    assert client.post(
        f"/api/workflows/{child}/review",
        json={
            "actor_id": "reviewer-02",
            "outcome": "request_changes",
            "note": "One more revision is required.",
        },
    ).status_code == 200

    second = client.post(
        f"/api/evaluations/{child}/revisions",
        json=_payload(session="session-r2"),
    )
    assert second.status_code == 201
    lineage = second.get_json()["revision"]
    assert lineage["revision_number"] == 2
    assert lineage["root_artifact_id"] == root
    assert lineage["supersedes_artifact_id"] == child


def test_revision_storage_rejects_overwrite_and_corrupt_sidecar(tmp_path: Path) -> None:
    lineage = workbench.create_revision_lineage(
        artifact_id="child.json",
        task_id="task-001",
        supersedes_artifact_id="parent.json",
        requested_by="reviewer-01",
        created_by="eval-01",
        request_note="Revise it.",
        occurred_at="2026-09-02T12:00:00Z",
    )
    path = workbench.save_revision_lineage(tmp_path, lineage)
    assert workbench.load_revision_lineage(tmp_path, "child.json") == lineage

    with pytest.raises(ValueError, match="already exists"):
        workbench.save_revision_lineage(tmp_path, lineage)

    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid revision JSON"):
        workbench.load_revision_lineage(tmp_path, "child.json")

    assert workbench.load_revision_lineage(tmp_path, "missing.json") is None


def test_revision_route_requires_json_workflow_and_requested_state(tmp_path: Path) -> None:
    app = workbench.create_app(tmp_path)
    app.testing = True
    client = app.test_client()

    no_workflow = client.post("/api/evaluations", json=json.loads(
        Path("examples/text-evaluation.json").read_text(encoding="utf-8")
    ))
    filename = no_workflow.get_json()["filename"]
    missing_sidecar = client.post(
        f"/api/evaluations/{filename}/revisions",
        json=_payload(session="session-r1"),
    )
    assert missing_sidecar.status_code == 400
    assert "does not have a workflow sidecar" in missing_sidecar.get_json()["error"]

    requested = _requested_parent(client)
    invalid_json = client.post(
        f"/api/evaluations/{requested}/revisions",
        data="not-json",
        content_type="application/json",
    )
    assert invalid_json.status_code == 400
    assert "JSON object" in invalid_json.get_json()["error"]

    assert client.post(
        "/api/evaluations/missing.json/revisions",
        json=_payload(session="session-r2"),
    ).status_code == 404
