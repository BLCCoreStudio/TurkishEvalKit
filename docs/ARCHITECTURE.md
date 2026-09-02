# Architecture

TurkishEvalKit is intentionally split so human judgment remains a domain input rather than an implementation detail hidden inside a UI or model call.

## Design goals

1. **Human authority** — the core records and validates evaluator judgments; it does not silently replace them.
2. **Reproducibility** — a stored result identifies the exact rubric id and version used to compute it.
3. **Auditability** — scoring is deterministic and small enough to inspect directly.
4. **Portability** — the first interchange format is plain UTF-8 JSON with no database requirement.
5. **UI independence** — CLI, future web/desktop UI, and batch tooling should use the same domain model and scoring engine.
6. **Privacy by default** — source metadata may reference local media, but media is not required to be copied into the project or result artifact.

## Layers

### `models.py`

Defines the immutable domain objects:

- `EvaluationType`
- `Rating`
- `RubricCriterion`
- `Rubric`
- `EvaluationRecord`

Validation that is intrinsic to a value belongs here. Examples: rating bounds, non-empty identifiers, positive criterion weights, and unique criterion ids.

### `rubrics.py`

Contains the built-in, versioned Turkish rubrics. A rubric version is part of the persisted evaluation record. Existing rubric semantics must not be changed in place after publication; semantic changes require a new version.

### `evaluation.py`

Performs cross-object validation and deterministic aggregation. It rejects:

- mismatched rubric id/version;
- missing criterion ratings;
- unknown criterion ratings;
- duplicate ratings.

The engine does not infer missing values and does not repair evaluator input.

### `serialization.py`

Converts JSON-compatible data into domain objects and writes scored results. Serialization is kept separate from scoring so another storage layer can be added without changing evaluation semantics.

### `cli.py`

A thin interface around the core. Business rules should not be added only in the CLI; future interfaces need identical behavior.

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

The core stores audio references as source metadata. Future timestamp annotations should point to intervals in the referenced asset rather than embedding media bytes in the record. The application should not assume that an audio asset may be uploaded or retained indefinitely.

## Future local workbench

The planned UI should be an adapter over the core:

```text
local asset / prompt / response
            ↓
       workbench UI
            ↓
     EvaluationRecord
            ↓
 validation + scoring
            ↓
 local history / export
```

The UI may improve evaluator ergonomics, but it must not become the only place where validation rules exist.
