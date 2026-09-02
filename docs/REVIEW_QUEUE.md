# Review Queue

TurkishEvalKit's review queue is an action-oriented view over saved evaluation, workflow, and revision artifacts. It does not introduce another workflow state machine and it does not mutate evaluation scores while filtering or sorting.

## Start the queue

Install the workbench extra:

```bash
python -m pip install -e ".[workbench]"
```

Open the queue-first combined workbench:

```bash
turkisheval-queue
```

Use a dedicated workspace or port when needed:

```bash
turkisheval-queue --workspace ./my-evaluations --port 8765
```

The server binds to `127.0.0.1` only. The queue is available at `/queue`; the normal workbench and calibration dashboard remain available from the same process.

## Derived action state

Queue action is calculated from persisted workflow state instead of being written as a second source of truth.

| Persisted workflow | Review outcome | Derived queue action |
| --- | --- | --- |
| `draft` | — | `draft` |
| `submitted` | — | `awaiting_review` |
| `revision_requested` | `request_changes` | `awaiting_revision` |
| `reviewed` | `escalate` | `awaiting_adjudication` |
| `reviewed` | `accept` | `complete` |
| `adjudicated` | any valid adjudication | `complete` |
| `superseded` or artifact has a child revision | — | `superseded` |
| no trusted workflow sidecar | — | `untracked` |

The queue therefore remains reproducible from the stored artifacts. Deleting or corrupting a workflow sidecar does not silently manufacture a trusted state; the evaluation becomes `untracked` in the queue.

## Priority ordering

The default `priority` sort is deterministic:

1. awaiting adjudication;
2. awaiting review;
3. awaiting evaluator revision;
4. draft;
5. untracked;
6. complete;
7. superseded.

Within one priority bucket, newer artifacts appear first. Other supported orderings are newest, oldest, and task ID.

Priority is an operational convenience, not a claim about evaluation importance or correctness.

## Filters

The queue API supports server-side filtering by:

- free-text search across task ID, artifact filename, evaluation type, rubric ID, evaluator ID, and session ID;
- derived action state;
- evaluation type;
- rubric ID;
- evaluator ID;
- sort mode;
- page and page size.

The browser keeps the filter state in the queue URL so a local filtered view can be reopened without creating a saved server-side query object.

Example API request:

```text
/api/review-queue?action=awaiting_review&evaluator_id=eval-01&sort=priority&page=1&per_page=50
```

`per_page` is limited to `1..100`. Search strings and repeated filter values are bounded to keep malformed requests from creating unbounded parser work.

## Facets and summary counts

Each queue response includes:

- workspace total;
- actionable total;
- counts for every derived action;
- evaluator, rubric, and evaluation-type facets;
- matched total;
- page metadata.

Facets describe the complete current workspace, not only the current result page. This lets the UI retain useful filter options even when a narrow filter is active.

## Review and adjudication from the queue

The queue page reuses the existing workbench workflow endpoints:

- a `submitted` artifact can be reviewed as `accept`, `request_changes`, or `escalate`;
- an escalated `reviewed` artifact can be independently adjudicated.

All existing workflow invariants still apply. In particular:

- evaluators cannot review their own evaluation;
- `request_changes` and `escalate` require explanatory notes;
- adjudicators must be independent from evaluator and reviewer;
- review/adjudication never rewrites the original evaluation artifact.

Requested revisions are still created through the main workbench because revision mode needs the editable evaluation form while preserving the original source/rubric identity.

## Pagination model

The current local implementation reads the workspace's append-only evaluation history, derives queue state, applies filters, then paginates the matched result set. This is appropriate for local alpha workspaces and keeps JSON artifacts as the source of truth.

For very large workspaces, a future index may cache searchable metadata. Any such index must remain rebuildable from the evaluation/workflow/revision artifacts and must not become an independent authority for workflow state.

## Privacy and trust boundary

The queue:

- makes no external LLM calls;
- has no telemetry;
- does not upload prompts, responses, evaluator IDs, notes, or local paths;
- does not copy referenced audio;
- uses local evaluator IDs only as workflow attribution labels;
- treats malformed workflow or revision data conservatively.

Local-only operation does not replace organizational access control or retention policy. Process only evaluation material you are authorized to handle.
