# Review and Adjudication Workflow

TurkishEvalKit separates **evaluation evidence** from **workflow evidence**.

A scored evaluation is an immutable artifact containing the evaluator's ratings or pairwise judgments, source/context, notes, rubric version, and deterministic aggregate. Review and adjudication are recorded in a separate workflow sidecar that references the saved evaluation artifact.

This separation is intentional: later human decisions must not silently rewrite what the original evaluator actually submitted.

## State machine

```text
create
  ↓
draft
  ↓ submit (session evaluator only)
submitted
  ↓ review (independent reviewer)
reviewed
  ├─ accept ───────────────→ terminal
  │
  └─ escalate
       ↓ adjudicate (independent adjudicator)
   adjudicated ────────────→ terminal
```

The current state is a snapshot. The complete path to that state is retained in the workflow's ordered `events` list.

## Actors

### Evaluator

The evaluator authors the original evaluation and owns the local evaluator session recorded when the workflow is created.

Only this evaluator may transition their workflow from `draft` to `submitted`.

### Reviewer

The reviewer independently inspects the submitted evaluation. The reviewer ID must differ from the evaluator ID.

The reviewer chooses one disposition:

- `accept`
- `escalate`

An escalation must contain a non-empty note explaining the disagreement or uncertainty that requires another decision-maker.

### Adjudicator

Adjudication is only available after an escalated review. The adjudicator ID must differ from **both** the evaluator and reviewer.

The adjudicator records one resolution:

- `evaluation_upheld` — the original evaluator judgment remains the supported resolution;
- `review_concern_upheld` — the reviewer concern is supported;
- `inconclusive` — the available evidence does not justify choosing either side conclusively.

A resolution note is mandatory.

These outcomes describe process resolution. They do not alter the original score or pairwise preference.

## Workflow event

Every transition is persisted as an immutable event containing:

- contiguous `sequence` number;
- unique `event_id`;
- event `kind`;
- `from_state` and `to_state`;
- `actor_id`;
- `actor_role`;
- timezone-aware `occurred_at` timestamp;
- optional/required human note depending on transition;
- review or adjudication outcome when applicable.

The workflow loader validates that:

1. event sequences are contiguous from `1`;
2. each `from_state` matches the previous event's `to_state`;
3. the workflow snapshot `state` equals the last event's `to_state`;
4. outcome fields appear only on their valid event kinds.

Malformed persisted state is therefore rejected rather than accepted merely because it exists on disk.

## Artifact relationship

For an evaluation file:

```text
evaluations/text-demo-001-20260902T100000000000Z.json
```

its workflow sidecar is:

```text
workflows/text-demo-001-20260902T100000000000Z.workflow.json
```

The sidecar stores the evaluation filename as `artifact_id` plus the task ID. The evaluation does not need to embed the workflow state.

### Why the evaluation stays immutable

A reviewer may disagree with an evaluator, but disagreement does not make the earlier judgment disappear. Preserving the original artifact supports:

- audit trails;
- calibration analysis;
- later disagreement metrics;
- reproducible debugging of rubric interpretation;
- explicit superseding/revision semantics in a future schema.

Silently changing the evaluator's ratings after review would remove exactly the evidence needed to understand disagreement.

## Sidecar updates

The workflow sidecar is an atomically replaced **snapshot** containing the entire append-only event chain. Replacing the snapshot file as state advances does not discard earlier workflow history because all preceding events remain in the new snapshot.

This differs from evaluation storage:

- evaluation artifacts are append-only files and are not replaced;
- workflow snapshots advance, but their event histories only grow.

## Missing or damaged sidecars

The scored evaluation remains the source artifact even if its workflow sidecar is missing or cannot be parsed.

The workbench history therefore continues to show the evaluation and treats lifecycle information as unavailable/untracked. It must not hide or delete an evaluation because supplementary workflow metadata is damaged.

## Accepted review vs adjudication

`reviewed` is a valid terminal state when the reviewer chooses `accept`.

TurkishEvalKit does not create a meaningless adjudication step merely to force every workflow to the same final label. Only explicit disagreement (`escalate`) creates an adjudication path.

## No in-place revision loop yet

The current workflow does not implement:

```text
request changes → edit original evaluation → resubmit
```

That shortcut would conflict with artifact immutability.

A future revision model should instead create a **new evaluation artifact** and explicitly connect it to the prior one with a superseding/revision relationship. The workflow schema can then represent what was reviewed without destroying the earlier submission.

Until that model is specified and tested, `accept` and `escalate` are the only review outcomes.

## Identity and trust boundary

Evaluator, reviewer, and adjudicator IDs are local audit identifiers. They are not authentication, signatures, or proof of real-world identity.

TurkishEvalKit currently enforces role separation by comparing IDs within the workflow. A multi-user deployment requiring strong identity assurance should integrate an authenticated identity provider at a higher layer rather than treating local string identifiers as security credentials.

## Privacy

Workflow notes may contain review rationale and therefore can be sensitive. They remain local to the selected workbench workspace unless another system explicitly exports or copies them.

Do not place passwords, access tokens, or unnecessary personal data in actor IDs or notes.
