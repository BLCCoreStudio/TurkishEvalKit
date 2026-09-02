"""Built-in Turkish text and audio quality rubrics."""

from .models import Rubric, RubricCriterion

TEXT_QUALITY_RUBRIC = Rubric(
    id="tr-text-quality",
    version="1.0",
    title="Turkish AI Text Quality",
    criteria=(
        RubricCriterion(
            id="fluency",
            label="Fluency",
            description="Natural, idiomatic Turkish with coherent sentence flow.",
        ),
        RubricCriterion(
            id="instruction_following",
            label="Instruction following",
            description="Fulfils the explicit user request and relevant constraints.",
        ),
        RubricCriterion(
            id="factuality",
            label="Factuality",
            description="Avoids unsupported claims, contradictions, and fabricated details.",
        ),
        RubricCriterion(
            id="helpfulness",
            label="Helpfulness",
            description="Provides relevant, actionable, and appropriately scoped information.",
        ),
        RubricCriterion(
            id="locale_fit",
            label="Turkish locale fit",
            description="Uses culturally and linguistically appropriate Turkish conventions.",
        ),
    ),
)

AUDIO_QUALITY_RUBRIC = Rubric(
    id="tr-audio-quality",
    version="1.0",
    title="Turkish AI Audio Quality",
    criteria=(
        RubricCriterion(
            id="nativeness",
            label="Nativeness",
            description="Sounds like natural Turkish rather than translated or synthetic phrasing.",
        ),
        RubricCriterion(
            id="pronunciation",
            label="Pronunciation",
            description=(
                "Turkish phonemes, proper nouns, suffixes, and word stress are pronounced clearly."
            ),
        ),
        RubricCriterion(
            id="fluency",
            label="Fluency",
            description="Speech timing and transitions are smooth without unnatural breaks.",
        ),
        RubricCriterion(
            id="intonation",
            label="Intonation",
            description="Prosody, emphasis, and sentence-final contours fit the utterance.",
        ),
        RubricCriterion(
            id="audio_artifacts",
            label="Audio cleanliness",
            description=(
                "Speech is free from clipping, glitches, repetitions, or distracting synthesis "
                "artifacts."
            ),
        ),
    ),
)

BUILTIN_RUBRICS = {
    TEXT_QUALITY_RUBRIC.id: TEXT_QUALITY_RUBRIC,
    AUDIO_QUALITY_RUBRIC.id: AUDIO_QUALITY_RUBRIC,
}
