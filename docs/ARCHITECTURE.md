# Architecture

TurkishEvalKit is intentionally split so human judgment remains a domain input rather than an implementation detail hidden inside a UI or model call. Review metadata is also kept outside the scored evaluation artifact so later decisions cannot silently rewrite historical evidence.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments; it does not silently replace them.
2. **Reproducibility** — a stored result identifies the exact rubric id and version used to compute it.
3. **Auditability** — scoring is deterministic, and workflow transitions retain actor/time/outcome evidence.
4. **Artifact immutability** — once saved, an evaluation artifact is not edited by review or adjudication.
5. **Portability** — UTF-8 JSON remains the interchange format; no database is required.
6. **Interface independence** — CLI, browser workbench, and future batch tooling use the same domain models and engines.
7. **Privacy by default** — source metadata may reference local media, but the workbench does not copy referenced media into evaluation history.
8. **Local-first operation** — the browser workbench binds to loopback and does not require a remote service or CDN.

## Layers

### `models.py`

Defines immutable evaluation-domain objects:

- `EvaluationType`
- `Preference`
- `Rating`
- `PairwiseJudgment`
- `RubricCriterion`
- `Rubric`
- `EvaluationRecord`
- `PairwiseEvaluationRecord`

Validation intrinsic to a value belongs here. Examples include rating bounds, pairwise preference-strength bounds, non-empty identifiers, positive criterion weights, and unique criterion ids.

A `Rubric` declares its `evaluation_type`. This is a domain invariant rather than a UI convention. Scalar text/audio submissions use `EvaluationRecord`; pairwise A/B submissions use `PairwiseEvaluationRecord` so the two judgment models cannot be silently conflated.

### `rubrics.py`

Contains built-in, versioned Turkish rubrics. A rubric version is part of the persisted evaluation record. Existing rubric semantics must not be changed in place after publication; semantic changes require a new version.

### `evaluation.py`

Performs cross-object validation and deterministic aggregation for scalar text/audio records. It rejects:

- mismatched rubric id/version;
- mismatched evaluation type;
- missing criterion ratings;
- unknown criterion ratings;
- duplicate ratings.

The engine does not infer missing values and does not repair evaluator input.

### `pairwise.py`

Performs cross-object validation and deterministic aggregation for pairwise A/B records. It rejects mismatched rubric/type data plus missing, unknown, or duplicate criterion judgments.

Criterion choices are mapped to directional values (`A = +1`, `Tie = 0`, `B = -1`) and weighted into a signed `-100..+100` preference score. The separately authored `overall_preference` and `preference_strength` remain intact and are not replaced by this aggregate.

### `workflow.py`

Defines the evaluation-lifecycle state machine independently of scoring.

Core types include:

- `EvaluationSession`
- `EvaluationWorkflow`
- `WorkflowEvent`
- `WorkflowState`
- `WorkflowEventKind`
- `ActorRole`
- `ReviewOutcome`
- `AdjudicationOutcome`

The supported lifecycle is:

```text
created → draft → submitted → reviewed
                              ├─ accepted: terminal
                              └─ escalated → adjudicated
```

The module enforces:

- only the session evaluator may submit a draft;
- the reviewer must differ from the evaluator;
- escalated review requires an explanatory note;
- only escalated reviews may be adjudicated;
- the adjudicator must differ from both evaluator and reviewer;
- adjudication requires a resolution note;
- event sequence numbers are contiguous;
- every event's `from_state` matches the prior event's `to_state`;
- the workflow snapshot state matches the final event.

A workflow transition changes the workflow artifact only. It never mutates evaluation ratings, judgments, source content, or evaluator evidence.

### `serialization.py`

Converts JSON-compatible data into scalar/pairwise evaluation records and workflow snapshots. It also reconstructs workflow event chains through the same domain validators, so malformed persisted state cannot bypass the state-machine invariants merely because it came from disk.

### `cli.py`

A thin command adapter around the evaluation core. It exposes rubric listing, file-based scalar/pairwise evaluation, and the local workbench launcher. Business rules must not exist only in the CLI.

### `workbench.py`

A local-only adapter over the evaluation and workflow cores. It is responsible for:

- creating the browser application;
- exposing built-in rubrics and workflow option metadata to the frontend;
- converting submitted JSON into the appropriate typed evaluation record;
- delegating validation and scoring to the scalar or pairwise engine;
- writing append-only scored evaluation history;
- creating optional evaluator-session workflow sidecars;
- loading and atomically persisting workflow snapshots;
- delegating submit/review/adjudicate transitions to `workflow.py`;
- listing and exporting saved result files.

It must not duplicate rubric, scoring, or workflow-transition rules.

### `templates/` and `static/`

Contain the offline browser UI. The frontend does not use a CDN, does not calculate authoritative scores, and does not decide whether workflow transitions are valid. It collects human input, calls the local API, and renders validated responses.

## Evaluation boundary

```text
prompt / response / candidates / audio reference
                    ↓
             browser or JSON input
                    ↓
      scalar or pairwise typed record
                    ↓
      validation + deterministic scoring
                    ↓
         immutable evaluation JSON
```

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

The workflow sidecar refers to the evaluation by its saved artifact filename. Review therefore records what happened *to the evaluation process* without altering what the evaluator originally submitted.

## Local storage

The workbench separates scored evidence and lifecycle evidence:

```text
<workspace>/
├── evaluations/
│   ├── text-demo-001-<timestamp>.json
│   └── pairwise-demo-001-<timestamp>.json
└── workflows/
    └── text-demo-001-<timestamp>.workflow.json
```

Evaluation filenames include the task id and UTC timestamp and are append-only. Re-evaluating the same task creates a new artifact instead of overwriting an earlier judgment.

Workflow sidecars are snapshots and therefore are atomically replaced as the lifecycle advances. This replacement is not loss of audit history: every prior transition remains inside the `events` tuple. The state snapshot and event chain are validated together whenever the sidecar is loaded.

A missing or corrupt workflow sidecar must not cause the underlying evaluation artifact to disappear from history. Workflow metadata is supplementary lifecycle evidence, not ownership of the evaluation itself.

## Score semantics

### Scalar

A scalar criterion is rated from 1 through 5. Aggregate scores are weighted means. The normalized 0–100 number is a display convenience, not an independent judgment signal.

### Pairwise

A pairwise criterion records `A`, `Tie`, or `B`. The signed aggregate reports the weighted direction of criterion evidence from `-100` (all B) to `+100` (all A). It is not an objective quality score and it does not override the human-authored overall preference or strength.

A future rubric may assign unequal positive weights, but weight changes are semantic changes and therefore require a new rubric version.

## Review semantics

A `reviewed` workflow can have one of two reviewer dispositions:

- `accept` — review is complete; no adjudication is required;
- `escalate` — reviewer disagreement is explicitly recorded and may continue to adjudication.

An adjudicator resolves an escalation with one of:

- `evaluation_upheld`;
- `review_concern_upheld`;
- `inconclusive`.

These labels describe workflow resolution. They are not new evaluation scores.

The current model deliberately has no `request_changes` transition. Supporting revisions correctly requires a superseding-artifact relationship so a revised evaluator submission does not erase the earlier artifact. That model should be designed explicitly rather than introducing in-place edits.

## Schema evolution

Before stable `1.0` evaluation and workflow interchange schemas are declared, JSON field names may evolve. Once stable schemas are published:

- compatible additive fields may remain in the same major schema line;
- required-field changes or semantic reinterpretation require a migration path;
- rubric versions remain independent of application/package versions;
- workflow schema evolution remains independent of rubric versions;
- old evaluation records must never be silently reinterpreted under a newer rubric;
- old workflow events must never be silently rewritten as a different transition meaning.

## Pairwise evaluation

Pairwise evaluation is deliberately represented by its own typed model rather than two ordinary scalar records. The record preserves criterion-level A/Tie/B judgments, criterion notes, an overall preference, preference strength, both candidate responses, and evaluator evidence in one auditable artifact.

The current schema does not include an `insufficient_evidence` preference state. If that state is added later, it requires explicit scoring semantics and a rubric/schema version decision rather than silently treating it as a tie.

## Audio evaluation

The core stores audio references as source metadata. Future timestamp annotations should point to intervals in the referenced asset rather than embedding media bytes in the record. The application must not assume an audio asset may be uploaded or retained indefinitely.
