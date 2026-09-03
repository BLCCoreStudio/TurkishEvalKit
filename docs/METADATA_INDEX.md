# Rebuildable Metadata Index

TurkishEvalKit `0.12.x` adds an **optional, disposable SQLite metadata index** for large local workspaces.

The index is a read-optimization layer only. Evaluation JSON, workflow sidecars, and revision sidecars remain the canonical source of truth.

## Why it exists

The normal history path derives queue/history metadata by reading evaluation artifacts and their workflow/revision sidecars. That is simple and trustworthy, but repeated JSON parsing becomes unnecessary overhead as a workspace grows.

The metadata index stores the already-derived history projection in a compact local SQLite file so read-heavy history and review-queue requests can reuse it.

The design deliberately does **not** turn SQLite into a second authority.

## Opt-in behavior

No index is created automatically.

Check status:

```bash
turkisheval index status --workspace ./my-evaluations
```

Inspect machine-readable status:

```bash
turkisheval index status --workspace ./my-evaluations --json
```

Build or rebuild the index:

```bash
turkisheval index rebuild --workspace ./my-evaluations
```

Delete it:

```bash
turkisheval index clear --workspace ./my-evaluations
```

Deleting the index never deletes evaluations, workflows, revisions, calibration artifacts, or interchange datasets.

## Storage

The cache lives at:

```text
<workspace>/indexes/metadata.sqlite3
```

The current metadata-index schema version is `1`.

The database contains one row per valid history entry plus indexed columns commonly used by operational views, including:

- task ID;
- evaluation type;
- rubric ID/version;
- evaluator/session IDs;
- workflow state;
- review/adjudication outcomes;
- revision lineage summary;
- scalar/pairwise aggregate fields;
- saved timestamp.

Indexes exist for common history/queue dimensions such as task, evaluation type, rubric, evaluator, workflow state, and saved time.

## Freshness model

A rebuild records a SHA-256 fingerprint over **file metadata** for canonical history sources:

- `evaluations/*.json`;
- `workflows/*.workflow.json`;
- `revisions/*.revision.json`.

The fingerprint uses each relative path, file size, and nanosecond modification time. This avoids reparsing JSON merely to decide whether a cache can be reused.

Index status is one of:

- `absent` — no optional cache exists;
- `fresh` — schema and canonical-source fingerprint match;
- `stale` — source files changed or the index schema version is no longer current;
- `corrupt` — the SQLite file cannot be read as a valid index.

## Read behavior

`workbench.list_history()` follows this order:

```text
metadata index exists?
        │
        ├─ no ───────────────→ canonical JSON scan
        │
        └─ yes
             ↓
       schema + fingerprint valid?
             │
             ├─ yes ─────────→ indexed history projection
             │
             └─ no ──────────→ canonical JSON scan
```

A stale or corrupt index is never used merely because it exists. The indexed read verifies freshness before reading rows and checks the canonical-source fingerprint again before returning the cached projection, reducing the window in which a concurrent canonical write could expose stale cache data.

The review queue already consumes `list_history()`, so it automatically receives the same safe acceleration when a fresh index is present.

## Rebuild semantics

`index rebuild` always starts from a canonical history scan. It does not rebuild from the previous database.

The CLI captures the canonical source fingerprint before scanning. The SQLite writer verifies that the same source snapshot still exists before writing and again immediately before atomically publishing the new database. If evaluation/workflow/revision files change during the rebuild, the operation fails and no new index is published; the caller can retry against the newer canonical state.

The new database is written to a temporary sibling SQLite file and atomically replaces the old index only after the rebuild succeeds. SQLite connections are closed before replacement so the lifecycle also works correctly on platforms with stricter file-lock semantics.

If the rebuild fails, the existing canonical artifacts are untouched.

Malformed evaluation/workflow/revision files keep the same isolation behavior as the normal history scanner. For example, an invalid evaluation JSON is not invented into a history row.

## Trust boundary

The index may be deleted at any time and reconstructed from canonical files.

It must never be used to:

- create or repair workflow state;
- establish evaluator identity;
- establish revision parentage;
- overwrite an evaluation artifact;
- restore deleted canonical files;
- import external reviewer/adjudicator state;
- decide which evaluator is correct;
- become a hidden synchronization database.

If index content disagrees with canonical files, canonical files win by invalidating the index fingerprint.

## External file changes

The fast freshness check uses path, size, and `mtime_ns`, not full content hashes. Normal TurkishEvalKit writes change those attributes and therefore invalidate a stale snapshot.

An external tool that intentionally modifies file contents while preserving both file size and nanosecond modification time could evade this cheap freshness check. In environments that perform such metadata-preserving rewrites, run `turkisheval index rebuild` after external changes or clear the index entirely.

This trade-off is intentional: hashing every canonical file on every read would largely remove the performance benefit of the cache.

## Non-goals

The `0.12.x` metadata index does not:

- update incrementally after every write;
- replace append-only JSON persistence;
- index calibration or reliability results;
- provide multi-process transaction semantics for canonical artifacts;
- provide remote/database-backed workspace synchronization;
- guarantee semantic search;
- perform full-content hashing on each read;
- require users with small workspaces to enable it.

The index exists only when workspace scale makes repeated metadata parsing worth avoiding.
