"""Typed domain models for human evaluation records and rubrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EvaluationType(StrEnum):
    """Supported human-evaluation task families in the current stable core."""

    TEXT = "text"
    AUDIO = "audio"
    PAIRWISE = "pairwise"


class Preference(StrEnum):
    """Pairwise preference labels for candidate A, candidate B, or a tie."""

    A = "a"
    B = "b"
    TIE = "tie"


class AudioIssueCategory(StrEnum):
    """Localized issue categories for timestamped audio-quality evidence."""

    NATIVENESS = "nativeness"
    PRONUNCIATION = "pronunciation"
    FLUENCY = "fluency"
    INTONATION = "intonation"
    UNNATURAL_PAUSE = "unnatural_pause"
    PACE = "pace"
    EMPHASIS = "emphasis"
    AUDIO_ARTIFACT = "audio_artifact"
    NOISE = "noise"
    CLIPPING = "clipping"
    OTHER = "other"


class AudioIssueSeverity(StrEnum):
    """Human-authored impact level for one localized audio issue."""

    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AudioAnnotation:
    """One timestamped human observation tied to an audio evaluation."""

    start_ms: int
    end_ms: int
    category: AudioIssueCategory
    severity: AudioIssueSeverity
    note: str

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms < 0:
            raise ValueError("audio annotation timestamps must be non-negative")
        if self.end_ms < self.start_ms:
            raise ValueError("audio annotation end_ms must be greater than or equal to start_ms")
        if not self.note.strip():
            raise ValueError("audio annotation note must not be empty")


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
class PairwiseJudgment:
    """A preference judgment for one rubric criterion."""

    criterion_id: str
    preference: Preference
    note: str = ""

    def __post_init__(self) -> None:
        if not self.criterion_id.strip():
            raise ValueError("criterion_id must not be empty")


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
    """A named, versioned collection of evaluation criteria for one task family."""

    id: str
    version: str
    title: str
    evaluation_type: EvaluationType
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
    """A complete human-authored scalar evaluation submission."""

    task_id: str
    evaluation_type: EvaluationType
    rubric_id: str
    rubric_version: str
    ratings: tuple[Rating, ...]
    evaluator_note: str = ""
    justification_en: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    audio_annotations: tuple[AudioAnnotation, ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if self.evaluation_type is EvaluationType.PAIRWISE:
            raise ValueError("pairwise submissions must use PairwiseEvaluationRecord")
        if not self.rubric_id.strip() or not self.rubric_version.strip():
            raise ValueError("rubric id and version must not be empty")
        if not self.ratings:
            raise ValueError("evaluation must contain at least one rating")
        if self.audio_annotations and self.evaluation_type is not EvaluationType.AUDIO:
            raise ValueError("audio_annotations are only valid for audio evaluations")
        if len(set(self.audio_annotations)) != len(self.audio_annotations):
            raise ValueError("audio annotations must not contain exact duplicates")


@dataclass(frozen=True, slots=True)
class PairwiseEvaluationRecord:
    """A complete A/B human-preference evaluation submission."""

    task_id: str
    rubric_id: str
    rubric_version: str
    judgments: tuple[PairwiseJudgment, ...]
    overall_preference: Preference
    preference_strength: int
    evaluator_note: str = ""
    justification_en: str = ""
    source: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_type: EvaluationType = field(default=EvaluationType.PAIRWISE, init=False)

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.rubric_id.strip() or not self.rubric_version.strip():
            raise ValueError("rubric id and version must not be empty")
        if not self.judgments:
            raise ValueError("pairwise evaluation must contain at least one judgment")
        if not 1 <= self.preference_strength <= 3:
            raise ValueError("preference_strength must be between 1 and 3")
