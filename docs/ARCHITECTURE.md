# Architecture

TurkishEvalKit is intentionally split so human judgment remains a domain input rather than an implementation detail hidden inside a UI or model call. Review metadata is also kept outside the scored evaluation artifact so later decisions cannot silently rewrite historical evidence.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments; it does not silently replace them.
2. **Reproducibility** — a stored result identifies the exact rubric id and version used to compute it.
3. **Auditability** — scoring is deterministic, localized audio evidence is explicit, and workflow transitions retain actor/time/outcome evidence.
4. **Artifact immutability** — once saved, an evaluation artifact is not edited by review or adjudication.
5. **Portability** — UTF-8 JSON remains the interchange format; no database is required.
6. **Interface independence** — CLI, browser workbench, and future batch tooling use the same domain models and engines.
7. **Privacy by default** — source metadata may reference local media, but the workbench does not copy referenced media into evaluation history.
8. **Local-first operation** — the browser workbench binds to loopback and does not require a remote service or CDN.

## Layers

### `models.py`

Defines immutable evaluation-domain objects, including:

- `EvaluationType`
- `Preference`
- `Rating`
- `AudioAnnotation`
- `AudioIssueCategory`
- `AudioIssueSeverity`
- `PairwiseJudgment`
- `RubricCriterion`
- `Rubric`
- `EvaluationRecord`
- `PairwiseEvaluationRecord`

Validation intrinsic to a value belongs here. Examples include rating bounds, pairwise preference-strength bounds, non-empty identifiers, positive criterion weights, unique criterion ids, non-negative audio timestamps, non-reversed audio intervals, non-empty annotation notes, and audio-only annotation use.

A `Rubric` declares its `evaluation_type`. This is a domain invariant rather than a UI convention. Scalar text/audio submissions use `EvaluationRecord`; pairwise A/B submissions use `PairwiseEvaluationRecord` so the two judgment models cannot be silently conflated.

`EvaluationRecord.audio_annotations` is additive and placed after the pre-existing default fields so the 0.4 feature does not unnecessarily change older positional argument meaning.

### `rubrics.py`

Contains built-in, versioned Turkish rubrics. A rubric version is part of the persisted evaluation record. Existing rubric semantics must not be changed in place after publication; semantic changes require a new version.

### `evaluation.py`

Performs cross-object validation and deterministic aggregation for scalar text/audio records. It rejects mismatched rubric data, cross-type use, missing/unknown/duplicate ratings, and relies on model-level annotation validation before scoring.

Timestamped audio annotations are carried into the immutable result payload through the typed record. They do **not** enter the weighted-score formula. This preserves a clean distinction between a human rubric rating and localized supporting evidence.

### `pairwise.py`

Performs cross-object validation and deterministic aggregation for pairwise A/B records. Criterion choices map to directional values (`A = +1`, `Tie = 0`, `B = -1`) and are weighted into a signed `-100..+100` preference score. The separately authored `overall_preference` and `preference_strength` remain intact.

### `workflow.py`

Defines the evaluation-lifecycle state machine independently of scoring and audio annotation semantics.

```text
created → draft → submitted → reviewed
                              ├─ accepted: terminal
                              └─ escalated → adjudicated
```

The module enforces actor separation, required review/adjudication notes, contiguous event sequences, consistent state transitions, and snapshot/event agreement. A workflow transition changes the workflow artifact only. It never mutates evaluation ratings, annotations, candidate judgments, source content, or evaluator evidence.

### `serialization.py`

Converts JSON-compatible data into scalar/pairwise evaluation records and workflow snapshots.

For audio annotations it:

- requires `audio_annotations` to be a list when supplied;
- requires each item to be an object;
- converts timestamps to integer milliseconds;
- converts category/severity strings through the typed enums;
- delegates interval/note/task-type validation to `AudioAnnotation` and `EvaluationRecord`.

Missing `audio_annotations` remains backward compatible and becomes an empty tuple.

### `cli.py`

A thin command adapter around the evaluation core. The CLI can evaluate audio JSON containing timestamp annotations without special scoring logic because the same serializer and core models are used.

### `workbench.py`

A local-only Flask adapter over the evaluation and workflow cores. It accepts the submitted JSON, reconstructs typed records, delegates validation/scoring, writes append-only history, and maintains workflow sidecars. It does not implement audio annotation business rules itself.

### `static/workbench.js`

Contains the shared evaluator UI behavior for text, audio, pairwise, history, and review workflows.

### `static/audio_annotations.js`

A focused browser adapter for audio QA. It augments Audio mode rather than moving annotation rules into the main workbench file. It:

- adds/removes localized issue rows;
- accepts seconds, `MM:SS`, or `HH:MM:SS`-style input;
- converts display timestamps to integer milliseconds;
- treats an empty End field as a point marker;
- performs early UX validation;
- adds `audio_annotations` to the audio submission payload.

Browser validation is advisory. The Python domain model remains authoritative.

### `static/audio_annotations.css`

Contains responsive layout for the audio issue editor, including the 390px mobile flow covered by Chromium E2E.

## Evaluation boundary

```text
prompt / response / candidates / audio reference
                    ↓
           human judgments
                    ↓
       audio localized evidence*
                    ↓
      scalar or pairwise typed record
                    ↓
      validation + deterministic scoring
                    ↓
         immutable evaluation JSON

* audio tasks only; evidence does not automatically alter scores
```

## Audio annotation boundary

```text
referenced audio
     │
     ├── source metadata (reference only)
     │
     └── evaluator hears issue
              ↓
        start_ms / end_ms
        category / severity
        evidence note
              ↓
        AudioAnnotation
              ↓
     EvaluationRecord payload
```

The media itself is outside the annotation object. TurkishEvalKit does not need to retain a WAV/MP3 to represent the human observation.

### Point vs interval

- `start_ms == end_ms`: point marker.
- `end_ms > start_ms`: interval.
- `end_ms < start_ms`: invalid.

Timestamps are persisted as integer milliseconds for stable interchange. The core validates timestamp ordering but currently has no trustworthy media-duration object to compare against, so it does not claim that an annotation lies within the actual asset length.

Overlapping annotations are allowed because distinct issue types can legitimately apply to the same audible region.

## Review boundary

```text
immutable evaluation JSON
           │ artifact_id
           ↓
   workflow sidecar JSON
           ↓
  typed workflow snapshot
           ↓
 state-machine transition
           ↓
 updated snapshot containing
 complete append-only event chain
```

Review records what happened to the evaluation process without altering what the evaluator originally submitted, including its audio annotations.

## Local storage

```text
<workspace>/
├── evaluations/
│   ├── text-demo-001-<timestamp>.json
│   ├── audio-demo-001-<timestamp>.json
│   └── pairwise-demo-001-<timestamp>.json
└── workflows/
    └── <task>-<timestamp>.workflow.json
```

Evaluation filenames include the task id and UTC timestamp and are append-only. Audio annotation evidence lives inside the saved audio evaluation payload; the referenced media does not.

Workflow sidecars are snapshots that retain their complete event chain and are atomically replaced as the lifecycle advances. A missing/corrupt workflow sidecar must not hide the underlying evaluation artifact.

## Score semantics

### Scalar

A scalar criterion is rated from 1 through 5. Aggregate scores are weighted means. Timestamped audio annotations are not score inputs; they are supporting human evidence for the evaluator's ratings.

### Pairwise

A pairwise criterion records `A`, `Tie`, or `B`. The signed aggregate reports weighted direction from `-100` to `+100` and does not override the human-authored overall preference or strength.

## Review semantics

A `reviewed` workflow can be `accept` or `escalate`. Only escalated reviews can proceed to an independent adjudicator, who records `evaluation_upheld`, `review_concern_upheld`, or `inconclusive`. These labels describe workflow resolution, not a new evaluation score.

The current model deliberately has no in-place `request_changes` transition. Revision support needs a superseding-artifact relationship so earlier evidence is preserved.

## Schema evolution

Before stable `1.0` evaluation and workflow interchange schemas are declared, JSON field names may evolve. Once stable schemas are published:

- compatible additive fields may remain in the same major schema line;
- required-field changes or semantic reinterpretation require a migration path;
- rubric versions remain independent of package versions;
- workflow schema evolution remains independent of rubric versions;
- old evaluation records must never be silently reinterpreted under a newer rubric;
- old workflow events must never be silently rewritten as a different transition meaning.

## Audio evaluation limitations

The core stores audio references as source metadata and annotations as typed time-localized evidence. It currently does not open/decode media, verify the real duration, generate waveforms, play audio, infer issues automatically, or convert annotation severity/count into automatic penalties. Those boundaries keep media handling and human score semantics explicit.
