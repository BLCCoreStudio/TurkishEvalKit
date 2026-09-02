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

__all__ = [
    "AUDIO_QUALITY_RUBRIC",
    "PAIRWISE_QUALITY_RUBRIC",
    "TEXT_QUALITY_RUBRIC",
    "EvaluationRecord",
    "EvaluationType",
    "PairwiseEvaluationRecord",
    "PairwiseEvaluationResult",
    "PairwiseJudgment",
    "Preference",
    "Rating",
    "Rubric",
    "RubricCriterion",
    "evaluate_pairwise_submission",
    "evaluate_submission",
]

__version__ = "0.2.0"
