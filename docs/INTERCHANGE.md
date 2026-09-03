# Evaluation Dataset Interchange

TurkishEvalKit adds a versioned, local-first interchange layer for moving
**evaluator-authored evaluation records** between files and TurkishEvalKit workspaces.

The interchange boundary intentionally excludes trusted workflow, review, adjudication,
and revision state. Those relationships are server-owned process metadata and must not be
accepted from an external dataset as if they were locally verified history.

## Canonical bundle

The preferred portable representation is a UTF-8 JSON object:

```json
{
  "schema": "turkishevalkit.evaluation-dataset",
  "schema_version": "1.0",
  "record_count": 2,
  "records": [
    {
      "task_id": "text-001",
      "evaluation_type": "text",
      "rubric_id": "tr-text-quality",
      "rubric_version": "1.0",
      "ratings": [],
      "audio_annotations": [],
      "evaluator_note": "",
      "justification_en": "",
      "source": {},
      "metadata": {}
    }
  ]
}
```

`record_count` must exactly match the number of records. Unsupported schema versions are
rejected rather than guessed or silently migrated.

The actual evaluation objects use the same record schema consumed by the existing
`evaluate`, calibration, and reliability engines. Interchange does not introduce a second
evaluation model.

## Accepted input forms

`turkisheval convert` and `turkisheval import` can read:

- the canonical versioned bundle;
- a JSON array of evaluation records;
- one JSON evaluation record;
- an existing TurkishEvalKit scored-result object containing a `payload` record;
- JSONL/NDJSON with one record or scored-result object per non-empty line.

With `--input-format auto`, `.jsonl` and `.ndjson` files are treated as JSONL. Other files
are first parsed as JSON and then, if needed, as JSONL.

Every imported or converted record is reconstructed through the normal typed record
parser and validated against the referenced built-in rubric using the existing scalar or
pairwise scoring engine. Invalid criteria, rubric versions, score bounds, preferences, and
audio evidence are therefore rejected at the same correctness boundary used elsewhere.

## Convert files

Convert any accepted representation to the canonical bundle:

```bash
turkisheval convert input.json output.json
```

Convert to JSONL:

```bash
turkisheval convert input.json output.jsonl --output-format jsonl
```

Convert to a plain JSON array:

```bash
turkisheval convert input.jsonl output.json --output-format array
```

Supported output formats are:

- `bundle` — versioned canonical dataset envelope;
- `array` — plain JSON array of evaluator records;
- `jsonl` — one canonical evaluator record per line.

Outputs are written through a temporary sibling file and then replaced.

## Export a workspace

```bash
turkisheval export \
  --workspace ./my-evaluations \
  --output evaluations.json
```

JSONL export:

```bash
turkisheval export \
  --workspace ./my-evaluations \
  --output evaluations.jsonl \
  --format jsonl
```

Export reads `<workspace>/evaluations/*.json`, extracts each evaluator-authored `payload`,
and validates it before writing the dataset. A malformed saved evaluation causes an
explicit export error rather than being silently omitted.

The export does **not** include:

- workflow sidecars;
- reviewer or adjudicator transitions;
- revision lineage sidecars;
- queue projections;
- calibration artifacts;
- disagreement projections;
- reliability reports.

Those artifact classes have different trust and lifecycle semantics.

## Import into a workspace

Preview an import without writing files:

```bash
turkisheval import evaluations.json \
  --workspace ./my-evaluations \
  --dry-run
```

Perform the import:

```bash
turkisheval import evaluations.json \
  --workspace ./my-evaluations
```

Imported records are rescored with the current implementation for their exact persisted
rubric ID/version and are saved as ordinary scored evaluation artifacts.

They deliberately receive **no workflow sidecar**. External evaluator/session/reviewer
metadata is not promoted into trusted local workflow state. In operational views these
artifacts therefore remain untracked until a future explicit attribution/import policy
defines a trustworthy process for that metadata.

## Deduplication

Workspace import computes a SHA-256 digest over a canonical JSON representation of the
evaluator-authored record. This digest excludes result wrappers and workflow metadata.

The importer deduplicates:

- records already present in the workspace;
- duplicate records repeated inside the same input dataset.

Imported artifact names include a digest prefix, so identical re-imports are deterministic
and do not create timestamp-driven copies.

Deduplication is exact-content deduplication. TurkishEvalKit does not currently attempt
semantic or fuzzy duplicate detection.

## Failure and rollback behavior

All input records are parsed and scored before import writes begin. If persistence fails
after new files have started to be created, files created by that import operation are
removed before the error is returned.

Existing workspace artifacts are never rewritten by interchange import.

## Security and privacy boundary

The interchange layer performs no network requests, telemetry, or external AI calls.

A portable dataset may contain prompts, responses, audio references, human notes, or other
sensitive evaluation material inside `source` and `metadata`. Exporting a dataset makes
that evaluator-authored content portable; it does not make the content non-sensitive.
Handle exported files according to the source material's access and retention rules.

## Non-goals

The `1.0` interchange schema does not:

- synchronize two workspaces bidirectionally;
- merge workflow or revision histories;
- trust externally supplied reviewer identities;
- import calibration or reliability reports as authoritative local state;
- migrate unknown future schema versions automatically;
- infer equivalence between records that differ in content;
- provide a database or remote registry.

The goal is a small, explicit, inspectable boundary for moving evaluation records without
weakening TurkishEvalKit's audit model.
