# TurkishEvalKit

[![CI](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml/badge.svg)](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Human-in-the-loop evaluation toolkit for Turkish AI text, timestamped audio QA, pairwise A/B review, multi-evaluator calibration, and auditable review workflows.**

TurkishEvalKit records native-language human judgments against explicit, versioned rubrics and turns them into inspectable local artifacts. It is designed for evaluator workflows, QA, research prototypes, and teams that need structured evidence without pretending an automated heuristic can replace the evaluator.

> **Status:** alpha (`0.6.x`). The project includes deterministic text/audio/pairwise evaluation, timestamped audio evidence, two-or-more-evaluator calibration, review/adjudication workflows, JSON/CLI interfaces, and a localhost-only browser workbench with calibration history and visualization.

## Why this exists

AI evaluation often fails in two opposite ways: free-form notes are difficult to compare, while over-automated scoring can hide the human judgment the task actually depends on. TurkishEvalKit keeps the evaluator responsible for the decision and standardizes the surrounding workflow.

The project separates:

- **judgment** — authored by a human evaluator;
- **rubric structure** — explicit, typed, and versioned;
- **validation** — deterministic completeness and compatibility checks;
- **aggregation** — reproducible scalar or pairwise score calculation;
- **localized evidence** — timestamped audio observations that explain where an issue is audible;
- **calibration** — observed agreement/disagreement across independent evaluators of the same stimulus;
- **workflow** — evaluator session, review, escalation, and adjudication events that never rewrite the original evaluation;
- **interfaces** — CLI and local browser workbench over the same core models.

## Current capabilities

### Text and audio evaluation

- Turkish text-quality rubric covering fluency, instruction following, factuality, helpfulness, and locale fit.
- Turkish audio-quality rubric covering nativeness, pronunciation, fluency, intonation, and synthesis/audio artifacts.
- Strict 1–5 criterion ratings with complete-rubric validation.
- Weighted deterministic aggregate plus a normalized `0..100` score.
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

### Multi-evaluator calibration

- Two or more independent evaluators can be compared when task ID, evaluation type, rubric ID/version, and source stimulus match.
- Scalar reports include exact agreement, within-one agreement, rating differences, criterion observations, evaluator scores, and score spread.
- Pairwise reports include criterion preference agreement, overall-preference agreement, strength differences, evaluator preference scores, and score spread.
- Audio calibration uses category-aware one-to-one timestamp matching with configurable tolerance and reports annotation F1, severity agreement, and temporal similarity.
- Calibration is diagnostic: it does not decide which evaluator is correct or automatically pass/fail/rank evaluators.

### Review and adjudication

- Evaluator sessions with local evaluator/session IDs.
- Typed lifecycle: `draft → submitted → reviewed`, with escalated reviews optionally continuing to `adjudicated`.
- A reviewer cannot review their own evaluation.
- An adjudicator cannot be the evaluator or reviewer.
- Append-only workflow event history records actor, role, time, transition, outcome, and note.
- Review and adjudication never rewrite the original scored artifact.

### Local browser workbench

- Text, Audio, and Pairwise evaluation forms.
- Timestamped audio issue editor.
- Evaluation history and JSON export.
- Review/adjudication controls.
- Dedicated **Calibration** workspace using actual saved evaluation artifacts.
- Compatibility-grouped evaluator selection.
- Calibration metric cards, evaluator aggregate view, criterion observation table, and audio pair-agreement details.
- Append-only calibration history with reopen/download support.
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

Run a scalar example:

```bash
turkisheval calibrate examples/calibration-text.json
```

Emit the complete JSON report:

```bash
turkisheval calibrate examples/calibration-audio.json --json
```

Persist a report:

```bash
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

Start the workbench:

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

The main page records evaluations and review workflow state. Open **Calibration** from the header to compare two or more compatible evaluations already saved in that workspace.

The dashboard reads evaluator identity from each evaluation's workflow sidecar. A missing or corrupt workflow sidecar does not hide the underlying evaluation; it is shown as unavailable for calibration because attribution cannot be established safely.

See [`docs/WORKBENCH.md`](docs/WORKBENCH.md) and [`docs/CALIBRATION_DASHBOARD.md`](docs/CALIBRATION_DASHBOARD.md).

## Calibration dashboard semantics

Dashboard calibration is deliberately read-only over its inputs:

```text
saved evaluation A ─┐
saved evaluation B ─┼─ compatibility check ─ calibration engine ─ report artifact
saved evaluation C ─┘                                      │
                                                           └─ dashboard/history
```

The UI groups evaluations by a deterministic compatibility identity. Selection is constrained to one compatible group, and the server revalidates all invariants before generating a report. Client-side grouping is therefore a usability aid, not a security or correctness boundary.

A saved dashboard report records:

- report schema version and creation time;
- source evaluation filenames;
- local evaluator IDs associated with those source artifacts;
- the complete core calibration report.

Reopening history reads the saved calibration artifact instead of silently recomputing it from future workspace state.

## Scoring model

### Scalar text/audio

For criterion ratings `rᵢ` and rubric weights `wᵢ`:

```text
weighted_score = Σ(rᵢ × wᵢ) / Σ(wᵢ)
normalized_score = (weighted_score - 1) / 4 × 100
```

The normalized value maps `1 → 0` and `5 → 100`. Timestamped annotations are not part of this formula.

### Pairwise A/B

Each criterion direction is mapped as:

```text
A = +1
Tie = 0
B = -1

preference_score = Σ(directionᵢ × wᵢ) / Σ(wᵢ) × 100
```

`+100` means every weighted criterion favors A, `-100` means every weighted criterion favors B, and `0` means the criterion evidence is balanced. The score does not replace `overall_preference` or `preference_strength`.

All aggregation is deterministic; interpretation remains a human responsibility.

## Local storage and privacy

The workbench keeps evaluation, workflow, and calibration artifacts separate:

```text
<workspace>/
├── evaluations/
│   └── <task>-<timestamp>.json
├── workflows/
│   └── <task>-<timestamp>.workflow.json
└── calibrations/
    └── <task>-<timestamp>.calibration.json
```

Evaluation artifacts are append-only. Workflow sidecars can advance state while retaining their complete event chain. Calibration artifacts are also append-only and contain references to the local source evaluation filenames used to generate them.

The workbench:

- performs no external LLM calls;
- has no telemetry;
- does not upload prompts, responses, evaluator IDs, audio references, or calibration reports;
- does not copy referenced audio into evaluation or calibration history.

A local-only design is not a substitute for organizational access control. Evaluators should process only material they are authorized to access and follow applicable retention/privacy requirements.

## Review and calibration are different

Review records a human workflow decision about one evaluation. Calibration compares independent evaluations and exposes where rubric interpretation diverges.

```text
immutable evaluation ── review sidecar ── submitted/reviewed/adjudicated
        │
        └──────── calibration input with peer evaluations
                              │
                              └─ separate agreement report
```

Neither layer rewrites ratings, pairwise judgments, timestamps, source content, or evaluator notes.

See [`docs/REVIEW_WORKFLOW.md`](docs/REVIEW_WORKFLOW.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

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
- rewrite submitted evaluations during review;
- provide a request-changes/resubmit revision model yet.

These are intentional boundaries. Calibration exposes disagreement before resolution; review records a separate human decision; automated penalties would change the meaning of human-authored rubric ratings.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest --cov=turkishevalkit --cov-report=term-missing
```

CI currently validates:

- Python 3.11, 3.12, and 3.13;
- Ruff;
- strict mypy;
- pytest with a 90% coverage floor;
- wheel/package-data smoke checks;
- installed CLI smoke tests;
- real localhost HTTP/persistence flows;
- desktop and mobile Chromium workbench flows.

The dashboard test suite additionally verifies compatibility grouping, evaluator attribution, append-only source preservation, calibration history, JSON download, malformed-artifact behavior, request validation, and incompatible-source rejection.

## Project map

```text
src/turkishevalkit/
├── models.py                  # typed evaluation records
├── rubrics.py                 # built-in versioned rubrics
├── evaluation.py              # scalar validation/scoring
├── pairwise.py                # pairwise validation/scoring
├── calibration.py             # multi-evaluator agreement engine
├── calibration_dashboard.py   # dashboard/history adapter
├── workflow.py                # review/adjudication lifecycle
├── serialization.py           # JSON boundaries
├── cli.py                     # command-line interface
├── workbench.py               # localhost Flask adapter
├── templates/
└── static/
```

## Documentation

- [`docs/RUBRICS.md`](docs/RUBRICS.md) — rubric definitions and scoring semantics
- [`docs/AUDIO_ANNOTATIONS.md`](docs/AUDIO_ANNOTATIONS.md) — timestamped evidence model
- [`docs/CALIBRATION.md`](docs/CALIBRATION.md) — agreement engine and metric semantics
- [`docs/CALIBRATION_DASHBOARD.md`](docs/CALIBRATION_DASHBOARD.md) — browser dashboard, history, routes, and trust boundary
- [`docs/REVIEW_WORKFLOW.md`](docs/REVIEW_WORKFLOW.md) — evaluator/reviewer/adjudicator lifecycle
- [`docs/WORKBENCH.md`](docs/WORKBENCH.md) — local browser workflow
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — package boundaries and artifact flow

## Roadmap

Near-term work remains ordered around evaluator correctness rather than surface area:

1. explicit superseding/revision semantics for request-changes/resubmit workflows;
2. queue/filtering tools for larger local review sets;
3. richer calibration drill-down without turning disagreement into a leaderboard;
4. population-level reliability statistics only with explicit assumptions and sufficiently sized repeated-task datasets;
5. stronger import/export interoperability while preserving local-first defaults.

## License

MIT. See [`LICENSE`](LICENSE).
