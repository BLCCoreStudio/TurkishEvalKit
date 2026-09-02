"""TurkishEvalKit public package interface."""

from .evaluation import evaluate_submission
from .models import EvaluationRecord, EvaluationType, Rating, Rubric, RubricCriterion
from .rubrics import AUDIO_QUALITY_RUBRIC, TEXT_QUALITY_RUBRIC

__all__ = [
    "AUDIO_QUALITY_RUBRIC",
    "TEXT_QUALITY_RUBRIC",
    "EvaluationRecord",
    "EvaluationType",
    "Rating",
    "Rubric",
    "RubricCriterion",
    "evaluate_submission",
]

__version__ = "0.2.0"
