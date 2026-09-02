# Local Workbench

The TurkishEvalKit workbench is a local browser interface over the same typed evaluation, validation, scoring, audio-evidence, and review-workflow engines used by the package core.

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

These identifiers are not authentication. They are audit metadata for a local human workflow.

## Evaluation modes

### Text

Provide a prompt/instruction and one model response, then rate every rubric criterion from `1` through `5`.

### Audio

Provide an authorized audio reference plus optional transcript/context, then rate every audio rubric criterion from `1` through `5`. The workbench stores the reference rather than copying the media into history.

Audio mode additionally exposes **Timestamped audio issues**. Each issue can contain:

- Start timestamp;
- optional End timestamp;
- issue category;
- severity;
- evidence note.

The editor accepts:

```text
12.5
01:12.500
00:01:12.500
```

These values are converted to integer milliseconds before submission.

Leaving **End** empty creates a point marker (`start_ms == end_ms`). A non-empty End creates an interval and must not be earlier than Start.

Current categories are nativeness, pronunciation, fluency, intonation, unnatural pause, pace, emphasis, audio artifact, noise, clipping, and other. Severity is minor, major, or critical.

Annotations are supporting evidence only. They do not automatically change a 1–5 rubric rating or the aggregate score. See [`AUDIO_ANNOTATIONS.md`](AUDIO_ANNOTATIONS.md).

### Pairwise

Provide one prompt and two candidate responses, **A** and **B**. For every criterion choose A, Tie, or B, then record a separate overall preference and preference strength (`1` slight, `2` moderate, `3` strong).

## Evaluation workflow

1. Choose **Text**, **Audio**, or **Pairwise**.
2. Confirm evaluator and session identifiers.
3. Provide a task id and source/context fields.
4. For Audio, optionally add timestamped localized evidence.
5. Complete every required scalar rating or pairwise criterion preference.
6. For Pairwise, choose overall preference and strength.
7. Add criterion notes and evaluator evidence.
8. Save the record.
9. The local API reconstructs the typed record.
10. The Python core validates task type, rubric id/version, completeness, duplicates, bounds, and audio annotation semantics.
11. The deterministic scalar or pairwise scorer computes the aggregate.
12. The scored evaluation JSON is written to append-only local history.
13. A separate workflow sidecar is created in `draft` state.

The browser performs early UX validation but does not calculate the authoritative score or define the authoritative audio annotation rules.

## Audio annotation behavior

### Point marker

Entering Start `5.1` and leaving End empty produces:

```json
{
  "start_ms": 5100,
  "end_ms": 5100
}
```

### Interval

Entering Start `00:01.250` and End `00:01.900` produces:

```json
{
  "start_ms": 1250,
  "end_ms": 1900
}
```

### Validation

The UI rejects malformed/non-negative time input, a range whose end is before its start, and an annotation without an evidence note. The Python core independently validates the persisted representation and remains authoritative for direct API/JSON use.

The current workbench does **not** open the referenced audio, know its real duration, provide a waveform/player, or clamp annotations to media length. It therefore does not make a false claim that a timestamp is within the actual asset duration.

Overlapping annotations are allowed because multiple issue types may be audible in the same interval.

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

An accepted review is terminal in the current workflow.

### Reviewed / escalated

An independent adjudicator provides a new actor ID, a required resolution note, and one resolution:

- **Original evaluation upheld**;
- **Reviewer concern upheld**;
- **Inconclusive**.

The adjudicator must differ from both evaluator and reviewer.

### Adjudicated

Adjudication is terminal in the current model. The complete event timeline remains visible and persisted.

See [`REVIEW_WORKFLOW.md`](REVIEW_WORKFLOW.md) for state-machine and artifact semantics.

## Pairwise result semantics

Pairwise criterion preferences map to `A = +1`, `Tie = 0`, and `B = -1`, then to a weighted `-100..+100` direction score. This is not an objective quality score and it does not override the separately authored overall preference or strength.

## Storage

The workbench separates immutable evaluation evidence from lifecycle evidence:

```text
<workspace>/
├── evaluations/
│   ├── text-demo-001-<timestamp>.json
│   ├── audio-demo-001-<timestamp>.json
│   └── pairwise-demo-001-<timestamp>.json
└── workflows/
    └── <task>-<timestamp>.workflow.json
```

For audio evaluations, timestamp annotations live inside the evaluation payload. The referenced media does not.

Evaluation files are append-only by naming convention. Re-evaluating the same task creates another timestamped artifact instead of overwriting earlier evidence.

Workflow sidecars are atomically updated as state changes but retain the complete event chain. Review/adjudication therefore cannot change the original evaluation JSON, ratings, or audio annotations.

If a workflow sidecar is absent or unreadable, the evaluation artifact remains visible in history as untracked.

## History interaction

Each recent evaluation can be opened to restore its result/workflow panel or downloaded as the original evaluation JSON. Opening history does not put the artifact back into an editable form and does not overwrite either evaluation or workflow data.

## Privacy

The workbench is designed for local evaluator workflows:

- the server listens on loopback only;
- the UI has no CDN dependency;
- no evaluation or workflow content is sent to a remote API by TurkishEvalKit;
- referenced audio files are not copied into history;
- source/context, human annotations, and workflow metadata supplied by the evaluator are persisted locally.

This does not make arbitrary evaluation data safe to process. Evaluators remain responsible for authorization, retention, device access, and organizational privacy requirements.

Audio annotation notes are persisted evidence; avoid unnecessary personal/confidential information. Evaluator/reviewer/adjudicator IDs are metadata, not authentication credentials.

## Failure behavior

Invalid evaluation submissions are not written to history. Examples include:

- missing scalar criterion scores;
- invalid scalar score bounds;
- malformed/negative audio timestamps;
- reversed audio intervals;
- empty audio annotation notes;
- unsupported audio categories/severities;
- audio annotations on non-audio tasks;
- exact duplicate audio annotations;
- missing pairwise criterion preferences;
- missing pairwise overall preference or strength;
- duplicate or unknown criterion ids;
- unknown rubric ids;
- cross-type rubric/task mismatch;
- missing evaluator/session identifiers in a workflow-enabled workbench submission.

Invalid workflow transitions also return an error without changing the sidecar, including self-review, escalation without rationale, adjudicating accepted reviews, or non-independent adjudicators.

Validation remains authoritative in the Python core, not in browser JavaScript.

## Current limitations

The workbench deliberately has no in-place request-changes/edit/resubmit loop; revision support needs an explicit superseding relationship between immutable evaluation artifacts.

Audio mode also deliberately has no built-in playback/waveform or media-duration validation yet. Those capabilities should only be added with an explicit media/privacy boundary rather than silently turning TurkishEvalKit into an upload service.
