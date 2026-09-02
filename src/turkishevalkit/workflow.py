"""Typed evaluator-session, review, and adjudication workflow primitives."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class WorkflowState(StrEnum):
    """Persisted lifecycle states for one saved evaluation artifact."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    ADJUDICATED = "adjudicated"


class ActorRole(StrEnum):
    """Human roles allowed to author workflow events."""

    EVALUATOR = "evaluator"
    REVIEWER = "reviewer"
    ADJUDICATOR = "adjudicator"


class WorkflowEventKind(StrEnum):
    """Append-only event kinds in the current workflow schema."""

    CREATED = "created"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    ADJUDICATED = "adjudicated"


class ReviewOutcome(StrEnum):
    """Reviewer disposition without mutating the original evaluation."""

    ACCEPT = "accept"
    ESCALATE = "escalate"


class AdjudicationOutcome(StrEnum):
    """Resolution labels for an escalated reviewer disagreement."""

    EVALUATION_UPHELD = "evaluation_upheld"
    REVIEW_CONCERN_UPHELD = "review_concern_upheld"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class EvaluationSession:
    """Local evaluator identity and session context embedded in a workflow."""

    session_id: str
    evaluator_id: str
    started_at: str

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if not self.evaluator_id.strip():
            raise ValueError("evaluator_id must not be empty")
        _validate_timestamp(self.started_at, "started_at")


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    """One immutable state transition authored by a named human role."""

    sequence: int
    event_id: str
    kind: WorkflowEventKind
    from_state: WorkflowState | None
    to_state: WorkflowState
    actor_id: str
    actor_role: ActorRole
    occurred_at: str
    note: str = ""
    review_outcome: ReviewOutcome | None = None
    adjudication_outcome: AdjudicationOutcome | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("workflow event sequence must be positive")
        if not self.event_id.strip():
            raise ValueError("event_id must not be empty")
        if not self.actor_id.strip():
            raise ValueError("actor_id must not be empty")
        _validate_timestamp(self.occurred_at, "occurred_at")
        if self.kind is WorkflowEventKind.REVIEWED and self.review_outcome is None:
            raise ValueError("review events require review_outcome")
        if self.kind is not WorkflowEventKind.REVIEWED and self.review_outcome is not None:
            raise ValueError("review_outcome is only valid on review events")
        if self.kind is WorkflowEventKind.ADJUDICATED and self.adjudication_outcome is None:
            raise ValueError("adjudication events require adjudication_outcome")
        if self.kind is not WorkflowEventKind.ADJUDICATED and self.adjudication_outcome is not None:
            raise ValueError("adjudication_outcome is only valid on adjudication events")


@dataclass(frozen=True, slots=True)
class EvaluationWorkflow:
    """Current workflow snapshot plus the complete transition history."""

    artifact_id: str
    task_id: str
    session: EvaluationSession
    state: WorkflowState
    events: tuple[WorkflowEvent, ...]

    def __post_init__(self) -> None:
        if not self.artifact_id.strip() or not self.task_id.strip():
            raise ValueError("artifact_id and task_id must not be empty")
        if not self.events:
            raise ValueError("workflow must contain at least one event")
        expected_sequences = list(range(1, len(self.events) + 1))
        if [event.sequence for event in self.events] != expected_sequences:
            raise ValueError("workflow event sequences must be contiguous from 1")
        if self.events[-1].to_state is not self.state:
            raise ValueError("workflow state must match the latest event")
        previous: WorkflowState | None = None
        for event in self.events:
            if event.from_state is not previous:
                raise ValueError("workflow event state chain is inconsistent")
            previous = event.to_state

    @property
    def review_outcome(self) -> ReviewOutcome | None:
        """Return the latest reviewer disposition, if one exists."""

        for event in reversed(self.events):
            if event.review_outcome is not None:
                return event.review_outcome
        return None

    @property
    def reviewer_id(self) -> str | None:
        """Return the latest reviewer identity, if one exists."""

        for event in reversed(self.events):
            if event.kind is WorkflowEventKind.REVIEWED:
                return event.actor_id
        return None

    @property
    def adjudication_outcome(self) -> AdjudicationOutcome | None:
        """Return the adjudication disposition, if one exists."""

        for event in reversed(self.events):
            if event.adjudication_outcome is not None:
                return event.adjudication_outcome
        return None


def utc_now_iso() -> str:
    """Return a canonical UTC timestamp for persisted workflow events."""

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_workflow(
    *,
    artifact_id: str,
    task_id: str,
    session_id: str,
    evaluator_id: str,
    occurred_at: str | None = None,
) -> EvaluationWorkflow:
    """Create a draft workflow for one already-saved evaluation artifact."""

    timestamp = occurred_at or utc_now_iso()
    session = EvaluationSession(
        session_id=session_id,
        evaluator_id=evaluator_id,
        started_at=timestamp,
    )
    created = _event(
        sequence=1,
        kind=WorkflowEventKind.CREATED,
        from_state=None,
        to_state=WorkflowState.DRAFT,
        actor_id=evaluator_id,
        actor_role=ActorRole.EVALUATOR,
        occurred_at=timestamp,
        note="Evaluation workflow created.",
    )
    return EvaluationWorkflow(
        artifact_id=artifact_id,
        task_id=task_id,
        session=session,
        state=WorkflowState.DRAFT,
        events=(created,),
    )


def submit_workflow(
    workflow: EvaluationWorkflow,
    *,
    actor_id: str,
    note: str = "",
    occurred_at: str | None = None,
) -> EvaluationWorkflow:
    """Submit a draft evaluation for independent review."""

    _require_state(workflow, WorkflowState.DRAFT, "submit")
    if actor_id != workflow.session.evaluator_id:
        raise ValueError("only the session evaluator can submit this workflow")
    return _append(
        workflow,
        kind=WorkflowEventKind.SUBMITTED,
        to_state=WorkflowState.SUBMITTED,
        actor_id=actor_id,
        actor_role=ActorRole.EVALUATOR,
        occurred_at=occurred_at,
        note=note,
    )


def review_workflow(
    workflow: EvaluationWorkflow,
    *,
    reviewer_id: str,
    outcome: ReviewOutcome,
    note: str = "",
    occurred_at: str | None = None,
) -> EvaluationWorkflow:
    """Record an independent review decision without rewriting evaluator evidence."""

    _require_state(workflow, WorkflowState.SUBMITTED, "review")
    if reviewer_id == workflow.session.evaluator_id:
        raise ValueError("reviewer must be different from the evaluator")
    if outcome is ReviewOutcome.ESCALATE and not note.strip():
        raise ValueError("escalated reviews require a note explaining the disagreement")
    return _append(
        workflow,
        kind=WorkflowEventKind.REVIEWED,
        to_state=WorkflowState.REVIEWED,
        actor_id=reviewer_id,
        actor_role=ActorRole.REVIEWER,
        occurred_at=occurred_at,
        note=note,
        review_outcome=outcome,
    )


def adjudicate_workflow(
    workflow: EvaluationWorkflow,
    *,
    adjudicator_id: str,
    outcome: AdjudicationOutcome,
    note: str,
    occurred_at: str | None = None,
) -> EvaluationWorkflow:
    """Resolve an escalated review while preserving the original evaluation and review."""

    _require_state(workflow, WorkflowState.REVIEWED, "adjudicate")
    if workflow.review_outcome is not ReviewOutcome.ESCALATE:
        raise ValueError("only escalated reviews can be adjudicated")
    if adjudicator_id in {workflow.session.evaluator_id, workflow.reviewer_id}:
        raise ValueError("adjudicator must be independent from evaluator and reviewer")
    if not note.strip():
        raise ValueError("adjudication requires a resolution note")
    return _append(
        workflow,
        kind=WorkflowEventKind.ADJUDICATED,
        to_state=WorkflowState.ADJUDICATED,
        actor_id=adjudicator_id,
        actor_role=ActorRole.ADJUDICATOR,
        occurred_at=occurred_at,
        note=note,
        adjudication_outcome=outcome,
    )


def _append(
    workflow: EvaluationWorkflow,
    *,
    kind: WorkflowEventKind,
    to_state: WorkflowState,
    actor_id: str,
    actor_role: ActorRole,
    note: str,
    occurred_at: str | None,
    review_outcome: ReviewOutcome | None = None,
    adjudication_outcome: AdjudicationOutcome | None = None,
) -> EvaluationWorkflow:
    event = _event(
        sequence=len(workflow.events) + 1,
        kind=kind,
        from_state=workflow.state,
        to_state=to_state,
        actor_id=actor_id,
        actor_role=actor_role,
        occurred_at=occurred_at or utc_now_iso(),
        note=note,
        review_outcome=review_outcome,
        adjudication_outcome=adjudication_outcome,
    )
    return replace(workflow, state=to_state, events=(*workflow.events, event))


def _event(
    *,
    sequence: int,
    kind: WorkflowEventKind,
    from_state: WorkflowState | None,
    to_state: WorkflowState,
    actor_id: str,
    actor_role: ActorRole,
    occurred_at: str,
    note: str,
    review_outcome: ReviewOutcome | None = None,
    adjudication_outcome: AdjudicationOutcome | None = None,
) -> WorkflowEvent:
    return WorkflowEvent(
        sequence=sequence,
        event_id=uuid4().hex,
        kind=kind,
        from_state=from_state,
        to_state=to_state,
        actor_id=actor_id,
        actor_role=actor_role,
        occurred_at=occurred_at,
        note=note.strip(),
        review_outcome=review_outcome,
        adjudication_outcome=adjudication_outcome,
    )


def _require_state(workflow: EvaluationWorkflow, expected: WorkflowState, action: str) -> None:
    if workflow.state is not expected:
        raise ValueError(f"cannot {action} workflow from state {workflow.state.value}")


def _validate_timestamp(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
