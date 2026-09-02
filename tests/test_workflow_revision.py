from __future__ import annotations

import pytest

from turkishevalkit.workflow import (
    ReviewOutcome,
    WorkflowEventKind,
    WorkflowState,
    create_workflow,
    mark_revision_created,
    review_workflow,
    submit_workflow,
)

CREATED_AT = "2026-09-02T12:00:00Z"
SUBMITTED_AT = "2026-09-02T12:05:00Z"
REVIEWED_AT = "2026-09-02T12:10:00Z"
REVISED_AT = "2026-09-02T12:15:00Z"


def _submitted():
    draft = create_workflow(
        artifact_id="task-r0.json",
        task_id="task-001",
        session_id="session-001",
        evaluator_id="eval-01",
        occurred_at=CREATED_AT,
    )
    return submit_workflow(draft, actor_id="eval-01", occurred_at=SUBMITTED_AT)


def _requested():
    return review_workflow(
        _submitted(),
        reviewer_id="reviewer-01",
        outcome=ReviewOutcome.REQUEST_CHANGES,
        note="The factuality evidence needs correction.",
        occurred_at=REVIEWED_AT,
    )


def test_request_changes_enters_revision_requested_state() -> None:
    workflow = _requested()

    assert workflow.state is WorkflowState.REVISION_REQUESTED
    assert workflow.review_outcome is ReviewOutcome.REQUEST_CHANGES
    assert workflow.reviewer_id == "reviewer-01"
    assert workflow.events[-1].kind is WorkflowEventKind.REVIEWED


def test_request_changes_requires_explanatory_note() -> None:
    with pytest.raises(ValueError, match="explanatory note"):
        review_workflow(
            _submitted(),
            reviewer_id="reviewer-01",
            outcome=ReviewOutcome.REQUEST_CHANGES,
        )


def test_revision_created_marks_parent_superseded() -> None:
    superseded = mark_revision_created(
        _requested(),
        actor_id="eval-01",
        revised_artifact_id="task-r1.json",
        occurred_at=REVISED_AT,
    )

    assert superseded.state is WorkflowState.SUPERSEDED
    assert superseded.superseded_by == "task-r1.json"
    assert superseded.events[-1].kind is WorkflowEventKind.REVISION_CREATED
    assert superseded.events[-1].related_artifact_id == "task-r1.json"
    assert [event.sequence for event in superseded.events] == [1, 2, 3, 4]


def test_only_original_evaluator_can_create_requested_revision() -> None:
    with pytest.raises(ValueError, match="only the original evaluator"):
        mark_revision_created(
            _requested(),
            actor_id="someone-else",
            revised_artifact_id="task-r1.json",
        )


def test_revision_cannot_be_created_without_request_changes() -> None:
    accepted = review_workflow(
        _submitted(),
        reviewer_id="reviewer-01",
        outcome=ReviewOutcome.ACCEPT,
        occurred_at=REVIEWED_AT,
    )
    with pytest.raises(ValueError, match="cannot create revision"):
        mark_revision_created(
            accepted,
            actor_id="eval-01",
            revised_artifact_id="task-r1.json",
        )
