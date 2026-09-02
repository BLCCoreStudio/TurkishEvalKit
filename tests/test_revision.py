from __future__ import annotations

import pytest

from turkishevalkit.revision import (
    RevisionLineage,
    create_revision_lineage,
    revision_from_dict,
    revision_to_dict,
)

CREATED_AT = "2026-09-02T12:00:00Z"


def test_revision_lineage_starts_at_one_and_roundtrips() -> None:
    lineage = create_revision_lineage(
        artifact_id="task-revision.json",
        task_id="task-001",
        supersedes_artifact_id="task-original.json",
        requested_by="reviewer-01",
        created_by="eval-01",
        request_note="Fix factuality evidence.",
        occurred_at=CREATED_AT,
    )

    assert lineage.schema_version == 1
    assert lineage.root_artifact_id == "task-original.json"
    assert lineage.revision_number == 1
    assert revision_from_dict(revision_to_dict(lineage)) == lineage


def test_revision_chain_increments_from_parent_lineage() -> None:
    first = create_revision_lineage(
        artifact_id="task-r1.json",
        task_id="task-001",
        supersedes_artifact_id="task-r0.json",
        requested_by="reviewer-01",
        created_by="eval-01",
        request_note="First revision.",
        occurred_at=CREATED_AT,
    )
    second = create_revision_lineage(
        artifact_id="task-r2.json",
        task_id="task-001",
        supersedes_artifact_id="task-r1.json",
        requested_by="reviewer-02",
        created_by="eval-01",
        request_note="Second revision.",
        parent_lineage=first,
        occurred_at=CREATED_AT,
    )

    assert second.root_artifact_id == "task-r0.json"
    assert second.revision_number == 2


def test_parent_lineage_must_match_superseded_artifact() -> None:
    parent = create_revision_lineage(
        artifact_id="task-r1.json",
        task_id="task-001",
        supersedes_artifact_id="task-r0.json",
        requested_by="reviewer-01",
        created_by="eval-01",
        request_note="First revision.",
        occurred_at=CREATED_AT,
    )

    with pytest.raises(ValueError, match="does not describe"):
        create_revision_lineage(
            artifact_id="task-r2.json",
            task_id="task-001",
            supersedes_artifact_id="different.json",
            requested_by="reviewer-02",
            created_by="eval-01",
            request_note="Second revision.",
            parent_lineage=parent,
            occurred_at=CREATED_AT,
        )


def test_revision_lineage_rejects_invalid_intrinsic_fields() -> None:
    values = {
        "schema_version": 1,
        "artifact_id": "task-r1.json",
        "task_id": "task-001",
        "root_artifact_id": "task-r0.json",
        "supersedes_artifact_id": "task-r0.json",
        "revision_number": 1,
        "requested_by": "reviewer-01",
        "created_by": "eval-01",
        "request_note": "Fix evidence.",
        "created_at": CREATED_AT,
    }

    with pytest.raises(ValueError, match="schema_version"):
        RevisionLineage(**{**values, "schema_version": 2})
    with pytest.raises(ValueError, match="cannot supersede itself"):
        RevisionLineage(**{**values, "supersedes_artifact_id": "task-r1.json"})
    with pytest.raises(ValueError, match="revision_number"):
        RevisionLineage(**{**values, "revision_number": 0})
    with pytest.raises(ValueError, match="request_note"):
        RevisionLineage(**{**values, "request_note": " "})
    with pytest.raises(ValueError, match="timezone"):
        RevisionLineage(**{**values, "created_at": "2026-09-02T12:00:00"})
