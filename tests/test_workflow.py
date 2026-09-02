from __future__ import annotations

import pytest

from turkishevalkit.workflow import (
    ActorRole,
    adjudicate_workflow,
    AdjudicationOutcome,
    create_workflow,
    ReviewOutcome,
    review_workflow,
    submit_workflow,
    WorkflowEventKind,
    WorkflowState,
)


CREATED_AT = "2026-09-02T10:00:00Z"
SUBMITTED_AT = "2026-09-02T10:05:00Z"
REVIEWED_AT = "2026-09-02T10:10:00Z"
ADJUDICATED_AT = "2026-09-02T10:15:00Z"


def _draft():
    return create_workflow(
        artifact_id="text-demo-001-20260902T100000000000Z.json",
        task_id="text-demo-001",
        session_id="session-001",
        evaluator_id="eval-01",
        occurred_at=CREATED_AT,
    )


def _submitted():
    return submit_workflow(_draft(), actor_id="eval-01", occurred_at=SUBMITTED_AT)


def _escalated():
    return review_workflow(
        _submitted(),
        reviewer_id="reviewer-01",
        outcome=ReviewOutcome.ESCALATE,
        note="The factuality judgment needs independent resolution.",
        occurred_at=REVIEWED_AT,
    )


def test_create_workflow_starts_draft_with_embedded_session() -> None:
    workflow = _draft()

    assert workflow.state is WorkflowState.DRAFT
    assert workflow.session.session_id == "session-001"
    assert workflow.session.evaluator_id == "eval-01"
    assert workflow.session.started_at == CREATED_AT
    assert len(workflow.events) == 1
    assert workflow.events[0].kind is WorkflowEventKind.CREATED
    assert workflow.events[0].actor_role is ActorRole.EVALUATOR
    assert workflow.events[0].from_state is None
    assert workflow.events[0].to_state is WorkflowState.DRAFT
    assert workflow.events[0].event_id


def test_submit_requires_session_evaluator_and_draft_state() -> None:
    workflow = _draft()

    submitted = submit_workflow(
        workflow,
        actor_id="eval-01",
        note="Ready for independent review.",
        occurred_at=SUBMITTED_AT,
    )
    assert submitted.state is WorkflowState.SUBMITTED
    assert submitted.events[-1].kind is WorkflowEventKind.SUBMITTED
    assert submitted.events[-1].sequence == 2

    with pytest.raises(ValueError, match="only the session evaluator"):
        submit_workflow(workflow, actor_id="someone-else")
    with pytest.raises(ValueError, match="cannot submit workflow from state submitted"):
        submit_workflow(submitted, actor_id="eval-01")


def test_review_requires_independent_reviewer() -> None:
    submitted = _submitted()

    accepted = review_workflow(
        submitted,
        reviewer_id="reviewer-01",
        outcome=ReviewOutcome.ACCEPT,
        occurred_at=REVIEWED_AT,
    )
    assert accepted.state is WorkflowState.REVIEWED
    assert accepted.review_outcome is ReviewOutcome.ACCEPT
    assert accepted.reviewer_id == "reviewer-01"
    assert accepted.events[-1].actor_role is ActorRole.REVIEWER

    with pytest.raises(ValueError, match="different from the evaluator"):
        review_workflow(
            submitted,
            reviewer_id="eval-01",
            outcome=ReviewOutcome.ACCEPT,
        )


def test_escalation_requires_explanatory_note() -> None:
    with pytest.raises(ValueError, match="require a note"):
        review_workflow(
            _submitted(),
            reviewer_id="reviewer-01",
            outcome=ReviewOutcome.ESCALATE,
        )


def test_only_escalated_reviews_can_be_adjudicated() -> None:
    accepted = review_workflow(
        _submitted(),
        reviewer_id="reviewer-01",
        outcome=ReviewOutcome.ACCEPT,
        occurred_at=REVIEWED_AT,
    )

    with pytest.raises(ValueError, match="only escalated reviews"):
        adjudicate_workflow(
            accepted,
            adjudicator_id="adjudicator-01",
            outcome=AdjudicationOutcome.EVALUATION_UPHELD,
            note="No escalation exists.",
        )


def test_adjudication_preserves_full_event_chain() -> None:
    adjudicated = adjudicate_workflow(
        _escalated(),
        adjudicator_id="adjudicator-01",
        outcome=AdjudicationOutcome.REVIEW_CONCERN_UPHELD,
        note="Reviewer concern is supported by the task evidence.",
        occurred_at=ADJUDICATED_AT,
    )

    assert adjudicated.state is WorkflowState.ADJUDICATED
    assert adjudicated.review_outcome is ReviewOutcome.ESCALATE
    assert adjudicated.adjudication_outcome is AdjudicationOutcome.REVIEW_CONCERN_UPHELD
    assert [event.sequence for event in adjudicated.events] == [1, 2, 3, 4]
    assert [event.kind for event in adjudicated.events] == [
        WorkflowEventKind.CREATED,
        WorkflowEventKind.SUBMITTED,
        WorkflowEventKind.REVIEWED,
        WorkflowEventKind.ADJUDICATED,
    ]
    assert adjudicated.events[-1].actor_role is ActorRole.ADJUDICATOR


def test_adjudicator_must_be_independent_and_explain_resolution() -> None:
    escalated = _escalated()

    for actor_id in ["eval-01", "reviewer-01"]:
        with pytest.raises(ValueError, match="independent"):
            adjudicate_workflow(
                escalated,
                adjudicator_id=actor_id,
                outcome=AdjudicationOutcome.INCONCLUSIVE,
                note="Independent resolution required.",
            )

    with pytest.raises(ValueError, match="requires a resolution note"):
        adjudicate_workflow(
            escalated,
            adjudicator_id="adjudicator-01",
            outcome=AdjudicationOutcome.INCONCLUSIVE,
            note="",
        )


def test_timestamps_must_be_timezone_aware_iso_8601() -> None:
    with pytest.raises(ValueError, match="must include a timezone"):
        create_workflow(
            artifact_id="artifact.json",
            task_id="task",
            session_id="session",
            evaluator_id="eval",
            occurred_at="2026-09-02T10:00:00",
        )

    with pytest.raises(ValueError, match="ISO-8601"):
        create_workflow(
            artifact_id="artifact.json",
            task_id="task",
            session_id="session",
            evaluator_id="eval",
            occurred_at="not-a-time",
        )
