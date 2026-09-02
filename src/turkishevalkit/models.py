"""Typed domain models for human evaluation records and rubrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EvaluationType(StrEnum):
    """Supported human-evaluation task families in the current stable core."""

    TEXT = "text"
    AUDIO = "audio"


@dataclass(frozen=True, slots=True)
class Rating:
    """A bounded numeric rating for one rubric criterion."""

    criterion_id: str
    score: int
    note: str = ""

    def __post_init__(self) -> None:
        if not self.criterion_id.strip():
            raise ValueError("criterion_id must not be empty")
        if not 1 <= self.score <= 5:
            raise ValueError("score must be between 1 and 5")


@dataclass(frozen=True, slots=True)
class RubricCriterion:
    """One independently scored dimension in an evaluation rubric."""

    id: str
    label: str
    description: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("criterion id must not be empty")
        if not self.label.strip():
            raise ValueError("criterion label must not be empty")
        if self.weight <= 0:
            raise ValueError("criterion weight must be positive")


@dataclass(frozen=True, slots=True)
class Rubric:
    """A named, versioned collection of evaluation criteria."""

    id: str
    version: str
    title: str
    criteria: tuple[RubricCriterion, ...]

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.version.strip() or not self.title.strip():
            raise ValueError("rubric id, version, and title must not be empty")
        if not self.criteria:
            raise ValueError("rubric must contain at least one criterion")
        ids = [criterion.id for criterion in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("rubric criterion ids must be unique")


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    """A complete human-authored evaluation submission."""

    task_id: str
    evaluation_type: EvaluationType
    rubric_id: str
    rubric_version: str
    ratings: tuple[Rating, ...]
    evaluator_note: str = ""
    justification_en: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.rubric_id.strip() or not self.rubric_version.strip():
            raise ValueError("rubric id and version must not be empty")
        if not self.ratings:
            raise ValueError("evaluation must contain at least one rating")
