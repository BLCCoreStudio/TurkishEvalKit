# TurkishEvalKit

[![CI](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml/badge.svg)](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Human-in-the-loop evaluation toolkit for Turkish AI text, timestamped audio QA, pairwise A/B review, multi-evaluator calibration, and auditable review workflows.**

TurkishEvalKit records native-language human judgments against explicit, versioned rubrics and turns them into inspectable evaluation artifacts. It is designed for evaluator workflows, QA, research prototypes, and teams that need structured evidence without pretending an automated heuristic can replace human judgment.

> **Status:** alpha (`0.5.x`). The current code supports Turkish text/audio ratings, timestamped audio issue evidence, pairwise A/B preference evaluation, two-or-more-evaluator calibration, evaluator sessions, independent review/adjudication, deterministic validation/scoring, JSON import/export, a CLI, and an optional localhost-only browser workbench.

## Why this exists

AI evaluation often fails in two opposite ways: free-form notes are difficult to compare, while over-automated scoring can hide the human judgment the task actually depends on. TurkishEvalKit keeps the evaluator in control and standardizes the surrounding workflow.

The project deliberately separates:

- **judgment** — authored by a human evaluator;
- **rubric structure** — explicit, typed, and versioned;
- **validation** — deterministic checks for task type, completeness, duplicates, and unknown criteria;
- **aggregation** — reproducible scalar or pairwise score calculation;
- **localized evidence** — timestamped audio observations explaining where an issue is audible without automatically changing the score;
- **calibration** — observed agreement/disagreement across independent evaluators of the same stimulus;
- **workflow** — evaluator session, review, escalation, and adjudication events that never rewrite the original evaluation;
- **interfaces** — CLI and local workbench remain adapters over the same core.

## Current capabilities

- Turkish text-quality rubric covering fluency, instruction following, factuality, helpfulness, and locale fit.
- Turkish audio-quality rubric covering nativeness, pronunciation, fluency, intonation, and synthesis/audio artifacts.
- Timestamped audio QA annotations with point/range timestamps, issue category, severity, and human evidence notes.
- Integer-millisecond annotation persistence with validation for negative/reversed timestamps, empty notes, unsupported labels, cross-task use, and exact duplicates.
- Turkish pairwise A/B rubric with criterion-level **A / Tie / B** judgments.
- Separate pairwise **overall preference** and **preference strength (1–3)** fields.
- Deterministic pairwise criterion aggregate from `-100` (all B) through `0` (balanced) to `+100` (all A).
- **2+ evaluator calibration** requiring the same task, evaluation type, rubric version, and source stimulus.
- Scalar calibration with exact agreement, within-one agreement, mean/max rating differences, criterion observations, evaluator scores, and score spread.
- Pairwise calibration with criterion preference agreement, overall-preference agreement, strength differences, and signed-score spread.
- Audio calibration with one-to-one category-aware timestamp matching, annotation F1, severity agreement, and temporal similarity.
- Calibration reports are separate artifacts and never mutate the underlying evaluations.
- Rubrics explicitly bound to evaluation type; cross-type mismatches are rejected by the core.
- Strict 1–5 criterion ratings for scalar text/audio tasks with complete-rubric validation.
- Versioned rubric identifiers stored with every evaluation record.
- Evaluator sessions with explicit local evaluator/session identifiers.
- Typed lifecycle: `draft → submitted → reviewed`, with escalated reviews optionally continuing to `adjudicated`.
- Independent-role enforcement: a reviewer cannot review their own evaluation; an adjudicator cannot be the evaluator or reviewer.
- Append-only workflow event history with actor, role, timestamp, transition, outcome, and notes.
- Immutable scored evaluation artifacts plus separate workflow sidecars.
- UTF-8 JSON input/output with Turkish text preserved.
- Human evaluator notes plus optional English justification.
- Optional browser workbench bound to `127.0.0.1` only.
- Append-only local evaluation history with JSON export.
- No CDN or external service requirement for the workbench UI.
- Self-authored text, timestamped-audio, pairwise, and calibration examples.
- Python 3.11–3.13 CI with Ruff, strict mypy, pytest, 90% coverage gate, CLI smoke, real HTTP, and Chromium browser tests.

## Multi-evaluator calibration

Calibration compares independent evaluations of the **same stimulus**. It exposes where people agree and where rubric interpretation diverges; it does not decide which evaluator is correct.

Run the text example:

```bash
turkisheval calibrate examples/calibration-text.json
```

Emit the full report:

```bash
turkisheval calibrate examples/calibration-audio.json --json
```

Persist a report:

```bash
turkisheval calibrate examples/calibration-pairwise.json --output calibration.json
```

Audio timestamp matching defaults to a `250 ms` tolerance and can be changed explicitly:

```bash
turkisheval calibrate examples/calibration-audio.json --annotation-tolerance-ms 150
```

Before calculating agreement, the core requires at least two unique evaluator IDs plus identical task id, evaluation type, rubric id/version, and source stimulus. Each submitted evaluation is independently validated and scored through the existing evaluation engines.

### Scalar text/audio

The report includes exact criterion agreement, agreement within one rating point, mean/max absolute rating differences, per-criterion observation counts, normalized score per evaluator, and aggregate-score spread.

### Pairwise A/B

The report includes criterion-level A/Tie/B agreement, overall-preference agreement, preference-strength differences, each evaluator's signed criterion-preference score, and score spread.

### Timestamped audio evidence

Audio calibration additionally aligns same-category annotations one-to-one using point/range timing and a configurable tolerance. It reports annotation F1, matched severity agreement, temporal similarity, and pair-level evidence counts.

These are **diagnostic agreement metrics**, not automatic evaluator grades. The current alpha does not claim a universal acceptable threshold and does not compute population-level reliability statistics such as Cohen/Fleiss kappa, Krippendorff's alpha, or ICC. See [`docs/CALIBRATION.md`](docs/CALIBRATION.md).

## Timestamped audio QA

Audio evaluations can preserve exactly where an evaluator heard an issue:

```json
{
  "audio_annotations": [
    {
      "start_ms": 1850,
      "end_ms": 2550,
      "category": "emphasis",
      "severity": "minor",
      "note": "The emphasis sounds synthetic in this interval."
    },
    {
      "start_ms": 5100,
      "end_ms": 5100,
      "category": "intonation",
      "severity": "minor",
      "note": "Sentence-final intonation becomes flat here."
    }
  ]
}
```

`start_ms == end_ms` is a point marker; a larger end value is an interval. The workbench accepts readable values such as `12.5`, `01:12.500`, or `00:01:12.500` and converts them to integer milliseconds before submission.

Annotations are **human evidence, not automatic penalties**. They do not change 1–5 rubric ratings or the aggregate score. TurkishEvalKit also does not currently inspect the media file or verify timestamps against the real audio duration. See [`docs/AUDIO_ANNOTATIONS.md`](docs/AUDIO_ANNOTATIONS.md).

## Review and adjudication

The review layer is deliberately separate from scoring. A saved evaluation remains the evaluator's original artifact. Workflow state lives in a sidecar with a complete transition history.

```text
Evaluation saved
      ↓
    Draft
      ↓ evaluator submits
  Submitted
      ↓ independent reviewer
   Reviewed ── accepted → terminal
      │
      └─ escalated
           ↓ independent adjudicator
       Adjudicated
```

A reviewer can either **accept** an evaluation or **escalate** a disagreement. Escalation requires an explanatory note. Only an escalated review can be adjudicated. The adjudicator records one of:

- `evaluation_upheld`
- `review_concern_upheld`
- `inconclusive`

The workflow records resolution; it does **not** rewrite ratings, audio annotations, pairwise preferences, source content, or evaluator notes. Calibration is also read-only over its input evaluations. See [`docs/REVIEW_WORKFLOW.md`](docs/REVIEW_WORKFLOW.md).

## Non-goals

TurkishEvalKit does **not** currently:

- automatically decide whether an answer, voice sample, or candidate response is good;
- send evaluation content to an external AI service;
- claim aggregate scores are objective ground truth;
- automatically pass, fail, rank, or remove evaluators from calibration metrics;
- claim a universal acceptable agreement threshold;
- infer which evaluator is correct when judgments disagree;
- compute population-level reliability statistics from tiny calibration batches;
- copy referenced private audio into evaluation history;
- open/decode referenced media, validate annotations against real duration, or provide a waveform/player;
- automatically turn annotation count/severity into rubric score penalties;
- edit a submitted evaluation in place after review;
- provide an edit/request-changes/resubmit revision loop yet.

These boundaries are intentional. Revision semantics require an explicit superseding-artifact model, calibration should expose disagreement before resolving it, and automated annotation penalties would alter the meaning of human-authored rubric ratings.

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

Evaluate the included Turkish text example:

```bash
turkisheval evaluate examples/text-evaluation.json
```

Evaluate the timestamped audio example:

```bash
turkisheval evaluate examples/audio-evaluation.json --json
```

Evaluate the pairwise A/B example:

```bash
turkisheval evaluate examples/pairwise-evaluation.json
```

Compare two independent evaluations:

```bash
turkisheval calibrate examples/calibration-text.json
```

Write a scored artifact:

```bash
turkisheval evaluate examples/audio-evaluation.json --output result.json
```

## Local workbench

Install the optional UI dependency:

```bash
python -m pip install -e ".[workbench]"
```

Start the local workbench:

```bash
turkisheval workbench
```

The server binds to `127.0.0.1` and opens the browser automatically. Evaluation content is processed locally. Saved results are written to a platform-appropriate local data directory.

Use a dedicated workspace when needed:

```bash
turkisheval workbench --workspace ./my-evaluations --port 8765
```

Run without opening a browser:

```bash
turkisheval workbench --no-browser
```

The workbench exposes **Text**, **Audio**, and **Pairwise** modes, a timestamped audio issue editor, and evaluator-session/review/adjudication controls. Calibration is currently a CLI/library workflow rather than a browser dashboard. See [`docs/WORKBENCH.md`](docs/WORKBENCH.md).

## Evaluation records

Scalar text/audio records contain task identity, evaluation type, exact rubric version, source material/metadata, one 1–5 rating per rubric criterion, and human-authored notes. Audio records can additionally contain `audio_annotations`.

```json
{
  "task_id": "text-demo-001",
  "evaluation_type": "text",
  "rubric_id": "tr-text-quality",
  "rubric_version": "1.0",
  "ratings": [
    {
      "criterion_id": "fluency",
      "score": 5,
      "note": "Akıcı ve doğal Türkçe."
    }
  ],
  "evaluator_note": "...",
  "justification_en": "...",
  "source": {},
  "metadata": {}
}
```

Pairwise records use criterion judgments instead of scalar ratings and preserve the holistic decision separately:

```json
{
  "task_id": "pairwise-demo-001",
  "evaluation_type": "pairwise",
  "rubric_id": "tr-pairwise-quality",
  "rubric_version": "1.0",
  "judgments": [
    {
      "criterion_id": "fluency",
      "preference": "a",
      "note": "A daha doğal ve akıcı."
    }
  ],
  "overall_preference": "a",
  "preference_strength": 2,
  "source": {
    "prompt": "...",
    "response_a": "...",
    "response_b": "..."
  }
}
```

A real record must include **every** criterion required by its rubric exactly once. See [`examples/text-evaluation.json`](examples/text-evaluation.json), [`examples/audio-evaluation.json`](examples/audio-evaluation.json), [`examples/pairwise-evaluation.json`](examples/pairwise-evaluation.json), and the `examples/calibration-*.json` files.

## Scoring model

### Scalar text/audio

Criterion scores are bounded to `1..5`. For a rubric with weights `wᵢ` and human ratings `rᵢ`:

```text
weighted_score = Σ(rᵢ × wᵢ) / Σ(wᵢ)
normalized_score = (weighted_score - 1) / 4 × 100
```

The normalized score maps `1 → 0` and `5 → 100` without changing the underlying human ratings. Timestamped audio annotations are carried as evidence and are not included in the formula.

### Pairwise A/B

Each criterion preference maps to a direction value:

```text
A = +1
Tie = 0
B = -1

preference_score = Σ(directionᵢ × wᵢ) / Σ(wᵢ) × 100
```

`+100` means every weighted criterion favors A, `-100` every weighted criterion favors B, and `0` means criterion evidence is balanced. This score does **not** replace `overall_preference` or `preference_strength`; both remain separate human judgments.

All aggregation is deterministic; interpretation remains a human responsibility.

## Local storage and privacy

The workbench separates evaluation content from workflow metadata:

```text
<workspace>/
├── evaluations/
│   └── <task>-<timestamp>.json
└── workflows/
    └── <task>-<timestamp>.workflow.json
```

Evaluation files are append-only. The workflow sidecar can advance through states, but every transition is retained in its event list. A corrupt or missing workflow sidecar does not make the underlying evaluation disappear from history.

Audio evaluation records can point to local assets through source metadata. The workbench stores the reference, transcript/context, and human-authored timestamp annotations but does not copy the referenced audio file into history. This repository intentionally ships no voice recordings.

Calibration specs/reports are ordinary user-selected JSON files in the current CLI workflow; TurkishEvalKit does not upload them or silently add them to workbench history.

Evaluators should only process media and prompts they are authorized to access and follow the applicable data-retention and privacy rules of the organization running the evaluation.

## Architecture

```text
source / candidates / audio reference
              ↓
       human evaluation
              ↓
 typed scalar / pairwise record
       + localized audio evidence
              ↓
 validation + deterministic scoring
              ↓
 immutable evaluation artifact
          ↙              ↘
 review workflow      calibration input
 sidecar              with peer artifacts
```

Review changes lifecycle state without changing the evaluation. Calibration reads two or more immutable evaluations and produces a separate agreement report. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest --cov=turkishevalkit --cov-report=term-missing
```

CI runs the quality suite on Python 3.11, 3.12, and 3.13, validates packaged workbench assets, exercises the live localhost API including timestamped-audio persistence and review/adjudication transitions, and runs desktop/mobile Chromium workflows.

## Roadmap

Near-term work remains ordered around evaluator correctness rather than surface area:

1. add calibration history/visualization to the local workbench without changing the read-only calibration boundary;
2. design explicit superseding/revision semantics for request-changes/resubmit workflows;
3. add queue/filtering tools for larger local review sets;
4. evaluate population-level reliability statistics only with explicit assumptions and sufficiently sized repeated-task datasets;
5. publish stable evaluation, calibration, and workflow schema documentation plus migration rules before a `1.0` interchange format.

## Contributing

Small, test-backed changes are welcome. New evaluation dimensions should include a clear definition, scoring guidance, examples, and tests rather than only adding another label. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security and responsible use

Please do not include confidential evaluation data, customer prompts, private audio, credentials, or proprietary datasets in issues or pull requests. See [`SECURITY.md`](SECURITY.md).

## License

MIT. See [`LICENSE`](LICENSE).
