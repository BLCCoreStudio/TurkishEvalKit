# Architecture

TurkishEvalKit is intentionally split so human judgment remains a domain input rather than an implementation detail hidden inside a UI or model call. Scoring, calibration, and review are separate consumers of immutable human evidence: none silently rewrites an evaluator's original judgment.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments; it does not silently replace them.
2. **Reproducibility** — a stored result identifies the exact rubric id/version used to compute it.
3. **Auditability** — scoring is deterministic, localized audio evidence is explicit, calibration metrics expose their inputs, and workflow transitions retain actor/time/outcome evidence.
4. **Artifact immutability** — saved evaluations are not edited by review, adjudication, or calibration.
5. **Portability** — UTF-8 JSON remains the interchange format; no database is required.
6. **Interface independence** — CLI, browser workbench, calibration, and future batch tooling share the same domain models and engines.
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

Intrinsic value validation belongs here: rating bounds, pairwise strength bounds, non-empty identifiers, positive criterion weights, unique criterion ids, non-negative audio timestamps, non-reversed intervals, non-empty annotation notes, and audio-only annotation use.

A `Rubric` declares its `evaluation_type`. Scalar text/audio submissions use `EvaluationRecord`; pairwise A/B submissions use `PairwiseEvaluationRecord`, preventing silent conflation of scalar and categorical judgments.

### `rubrics.py`

Contains built-in, versioned Turkish rubrics. A rubric version is persisted with the evaluation. Existing rubric semantics must not be changed in place after publication; semantic changes require a new version.

### `evaluation.py`

Validates and deterministically aggregates scalar text/audio records. It rejects mismatched rubric data, cross-type use, and missing/unknown/duplicate ratings.

Timestamped audio annotations are preserved in the result payload but do **not** enter the weighted-score formula. This keeps human ratings distinct from localized supporting evidence.

### `pairwise.py`

Validates and aggregates pairwise A/B records. Criterion choices map to directional values (`A = +1`, `Tie = 0`, `B = -1`) and are weighted into a signed `-100..+100` criterion-preference score. `overall_preference` and `preference_strength` remain separate human judgments.

### `calibration.py`

Compares two or more **independent evaluations of the same stimulus**. Calibration is deliberately downstream of the evaluation engines rather than a new scoring mode.

Core input object:

- `EvaluatorSubmission` — one explicit evaluator id paired with one immutable scalar or pairwise record.

Output objects include:

- `CalibrationReport`
- `CriterionAgreement`
- `AudioAnnotationAgreement`
- `AudioAnnotationPairAgreement`

Before comparison, calibration requires:

- at least two submissions;
- unique non-empty evaluator ids;
- identical `task_id`;
- identical evaluation type;
- identical rubric id/version;
- identical `source` stimulus;
- individually valid records under the supplied rubric.

Calibration then reuses `evaluate_submission` or `evaluate_pairwise_submission` for authoritative validation/scoring. It does not reimplement the rubric engines.

#### Scalar agreement

For text/audio 1–5 ratings, every unique evaluator pair is compared for every criterion. The report exposes:

- exact criterion agreement;
- within-one-point agreement;
- mean/max absolute rating differences;
- per-criterion rating observations and agreement;
- normalized score by evaluator;
- aggregate-score spread.

#### Pairwise agreement

For A/Tie/B judgments, the report exposes:

- criterion-preference agreement;
- per-criterion preference observations;
- overall-preference agreement;
- mean/max preference-strength differences;
- signed preference score by evaluator;
- score spread.

#### Audio annotation agreement

For audio evaluations, calibration also compares timestamped issue evidence. Annotations can match only when their categories agree. Temporal eligibility depends on point/range geometry and a configurable tolerance.

- point ↔ point: timestamp distance within tolerance;
- point ↔ range: point lies inside, or near, the range;
- range ↔ range: overlap uses intersection-over-union; nearby ranges may match within tolerance.

Eligible candidates are matched one-to-one in descending temporal-similarity order. Pair reports expose matched count, annotation F1, exact severity agreement among matches, and temporal similarity. The aggregate exposes mean pairwise F1 and overall matched-evidence agreement.

This is an explicit deterministic matching heuristic, not a claim of semantic truth. A future matching strategy that changes which candidates pair together is a calibration-semantic change and should be versioned/documented rather than silently substituted.

### `workflow.py`

Defines evaluation lifecycle independently of scoring, calibration, and audio annotation semantics.

```text
created → draft → submitted → reviewed
                              ├─ accepted: terminal
                              └─ escalated → adjudicated
```

The module enforces actor separation, required review/adjudication notes, contiguous event sequences, consistent transitions, and snapshot/event agreement. A workflow transition changes the workflow artifact only.

### `serialization.py`

Converts JSON-compatible data into scalar/pairwise evaluation records and workflow snapshots. For audio annotations it converts timestamps to integer milliseconds and category/severity strings through typed enums, then delegates intrinsic validation to the models.

Missing `audio_annotations` remains backward compatible and becomes an empty tuple.

### `cli.py`

A thin adapter over the domain engines. Current commands include:

- `rubrics` — list built-in rubric versions;
- `evaluate` — validate/score one human-authored evaluation;
- `calibrate` — compare two or more independent evaluations and optionally write a calibration report;
- `workbench` — run the localhost browser evaluator UI.

The CLI contains no alternative scoring or agreement rules.

### `workbench.py`

A localhost-only Flask adapter over evaluation and workflow cores. It reconstructs typed records, delegates validation/scoring, writes append-only history, and maintains workflow sidecars.

Calibration is currently **not** a workbench route/dashboard. The 0.5 calibration path is CLI/library based, keeping its read-only artifact boundary explicit before adding a larger UI surface.

### `static/workbench.js`

Shared evaluator UI behavior for text, audio, pairwise, history, and review workflows.

### `static/audio_annotations.js`

Focused browser adapter for audio QA. It adds/removes localized issue rows, accepts readable timestamps, converts them to integer milliseconds, performs early UX validation, and adds `audio_annotations` to the audio submission payload. Python remains authoritative.

### `static/audio_annotations.css`

Responsive layout for the audio issue editor, including the 390px mobile flow covered by Chromium E2E.

## Evaluation boundary

```text
prompt / response / candidates / audio reference
                    ↓
           independent human judgment
                    ↓
       audio localized evidence*
                    ↓
      scalar or pairwise typed record
                    ↓
      validation + deterministic scoring
                    ↓
         immutable evaluation JSON

* audio only; evidence does not automatically alter scores
```

## Calibration boundary

```text
immutable evaluation A + evaluator A id
immutable evaluation B + evaluator B id
          [optional C, D, ...]
                    ↓
      same task/type/rubric/source
              validation
                    ↓
      existing scoring engines
                    ↓
   pairwise agreement observations
                    ↓
      CalibrationReport JSON
```

The calibration artifact is derived evidence. It never changes:

- source evaluations;
- ratings or pairwise preferences;
- audio annotations;
- evaluator notes;
- workflow sidecars.

This separation lets teams rerun calibration with a different explicit timestamp tolerance while preserving the original judgments.

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

The media itself remains outside the annotation object. `start_ms == end_ms` is a point marker; `end_ms > start_ms` is an interval; reversed intervals are invalid. Overlapping annotations are allowed because different issue types can apply to the same audible region.

The core currently has no trusted media-duration object, so it cannot claim an annotation lies inside the actual asset duration.

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

Review records what happened to the evaluation process without altering what the evaluator originally submitted.

## Relationship between review and calibration

Review/adjudication and calibration answer different questions:

- **review** — what did an independent reviewer decide about one saved evaluation?
- **calibration** — how consistently did multiple independent evaluators judge the same stimulus?

A review acceptance is therefore not multi-evaluator agreement, and low agreement is not automatically a review failure. Any operational threshold must be defined by the organization using the toolkit, outside the core metric calculation.

## Local storage

Workbench-managed storage remains:

```text
<workspace>/
├── evaluations/
│   ├── text-demo-001-<timestamp>.json
│   ├── audio-demo-001-<timestamp>.json
│   └── pairwise-demo-001-<timestamp>.json
└── workflows/
    └── <task>-<timestamp>.workflow.json
```

Calibration specs and reports are user-selected CLI/library files in 0.5; they are not silently inserted into workbench history.

Evaluation filenames include task id and UTC timestamp and are append-only. Audio evidence lives in the saved evaluation payload; referenced media does not.

## Score semantics

### Scalar

A scalar criterion is rated `1..5`. Aggregate scores are weighted means. Timestamped audio annotations are supporting evidence, not score inputs.

### Pairwise

A pairwise criterion records `A`, `Tie`, or `B`. The signed aggregate reports weighted direction from `-100` to `+100` and does not override the human-authored overall preference or strength.

### Calibration

Calibration scores are **agreement diagnostics** over already-authored evaluations. Exact agreement, within-one agreement, F1, severity agreement, temporal similarity, and aggregate-score spread do not identify which evaluator is correct and are not universal pass/fail measures.

The current alpha deliberately does not compute population-level reliability statistics such as Cohen/Fleiss kappa, Krippendorff's alpha, or ICC. Such metrics require explicit assumptions about scale type, missingness, repeated tasks, evaluator assignment, and sample size.

## Review semantics

A `reviewed` workflow can be `accept` or `escalate`. Only escalated reviews can proceed to an independent adjudicator, who records `evaluation_upheld`, `review_concern_upheld`, or `inconclusive`. These labels describe workflow resolution, not new evaluation scores.

The current model has no in-place `request_changes` transition. Revision support needs a superseding-artifact relationship so earlier evidence is preserved.

## Schema evolution

Before stable `1.0` evaluation, calibration, and workflow interchange schemas are declared, JSON field names may evolve. Once stable schemas are published:

- compatible additive fields may remain in the same major schema line;
- required-field changes or semantic reinterpretation require a migration path;
- rubric versions remain independent of package versions;
- workflow schema evolution remains independent of rubric versions;
- calibration matching/metric semantic changes must be documented/versioned;
- old evaluation records must never be silently reinterpreted under a newer rubric;
- old workflow events must never be silently rewritten as a different transition meaning.

## Current limitations

TurkishEvalKit currently does not open/decode media, verify real duration, generate waveforms, infer audio issues, convert annotation severity/count into automatic penalties, resolve evaluator disagreements automatically, declare acceptable calibration thresholds, or rank evaluators. Those boundaries keep media handling, score meaning, and human authority explicit.

See [`CALIBRATION.md`](CALIBRATION.md), [`AUDIO_ANNOTATIONS.md`](AUDIO_ANNOTATIONS.md), and [`REVIEW_WORKFLOW.md`](REVIEW_WORKFLOW.md) for the corresponding domain semantics.
