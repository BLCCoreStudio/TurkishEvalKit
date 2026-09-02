# Architecture

TurkishEvalKit keeps human judgment, deterministic scoring, calibration, review state, and UI adapters separate. Later workflow or calibration activity never rewrites an evaluator's original judgment.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments rather than replacing them.
2. **Reproducibility** — stored results identify the exact rubric id/version used.
3. **Auditability** — scoring, agreement metrics, localized evidence, and workflow transitions are explicit.
4. **Artifact immutability** — evaluation artifacts are not edited by review, adjudication, or calibration.
5. **Portability** — UTF-8 JSON is the interchange format; no database is required.
6. **Interface independence** — CLI and browser flows use the same domain engines.
7. **Local-first operation** — the browser workbench binds to loopback and requires no remote service or CDN.

## Package layers

### `models.py`

Defines immutable evaluation-domain objects: scalar ratings, pairwise judgments, timestamped audio evidence, rubrics, and evaluation records. Intrinsic bounds and structural validation live here.

### `rubrics.py`

Contains built-in versioned Turkish rubrics. A semantic rubric change requires a new rubric version rather than silently reinterpreting old records.

### `evaluation.py`

Validates and scores scalar text/audio records deterministically. Timestamped audio annotations remain supporting evidence and do not automatically alter the 1–5 rubric aggregate.

### `pairwise.py`

Validates A/Tie/B criterion judgments and computes the signed weighted `-100..+100` criterion-preference score. Human-authored overall preference and strength remain separate.

### `calibration.py`

Compares two or more independent evaluations of the same stimulus. It requires unique evaluator IDs plus matching task ID, evaluation type, rubric ID/version, and source stimulus. Each input is revalidated through the existing scalar or pairwise engine.

Reports expose scalar agreement, pairwise preference agreement, evaluator score spread, and — for timestamped audio evidence — deterministic category-aware annotation F1, severity agreement, and temporal similarity.

Calibration is diagnostic. It does not determine which evaluator is correct, rank evaluators, or define a universal pass/fail threshold.

### `workflow.py`

Defines evaluation lifecycle independently of scoring and calibration:

```text
created → draft → submitted → reviewed
                              ├─ accepted: terminal
                              └─ escalated → adjudicated
```

Workflow transitions update only the workflow sidecar and retain the complete event chain.

### `serialization.py`

Owns JSON boundaries for evaluation and workflow records and delegates semantic validation back to typed models.

### `calibration_dashboard.py`

Adapts local workbench history to the calibration core. It:

1. discovers saved evaluation artifacts;
2. reads evaluator identity from matching workflow sidecars;
3. exposes compatibility metadata for browser grouping;
4. invokes the existing calibration engine after server-side validation;
5. writes a separate append-only calibration artifact;
6. serves calibration history and JSON downloads.

It does **not** implement a second agreement algorithm.

A valid evaluation with a missing or malformed workflow sidecar remains visible in candidate history but is marked unavailable for calibration because evaluator attribution cannot be established safely.

### `cli.py`

Thin adapter exposing `rubrics`, `evaluate`, `calibrate`, and `workbench`. It contains no alternative scoring or agreement semantics.

### `workbench.py`

Localhost Flask adapter for evaluation, review/adjudication, and the calibration dashboard. It delegates scoring/calibration to the same Python core used by the CLI.

### `templates/` and `static/`

Browser presentation and interactions. The main workbench covers evaluation/review; `/calibration` covers evaluator comparison and calibration history. JavaScript performs UX grouping/rendering while Python remains authoritative for validation and metric calculation.

## Evaluation boundary

```text
source stimulus
      ↓
independent human judgment
      ↓
typed scalar / pairwise record
      ↓
validation + deterministic scoring
      ↓
immutable evaluation JSON
```

For audio, timestamped annotations are stored as localized evidence alongside the record but do not automatically change the score.

## Calibration boundary

```text
saved evaluation A + evaluator A id ─┐
saved evaluation B + evaluator B id ─┼─ compatibility validation
        optional C, D, ...            ┘
                    ↓
          existing scoring engines
                    ↓
            calibration engine
                    ↓
       CalibrationReport snapshot
                    ↓
     append-only calibration history
```

Client-side grouping is a usability aid, not a correctness boundary. The server and core still reject incompatible task IDs, evaluation types, rubric versions, sources, or duplicate evaluator IDs.

Calibration never changes source evaluations, ratings, pairwise preferences, annotations, evaluator notes, or workflow sidecars.

## Review boundary

```text
immutable evaluation JSON
           ↓ artifact_id
   workflow sidecar JSON
           ↓
 typed workflow snapshot
           ↓
 state-machine transition
           ↓
updated sidecar with full event chain
```

Review records what happened to an evaluation without altering what the evaluator submitted.

## Review versus calibration

These layers answer different questions:

- **review** — what did an independent reviewer decide about one evaluation?
- **calibration** — how consistently did multiple evaluators judge the same stimulus?

Review acceptance is not the same as multi-evaluator agreement, and low agreement is not automatically a review failure.

## Local storage

Workbench-managed storage is:

```text
<workspace>/
├── evaluations/
│   └── <task>-<timestamp>.json
├── workflows/
│   └── <task>-<timestamp>.workflow.json
└── calibrations/
    └── <task>-<timestamp>.calibration.json
```

Evaluation and calibration filenames are append-only timestamped artifacts. Workflow sidecars can advance state while retaining their full event chain.

A dashboard-generated calibration artifact stores its schema version, creation time, source evaluation filenames, local evaluator IDs, and the complete calibration report. Reopening calibration history reads this saved snapshot rather than silently recomputing it from later workspace state.

## Failure isolation

Artifact classes are validated independently:

- malformed evaluations are omitted from calibration candidates;
- valid evaluations with missing/corrupt workflow sidecars stay visible but are not calibration-ready;
- malformed calibration artifacts are omitted from history summaries and rejected when opened directly.

This prevents corruption in one metadata layer from silently rewriting another artifact class.

## Score semantics

### Scalar

Criterion ratings are `1..5`; aggregates are deterministic weighted means.

### Pairwise

Criterion judgments are `A`, `Tie`, or `B`; the signed aggregate reports weighted direction from `-100` to `+100` and does not override the human overall preference.

### Calibration

Exact agreement, within-one agreement, annotation F1, severity agreement, temporal similarity, and score spread are agreement diagnostics. They are not evaluator rankings or universal acceptance thresholds.

The alpha does not yet compute population-level reliability statistics such as Cohen/Fleiss kappa, Krippendorff's alpha, or ICC because those require explicit assumptions about repeated tasks, assignment, scale type, missingness, and sample size.

## Privacy boundary

The workbench binds to `127.0.0.1` by default. It performs no external LLM calls or telemetry and does not upload evaluation content, evaluator IDs, audio references, workflow events, or calibration reports.

Local-first operation is not an access-control system; filesystem permissions and data-retention policy remain the operator's responsibility.

## Schema evolution

Before stable `1.0` interchange schemas are declared, field names may evolve. Once stable schemas exist:

- additive compatible fields may stay in the same major schema line;
- semantic reinterpretation requires a migration/version boundary;
- rubric versions remain independent of package versions;
- workflow schema evolution remains independent of rubric versions;
- calibration metric/matching changes must be documented and versioned;
- old evaluation/workflow evidence must not be silently reinterpreted.

## Current limitations

TurkishEvalKit does not currently decode media, verify media duration, generate waveforms, infer audio issues, convert annotation count/severity into automatic penalties, resolve evaluator disagreements automatically, declare acceptable agreement thresholds, rank evaluators, or provide in-place request-changes/resubmit semantics.

Revision support should use explicit superseding-artifact lineage so earlier evidence remains inspectable.

See [`CALIBRATION.md`](CALIBRATION.md), [`CALIBRATION_DASHBOARD.md`](CALIBRATION_DASHBOARD.md), [`AUDIO_ANNOTATIONS.md`](AUDIO_ANNOTATIONS.md), and [`REVIEW_WORKFLOW.md`](REVIEW_WORKFLOW.md).
