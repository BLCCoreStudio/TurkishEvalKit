# Revision workflow

TurkishEvalKit treats reviewer-requested changes as a new evaluation artifact, never an edit to previously saved human evidence.

## Why revisions are separate artifacts

A reviewer may identify a problem after an evaluator submits a record. Rewriting the existing JSON would destroy the evidence of what was originally judged, when it was submitted, and what the reviewer actually reacted to. The revision workflow therefore preserves both versions.

The boundary is:

```text
original evaluation JSON
        ↓ submit
independent review
        ↓ request_changes
revision_requested
        ↓ original evaluator creates revision
new evaluation JSON + revision sidecar
        ↓
original workflow → superseded
new workflow      → draft
```

The original evaluation JSON is not rewritten by any of these transitions.

## Requesting changes

A submitted workflow can receive one of three reviewer dispositions:

- `accept`
- `request_changes`
- `escalate`

`request_changes` requires an explanatory reviewer note. The workflow enters `revision_requested`; it is not treated as accepted, escalated, or adjudicated.

Reviewer feedback is process evidence. It does not automatically determine a new score and does not imply that the reviewer is objectively correct.

## Creating a revision

Only the evaluator who authored the original workflow can create the requested revision through the workbench flow.

A valid revision must preserve the identity of the stimulus being evaluated:

- `task_id`
- evaluation type
- rubric id
- rubric version
- source stimulus

The evaluator may revise human judgment fields such as ratings, pairwise preferences, notes, English justification, or audio issue annotations as appropriate.

The browser workbench pre-fills the previous record and locks task/source identity fields while revision mode is active. The Python server independently revalidates those invariants; the browser is not a trust boundary.

## Lineage sidecar

Each revision receives a server-owned sidecar under:

```text
<workspace>/revisions/<revision-artifact>.revision.json
```

The current schema records:

- child `artifact_id`
- `task_id`
- `root_artifact_id`
- immediate `supersedes_artifact_id`
- monotonically increasing `revision_number`
- reviewer that requested the change
- evaluator that created the revision
- original request note
- creation timestamp

An original artifact has no revision sidecar. Its first child is revision `1`. A later child of that revision is revision `2` while retaining the same root artifact id.

Revision numbers and parent/root links are created by the server rather than trusted from evaluation payload metadata.

## Linear chain

The current alpha intentionally enforces one direct superseding child per artifact. A parent cannot produce multiple parallel revisions.

This gives a deterministic chain:

```text
artifact r0 → artifact r1 → artifact r2 → ...
```

Branching revision graphs may be useful for future collaborative workflows, but they require explicit conflict and merge semantics and are outside the current model.

## Workflow state after revision creation

When the new revision is successfully persisted:

1. the child evaluation exists as a new immutable JSON artifact;
2. the child receives a fresh `draft` workflow and session;
3. the child receives its immutable revision lineage sidecar;
4. the parent workflow receives a `revision_created` event;
5. the parent workflow becomes `superseded` and references the child artifact.

The child then follows the ordinary draft → submit → independent-review lifecycle. A later reviewer may request another revision, producing the next lineage generation.

## Storage and failure boundary

Workbench-managed storage is separated by artifact type:

```text
<workspace>/
├── evaluations/   # immutable scored human judgments
├── workflows/     # lifecycle snapshots + append-only event chains
├── revisions/     # immutable parent/root lineage sidecars
└── calibrations/  # derived multi-evaluator agreement reports
```

Revision creation validates the parent before writing a child. If child evaluation, workflow, or lineage persistence fails during creation, newly created child-side files are removed rather than leaving an apparently valid partial revision.

The evaluation artifact that triggered the revision request is never used as rollback scratch space and is never rewritten.

## Revision vs review, adjudication, and calibration

These concepts answer different questions:

- **review**: what did an independent reviewer decide about one evaluation?
- **revision**: what new evaluator artifact supersedes a record after requested changes?
- **adjudication**: how was an escalated reviewer disagreement resolved?
- **calibration**: how consistently did independent evaluators judge the same stimulus?

A revision is not adjudication, and a high revision number is not a quality score. Calibration metrics must continue to operate on explicit evaluation artifacts rather than silently replacing older judgments with the newest revision.

## Current limitations

The current alpha does not support parallel revision branches, in-place edits, automatic reviewer suggestions, automatic acceptance of a revision, semantic diff scoring, or conflict merging. These exclusions preserve a simple auditable lineage until those behaviors can be specified explicitly.
