"""TurkishEvalKit public package interface."""

from .evaluation import evaluate_submission
from .models import (
    EvaluationRecord,
    EvaluationType,
    PairwiseEvaluationRecord,
    PairwiseJudgment,
    Preference,
    Rating,
    Rubric,
    RubricCriterion,
)
from .pairwise import PairwiseEvaluationResult, evaluate_pairwise_submission
from .rubrics import AUDIO_QUALITY_RUBRIC, PAIRWISE_QUALITY_RUBRIC, TEXT_QUALITY_RUBRIC
from .workflow import (
    ActorRole,
    AdjudicationOutcome,
    EvaluationSession,
    EvaluationWorkflow,
    ReviewOutcome,
    WorkflowEvent,
    WorkflowEventKind,
    WorkflowState,
    adjudicate_workflow,
    create_workflow,
    review_workflow,
    submit_workflow,
)

__all__ = [
    "AUDIO_QUALITY_RUBRIC",
    "PAIRWISE_QUALITY_RUBRIC",
    "TEXT_QUALITY_RUBRIC",
    "ActorRole",
    "AdjudicationOutcome",
    "EvaluationRecord",
    "EvaluationSession",
    "EvaluationType",
    "EvaluationWorkflow",
    "PairwiseEvaluationRecord",
    "PairwiseEvaluationResult",
    "PairwiseJudgment",
    "Preference",
    "Rating",
    "ReviewOutcome",
    "Rubric",
    "RubricCriterion",
    "WorkflowEvent",
    "WorkflowEventKind",
    "WorkflowState",
    "adjudicate_workflow",
    "create_workflow",
    "evaluate_pairwise_submission",
    "evaluate_submission",
    "review_workflow",
    "submit_workflow",
]

__version__ = "0.3.0"
