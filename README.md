# TurkishEvalKit

[![CI](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml/badge.svg)](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Human-in-the-loop evaluation toolkit for Turkish AI text, audio, pairwise review, calibration, repeated-task reliability, immutable review workflows, and local QA operations.**

TurkishEvalKit records native-language human judgments against explicit, versioned rubrics and turns them into inspectable local artifacts. It is designed for evaluator workflows, QA, research prototypes, and teams that need structured evidence without pretending an automated heuristic can replace the evaluator.

> **Status:** alpha (`0.10.x`). The project includes deterministic text/audio/pairwise evaluation, timestamped audio evidence, review/request-changes/adjudication workflows, immutable revision lineage, action-oriented review queues, multi-evaluator calibration, disagreement drill-down, repeated-task reliability statistics, JSON/CLI interfaces, and localhost-only browser tools.

## Why this exists

AI evaluation often fails in two opposite ways: free-form notes are difficult to compare, while over-automated scoring can hide the human judgment the task actually depends on. TurkishEvalKit keeps the evaluator responsible for the decision and standardizes the surrounding workflow.

The project separates:

- **judgment** — authored by a human evaluator;
- **rubric structure** — explicit, typed, and versioned;
- **validation** — deterministic completeness and compatibility checks;
- **aggregation** — reproducible scalar or pairwise score calculation;
- **localized evidence** — timestamped audio observations;
- **review** — independent reviewer and adjudicator decisions over immutable evidence;
- **revision** — new artifacts that supersede older evaluations without rewriting them;
- **queueing** — next-action state derived from trusted workflow/revision artifacts;
- **calibration** — agreement/disagreement on the same stimulus;
- **disagreement exploration** — criterion/evaluator/evidence drill-down;
- **population reliability** — repeated-task agreement statistics under explicit assumptions;
- **interfaces** — CLI and local browser adapters over the same domain engines.

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
- Annotations remain evidence: they do not automatically change the 1–5 rubric score.

### Pairwise A/B evaluation

- Criterion-level **A / Tie / B** judgments.
- Separate overall preference and preference strength (`1..3`).
- Deterministic signed criterion aggregate from `-100` to `+100`.
- Holistic preference remains explicit human judgment rather than being inferred from the aggregate.

### Review, request changes, and adjudication

- Evaluator sessions with local evaluator/session IDs.
- Independent reviewer decisions: `accept`, `request_changes`, or `escalate`.
- `request_changes` requires an explanatory reviewer note.
- Requested changes create a **new evaluation artifact**; the original evaluation JSON remains unchanged.
- New revisions start a fresh draft workflow and record server-owned parent/root lineage.
- One direct superseding child per artifact, producing a deterministic `r0 → r1 → r2` chain.
- Reviewer and adjudicator separation rules are enforced by the core.
- Append-only workflow events retain actor, role, timestamp, transition, outcome, note, and revision links.

See [`docs/REVIEW_WORKFLOW.md`](docs/REVIEW_WORKFLOW.md) and [`docs/REVISION_WORKFLOW.md`](docs/REVISION_WORKFLOW.md).

### Action-oriented review queue

- Server-side search across task, artifact, type, rubric, evaluator, and session identifiers.
- Filters for derived action state, evaluation type, rubric, and evaluator.
- Deterministic priority/newest/oldest/task sorting.
- Bounded pagination up to 100 rows per request.
- Derived states: `awaiting_review`, `awaiting_revision`, `awaiting_adjudication`, `draft`, `complete`, `superseded`, and `untracked`.
- Direct review and adjudication through the existing workflow endpoints.
- Queue state is **not persisted separately**; it is derived from trusted history.

See [`docs/REVIEW_QUEUE.md`](docs/REVIEW_QUEUE.md).

### Multi-evaluator calibration

Calibration compares two or more independent evaluations of the **same stimulus**.

- Requires matching task ID, evaluation type, rubric ID/version, and source stimulus.
- Scalar reports include exact agreement, within-one agreement, rating differences, evaluator scores, and score spread.
- Pairwise reports include criterion preference agreement, overall-preference agreement, strength differences, and score spread.
- Audio calibration uses category-aware one-to-one timestamp matching with configurable tolerance and reports annotation F1, severity agreement, and temporal similarity.
- Calibration is diagnostic: it does not decide which evaluator is correct or automatically pass/fail/rank evaluators.

### Calibration disagreement explorer

- Orders criterion hotspots by differing evaluator pairs.
- Shows each evaluator's rating/preference and criterion-specific human evidence note.
- Scalar drill-down reports rating gaps.
- Pairwise drill-down reports A/Tie/B directional gaps.
- Audio drill-down shows unmatched annotations and matched timing/severity variance.
- Reconstructs historical attribution from saved calibration source snapshots.
- Missing historical source evaluations return an explicit conflict rather than partial invented evidence.
- Explorer state is derived at read time and is not persisted as a leaderboard or second truth.

See [`docs/DISAGREEMENT_EXPLORER.md`](docs/DISAGREEMENT_EXPLORER.md).

### Population-level reliability

Population reliability is **not** another single-task calibration score. It analyzes a repeated-task dataset containing multiple independently rated task units.

Current `0.10.x` metrics:

- **Krippendorff's alpha**
  - ordinal alpha for scalar `1..5` rubric criteria;
  - nominal alpha for pairwise A/Tie/B criteria and overall preference;
  - ordinal alpha for pairwise preference strength;
  - supports varying evaluator counts/identities by task when each task still has at least two ratings.
- **Fleiss' kappa**
  - pairwise nominal judgments only;
  - requires the same number of ratings on every included task;
  - evaluator identities may vary by task.
- **ICC(A,1)**
  - scalar criterion ratings and normalized aggregate scores;
  - two-way random-effects, absolute-agreement, single-measure form;
  - requires the same evaluator identities on every included task.

Every coefficient is wrapped in an explicit applicability result:

```json
{
  "metric": "icc_a1_absolute_agreement",
  "value": null,
  "applicable": false,
  "reason": "ICC(A,1) requires the same evaluator identities on every task",
  "assumptions": ["..."]
}
```

TurkishEvalKit does not silently coerce a dataset just to produce a number. If a metric's assumptions are not satisfied, the metric is returned as `applicable: false` with a reason.

A reliability specification must declare `minimum_task_count` and the value must be at least `3`. This is an inclusion guardrail chosen by the dataset author, **not** a claim that three tasks are universally statistically sufficient.

Reliability coefficients are not evaluator correctness scores and are never converted automatically into pass/fail thresholds or rankings.

See [`docs/RELIABILITY.md`](docs/RELIABILITY.md) for formulas, assumptions, and interpretation boundaries.

## Quick start

Requires Python 3.11 or newer.

```bash
git clone https://github.com/BLCCoreStudio/TurkishEvalKit.git
cd TurkishEvalKit
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

List built-in rubrics:

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

See [`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## Population reliability from the CLI

Run the repeated-task example:

```bash
turkisheval reliability examples/reliability-text.json
```

Inspect the complete applicability-aware report:

```bash
turkisheval reliability examples/reliability-text.json --json
```

Write the report:

```bash
turkisheval reliability examples/reliability-text.json --output reliability-report.json
```

The `0.10.x` reliability surface is intentionally **core + CLI + portable JSON**. There is no separate browser statistics engine; a future browser view should call the same reliability core.

## Local workbench

Install the optional UI dependency:

```bash
python -m pip install -e ".[workbench]"
```

Start the standard workbench:

```bash
turkisheval workbench
```

Use a dedicated workspace:

```bash
turkisheval workbench --workspace ./my-evaluations --port 8765
```

Run without opening a browser:

```bash
turkisheval workbench --no-browser
```

The main workbench records evaluations, workflow state, revision lineage, history, and JSON exports. Calibration is available from the same localhost application.

## Review queue

Start the combined local application directly in queue mode:

```bash
turkisheval queue
```

Equivalent convenience entry point:

```bash
turkisheval-queue
```

The queue-first launcher serves:

- `/` — evaluation workbench;
- `/queue` — action-oriented review queue;
- `/calibration` — calibration dashboard and disagreement explorer.

The application binds to `127.0.0.1` by default and has no CDN, telemetry, or external AI-service requirement.

## Score semantics

### Scalar text/audio

```text
weighted_score = Σ(rᵢ × wᵢ) / Σ(wᵢ)
normalized_score = (weighted_score - 1) / 4 × 100
```

Timestamped audio annotations are not score inputs.

### Pairwise A/B

```text
A = +1
Tie = 0
B = -1

preference_score = Σ(directionᵢ × wᵢ) / Σ(wᵢ) × 100
```

The signed aggregate does not replace the human-authored overall preference or preference strength.

### Reliability

Reliability coefficients describe properties of repeated human ratings. Negative alpha/kappa/ICC values are preserved rather than clipped because clipping would hide disagreement or model mismatch.

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

Evaluation artifacts are append-only. Workflow sidecars advance state while retaining the event chain. Revision sidecars are immutable lineage metadata. Calibration reports are append-only derived artifacts. Queue and disagreement-explorer state are read-time projections.

Population reliability reports are portable CLI/library outputs in `0.10.x`; TurkishEvalKit does not create a hidden persistent reliability database.

The local interfaces:

- perform no external LLM calls;
- have no telemetry;
- do not upload prompts, responses, evaluator IDs, audio references, revision data, queue filters, disagreement evidence, calibration reports, or reliability datasets;
- do not copy referenced audio into evaluation history.

A local-only design is not a substitute for organizational access control. Process only material you are authorized to access and follow applicable retention/privacy requirements.

## Artifact boundaries

```text
immutable evaluation r0
        │
        ├─ workflow → queue projection → next human action
        ├─ review → accept / escalate → optional adjudication
        ├─ review → request_changes → immutable evaluation r1 → new workflow
        └─ same-stimulus peer evaluations → calibration report → disagreement explorer

multiple independent task units
        ↓
repeated-task reliability spec
        ↓
applicability checks + reliability coefficients
        ↓
portable PopulationReliabilityReport
```

Population reliability consumes evaluation submissions but does not rewrite evaluation, workflow, revision, queue, calibration, or disagreement artifacts.

## Non-goals

TurkishEvalKit does **not** currently:

- automatically decide whether an answer or voice sample is good;
- send evaluation content to an external AI service;
- claim aggregate scores are objective ground truth;
- automatically pass, fail, rank, or remove evaluators;
- infer which evaluator is correct when judgments disagree;
- define a universal acceptable calibration or reliability threshold;
- claim population validity from the declared minimum task count alone;
- treat scalar ordinal ratings as nominal just to obtain Fleiss' kappa;
- treat pairwise categorical preference scores as interval data for ICC;
- impute missing evaluator identities to make ICC applicable;
- decode referenced media or validate annotations against actual media duration;
- turn annotation count/severity into score penalties;
- rewrite an evaluation in place during review or revision;
- persist queue priority or disagreement hotspot order as independent workflow truth;
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

Feature-specific gates additionally validate calibration, disagreement drill-down, immutable revision lineage, review queue behavior, and population reliability semantics/public API/wheel packaging.

## Project map

```text
src/turkishevalkit/
├── models.py                  # typed evaluation records
├── rubrics.py                 # built-in versioned rubrics
├── evaluation.py              # scalar validation/scoring
├── pairwise.py                # pairwise validation/scoring
├── calibration.py             # same-stimulus multi-evaluator agreement
├── disagreement.py            # evidence-level calibration drill-down
├── reliability.py             # repeated-task population reliability
├── calibration_dashboard.py   # calibration history/explorer adapter
├── workflow.py                # review/revision/adjudication lifecycle
├── revision.py                # immutable superseding-artifact lineage
├── review_queue.py            # queue projection/filter/sort/pagination
├── review_queue_app.py        # queue routes and local launcher
├── serialization.py           # JSON boundaries
├── cli.py                     # command-line interface
├── workbench.py               # localhost Flask adapter
├── templates/
└── static/
```

## Documentation

- [`docs/RUBRICS.md`](docs/RUBRICS.md)
- [`docs/AUDIO_ANNOTATIONS.md`](docs/AUDIO_ANNOTATIONS.md)
- [`docs/REVIEW_WORKFLOW.md`](docs/REVIEW_WORKFLOW.md)
- [`docs/REVISION_WORKFLOW.md`](docs/REVISION_WORKFLOW.md)
- [`docs/REVIEW_QUEUE.md`](docs/REVIEW_QUEUE.md)
- [`docs/CALIBRATION.md`](docs/CALIBRATION.md)
- [`docs/CALIBRATION_DASHBOARD.md`](docs/CALIBRATION_DASHBOARD.md)
- [`docs/DISAGREEMENT_EXPLORER.md`](docs/DISAGREEMENT_EXPLORER.md)
- [`docs/RELIABILITY.md`](docs/RELIABILITY.md)
- [`docs/WORKBENCH.md`](docs/WORKBENCH.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Roadmap

Near-term work remains ordered around evaluator correctness rather than surface area:

1. stronger import/export interoperability while preserving local-first defaults;
2. optional rebuildable metadata indexing only when local workspace scale justifies it;
3. an optional browser reliability workspace that reuses the `reliability.py` core instead of duplicating statistics;
4. explicit branching semantics only if real collaborative revision use cases justify the complexity;
5. shared audio-alignment primitives if additional evidence consumers need timestamp matching beyond calibration/explorer paths.

## License

MIT. See [`LICENSE`](LICENSE).
