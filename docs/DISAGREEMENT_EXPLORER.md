# Calibration Disagreement Explorer

The calibration report answers **how much** independent evaluators agree. The disagreement explorer answers **where** they differ and exposes the human-authored evidence needed for calibration or review.

It is deliberately diagnostic. It does not decide which evaluator is correct, assign evaluator quality scores, create a leaderboard, or apply an acceptance threshold.

## Data boundary

The explorer is derived from an already-saved calibration artifact and its immutable source evaluations.

```text
saved calibration artifact
        │
        ├─ saved source filenames + evaluator attribution snapshot
        │
        └─ saved calibration metadata / audio tolerance
                  │
                  v
immutable source evaluations ── deterministic drill-down ── browser/API response
```

The explorer does **not** create a new persistent artifact class. Reopening it recomputes the drill-down from the saved calibration's source references so there is no second disagreement state to keep synchronized.

The saved `source_artifacts` evaluator IDs are treated as the historical attribution snapshot for that calibration. The explorer does not silently replace them with a later workflow identity.

## Criterion drill-down

Every rubric criterion includes:

- criterion ID and label;
- exact agreement rate from the calibration engine;
- each evaluator's observed rating or pairwise preference;
- each evaluator's criterion-specific evidence note when present;
- only the evaluator pairs whose observations differ;
- a deterministic gap value for each differing pair.

Criteria are ordered by the number of differing evaluator pairs, then by rubric order. This is a **disagreement hotspot order**, not an evaluator-quality ranking.

### Scalar ratings

For text and audio scalar tasks, pair gap is the absolute difference between the two `1..5` ratings.

Example:

```text
evaluator-a: 5
evaluator-b: 3
gap: 2
```

The gap describes rating distance only. It does not say which rating is correct.

### Pairwise preferences

For A/B tasks, the directional positions are:

```text
B   = -1
Tie =  0
A   = +1
```

The displayed gap is the absolute distance between those positions. Therefore `A ↔ Tie` has gap `1`, while `A ↔ B` has gap `2`.

This is a compact disagreement-distance convention, not a claim that the categories form a psychometric interval scale.

Criterion judgments remain separate from `overall_preference` and `preference_strength`. The explorer reports holistic pairwise differences independently so a criterion aggregate cannot overwrite a human holistic judgment.

## Timestamped audio evidence

For audio tasks, the explorer uses the same category-aware point/range matching semantics and saved tolerance used by the calibration report.

For each evaluator pair it exposes:

- unmatched annotations authored only by evaluator A;
- unmatched annotations authored only by evaluator B;
- matched annotations whose timing is not identical;
- matched annotations whose severity differs;
- category, timestamp/range, severity, evaluator identity, and human note.

A matched annotation with identical timing and identical severity is not repeated as a disagreement item.

Annotation differences remain evidence. They do not automatically alter the scalar rubric score.

## Saved tolerance

When a calibration contains timestamped audio agreement, the explorer reads `audio_annotation_agreement.tolerance_ms` from the saved report. This prevents a historical drill-down from silently using a different future default.

If no saved audio tolerance exists, the deterministic fallback is `250 ms`.

## API

```text
GET /api/calibrations/<calibration-artifact>/disagreements
```

Successful responses contain a derived `DisagreementReport` with criterion, holistic pairwise, and audio-evidence sections as applicable.

### Missing source evaluations

A calibration artifact remains a valid historical report even if one of its referenced evaluation files is later removed. In that case:

- calibration `details` and download remain available;
- disagreement reconstruction returns HTTP `409 Conflict`;
- TurkishEvalKit does not fabricate or partially infer the missing evidence.

### Tamper and compatibility checks

The explorer reuses the calibration engine's compatibility validation and additionally checks the saved calibration identity against reconstructed sources, including:

- evaluator attribution order;
- task ID;
- evaluation type;
- rubric ID and version;
- unique source filenames and evaluator IDs.

A mismatch returns an explicit validation error rather than silently producing a misleading drill-down.

## Privacy

The disagreement explorer is local-first like the rest of the workbench:

- no external LLM calls;
- no telemetry;
- no evidence upload;
- no copied audio bytes;
- no new persistent disagreement database.

Local-only processing is not an authorization system. Users remain responsible for handling only data they are permitted to access and for following applicable retention rules.
