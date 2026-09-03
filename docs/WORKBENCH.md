# Local Workbench

The TurkishEvalKit workbench is a local browser interface over the same typed evaluation, validation, scoring, audio-evidence, workflow, calibration, disagreement, and reliability engines used by the package core.

## Install

```bash
python -m pip install -e ".[workbench]"
```

The dependency is optional so CLI/library use can remain dependency-free.

## Start

```bash
turkisheval workbench
```

Default behavior:

- binds to `127.0.0.1`;
- uses port `8765`;
- opens the default browser;
- stores authoritative workspace artifacts in the selected local workspace.

Useful options:

```bash
turkisheval workbench --workspace ./eval-data
turkisheval workbench --port 9876
turkisheval workbench --no-browser
```

The CLI deliberately does not expose a public network bind-address option.

## Browser surfaces

A standard workbench process serves:

```text
/             evaluation + workflow + revision workbench
/calibration  same-stimulus calibration + disagreement explorer
/reliability  repeated-task population reliability workspace
```

The queue-first launcher additionally serves `/queue` while retaining all standard workbench routes:

```bash
turkisheval queue
```

The browser pages are adapters. Authoritative validation and statistics remain in Python domain modules.

## Evaluator session

The evaluation workbench starts with two local workflow fields:

- **Evaluator ID** — local attribution for the original human judgment;
- **Session ID** — groups evaluations created in the same working session.

The browser remembers these values locally for convenience. They are audit metadata, not authentication credentials.

## Evaluation modes

### Text

Provide a prompt/instruction and one model response, then rate every rubric criterion from `1` through `5`.

### Audio

Provide an authorized audio reference plus optional transcript/context, then rate every audio rubric criterion from `1` through `5`.

Audio mode can also record timestamped issue evidence with:

- start timestamp;
- optional end timestamp;
- issue category;
- severity;
- evidence note.

Accepted time input includes:

```text
12.5
01:12.500
00:01:12.500
```

The UI converts these values to integer milliseconds before submission. Leaving **End** empty creates a point marker (`start_ms == end_ms`).

Annotations are supporting evidence only. They do not automatically change a 1–5 rating or aggregate score. See [`AUDIO_ANNOTATIONS.md`](AUDIO_ANNOTATIONS.md).

### Pairwise

Provide one prompt and candidates **A** and **B**. For every criterion choose A, Tie, or B, then record a separate overall preference and preference strength (`1` slight, `2` moderate, `3` strong).

## Evaluation save path

1. The browser collects evaluator-authored fields.
2. The local API reconstructs the typed record.
3. The Python core validates task type, rubric ID/version, completeness, bounds, duplicates, and audio semantics.
4. The normal scalar or pairwise scorer computes the aggregate.
5. A new append-only evaluation JSON is written.
6. When workflow context is present, a separate workflow sidecar is created in `draft` state.

The browser performs early UX checks but does not calculate authoritative scores.

## Review and revision workflow

Workflow state is separate from immutable evaluation evidence.

Typical paths:

```text
draft → submitted → accept
                 ├→ escalate → adjudicate
                 └→ request_changes → immutable revision
```

`request_changes` does not reopen or edit the original evaluation. The original evaluator creates a new compatible evaluation artifact, a fresh child workflow, and immutable revision-lineage metadata. The parent is then marked superseded.

The server verifies:

- the base evaluation and workflow exist;
- the base is actually awaiting a revision;
- the base is not already superseded;
- the creating evaluator is the original evaluator;
- task ID, evaluation type, rubric ID/version, and source stimulus remain unchanged;
- the new record independently validates and scores.

See [`REVIEW_WORKFLOW.md`](REVIEW_WORKFLOW.md) and [`REVISION_WORKFLOW.md`](REVISION_WORKFLOW.md).

## Calibration dashboard

`/calibration` compares independently attributed evaluations of one shared stimulus.

The dashboard:

- requires trusted evaluator attribution from workflow sidecars;
- groups only compatible task/type/rubric/source evaluations;
- invokes the same calibration core used by the library/CLI;
- stores calibration as a separate append-only derived artifact;
- exposes a read-time disagreement explorer without modifying the source evaluations.

Calibration does not determine which evaluator is correct.

## Reliability Workspace

`/reliability`, introduced in `0.13.x`, analyzes repeated-task reliability across multiple independently rated task units.

Candidate groups are derived from canonical evaluation JSON plus trusted workflow attribution. A group is unavailable when it has missing evaluator attribution, duplicate evaluator IDs, or fewer than two usable evaluator submissions.

When the user analyzes a selection:

1. the client sends only selected evaluation filenames and the declared minimum task count;
2. the server reloads each canonical evaluation and workflow sidecar;
3. evaluator identities are re-established server-side;
4. duplicate filenames, evaluator IDs, and cross-task artifact reuse are rejected;
5. an in-memory `PopulationReliabilitySpec` is constructed;
6. the existing `reliability.py` core computes the report.

The browser does not implement Krippendorff alpha, Fleiss kappa, or ICC itself.

Reliability results are ephemeral by default. The user can explicitly export JSON, but browser analysis does not create an authoritative `reliability/` directory or evaluator leaderboard.

See [`RELIABILITY.md`](RELIABILITY.md).

## Storage

Authoritative and disposable state remain separate:

```text
<workspace>/
├── evaluations/
│   └── <task>-<timestamp-or-import-digest>.json
├── workflows/
│   └── <task>-<timestamp>.workflow.json
├── revisions/
│   └── <task>-<timestamp>.revision.json
├── calibrations/
│   └── <task>-<timestamp>.calibration.json
└── indexes/
    └── metadata.sqlite3
```

- Evaluation files are append-only human evidence.
- Workflow sidecars can advance state while retaining their event chain.
- Revision sidecars are immutable lineage metadata.
- Calibration files are append-only derived reports.
- `indexes/metadata.sqlite3` is optional disposable acceleration.
- Queue/disagreement/reliability browser views do not create new authoritative state merely by being opened or queried.

## History interaction

Recent evaluations can be opened to inspect their result, workflow, and revision state or downloaded as JSON. Opening history does not put an artifact back into an in-place editable form.

When an optional metadata index is fresh, history and review-queue reads can use it. Missing/stale/corrupt indexes fall back to canonical JSON scanning.

## Privacy

The workbench is local-first:

- the server listens on loopback only;
- the UI has no CDN dependency;
- no evaluation/workflow/calibration/reliability content is sent to a remote API by TurkishEvalKit;
- referenced audio files are not copied into history;
- source/context, annotations, and human workflow metadata are persisted locally when they belong to an authoritative artifact.

A local-only design is not a substitute for organizational access control. Process only material you are authorized to access and follow applicable retention/privacy requirements.

## Failure behavior

Invalid evaluation submissions are not persisted as valid history. Examples include:

- missing or out-of-range scalar ratings;
- malformed/negative/reversed audio timestamps;
- empty audio evidence notes;
- unsupported audio categories/severities;
- audio annotations on non-audio tasks;
- duplicate/unknown criterion IDs;
- missing pairwise preferences/strength;
- unknown rubric IDs;
- cross-type rubric/task mismatch.

Invalid workflow transitions return an error without rewriting evaluation evidence.

Reliability Workspace similarly rejects invalid dataset construction before statistics are returned, including insufficient task groups, missing attribution, duplicate evaluator identities, reused artifacts, invalid filenames, and incompatible task/rubric designs.

Validation remains authoritative in Python, not browser JavaScript.

## Current limitations

The workbench still does not:

- authenticate evaluator IDs;
- expose a public network binding mode;
- decode referenced media or provide a waveform/player;
- validate timestamps against trusted media duration;
- automatically resolve evaluator disagreement;
- define universal calibration/reliability thresholds;
- persist browser reliability results as evaluator performance truth;
- create or merge parallel revision branches.
