# Architecture

TurkishEvalKit is intentionally split so human judgment remains a domain input rather than an implementation detail hidden inside a UI or model call.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments; it does not silently replace them.
2. **Reproducibility** — a stored result identifies the exact rubric id and version used to compute it.
3. **Auditability** — scoring is deterministic and small enough to inspect directly.
4. **Portability** — UTF-8 JSON remains the interchange format; no database is required.
5. **Interface independence** — CLI, browser workbench, and future batch tooling use the same domain model and scoring engine.
6. **Privacy by default** — source metadata may reference local media, but the workbench does not copy referenced media into evaluation history.
7. **Local-first operation** — the browser workbench binds to loopback and does not require a remote service or CDN.

## Layers

### `models.py`

Defines the immutable domain objects:

- `EvaluationType`
- `Rating`
- `RubricCriterion`
- `Rubric`
- `EvaluationRecord`

Validation intrinsic to a value belongs here. Examples include rating bounds, non-empty identifiers, positive criterion weights, and unique criterion ids.

A `Rubric` also declares its `evaluation_type`. This is a domain invariant rather than a UI convention.

### `rubrics.py`

Contains built-in, versioned Turkish rubrics. A rubric version is part of the persisted evaluation record. Existing rubric semantics must not be changed in place after publication; semantic changes require a new version.

### `evaluation.py`

Performs cross-object validation and deterministic aggregation. It rejects:

- mismatched rubric id/version;
- mismatched evaluation type;
- missing criterion ratings;
- unknown criterion ratings;
- duplicate ratings.

The engine does not infer missing values and does not repair evaluator input.

### `serialization.py`

Converts JSON-compatible data into domain objects and writes scored results. Serialization is separate from scoring so storage and interfaces can evolve without changing evaluation semantics.

### `cli.py`

A thin command adapter around the core. It exposes rubric listing, file-based evaluation, and the local workbench launcher. Business rules must not exist only in the CLI.

### `workbench.py`

A local-only adapter over the same core. It is responsible for:

- creating the browser application;
- exposing built-in rubrics to the frontend;
- converting submitted JSON into `EvaluationRecord`;
- delegating validation and scoring to the core;
- writing append-only scored history;
- listing and exporting saved result files.

It must not duplicate rubric or scoring rules.

### `templates/` and `static/`

Contain the offline browser UI. The frontend does not use a CDN and does not calculate authoritative scores. It collects evaluator input, calls the local API, and renders the validated result.

## Workbench boundary

```text
prompt / response / audio reference
               ↓
        browser workbench
               ↓
          local JSON API
               ↓
        EvaluationRecord
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

A criterion is rated from 1 through 5. Aggregate scores are weighted means. The normalized 0–100 number is a display convenience, not an independent judgment signal.

A future rubric may assign unequal positive weights, but weight changes are semantic changes and therefore require a new rubric version.

## Schema evolution

Before a stable `1.0` interchange schema is declared, JSON field names may evolve. Once a stable schema is published:

- compatible additive fields may remain in the same major schema line;
- required-field changes or semantic reinterpretation require a migration path;
- rubric versions remain independent of application/package versions;
- old records must never be silently reinterpreted under a newer rubric.

## Pairwise evaluation

Pairwise evaluation is intentionally not represented as two ordinary scalar records. A correct model needs explicit decisions such as candidate A, candidate B, tie, and insufficient evidence, plus criterion-level rationale. It will be added only with a dedicated typed model and tests.

## Audio evaluation

The core stores audio references as source metadata. Future timestamp annotations should point to intervals in the referenced asset rather than embedding media bytes in the record. The application must not assume an audio asset may be uploaded or retained indefinitely.
