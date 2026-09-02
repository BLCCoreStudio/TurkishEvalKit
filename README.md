# TurkishEvalKit

[![CI](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml/badge.svg)](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Human-in-the-loop evaluation toolkit for Turkish AI text, timestamped audio QA, pairwise A/B review, action-oriented review queues, immutable revisions, and multi-evaluator calibration.**

TurkishEvalKit records native-language human judgments against explicit, versioned rubrics and turns them into inspectable local artifacts. It is designed for evaluator workflows, QA, research prototypes, and teams that need structured evidence without pretending an automated heuristic can replace the evaluator.

> **Status:** alpha (`0.8.x`). The project includes deterministic text/audio/pairwise evaluation, timestamped audio evidence, review/request-changes/adjudication workflows, immutable revision lineage, server-side review queues and filtering, two-or-more-evaluator calibration, JSON/CLI interfaces, and localhost-only browser tools.

## Why this exists

AI evaluation often fails in two opposite ways: free-form notes are difficult to compare, while over-automated scoring can hide the human judgment the task actually depends on. TurkishEvalKit keeps the evaluator responsible for the decision and standardizes the surrounding workflow.

The project separates:

- **judgment** — authored by a human evaluator;
- **rubric structure** — explicit, typed, and versioned;
- **validation** — deterministic completeness and compatibility checks;
- **aggregation** — reproducible scalar or pairwise score calculation;
- **localized evidence** — timestamped audio observations that explain where an issue is audible;
- **review** — independent reviewer and adjudicator decisions over immutable evidence;
- **revision** — a new artifact that supersedes an older evaluation without rewriting it;
- **queueing** — action state derived from persisted workflow/revision artifacts rather than stored as a second source of truth;
- **calibration** — observed agreement/disagreement across independent evaluators of the same stimulus;
- **interfaces** — CLI and local browser tools over the same core models and workflow APIs.

## Current capabilities

### Text and audio evaluation

- Turkish text-quality rubric covering fluency, instruction following, factuality, helpfulness, and locale fit.
- Turkish audio-quality rubric covering nativeness, pronunciation, fluency, intonation, and synthesis/audio artifacts.
- Strict 1–5 criterion ratings with complete-rubric validation.
- Weighted deterministic aggregate plus normalized `0..100` score.
- Human evaluator note plus optional concise English justification.
- Exact rubric ID/version persisted with every record.

### Timestamped audio evidence

- Point or interval annotations in integer milliseconds.
- Issue category, severity, and human evidence note.
- Validation for negative/reversed timestamps, empty notes, unsupported labels, cross-task use, and duplicates.
- Annotations remain evidence: they do not automatically penalize the 1–5 rubric score.

### Pairwise A/B evaluation

- Criterion-level **A / Tie / B** judgments.
- Separate overall preference and preference strength (`1..3`).
- Deterministic signed criterion aggregate from `-100` to `+100`.
- Holistic preference remains a separate human judgment rather than being inferred from the aggregate.

### Review, request changes, and adjudication

- Evaluator sessions with local evaluator/session IDs.
- Independent reviewer decisions: `accept`, `request_changes`, or `escalate`.
- `request_changes` requires an explanatory reviewer note.
- Reviewer-requested changes create a **new evaluation artifact**; the original evaluation JSON remains unchanged.
- The new artifact starts a fresh draft workflow and records server-owned parent/root lineage.
- One direct superseding child is allowed per artifact, producing a deterministic `r0 → r1 → r2` chain.
- A reviewer cannot review their own evaluation.
- An adjudicator cannot be the evaluator or reviewer.
- Append-only workflow events record actor, role, time, transition, outcome, note, and revision link where applicable.

Revision identity checks preserve the same task, evaluation type, rubric ID/version, and source stimulus. The evaluator may revise the human judgment and evidence fields. See [`docs/REVISION_WORKFLOW.md`](docs/REVISION_WORKFLOW.md).

### Action-oriented review queue

- Server-side free-text search across task, artifact, type, rubric, evaluator, and session identifiers.
- Filters for derived action state, evaluation type, rubric ID, and evaluator ID.
- Deterministic priority, newest, oldest, and task-ID sorting.
- Bounded pagination up to 100 rows per request.
- Workspace-wide action counts and filter facets.
- Derived states: `awaiting_review`, `awaiting_revision`, `awaiting_adjudication`, `draft`, `complete`, `superseded`, and `untracked`.
- Direct review of submitted evaluations and adjudication of escalated reviews through the existing workflow endpoints.
- Filter state is encoded in the local `/queue` URL so a view can be reopened without creating a second saved-query store.

Queue state is not persisted separately. It is reproducibly derived from the evaluation's trusted workflow and revision artifacts, so the queue cannot silently become an independent workflow authority. See [`docs/REVIEW_QUEUE.md`](docs/REVIEW_QUEUE.md).

### Multi-evaluator calibration

- Two or more independent evaluators can be compared when task ID, evaluation type, rubric ID/version, and source stimulus match.
- Scalar reports include exact agreement, within-one agreement, rating differences, criterion observations, evaluator scores, and score spread.
- Pairwise reports include criterion-preference agreement, overall-preference agreement, strength differences, evaluator preference scores, and score spread.
- Audio calibration uses category-aware one-to-one timestamp matching with configurable tolerance and reports annotation F1, severity agreement, and temporal similarity.
- Calibration is diagnostic: it does not decide which evaluator is correct or automatically pass/fail/rank evaluators.

### Local browser workbench

- Text, Audio, and Pairwise evaluation forms.
- Timestamped audio issue editor.
- Evaluation history and JSON export.
- Review, request-changes, revision, and adjudication controls.
- Revision mode pre-fills the previous judgment while locking task/source identity fields; the server independently validates the same constraints.
- Revision generation and supersession are visible in local history.
- Dedicated **Calibration** workspace using actual saved evaluation artifacts.
- Compatibility-grouped evaluator selection and append-only calibration history.
- Queue-first launcher combines Workbench, Review Queue, and Calibration on the same localhost process.
- No CDN, telemetry, or external AI-service requirement.
- Server binds to `127.0.0.1` by default.

## Quick start

Requires Python 3.11 or newer.

```bash
git clone https://github.com/BLCCoreStudio/TurkishEvalKit.git
cd TurkishEvalKit
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

List rubrics:

```bash
turkisheval rubrics
```

Run the self-authored examples:

```bash
turkisheval evaluate examples/text-evaluation.json
turkisheval evaluate examples/audio-evaluation.json --json
turkisheval evaluate examples/pairwise-evaluation.json
```

## Calibration from the CLI

```bash
turkisheval calibrate examples/calibration-text.json
turkisheval calibrate examples/calibration-audio.json --json
turkisheval calibrate examples/calibration-pairwise.json --output calibration.json
```

Audio timestamp matching defaults to `250 ms` and can be changed explicitly:

```bash
turkisheval calibrate examples/calibration-audio.json --annotation-tolerance-ms 150
```

Before calculating agreement, the core requires at least two unique evaluator IDs plus identical task ID, evaluation type, rubric ID/version, and source stimulus. Each source evaluation is validated through the same evaluation engines used elsewhere in the project.

See [`docs/CALIBRATION.md`](docs/CALIBRATION.md) for metric semantics and limitations.

## Local workbench

Install the optional UI dependency:

```bash
python -m pip install -e ".[workbench]"
```

Start the standard evaluation workbench:

```bash
turkisheval workbench
```

Use a dedicated workspace when needed:

```bash
turkisheval workbench --workspace ./my-evaluations --port 8765
```

Run without opening a browser:

```bash
turkisheval workbench --no-browser
```

The main page records evaluations and workflow state. A submitted evaluation can be accepted, escalated, or returned to the original evaluator with `request_changes`. When the evaluator creates the requested revision, the old evaluation remains immutable and the new artifact receives its own draft workflow and revision-lineage sidecar.

Open **Calibration** from the workbench header to compare two or more compatible evaluations already saved in the workspace. Evaluator identity is read from each evaluation's workflow sidecar; missing/corrupt attribution does not silently become a calibration identity.

See [`docs/WORKBENCH.md`](docs/WORKBENCH.md), [`docs/REVISION_WORKFLOW.md`](docs/REVISION_WORKFLOW.md), and [`docs/CALIBRATION_DASHBOARD.md`](docs/CALIBRATION_DASHBOARD.md).

## Review queue

Start the combined local application and open directly into the queue:

```bash
turkisheval queue
```

The dedicated console alias is equivalent:

```bash
turkisheval-queue
```

Workspace, port, and browser flags mirror the standard workbench:

```bash
turkisheval queue --workspace ./my-evaluations --port 8765 --no-browser
```

The queue-first launcher serves the existing workbench at `/`, the review queue at `/queue`, and the calibration dashboard at `/calibration` from one loopback-only process. The queue reuses the existing review/adjudication endpoints rather than implementing a second workflow engine.

The default queue order is operational, not evaluative: awaiting adjudication → awaiting review → awaiting revision → draft → untracked → complete → superseded. It does not imply which evaluation is more correct or valuable.

See [`docs/REVIEW_QUEUE.md`](docs/REVIEW_QUEUE.md) for query semantics, facets, trust boundaries, and pagination behavior.

## Score semantics

### Scalar text/audio

For criterion ratings `rᵢ` and rubric weights `wᵢ`:

```text
weighted_score = Σ(rᵢ × wᵢ) / Σ(wᵢ)
normalized_score = (weighted_score - 1) / 4 × 100
```

The normalized value maps `1 → 0` and `5 → 100`. Timestamped annotations are not part of this formula.

### Pairwise A/B

```text
A = +1
Tie = 0
B = -1

preference_score = Σ(directionᵢ × wᵢ) / Σ(wᵢ) × 100
```

`+100` means every weighted criterion favors A, `-100` means every weighted criterion favors B, and `0` means the criterion evidence is balanced. The score does not replace `overall_preference` or `preference_strength`.

All aggregation is deterministic; interpretation remains a human responsibility.

## Local storage and privacy

Workbench-managed artifact classes remain separate:

```text
<workspace>/
├── evaluations/
│   └── <task>-<timestamp>.json
├── workflows/
│   └── <task>-<timestamp>.workflow.json
├── revisions/
│   └── <task>-<timestamp>.revision.json
└── calibrations/
    └── <task>-<timestamp>.calibration.json
```

Evaluation artifacts are append-only. Workflow sidecars advance state while retaining the complete event chain. Revision sidecars are immutable and record server-owned parent/root lineage. Calibration reports are derived append-only artifacts over explicit source evaluations. Review-queue state is derived at read time and does not add another persisted artifact class.

The local interfaces:

- perform no external LLM calls;
- have no telemetry;
- do not upload prompts, responses, evaluator IDs, audio references, revision data, queue filters, or calibration reports;
- do not copy referenced audio into evaluation history.

A local-only design is not a substitute for organizational access control. Evaluators should process only material they are authorized to access and follow applicable retention/privacy requirements.

## Artifact boundaries

Review, revision, queueing, adjudication, and calibration answer different questions:

```text
immutable evaluation r0
        │
        ├─ workflow → queue projection → next human action
        ├─ review → accept / escalate → optional adjudication
        ├─ review → request_changes → immutable evaluation r1 → new workflow
        └─ calibration input with independent peer evaluations → separate report
```

The queue is a projection over persisted workflow state. No layer silently rewrites the evaluator's previous ratings, pairwise judgments, timestamps, source content, or notes.

## Non-goals

TurkishEvalKit does **not** currently:

- automatically decide whether an answer or voice sample is good;
- send evaluation content to an external AI service;
- claim aggregate scores are objective ground truth;
- automatically pass, fail, rank, or remove evaluators from calibration metrics;
- infer which evaluator is correct when judgments disagree;
- define a universal acceptable agreement threshold;
- claim population reliability from a tiny calibration batch;
- calculate Cohen/Fleiss kappa, Krippendorff's alpha, or ICC yet;
- decode referenced media or validate annotations against actual media duration;
- turn annotation count/severity into score penalties;
- rewrite an evaluation in place during review or revision;
- persist queue priority as an independent workflow truth;
- create parallel revision branches or automatically merge competing revisions.

These are intentional boundaries. Human judgment remains explicit and the audit trail remains inspectable.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest --cov=turkishevalkit --cov-report=term-missing
```

CI validates:

- Python 3.11, 3.12, and 3.13;
- Ruff;
- strict mypy;
- pytest with a 90% coverage floor;
- wheel/package-data smoke checks;
- installed CLI smoke tests;
- real localhost HTTP/persistence flows;
- desktop and mobile Chromium workbench flows.

Feature-specific gates additionally verify calibration, immutable revision lineage, review-queue backend behavior, JavaScript syntax, console entry points, browser assets, and wheel packaging.

## Project map

```text
src/turkishevalkit/
├── models.py                  # typed evaluation records
├── rubrics.py                 # built-in versioned rubrics
├── evaluation.py              # scalar validation/scoring
├── pairwise.py                # pairwise validation/scoring
├── calibration.py             # multi-evaluator agreement engine
├── calibration_dashboard.py   # dashboard/history adapter
├── workflow.py                # review/revision/adjudication lifecycle
├── revision.py                # immutable superseding-artifact lineage
├── review_queue.py            # queue projection/filter/sort/pagination engine
├── review_queue_app.py        # queue routes and queue-first local launcher
├── serialization.py           # JSON boundaries
├── cli.py                     # command-line interface
├── workbench.py               # localhost Flask adapter
├── templates/
└── static/
```

## Documentation

- [`docs/RUBRICS.md`](docs/RUBRICS.md) — rubric definitions and scoring semantics
- [`docs/AUDIO_ANNOTATIONS.md`](docs/AUDIO_ANNOTATIONS.md) — timestamped evidence model
- [`docs/REVIEW_WORKFLOW.md`](docs/REVIEW_WORKFLOW.md) — evaluator/reviewer/adjudicator lifecycle
- [`docs/REVISION_WORKFLOW.md`](docs/REVISION_WORKFLOW.md) — request-changes and immutable revision lineage
- [`docs/REVIEW_QUEUE.md`](docs/REVIEW_QUEUE.md) — action-state derivation, filtering, pagination, and queue trust boundary
- [`docs/CALIBRATION.md`](docs/CALIBRATION.md) — agreement engine and metric semantics
- [`docs/CALIBRATION_DASHBOARD.md`](docs/CALIBRATION_DASHBOARD.md) — browser dashboard and history
- [`docs/WORKBENCH.md`](docs/WORKBENCH.md) — local browser workflow
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — package boundaries and artifact flow

## Roadmap

Near-term work remains ordered around evaluator correctness rather than surface area:

1. richer calibration drill-down without turning disagreement into a leaderboard;
2. population-level reliability statistics only with explicit assumptions and sufficiently sized repeated-task datasets;
3. stronger import/export interoperability while preserving local-first defaults;
4. optional rebuildable metadata indexing only when local workspace scale justifies it;
5. explicit branching semantics only if real collaborative revision use cases justify the complexity.

## License

MIT. See [`LICENSE`](LICENSE).
