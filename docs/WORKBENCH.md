# Local Workbench

The TurkishEvalKit workbench is a local browser interface over the same typed evaluation, validation, scoring, and review-workflow engines used by the package core.

## Install

```bash
python -m pip install -e ".[workbench]"
```

The workbench dependency is optional so the core package can remain dependency-free for CLI and library use.

## Start

```bash
turkisheval workbench
```

Default behavior:

- binds to `127.0.0.1`;
- uses port `8765`;
- opens the default browser;
- stores results in the platform-specific TurkishEvalKit data directory.

Useful options:

```bash
turkisheval workbench --workspace ./eval-data
turkisheval workbench --port 9876
turkisheval workbench --no-browser
```

The current CLI deliberately does not expose a network bind-address option.

## Evaluator session

The workbench starts with two local workflow fields:

- **Evaluator ID** — a local identifier that attributes the original judgment;
- **Session ID** — groups evaluations created in the same working session.

The browser remembers these values in local storage for convenience. A new session ID can be generated without changing the evaluator ID.

These identifiers are not authentication. They are audit metadata for a local human workflow. Organizations embedding TurkishEvalKit are responsible for mapping them to their own identity controls if stronger guarantees are required.

## Evaluation modes

The workbench exposes three task families.

### Text

Provide a prompt/instruction and one model response, then rate every rubric criterion from `1` through `5`.

### Audio

Provide an authorized audio reference plus optional transcript/context, then rate every audio rubric criterion from `1` through `5`. TurkishEvalKit stores the reference rather than copying the audio asset into history.

### Pairwise

Provide one prompt and two candidate responses, **A** and **B**. For every criterion choose:

- **A** — candidate A is better for this criterion;
- **Tie** — neither candidate is meaningfully preferable for this criterion;
- **B** — candidate B is better for this criterion.

Then record a separate **overall preference** (`A`, `Tie`, or `B`) and **preference strength** (`1` slight, `2` moderate, `3` strong). The overall decision is intentionally stored separately from the criterion aggregate.

## Evaluation workflow

1. Choose **Text**, **Audio**, or **Pairwise**.
2. Confirm the evaluator and session identifiers.
3. Provide a task id and source/context fields.
4. Complete every required scalar rating or pairwise criterion preference.
5. For pairwise tasks, also choose the overall preference and strength.
6. Add criterion notes and evaluator evidence.
7. Save the record.
8. The local API reconstructs the appropriate typed record.
9. The core validates task type, rubric id/version, completeness, duplicates, and value bounds.
10. The deterministic scalar or pairwise scorer computes the aggregate.
11. The scored evaluation JSON is written to append-only local history.
12. A separate workflow sidecar is created in `draft` state.

The browser does not calculate the authoritative score and does not decide whether a workflow transition is allowed.

## Review workflow

After an evaluation is saved, its workflow panel can advance through explicit human-controlled states.

### Draft

The original evaluator may add an optional handoff note and choose **Submit for review**. Only the evaluator recorded in the session may submit the workflow.

### Submitted

An independent reviewer provides a reviewer ID and chooses:

- **Accept evaluation** — review completes without adjudication;
- **Escalate disagreement** — disagreement is preserved explicitly and an explanatory note is required.

The reviewer ID must differ from the evaluator ID.

### Reviewed / accepted

An accepted review is terminal in the current workflow. No adjudication is required.

### Reviewed / escalated

An independent adjudicator provides a new actor ID, a required resolution note, and one resolution:

- **Original evaluation upheld**;
- **Reviewer concern upheld**;
- **Inconclusive**.

The adjudicator must be different from both the evaluator and reviewer.

### Adjudicated

Adjudication is terminal in the current model. The complete event timeline remains visible and persisted.

See [`REVIEW_WORKFLOW.md`](REVIEW_WORKFLOW.md) for state-machine and artifact semantics.

## Pairwise result semantics

Pairwise criterion preferences are converted to directional values:

```text
A = +1
Tie = 0
B = -1
```

After rubric weights are applied, the aggregate is normalized to `-100..+100`:

- `+100`: all weighted criterion evidence favors A;
- `0`: criterion evidence is balanced;
- `-100`: all weighted criterion evidence favors B.

This is a **criterion preference direction**, not an objective quality score. `overall_preference` and `preference_strength` remain distinct fields in the saved result.

## Storage

The workbench separates immutable evaluation evidence from lifecycle evidence:

```text
<workspace>/
├── evaluations/
│   ├── text-demo-001-20260902T021500123456Z.json
│   ├── audio-demo-001-20260902T021700654321Z.json
│   └── pairwise-demo-001-20260902T021900777777Z.json
└── workflows/
    ├── text-demo-001-20260902T021500123456Z.workflow.json
    ├── audio-demo-001-20260902T021700654321Z.workflow.json
    └── pairwise-demo-001-20260902T021900777777Z.workflow.json
```

Evaluation files are append-only by naming convention. Re-evaluating the same task produces another timestamped file instead of overwriting an earlier judgment.

Workflow sidecars are atomically updated as state changes, but they contain the complete event chain from creation onward. Review/adjudication therefore cannot change the original evaluation JSON.

If a workflow sidecar is absent or unreadable, the evaluation artifact remains visible in history as an untracked evaluation. Lifecycle metadata is supplementary rather than a prerequisite for preserving the scored record.

Scalar history entries expose their normalized `/100` score. Pairwise history entries expose the overall decision plus the signed A↔B criterion preference score. Workflow badges show lifecycle state without conflating it with evaluation quality.

## History interaction

Each recent evaluation has two distinct actions:

- open the evaluation to restore its result and workflow panel;
- download the original evaluation JSON.

Opening a historical item loads the scored evaluation and its workflow sidecar through a details endpoint. It does not load the artifact back into the editable evaluation form and does not overwrite either artifact.

## Privacy

The workbench is designed for local evaluator workflows:

- the server listens on loopback only;
- the UI has no CDN dependency;
- no evaluation or workflow content is sent to a remote API by TurkishEvalKit;
- referenced audio files are not copied into history;
- only the source/context and workflow metadata supplied in the record are persisted.

This does not make arbitrary evaluation data safe to process. Evaluators remain responsible for authorization, retention, device access, and organizational privacy requirements. Pairwise prompts and both candidate responses are stored in the evaluation artifact, so confidential candidate content should only be used in an appropriately protected workspace.

Evaluator/reviewer/adjudicator IDs are metadata, not authentication credentials. Do not put secrets in these fields.

## Audio references

The current audio form accepts a local asset path, asset id, or other authorized reference plus optional transcript/context. It does not upload or duplicate the audio file.

Future timestamped annotation support should continue to reference media rather than assume that private media can be retained by the tool.

## Failure behavior

Invalid evaluation submissions return an error and are not written to history. Examples include:

- missing scalar criterion scores;
- invalid scalar score bounds;
- missing pairwise criterion preferences;
- missing pairwise overall preference or strength;
- duplicate or unknown criterion ids;
- unknown rubric ids;
- cross-type rubric/task mismatch;
- missing evaluator/session identifiers in a workflow-enabled workbench submission.

Invalid workflow transitions also return an error without changing the sidecar. Examples include:

- a non-evaluator trying to submit the draft;
- an evaluator trying to review their own evaluation;
- escalation without an explanatory note;
- adjudicating an accepted review;
- evaluator or reviewer attempting to act as adjudicator;
- adjudication without a resolution note.

Validation remains authoritative in the Python core, not in browser JavaScript.

## Current workflow limitation

The current workflow deliberately has no **request changes → edit → resubmit** loop. A correct implementation needs an explicit superseding relationship between immutable evaluation artifacts. Editing the original JSON in place would destroy the audit trail and is therefore not used as a shortcut.
