from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import turkishevalkit.workbench as workbench


def _payload() -> dict[str, Any]:
    data = json.loads(Path("examples/text-evaluation.json").read_text(encoding="utf-8"))
    data["workflow_context"] = {"session_id": "session-001", "evaluator_id": "eval-01"}
    return data


def test_requested_revision_preserves_parent_and_creates_lineage(tmp_path: Path) -> None:
    app = workbench.create_app(tmp_path)
    app.testing = True
    client = app.test_client()

    created = client.post("/api/evaluations", json=_payload())
    assert created.status_code == 201
    parent = created.get_json()["filename"]
    parent_path = tmp_path / "evaluations" / parent
    original_bytes = parent_path.read_bytes()

    assert client.post(
        f"/api/workflows/{parent}/submit", json={"actor_id": "eval-01"}
    ).status_code == 200
    requested = client.post(
        f"/api/workflows/{parent}/review",
        json={
            "actor_id": "reviewer-01",
            "outcome": "request_changes",
            "note": "Correct the factuality evidence and resubmit.",
        },
    )
    assert requested.status_code == 200
    assert requested.get_json()["workflow"]["state"] == "revision_requested"

    revision_payload = _payload()
    revision_payload["workflow_context"]["session_id"] = "session-002"
    revision_payload["ratings"][2]["score"] = 4
    revision_payload["evaluator_note"] = "Revision after reviewer feedback."
    revised = client.post(f"/api/evaluations/{parent}/revisions", json=revision_payload)
    assert revised.status_code == 201
    body = revised.get_json()
    child = body["filename"]

    assert child != parent
    assert body["workflow"]["state"] == "draft"
    assert body["revision"]["supersedes_artifact_id"] == parent
    assert body["revision"]["root_artifact_id"] == parent
    assert body["revision"]["revision_number"] == 1
    assert body["revision"]["requested_by"] == "reviewer-01"
    assert body["superseded_workflow"]["state"] == "superseded"
    assert parent_path.read_bytes() == original_bytes

    parent_details = client.get(f"/api/history/{parent}/details").get_json()
    child_details = client.get(f"/api/history/{child}/details").get_json()
    assert parent_details["superseded_by"] == child
    assert child_details["revision"]["supersedes_artifact_id"] == parent
