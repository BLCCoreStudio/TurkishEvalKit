# Architecture

TurkishEvalKit is intentionally split so human judgment remains a domain input rather than an implementation detail hidden inside a UI or model call.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments; it does not silently replace them.
2. **Reproducibility** — a stored result identifies the exact rubric id and version used to compute it.
3. **Auditability** — scoring is deterministic and small enough to inspect directly.
4. **Portability** — UTF-8 JSON remains the interchange format; no database is required.
5. **Interface independence** — CLI, browser workbench, and future batch tooling use the same domain models and scoring engines.
6. **Privacy by default** — source metadata may reference local media, but the workbench does not copy referenced media into evaluation history.
7. **Local-first operation** — the browser workbench binds to loopback and does not require a remote service or CDN.

## Layers

### `models.py`

Defines the immutable domain objects:

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

### `serialization.py`

Converts JSON-compatible data into the correct scalar or pairwise domain object and writes scored results. Serialization is separate from scoring so storage and interfaces can evolve without changing evaluation semantics.

### `cli.py`

A thin command adapter around the core. It exposes rubric listing, file-based scalar/pairwise evaluation, and the local workbench launcher. Business rules must not exist only in the CLI.

### `workbench.py`

A local-only adapter over the same core. It is responsible for:

- creating the browser application;
- exposing built-in rubrics to the frontend;
- converting submitted JSON into the appropriate typed record;
- delegating validation and scoring to the scalar or pairwise core;
- writing append-only scored history;
- listing and exporting saved result files.

It must not duplicate rubric or scoring rules.

### `templates/` and `static/`

Contain the offline browser UI. The frontend does not use a CDN and does not calculate authoritative scores. It collects evaluator input, calls the local API, and renders the validated result.

## Workbench boundary

```text
prompt / response / candidates / audio reference
                    ↓
             browser workbench
                    ↓
               local JSON API
                    ↓
      scalar or pairwise typed record
                    ↓
      validation + deterministic scoring
                    ↓
      append-only history / JSON export
```

The server binds to `127.0.0.1` by design. Network exposure is not an option in the current CLI because the workbench is intended as a local evaluator tool, not a multi-user web service.

## Local storage

The workbench writes one scored JSON file per successful evaluation. Filenames include the task id and a UTC timestamp so existing records are not overwritten.

This append-only behavior is intentional. Editing, superseding, review states, or schema migrations should be represented explicitly in future versions rather than silently rewriting historical evidence.

## Score semantics

### Scalar

A scalar criterion is rated from 1 through 5. Aggregate scores are weighted means. The normalized 0–100 number is a display convenience, not an independent judgment signal.

### Pairwise

A pairwise criterion records `A`, `Tie`, or `B`. The signed aggregate reports the weighted direction of criterion evidence from `-100` (all B) to `+100` (all A). It is not an objective quality score and it does not override the human-authored overall preference or strength.

A future rubric may assign unequal positive weights, but weight changes are semantic changes and therefore require a new rubric version.

## Schema evolution

Before a stable `1.0` interchange schema is declared, JSON field names may evolve. Once a stable schema is published:

- compatible additive fields may remain in the same major schema line;
- required-field changes or semantic reinterpretation require a migration path;
- rubric versions remain independent of application/package versions;
- old records must never be silently reinterpreted under a newer rubric.

## Pairwise evaluation

Pairwise evaluation is deliberately represented by its own typed model rather than two ordinary scalar records. The record preserves criterion-level A/Tie/B judgments, criterion notes, an overall preference, preference strength, both candidate responses, and evaluator evidence in one auditable artifact.

The current schema does not include an `insufficient_evidence` preference state. If that state is added later, it requires explicit scoring semantics and a rubric/schema version decision rather than silently treating it as a tie.

## Audio evaluation

The core stores audio references as source metadata. Future timestamp annotations should point to intervals in the referenced asset rather than embedding media bytes in the record. The application must not assume an audio asset may be uploaded or retained indefinitely.
