# Rubric Guidance

The built-in rubrics are intentionally compact. They are meant to structure human judgment, not to create false precision.

## Shared 1–5 anchors

Unless a task-specific guideline overrides them, use these anchors consistently for scalar text/audio evaluations:

| Score | General interpretation |
| --- | --- |
| 5 | No meaningful issue for this criterion. Natural/correct at the expected quality bar. |
| 4 | Minor issue that does not materially harm usability or meaning. |
| 3 | Noticeable issue or mixed quality; still usable with clear reservations. |
| 2 | Major issue that substantially harms quality, trust, or usability. |
| 1 | Severe failure for the criterion or effectively unusable performance. |

Do not use intermediate decimals in human ratings. If the evidence sits between two scores, choose the better-supported integer and explain the uncertainty in the note.

## Turkish text rubric (`tr-text-quality@1.0`)

### Fluency

Evaluate whether the Turkish reads naturally and coherently. Look for awkward translated syntax, incorrect suffix use, broken agreement, unnatural word order, repetitive phrasing, and sentence transitions.

### Instruction following

Judge only against the request and applicable task constraints. A fluent answer can still score poorly if it ignores format, scope, language, or requested output requirements.

### Factuality

Evaluate claims that can reasonably be checked from the task context or established knowledge. Distinguish factual errors from missing detail and from stylistic disagreement. When evidence is insufficient, record that limitation rather than inventing certainty.

### Helpfulness

Consider relevance, clarity, actionability, and whether the response gives the user what is needed without avoidable distraction. More text is not automatically more helpful.

### Turkish locale fit

Evaluate Turkish conventions beyond grammatical correctness: culturally appropriate wording, expected terminology, number/date/currency conventions when relevant, and avoidance of expressions that sound mechanically localized.

## Turkish audio rubric (`tr-audio-quality@1.0`)

### Nativeness

Judge whether the speech sounds like natural Turkish delivery rather than text translated or synthesized without Turkish-specific rhythm and phrasing.

### Pronunciation

Focus on phoneme realization, suffixes, stress, names, abbreviations, and word boundaries. Separate pronunciation errors from recording artifacts.

### Fluency

Evaluate pacing, pauses, repetitions, restarts, and continuity. A deliberate expressive pause should not be treated as a defect merely because silence exists.

### Intonation

Evaluate prosody, emphasis, question/statement contours, and whether sentence-final pitch fits the intended utterance.

### Audio cleanliness

Look for clipping, dropouts, clicks, duplicated fragments, abrupt cuts, synthesis glitches, or other artifacts that interfere with the speech signal.

## Turkish pairwise rubric (`tr-pairwise-quality@1.0`)

The pairwise rubric compares two candidate responses to the **same prompt** using the text-quality dimensions above. It does not ask for separate 1–5 scores. For every criterion select one of:

| Preference | Meaning |
| --- | --- |
| A | Response A is meaningfully better on this criterion. |
| Tie | Neither response is meaningfully preferable on this criterion. |
| B | Response B is meaningfully better on this criterion. |

Judge candidates relative to each other, not against an imagined perfect answer. A pair may be weak overall while one candidate is still clearly preferable, or both may be strong enough that the evidence supports a tie.

### Overall preference

After criterion judgments, make a separate holistic decision: `A`, `Tie`, or `B`. Do not mechanically derive this choice from the number of criterion wins. Some failures can be more decision-relevant than others even when rubric weights are equal.

### Preference strength

Record how material the overall difference is:

| Strength | Interpretation |
| --- | --- |
| 1 | Slight preference; the difference is real but small. |
| 2 | Moderate preference; the better candidate has a clear practical advantage. |
| 3 | Strong preference; the difference is substantial and decision-relevant. |

A tie still records a strength field for schema consistency, but evaluators should normally use `1` unless a task-specific protocol defines a different convention.

### Pairwise aggregate

For deterministic aggregation only, criterion preferences map to `A = +1`, `Tie = 0`, and `B = -1`, then rubric weights are applied and the result is normalized to `-100..+100`.

This signed value reports the direction of criterion evidence. It is not an objective quality score and does not override the separately recorded overall preference or strength.

## Notes and English justification

Criterion notes should point to observable evidence. The optional English justification should summarize the most decision-relevant strengths and weaknesses rather than mechanically translating every Turkish note.

For pairwise tasks, notes should identify the comparative evidence when possible: what A does better than B, what B does better than A, or why the difference is not meaningful enough to break a tie.

## Calibration

Teams using TurkishEvalKit should calibrate evaluators on shared examples before comparing aggregate scores or pairwise preference rates. A rubric can standardize categories, but it cannot guarantee that two humans interpret those categories identically. Future multi-evaluator features should make disagreement visible rather than hiding it inside an average.
