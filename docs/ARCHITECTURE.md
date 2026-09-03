# Architecture

TurkishEvalKit separates human judgment, deterministic scoring, trusted process state, immutable revision lineage, operational projections, same-stimulus calibration, disagreement exploration, repeated-task reliability, dataset interchange, optional rebuildable metadata indexing, and localhost browser adapters.

A later review, revision, adjudication, queue query, calibration, disagreement drill-down, reliability analysis, export, import, or index rebuild must not silently rewrite an evaluator's earlier evidence.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments rather than replacing them.
2. **Reproducibility** — stored results identify the exact rubric ID/version used.
3. **Auditability** — scoring, localized evidence, workflow transitions, revision parentage, agreement metrics, reliability assumptions, interchange boundaries, and cache freshness are explicit.
4. **Artifact immutability** — evaluation artifacts are append-only; corrections become new artifacts.
5. **Portable records** — UTF-8 JSON is the canonical local artifact format and the evaluation-dataset interchange schema is versioned independently.
6. **Disposable acceleration** — optional indexes may accelerate reads but never become authoritative state.
7. **Interface independence** — CLI and browser flows use the same domain engines.
8. **Server-owned process metadata** — workflow, reviewer, adjudicator, evaluator attribution, and revision relationships are not trusted from evaluator payloads, imported datasets, or browser claims.
9. **Derived operational views** — queue priority/filter state, disagreement hotspots, and reliability candidate grouping are computed rather than stored as new truth.
10. **Applicability-aware statistics** — a reliability coefficient is emitted only when its documented design assumptions are satisfied.
11. **Local-first operation** — browser tools bind to loopback and require no remote service, CDN, telemetry, or external AI service.

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

### `workflow.py`

Defines lifecycle independently of scoring, revision payloads, queue projection, calibration, reliability, interchange, and indexing.

Normal terminal paths:

```text
created → draft → submitted → reviewed
                              ├─ accept: terminal
                              └─ escalate → adjudicated
```

Requested changes create a new immutable artifact:

```text
created → draft → submitted → revision_requested
                                   ↓
                         revision_created event
                                   ↓
                              superseded
```

Workflow sidecars may advance state, but the underlying evaluation JSON is never edited by these transitions. Event sequences retain actor, role, timestamp, outcome, note, and related artifact where applicable.

### `revision.py`

Owns immutable superseding-artifact lineage. The current alpha enforces a linear chain: one direct superseding child per artifact. Parallel branches require explicit conflict/merge semantics and are not inferred automatically.

### `calibration.py`

Compares two or more independent evaluations of the **same stimulus**. It requires unique evaluator IDs plus matching task ID, evaluation type, rubric ID/version, and source stimulus. Each input is revalidated through the existing scalar or pairwise engine.

Reports expose scalar agreement, pairwise preference agreement, evaluator score spread, and — for timestamped audio evidence — deterministic category-aware annotation F1, severity agreement, and temporal similarity.

Calibration is diagnostic. It does not determine which evaluator is correct, rank evaluators, or define a universal pass/fail threshold.

### `disagreement.py`

Builds an evidence-level read-time projection over a saved calibration and its immutable source evaluations. It does not create a persistent leaderboard, determine who is correct, or rewrite calibration/source artifacts.

### `reliability.py`

Owns repeated-task population reliability and remains deliberately separate from `calibration.py`.

The input is a `PopulationReliabilitySpec` containing multiple `ReliabilityTask` units. Each unit contains two or more independent evaluator submissions and is first validated through the same calibration/evaluation engines used elsewhere.

Across the dataset:

- task IDs must be unique;
- all tasks must use the same evaluation type;
- all tasks must use the supplied rubric ID/version;
- every task independently satisfies same-stimulus calibration invariants;
- the specification declares `minimum_task_count >= 3` and contains at least that many task units.

The module computes:

- ordinal/nominal Krippendorff alpha according to the declared data scale;
- Fleiss kappa only for applicable pairwise nominal designs with fixed rating counts;
- ICC(A,1) only for scalar designs with the same evaluator panel across tasks.

Every statistic is returned as `ReliabilityEstimate` with:

```text
metric
value | null
applicable
reason | null
assumptions[]
```

If assumptions fail, TurkishEvalKit returns `applicable=false` and a reason rather than coercing the dataset. Negative coefficients are preserved rather than clipped.

The reliability core is read-only with respect to workspace artifacts.

### `workspace_evaluations.py`

Owns a small read-only boundary for reconstructing saved evaluations plus trusted local evaluator attribution.

It:

- reads canonical evaluation JSON from `evaluations/`;
- reconstructs records through `serialization.py`;
- accepts evaluator identity only from a valid matching workflow sidecar;
- rejects a workflow whose `artifact_id` does not match the evaluation filename;
- derives same-stimulus compatibility keys for local grouping;
- isolates malformed artifacts rather than inventing partial attribution.

The module does not mutate evaluations or workflow state and does not make compatibility keys authoritative.

### `reliability_workspace.py`

Introduced in `0.13.x`, this is the localhost browser adapter for population reliability.

It does **not** implement statistical formulas. Its responsibilities are limited to:

1. discovering canonical saved evaluations through `workspace_evaluations.py`;
2. grouping them by task/type/rubric/source compatibility for browser selection;
3. marking groups unavailable when attribution is missing, evaluator IDs are duplicated, or fewer than two usable evaluations exist;
4. exposing grouping metadata through `GET /api/reliability/candidates`;
5. reloading every selected filename from canonical storage when `POST /api/reliability/analyze` is called;
6. rejecting duplicate filenames, cross-task artifact reuse, duplicate evaluator identities, invalid paths, and undersized selections;
7. building an in-memory `PopulationReliabilitySpec`;
8. delegating the calculation to `build_population_reliability_report()`;
9. returning the ordinary reliability report without persisting a new workspace artifact class.

Client-provided grouping keys are convenience metadata only. The server reconstructs and revalidates the selected records instead of trusting browser state.

### `calibration_dashboard.py`

Adapts local workbench history to the calibration core. It discovers saved evaluation artifacts, reads evaluator identity from workflow sidecars, invokes the existing calibration engine after server-side validation, writes append-only calibration reports, and serves disagreement exploration.

It does not implement a second agreement algorithm.

### `review_queue.py`

Builds a read-only operational projection over evaluation-history metadata. It derives one action state from trusted workflow/revision summaries, applies bounded filters, sorts deterministically, computes facets, and paginates the result.

The queue consumes `workbench.list_history()`. When a fresh optional metadata index exists, the queue receives the indexed projection; otherwise it falls back to canonical JSON scanning.

### `review_queue_app.py`

Adds `/queue` and `/api/review-queue` to an ordinary workbench application and exposes a queue-first launcher. It reuses the normal workbench routes, workflow mutation endpoints, calibration dashboard, and Reliability Workspace in the same localhost process.

### `interchange.py`

Owns the portable evaluator-record dataset boundary.

The canonical bundle is versioned as:

```text
turkishevalkit.evaluation-dataset@1.0
```

It can read one record, arrays, canonical bundles, scored-result wrappers, and JSONL/NDJSON. Every record is reconstructed through `serialization.py` and revalidated through the existing scalar or pairwise scoring engine before conversion or workspace import.

Workspace import creates no workflow sidecar and never promotes external reviewer/session/revision metadata into trusted local process history.

### `metadata_index.py`

Owns the optional disposable SQLite history cache introduced in `0.12.x`.

The index lives at:

```text
<workspace>/indexes/metadata.sqlite3
```

It stores the already-derived history projection. Only a schema-compatible snapshot whose canonical-source fingerprint is current may be read. Missing, stale, or corrupt caches fall back to canonical scanning.

The cache can never establish workflow state, evaluator identity, revision parentage, or artifact existence.

### `workbench.py`

Localhost Flask adapter for evaluation creation, workflow transitions, revision persistence, history, calibration mounting, and Reliability Workspace mounting.

History is split into two paths:

- `scan_history()` — canonical JSON derivation and the source used for index rebuilds;
- `list_history()` — uses a fresh metadata index when available, otherwise delegates to `scan_history()`.

The application registers both the calibration and reliability blueprints against the same resolved workspace, so browser adapters operate over the same canonical artifacts.

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
index status
index rebuild
index clear
workbench
queue
```

It contains no alternative scoring, reliability, revision, queue-state, agreement, interchange-validation, or metadata-derivation semantics.

### `templates/` and `static/`

Browser code is an adapter, not a correctness boundary. Python routes repeat identity, compatibility, workflow, and persistence validation.

The Reliability Workspace renders applicability-aware outputs returned by `reliability.py`; it does not calculate alpha, kappa, or ICC in JavaScript.

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

## Calibration boundary

```text
same-stimulus evaluations + trusted evaluator IDs
                         ↓
                calibration validation
                         ↓
                 CalibrationReport
                         ↓
          append-only calibration artifact
                         ↓
          derived disagreement explorer
```

Calibration never changes source evaluations, workflows, revision sidecars, ratings, pairwise preferences, audio annotations, or evaluator notes.

## Reliability boundary

```text
canonical evaluation JSON + valid workflow attribution
                         ↓
             same-stimulus candidate groups
                         ↓
            browser selects 3+ compatible tasks
                         ↓
        server reloads selected canonical files
                         ↓
             PopulationReliabilitySpec
                         ↓
               reliability.py core
                  ┌──────┼──────┐
                  │      │      │
                alpha  Fleiss  ICC(A,1)
                  │      │      │
                  └──────┼──────┘
                         ↓
             PopulationReliabilityReport
                  ┌──────┴──────┐
                  │             │
             browser view   explicit JSON export
                  │
             no persistence
```

Important distinctions:

- **calibration** describes agreement on one stimulus;
- **reliability** describes repeated-task behavior across multiple task units;
- neither identifies ground truth;
- neither automatically ranks or passes/fails evaluators;
- browser grouping metadata is not a trust boundary;
- reliability output does not become workflow state or review-queue input.

## Dataset interchange boundary

```text
single record / scored payload / array / bundle / JSONL
                         ↓
               typed record parser
                         ↓
          existing rubric + scoring engine
                         ↓
              canonical record(s)
                         ↓
         explicit export/import operation
```

The portable dataset carries evaluator-authored records, not trusted local process history.

## Metadata-index boundary

```text
evaluations/*.json + workflows/*.workflow.json + revisions/*.revision.json
                                  ↓
                      canonical scan_history()
                                  ↓
                      derived history metadata
                                  ↓
                      explicit index rebuild
                                  ↓
                 indexes/metadata.sqlite3
                         (disposable)
                                  ↓
                     schema + fingerprint
                         ┌────────┴────────┐
                      fresh          stale/corrupt
                        ↓                  ↓
                 indexed history     canonical scan
                        ↓                  ↓
                        └────── list_history() ──────┘
                                      ↓
                                 review queue
```

## Local storage

```text
<workspace>/
├── evaluations/
│   └── <task>-<timestamp-or-import-digest>.json
├── workflows/
│   └── <task>-<timestamp>.workflow.json
├── revisions/
│   └── <task>-<timestamp>.revision.json
├── calibrations/
│   └── <task>-<timestamp>.calibration.json
└── indexes/
    └── metadata.sqlite3
```

No `reliability/` directory is created by browser analysis. Reliability reports remain in-memory until the caller explicitly exports or stores them.

## Score and statistic semantics

### Scalar score

A criterion is rated `1..5`; aggregate scores are weighted means normalized to `0..100`. Timestamped audio annotations are supporting evidence, not score inputs.

### Pairwise score

A criterion records `A`, `Tie`, or `B`. The signed aggregate reports weighted direction from `-100` to `+100` and does not override human-authored overall preference or strength.

### Calibration metrics

Agreement and spread metrics describe already-authored evaluations. They do not identify which evaluator is correct.

### Reliability coefficients

Krippendorff alpha, Fleiss kappa, and ICC(A,1) describe repeated-task agreement/reliability under different assumptions. Applicability is part of the output. A missing coefficient is not silently replaced by a different statistic.

### Queue priority

Queue priority is an operational ordering, not a score.

### Interchange digest

The SHA-256 digest used by import is an exact-content identity key for canonical evaluator-record JSON. It is not a quality score or semantic equivalence proof.

### Metadata-index fingerprint

The metadata-index SHA-256 fingerprint covers relative paths, sizes, and nanosecond modification times of canonical history source files. It is a cache-freshness signal, not a content-integrity signature.

## Failure and trust model

- Browser controls are convenience only; server validation is authoritative.
- Evaluation payload metadata cannot establish trusted revision parentage or evaluator attribution.
- Imported datasets cannot establish trusted workflow, reviewer, adjudicator, session, or revision state.
- A malformed workflow sidecar is not silently interpreted as valid evaluator attribution.
- Reliability candidate groups with missing/duplicate attribution remain unavailable.
- Reliability analysis reloads selected filenames from canonical storage and does not trust client compatibility keys.
- The same evaluation artifact cannot be reused across multiple reliability task units in one analysis request.
- Reliability metric assumptions are explicit; unsupported designs produce `applicable=false` instead of fabricated coefficients.
- The declared reliability `minimum_task_count` is not interpreted as a universal power/sufficiency guarantee.
- Negative reliability coefficients are preserved rather than clipped.
- Queue action state is derived and not persisted independently.
- Interchange input is parsed and scored before workspace writes begin.
- A metadata index is used only when its schema and canonical-source fingerprint match.
- Missing, stale, or corrupt metadata indexes fall back to canonical scanning.
- External LLM calls and telemetry are outside the current local interface path.

## Schema evolution

The evaluator-record dataset interchange schema is stable at `turkishevalkit.evaluation-dataset@1.0`.

The metadata index has a separate disposable cache schema version. Incompatible versions are treated as stale and rebuilt rather than migrated as authoritative state.

Other persistence/semantic surfaces retain their own compatibility rules:

- rubric versions remain independent of package versions;
- workflow state/event changes require explicit compatibility handling;
- revision-lineage semantic changes require explicit versioning/migration;
- calibration/disagreement matching changes must be documented/versioned;
- queue action derivation changes must be documented because they alter operational semantics;
- reliability metric variant/applicability changes must be documented because they alter statistical interpretation;
- Reliability Workspace grouping/attribution changes must preserve the canonical-record and server-validation trust boundary;
- old evaluation records must never be silently reinterpreted under a newer rubric.

## Current limitations

TurkishEvalKit currently does not:

- open/decode media or verify actual media duration;
- generate waveforms or infer audio issues;
- convert annotation severity/count into automatic penalties;
- resolve evaluator disagreements automatically;
- rank evaluators or define universal calibration/reliability thresholds;
- infer statistical sufficiency from task count alone;
- persist Reliability Workspace reports as an authoritative evaluator database;
- use the SQLite metadata index as an authoritative database or remote synchronization layer;
- incrementally maintain the metadata index after every canonical write;
- full-content-hash all canonical history files on every indexed read;
- create parallel revision branches or merge competing revisions;
- edit previous evaluation artifacts in place;
- import workflow/reviewer/revision history from interchange datasets as trusted state;
- perform semantic/fuzzy duplicate detection during import;
- synchronize workspaces through a remote service.

See [`REVISION_WORKFLOW.md`](REVISION_WORKFLOW.md), [`REVIEW_QUEUE.md`](REVIEW_QUEUE.md), [`REVIEW_WORKFLOW.md`](REVIEW_WORKFLOW.md), [`CALIBRATION.md`](CALIBRATION.md), [`CALIBRATION_DASHBOARD.md`](CALIBRATION_DASHBOARD.md), [`DISAGREEMENT_EXPLORER.md`](DISAGREEMENT_EXPLORER.md), [`RELIABILITY.md`](RELIABILITY.md), [`INTERCHANGE.md`](INTERCHANGE.md), [`METADATA_INDEX.md`](METADATA_INDEX.md), and [`AUDIO_ANNOTATIONS.md`](AUDIO_ANNOTATIONS.md) for domain-specific semantics.
