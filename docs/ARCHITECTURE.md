# Architecture

TurkishEvalKit keeps human judgment, deterministic scoring, workflow state, immutable revision lineage, calibration, and browser adapters separate. A later review, revision, adjudication, or calibration action must not silently rewrite an evaluator's earlier evidence.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments rather than replacing them.
2. **Reproducibility** — stored results identify the exact rubric id/version used.
3. **Auditability** — scoring, localized evidence, workflow transitions, revision parentage, and agreement metrics are explicit.
4. **Artifact immutability** — evaluation artifacts are append-only; corrections become new artifacts.
5. **Portability** — UTF-8 JSON is the interchange format; no database is required.
6. **Interface independence** — CLI and browser flows use the same domain engines.
7. **Server-owned process metadata** — workflow and revision relationships are not trusted from evaluator payload metadata.
8. **Local-first operation** — the browser workbench binds to loopback and requires no remote service or CDN.

## Package layers

### `models.py`

Defines immutable evaluation-domain objects: scalar ratings, pairwise judgments, timestamped audio evidence, rubrics, and evaluation records. Intrinsic bounds and structural validation live here.

Scalar text/audio submissions use `EvaluationRecord`; A/B comparison tasks use `PairwiseEvaluationRecord`. This prevents categorical preference judgments from being silently mixed with 1–5 scalar ratings.

### `rubrics.py`

Contains built-in versioned Turkish rubrics. A semantic rubric change requires a new rubric version rather than silently reinterpreting old records.

### `evaluation.py`

Validates and scores scalar text/audio records deterministically. Timestamped audio annotations remain supporting evidence and do not automatically alter the 1–5 rubric aggregate.

### `pairwise.py`

Validates A/Tie/B criterion judgments and computes the signed weighted `-100..+100` criterion-preference score. Human-authored overall preference and strength remain separate.

### `workflow.py`

Defines lifecycle independently of scoring, revision payloads, and calibration.

The normal terminal paths are:

```text
created → draft → submitted → reviewed
                              ├─ accept: terminal
                              └─ escalate → adjudicated
```

A reviewer can instead request a new immutable revision:

```text
created → draft → submitted → revision_requested
                                   ↓
                         revision_created event
                                   ↓
                              superseded
```

`request_changes` requires an explanatory reviewer note. When a child revision has been persisted successfully, the parent workflow receives `revision_created`, stores the child artifact id as `related_artifact_id`, and moves to `superseded`.

Workflow sidecars may advance state, but the underlying evaluation JSON is never edited by these transitions. Event sequences remain contiguous and retain actor, role, timestamp, outcome, note, and related artifact where applicable.

### `revision.py`

Owns immutable superseding-artifact lineage. `RevisionLineage` records:

- child artifact id;
- task id;
- root artifact id;
- immediate superseded parent artifact id;
- revision number;
- reviewer who requested the change;
- evaluator who created the revision;
- original request note;
- creation timestamp.

The first child of an original artifact is revision `1`. A revision of that child becomes revision `2` while retaining the same root id.

The current alpha deliberately enforces a **linear chain**: one direct superseding child per artifact. Parallel branches require conflict and merge semantics and are not inferred automatically.

### `serialization.py`

Owns JSON boundaries for evaluation and workflow records and delegates semantic validation back to typed models. Workflow serialization preserves `related_artifact_id` for revision events.

Revision-lineage serialization lives with the revision domain because those fields are server-owned process metadata rather than evaluator-authored record data.

### `calibration.py`

Compares two or more independent evaluations of the same stimulus. It requires unique evaluator IDs plus matching task ID, evaluation type, rubric ID/version, and source stimulus. Each input is revalidated through the existing scalar or pairwise engine.

Reports expose scalar agreement, pairwise preference agreement, evaluator score spread, and — for timestamped audio evidence — deterministic category-aware annotation F1, severity agreement, and temporal similarity.

Calibration is diagnostic. It does not determine which evaluator is correct, rank evaluators, or define a universal pass/fail threshold.

### `calibration_dashboard.py`

Adapts local workbench history to the calibration core. It:

1. discovers saved evaluation artifacts;
2. reads evaluator identity from matching workflow sidecars;
3. exposes compatibility metadata for browser grouping;
4. invokes the existing calibration engine after server-side validation;
5. writes a separate append-only calibration artifact;
6. serves calibration history and JSON downloads.

It does **not** implement a second agreement algorithm. A valid evaluation with a missing or malformed workflow sidecar remains visible in candidate history but is unavailable for calibration until evaluator attribution can be established safely.

### `workbench.py`

Localhost Flask adapter for evaluation creation, workflow transitions, revision persistence, history, and calibration-dashboard mounting.

For revision creation the server is authoritative. It verifies that:

- the base evaluation exists;
- the base has a valid workflow;
- the workflow is `revision_requested`;
- the base has not already been superseded;
- the creating evaluator matches the original evaluator;
- task id, evaluation type, rubric id/version, and source stimulus are unchanged;
- the new record independently validates and scores.

Only after validation does the workbench create the child evaluation, child draft workflow, and revision sidecar, then mark the parent workflow superseded. Newly created child-side files are removed if persistence fails before the transition completes.

### `cli.py`

Thin adapter exposing `rubrics`, `evaluate`, `calibrate`, and `workbench`. It contains no alternative scoring, revision, or agreement semantics.

### `templates/` and `static/`

Browser code is an adapter, not a correctness boundary. Revision JavaScript can pre-fill a previous record and lock task/source fields for clarity, but the Python server repeats all identity and workflow checks.

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

## Review and revision boundary

```text
immutable evaluation r0
        ↓
workflow sidecar: draft → submitted
        ↓
independent reviewer
   ┌────┼─────────────┐
accept  escalate      request_changes
   │       │                 │
terminal  adjudicate     revision_requested
                             │
                  original evaluator revises
                             │
                  immutable evaluation r1
                    + new draft workflow
                    + revision sidecar
                             │
                 r0 workflow → superseded
```

The child artifact does not replace the parent on disk. The relationship is explicit and inspectable.

## Revision identity boundary

A requested revision represents another judgment of the **same task stimulus**, not a way to silently substitute a different task. The server therefore preserves:

```text
task_id
evaluation_type
rubric_id
rubric_version
source stimulus
```

Human judgment fields may change. For scalar tasks this includes ratings and notes; for pairwise tasks it includes criterion/overall preferences; for audio tasks it can include timestamped issue evidence.

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
      CalibrationReport JSON
                    ↓
       dashboard/history artifact
```

Calibration never changes source evaluations, workflows, revision sidecars, ratings, pairwise preferences, audio annotations, or evaluator notes.

## Audio annotation boundary

Audio issue evidence is stored as category/severity/note plus point or interval timestamps in integer milliseconds. Referenced media remains external to the artifact. The core does not currently decode media or claim that a timestamp lies within a trusted duration.

For calibration, annotations match only under explicit category and temporal rules. The deterministic matching heuristic is diagnostic rather than semantic ground truth.

## Local storage

```text
<workspace>/
├── evaluations/
│   └── <task>-<timestamp>.json
├── workflows/
│   └── <task>-<timestamp>.workflow.json
├── revisions/
│   └── <task>-<timestamp>.revision.json
└── calibrations/
    └── <task>-<timestamp>.calibration.json
```

### Evaluation artifacts

Append-only scored human judgments. Review and revision do not overwrite them.

### Workflow sidecars

Mutable snapshots containing a complete append-only event chain. Their current state can advance, but earlier events remain present.

### Revision sidecars

Immutable lineage metadata for child artifacts. Originals have no revision sidecar. Parent/root links and revision numbers are server-owned.

### Calibration artifacts

Append-only derived agreement reports referencing explicit source evaluation filenames and evaluator identities from workflow attribution.

## Score semantics

### Scalar

A criterion is rated `1..5`; aggregate scores are weighted means normalized to `0..100`. Timestamped audio annotations are supporting evidence, not score inputs.

### Pairwise

A criterion records `A`, `Tie`, or `B`. The signed aggregate reports weighted direction from `-100` to `+100` and does not override human-authored overall preference or strength.

### Calibration

Agreement metrics describe consistency between already-authored evaluations. Exact agreement, within-one agreement, annotation F1, severity agreement, temporal similarity, and score spread do not identify which evaluator is correct.

### Revision

A revision number is lineage metadata, not a quality metric. `r2` means the second superseding generation from the same root, not a better or worse evaluation than `r1`.

## Failure and trust model

- Browser controls are convenience only; server validation is authoritative.
- Evaluation payload metadata cannot establish trusted revision parentage.
- A malformed workflow sidecar is not silently interpreted as valid evaluator attribution.
- A malformed revision sidecar is not silently accepted as lineage truth.
- Child creation never uses the parent evaluation as rollback scratch space.
- External LLM calls and telemetry are outside the current workbench path.

## Schema evolution

Before stable `1.0` interchange schemas are declared, JSON field names may evolve. Once stable schemas are published:

- additive compatible fields may remain within the same major schema line;
- required-field or semantic reinterpretations need a migration path;
- rubric versions remain independent of package versions;
- workflow state/event semantics require explicit compatibility handling;
- revision-lineage semantic changes require explicit versioning/migration;
- calibration matching semantic changes must be documented/versioned;
- old evaluation records must never be silently reinterpreted under a newer rubric.

## Current limitations

TurkishEvalKit currently does not open/decode media, verify actual media duration, generate waveforms, infer audio issues, convert annotation severity/count into automatic penalties, resolve evaluator disagreements automatically, rank evaluators, define universal calibration thresholds, create parallel revision branches, merge competing revisions, or edit previous evaluation artifacts in place.

See [`REVISION_WORKFLOW.md`](REVISION_WORKFLOW.md), [`REVIEW_WORKFLOW.md`](REVIEW_WORKFLOW.md), [`CALIBRATION.md`](CALIBRATION.md), [`CALIBRATION_DASHBOARD.md`](CALIBRATION_DASHBOARD.md), and [`AUDIO_ANNOTATIONS.md`](AUDIO_ANNOTATIONS.md) for domain-specific semantics.
