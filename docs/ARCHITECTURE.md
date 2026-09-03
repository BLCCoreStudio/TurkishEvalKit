# Architecture

TurkishEvalKit separates human judgment, deterministic scoring, trusted process state, immutable revision lineage, operational projections, same-stimulus calibration, disagreement exploration, repeated-task reliability, dataset interchange, and browser adapters.

A later review, revision, adjudication, queue query, calibration, disagreement drill-down, reliability analysis, export, or import must not silently rewrite an evaluator's earlier evidence.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments rather than replacing them.
2. **Reproducibility** — stored results identify the exact rubric ID/version used.
3. **Auditability** — scoring, localized evidence, workflow transitions, revision parentage, agreement metrics, reliability assumptions, and interchange boundaries are explicit.
4. **Artifact immutability** — evaluation artifacts are append-only; corrections become new artifacts.
5. **Portable records** — UTF-8 JSON is the canonical local artifact format and the evaluation-dataset interchange schema is versioned independently.
6. **Interface independence** — CLI and browser flows use the same domain engines.
7. **Server-owned process metadata** — workflow, reviewer, adjudicator, and revision relationships are not trusted from evaluator payloads or imported datasets.
8. **Derived operational views** — queue priority/filter state and disagreement hotspot state are computed rather than stored as new truth.
9. **Applicability-aware statistics** — a reliability coefficient is emitted only when its documented design assumptions are satisfied.
10. **Local-first operation** — browser tools bind to loopback and require no remote service, CDN, telemetry, or external AI service.

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

### `serialization.py`

Owns JSON boundaries for evaluator-authored records and delegates semantic validation back to typed models.

Workflow/revision process metadata remains separate from evaluator-authored record data. Calibration, reliability, and interchange reuse the same evaluation record schema rather than inventing parallel scoring schemas.

### `interchange.py`

Owns the portable evaluator-record dataset boundary introduced in `0.11.x`.

The canonical bundle is versioned as:

```text
turkishevalkit.evaluation-dataset@1.0
```

The module can read:

- one evaluation record;
- a JSON array of records;
- a canonical versioned bundle;
- an existing scored-result object containing a `payload` record;
- JSONL/NDJSON with one record per non-empty line.

It can write canonical bundles, JSON arrays, and JSONL. Every record is reconstructed through `serialization.py` and revalidated through the existing scalar or pairwise scoring engine before conversion or workspace import.

Workspace export extracts evaluator-authored payloads from saved evaluation artifacts. It does not export workflow, reviewer/adjudicator transitions, revision lineage, queue state, calibration artifacts, disagreement projections, or reliability reports as part of the evaluation-dataset schema.

Workspace import:

- validates and scores all records before writes begin;
- computes exact-content SHA-256 digests over canonical evaluator-record JSON;
- deduplicates against existing workspace records and duplicates inside the input dataset;
- writes ordinary scored evaluation artifacts;
- deliberately creates no workflow sidecar;
- rolls back new final artifacts if persistence fails after writing begins.

Exact-content deduplication is not semantic equivalence detection. External workflow/reviewer/session metadata is never promoted into trusted local process history by this layer.

### `workflow.py`

Defines lifecycle independently of scoring, revision payloads, queue projection, calibration, reliability, and interchange.

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

`request_changes` requires an explanatory reviewer note. When a child revision has been persisted successfully, the parent workflow receives `revision_created`, stores the child artifact ID as `related_artifact_id`, and moves to `superseded`.

Workflow sidecars may advance state, but the underlying evaluation JSON is never edited by these transitions. Event sequences remain contiguous and retain actor, role, timestamp, outcome, note, and related artifact where applicable.

### `revision.py`

Owns immutable superseding-artifact lineage. `RevisionLineage` records:

- child artifact ID;
- task ID;
- root artifact ID;
- immediate superseded parent artifact ID;
- revision number;
- reviewer who requested the change;
- evaluator who created the revision;
- original request note;
- creation timestamp.

The current alpha enforces a linear chain: one direct superseding child per artifact. Parallel branches require explicit conflict/merge semantics and are not inferred automatically.

### `calibration.py`

Compares two or more independent evaluations of the **same stimulus**. It requires unique evaluator IDs plus matching task ID, evaluation type, rubric ID/version, and source stimulus. Each input is revalidated through the existing scalar or pairwise engine.

Reports expose scalar agreement, pairwise preference agreement, evaluator score spread, and — for timestamped audio evidence — deterministic category-aware annotation F1, severity agreement, and temporal similarity.

Calibration is diagnostic. It does not determine which evaluator is correct, rank evaluators, or define a universal pass/fail threshold.

### `disagreement.py`

Builds an evidence-level read-time projection over a saved calibration and its immutable source evaluations.

It exposes:

- criterion-level evaluator observations;
- evaluator-pair differences;
- scalar score gaps;
- pairwise preference gaps;
- human evidence notes;
- unmatched audio annotations;
- matched audio timing/severity variance.

It does not create a persistent leaderboard, determine who is correct, or rewrite calibration/source artifacts.

### `reliability.py`

Owns repeated-task population reliability. This is deliberately separate from `calibration.py`.

The input is a `PopulationReliabilitySpec` containing multiple `ReliabilityTask` units. Each unit contains two or more independent evaluator submissions and is first validated through the same calibration/evaluation engines used elsewhere.

Across the reliability dataset:

- task IDs must be unique;
- all tasks must use the same evaluation type;
- all tasks must use the supplied rubric ID/version;
- every task independently satisfies same-stimulus calibration invariants inside that task;
- the specification declares a `minimum_task_count >= 3` and contains at least that many task units.

The declared minimum is an inclusion guardrail, not a universal sample-size claim.

The module computes:

#### Krippendorff alpha

- scalar `1..5` criteria: ordinal alpha;
- pairwise A/Tie/B criteria: nominal alpha;
- pairwise overall preference: nominal alpha;
- pairwise preference strength `1..3`: ordinal alpha.

Alpha can remain applicable when evaluator counts or identities vary by task, as long as each task has at least two pairable observations.

#### Fleiss kappa

Used only for pairwise nominal judgments when every included task has the same number of ratings. Scalar 1–5 ratings are not silently collapsed to nominal categories just to make Fleiss kappa available.

#### ICC(A,1)

Used for scalar criterion ratings and normalized aggregate scalar scores only when the same evaluator identities rate every task. The implementation is the two-way random-effects, absolute-agreement, single-measure form.

Pairwise signed preference aggregates are not silently treated as interval measurements for ICC.

Every statistic is returned as `ReliabilityEstimate` with:

```text
metric
value | null
applicable
reason | null
assumptions[]
```

If assumptions fail, TurkishEvalKit returns `applicable=false` and a reason rather than coercing the dataset. Negative coefficients are preserved rather than clipped.

The reliability layer is read-only with respect to project artifacts. It does not mutate evaluations, workflows, revisions, calibrations, queue state, disagreement projections, or interchange datasets.

### `calibration_dashboard.py`

Adapts local workbench history to the calibration core. It:

1. discovers saved evaluation artifacts;
2. reads evaluator identity from matching workflow sidecars;
3. exposes compatibility metadata for browser grouping;
4. invokes the existing calibration engine after server-side validation;
5. writes a separate append-only calibration artifact;
6. serves calibration history, disagreement exploration, and JSON downloads.

It does not implement a second agreement algorithm. A valid evaluation with missing/malformed workflow attribution remains visible but unavailable for calibration until attribution is trustworthy.

### `review_queue.py`

Builds a read-only operational projection over evaluation-history metadata. It derives one action state from trusted workflow/revision summaries, applies bounded filters, sorts deterministically, computes facets, and paginates the result.

Derived action states are:

```text
awaiting_review
awaiting_revision
awaiting_adjudication
draft
complete
superseded
untracked
```

Default action priority is operational only; it is never interpreted as a quality, correctness, or evaluator-performance score.

Imported evaluation records without trusted workflow sidecars naturally appear as `untracked`; interchange does not synthesize attribution to change this state.

### `review_queue_app.py`

Adds `/queue` and `/api/review-queue` to an ordinary workbench application and exposes a queue-first launcher.

It deliberately reuses:

- `workbench.list_history` as the persisted-history source;
- existing workflow review/adjudication endpoints for mutations;
- normal workbench and calibration routes in the same localhost process.

The browser can therefore trigger legitimate workflow actions from the queue without introducing a second review state machine.

### `workbench.py`

Localhost Flask adapter for evaluation creation, workflow transitions, revision persistence, history, and calibration-dashboard mounting.

For revision creation the server verifies that:

- the base evaluation exists;
- the base has a valid workflow;
- the workflow is `revision_requested`;
- the base has not already been superseded;
- the creating evaluator matches the original evaluator;
- task ID, evaluation type, rubric ID/version, and source stimulus are unchanged;
- the new record independently validates and scores.

Only after validation does the workbench create the child evaluation, child draft workflow, and revision sidecar, then mark the parent workflow superseded. Newly created child-side files are removed if persistence fails before the transition completes.

### `cli.py`

Thin adapter exposing:

```text
rubrics
evaluate
calibrate
reliability
convert
export
import
workbench
queue
```

It contains no alternative scoring, reliability, revision, queue-state, agreement, or interchange-validation semantics.

### `templates/` and `static/`

Browser code is an adapter, not a correctness boundary. The Python server repeats workflow, identity, filtering, and persistence validation.

Population reliability still has no separate browser statistics engine in `0.11.x`; a future UI should invoke `reliability.py` rather than duplicate its formulas.

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

## Dataset interchange boundary

```text
single record / scored payload / array / bundle / JSONL
                         ↓
               typed record parser
                         ↓
          existing rubric + scoring engine
                         ↓
              canonical record(s)
                  ┌──────┼──────┐
                  │      │      │
                bundle  array  JSONL
                  │
                  └──── explicit export file

portable dataset
       ↓
validate + score every record
       ↓
exact-content deduplication
       ↓
workspace/evaluations/*.json
       │
       └─ no imported workflow/revision sidecar
```

The portable dataset carries evaluator-authored records, not trusted local process history. Interchange never turns externally supplied workflow/reviewer metadata into authoritative state.

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

## Review queue boundary

```text
evaluation history + workflow summaries + revision summaries
                         ↓
                derive action state
                         ↓
          search / filter / deterministic sort
                         ↓
                  bounded pagination
                         ↓
              local browser queue view
                         │
                         ├─ review → existing workflow endpoint
                         └─ adjudicate → existing workflow endpoint
```

Queue results are disposable projections. No `<workspace>/queue/` directory exists.

## Calibration boundary

```text
immutable evaluation A + evaluator A ID
immutable evaluation B + evaluator B ID
          [optional C, D, ...]
                    ↓
      same task/type/rubric/source
              validation
                    ↓
      existing scoring engines
                    ↓
          CalibrationReport
                    ↓
   append-only calibration artifact
                    ↓
 derived disagreement explorer
```

Calibration never changes source evaluations, workflows, revision sidecars, ratings, pairwise preferences, audio annotations, or evaluator notes.

## Population reliability boundary

```text
Task 1: same-stimulus evaluator submissions
Task 2: same-stimulus evaluator submissions
Task 3: same-stimulus evaluator submissions
... additional independent task units
                    ↓
        PopulationReliabilitySpec
                    ↓
  per-task validation through existing core
                    ↓
       metric applicability checks
          ┌─────────┼───────────┐
          │         │           │
   ordinal/nominal  Fleiss    ICC(A,1)
        alpha       kappa
          │         │           │
          └─────────┼───────────┘
                    ↓
       PopulationReliabilityReport
             portable JSON
```

Important distinctions:

- **calibration** describes agreement on one stimulus;
- **reliability** describes repeated-task behavior across multiple task units;
- neither identifies ground truth;
- neither automatically ranks or passes/fails evaluators.

Reliability output does not become a workflow sidecar and does not influence review-queue state.

## Audio annotation boundary

Audio evidence stores category/severity/note plus point or interval timestamps in integer milliseconds. Referenced media remains external to the artifact. The core does not currently decode media or claim that a timestamp lies within a trusted duration.

For calibration, annotations match only under explicit category and temporal rules. The deterministic matching heuristic is diagnostic rather than semantic ground truth.

## Local storage

```text
<workspace>/
├── evaluations/
│   └── <task>-<timestamp-or-import-digest>.json
├── workflows/
│   └── <task>-<timestamp>.workflow.json
├── revisions/
│   └── <task>-<timestamp>.revision.json
└── calibrations/
    └── <task>-<timestamp>.calibration.json
```

### Evaluation artifacts

Append-only scored human judgments. Review and revision do not overwrite them. Imported records are also stored here after normal validation/scoring.

### Workflow sidecars

Mutable snapshots containing a complete append-only event chain. Their current state can advance, but earlier events remain present. Interchange import never fabricates these sidecars.

### Revision sidecars

Immutable lineage metadata for child artifacts. Parent/root links and revision numbers are server-owned.

### Calibration artifacts

Append-only derived agreement reports referencing explicit source evaluation filenames and evaluator attribution snapshots.

### Review queue and disagreement explorer

No additional persistent artifact classes. Both are derived views over persisted data.

### Population reliability

Reliability reports are library/CLI outputs. No hidden workspace database, evaluator leaderboard, or persistent reliability authority is created automatically.

### Interchange datasets

Interchange datasets are explicit user-selected files outside hidden workspace state. Exporting one makes evaluator-authored source/metadata portable but does not change the workspace's workflow or revision history.

## Score and statistic semantics

### Scalar score

A criterion is rated `1..5`; aggregate scores are weighted means normalized to `0..100`. Timestamped audio annotations are supporting evidence, not score inputs.

### Pairwise score

A criterion records `A`, `Tie`, or `B`. The signed aggregate reports weighted direction from `-100` to `+100` and does not override human-authored overall preference or strength.

### Calibration metrics

Exact agreement, within-one agreement, annotation F1, severity agreement, temporal similarity, and score spread describe already-authored evaluations. They do not identify which evaluator is correct.

### Reliability coefficients

Krippendorff alpha, Fleiss kappa, and ICC(A,1) describe repeated-task agreement/reliability under different assumptions. Applicability is part of the output. A missing coefficient is not silently replaced by a different statistic.

### Revision number

A revision number is lineage metadata, not a quality metric.

### Queue priority

Queue priority is an operational ordering, not a score.

### Interchange digest

The SHA-256 digest used by import is an exact-content identity key for canonical evaluator-record JSON. It is not a quality score, semantic fingerprint, or proof that two different records express the same judgment.

## Failure and trust model

- Browser controls are convenience only; server validation is authoritative.
- Evaluation payload metadata cannot establish trusted revision parentage.
- Imported datasets cannot establish trusted workflow, reviewer, adjudicator, session, or revision state.
- A malformed workflow sidecar is not silently interpreted as valid evaluator attribution.
- A malformed revision sidecar is not silently accepted as lineage truth.
- Queue action state is derived and not persisted independently.
- Queue query bounds prevent arbitrarily large pages or unbounded repeated filter values.
- Child revision creation never uses the parent evaluation as rollback scratch space.
- Interchange input is fully parsed and scored before workspace writes begin; newly created final artifacts are rolled back when a later persistence error occurs.
- Exact-content import deduplication does not attempt fuzzy/semantic equivalence.
- Reliability metric assumptions are explicit; unsupported dataset designs produce `applicable=false` instead of fabricated coefficients.
- The declared reliability `minimum_task_count` is not interpreted as a universal power/sufficiency guarantee.
- Negative reliability coefficients are preserved rather than clipped.
- External LLM calls and telemetry are outside the current local interface path.

## Schema evolution

The evaluator-record dataset interchange schema is stable at `turkishevalkit.evaluation-dataset@1.0`.

For that schema:

- additive compatible fields may remain within the same major schema line;
- required-field removal, structural incompatibility, or semantic reinterpretation requires an explicit migration/versioning path;
- unsupported future schema versions are rejected rather than guessed or silently migrated;
- `record_count` must agree with the number of records in a canonical bundle.

Other internal persistence surfaces remain governed by their own compatibility rules:

- rubric versions remain independent of package versions;
- workflow state/event semantics require explicit compatibility handling;
- revision-lineage semantic changes require explicit versioning/migration;
- calibration/disagreement matching semantic changes must be documented/versioned;
- queue action derivation changes must be documented because they alter operational projection semantics;
- reliability metric variant/applicability changes must be documented because they alter statistical interpretation;
- old evaluation records must never be silently reinterpreted under a newer rubric.

## Current limitations

TurkishEvalKit currently does not:

- open/decode media or verify actual media duration;
- generate waveforms or infer audio issues;
- convert annotation severity/count into automatic penalties;
- resolve evaluator disagreements automatically;
- rank evaluators or define universal calibration/reliability thresholds;
- infer statistical sufficiency from task count alone;
- persist a database-backed queue/index layer;
- create parallel revision branches or merge competing revisions;
- edit previous evaluation artifacts in place;
- import workflow/reviewer/revision history from interchange datasets as trusted state;
- perform semantic/fuzzy duplicate detection during import;
- synchronize workspaces through a remote service;
- provide a separate browser reliability dashboard.

See [`REVISION_WORKFLOW.md`](REVISION_WORKFLOW.md), [`REVIEW_QUEUE.md`](REVIEW_QUEUE.md), [`REVIEW_WORKFLOW.md`](REVIEW_WORKFLOW.md), [`CALIBRATION.md`](CALIBRATION.md), [`CALIBRATION_DASHBOARD.md`](CALIBRATION_DASHBOARD.md), [`DISAGREEMENT_EXPLORER.md`](DISAGREEMENT_EXPLORER.md), [`RELIABILITY.md`](RELIABILITY.md), [`INTERCHANGE.md`](INTERCHANGE.md), and [`AUDIO_ANNOTATIONS.md`](AUDIO_ANNOTATIONS.md) for domain-specific semantics.
