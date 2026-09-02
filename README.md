# TurkishEvalKit

[![CI](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml/badge.svg)](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Human-in-the-loop evaluation toolkit and local workbench for Turkish AI text, audio, pairwise A/B quality, and review workflows.**

TurkishEvalKit records native-language human judgments against explicit, versioned rubrics and turns them into auditable evaluation artifacts. The project is designed for evaluator workflows, QA, research prototypes, and teams that need structured evidence without pretending that an automated heuristic can replace human judgment.

> **Status:** alpha (`0.3.x`). The current code supports Turkish text and audio-quality ratings, pairwise A/B preference evaluation, evaluator sessions, independent review and adjudication, deterministic rubric validation/scoring, JSON import/export, a CLI, and an optional localhost-only browser workbench.

## Why this exists

AI evaluation often fails in two opposite ways: free-form notes are difficult to compare, while over-automated scoring can hide the human judgment the task actually depends on. TurkishEvalKit keeps the evaluator in control and standardizes the surrounding workflow.

The project deliberately separates:

- **judgment** — authored by a human evaluator;
- **rubric structure** — explicit, typed, and versioned;
- **validation** — deterministic checks for task type, completeness, duplicates, and unknown criteria;
- **aggregation** — reproducible scalar or pairwise score calculation;
- **evidence** — criterion notes, evaluator notes, English justification, source metadata, and exports;
- **workflow** — evaluator session, review, escalation, and adjudication events that never rewrite the original evaluation;
- **interfaces** — CLI and local workbench are adapters over the same core.

## Current capabilities

- Turkish text-quality rubric covering fluency, instruction following, factuality, helpfulness, and locale fit.
- Turkish audio-quality rubric covering nativeness, pronunciation, fluency, intonation, and synthesis/audio artifacts.
- Turkish pairwise A/B rubric with criterion-level **A / Tie / B** judgments.
- Separate pairwise **overall preference** and **preference strength (1–3)** fields.
- Deterministic pairwise criterion aggregate from `-100` (all B) through `0` (balanced) to `+100` (all A).
- Rubrics explicitly bound to their evaluation type; cross-type mismatches are rejected by the core.
- Strict 1–5 criterion ratings for scalar text/audio tasks with complete-rubric validation.
- Versioned rubric identifiers stored with every evaluation record.
- Evaluator sessions with explicit local evaluator/session identifiers.
- Typed lifecycle: `draft → submitted → reviewed`, with escalated reviews optionally continuing to `adjudicated`.
- Independent-role enforcement: a reviewer cannot review their own evaluation; an adjudicator cannot be the evaluator or reviewer.
- Append-only workflow event history with actor, role, timestamp, transition, outcome, and notes.
- Immutable scored evaluation artifacts plus separate workflow sidecars, so review decisions cannot silently alter original evidence.
- UTF-8 JSON input/output with Turkish text preserved.
- Human evaluator notes plus optional English justification.
- CLI workflows for listing rubrics and scoring validated records.
- Optional browser workbench bound to `127.0.0.1` only.
- Append-only local evaluation history with JSON export.
- No CDN or external service requirement for the workbench UI.
- Example text, audio, and pairwise evaluation records.
- Python 3.11–3.13 CI with Ruff, strict mypy, pytest, coverage, CLI smoke, real HTTP, and Chromium browser tests.

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

The workflow records resolution; it does **not** rewrite ratings, pairwise preferences, source content, or evaluator notes. See [`docs/REVIEW_WORKFLOW.md`](docs/REVIEW_WORKFLOW.md).

## Non-goals

TurkishEvalKit does **not** currently:

- automatically decide whether an answer, voice sample, or candidate response is good;
- send evaluation content to an external AI service;
- claim that aggregate scores are objective ground truth;
- copy referenced private audio into evaluation history;
- edit a submitted evaluation in place after review;
- provide an edit/request-changes/resubmit revision loop yet;
- claim multi-evaluator consensus merely because one review or adjudication exists.

These boundaries are intentional. Revision semantics require an explicit superseding-artifact model rather than mutating historical evidence.

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

Evaluate the pairwise A/B example:

```bash
turkisheval evaluate examples/pairwise-evaluation.json
```

Emit the complete scored result as JSON:

```bash
turkisheval evaluate examples/pairwise-evaluation.json --json
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

The workbench exposes **Text**, **Audio**, and **Pairwise** modes plus evaluator-session and review/adjudication controls. See [`docs/WORKBENCH.md`](docs/WORKBENCH.md) for storage, privacy, and interaction details.

## Evaluation records

Scalar text/audio records contain the task identity, evaluation type, exact rubric version, source material/metadata, one 1–5 rating per rubric criterion, and human-authored notes.

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

A real record must include **every** criterion required by its rubric exactly once. See [`examples/text-evaluation.json`](examples/text-evaluation.json), [`examples/audio-evaluation.json`](examples/audio-evaluation.json), and [`examples/pairwise-evaluation.json`](examples/pairwise-evaluation.json) for complete records.

## Scoring model

### Scalar text/audio

Criterion scores are bounded to `1..5`. For a rubric with weights `wᵢ` and human ratings `rᵢ`:

```text
weighted_score = Σ(rᵢ × wᵢ) / Σ(wᵢ)
normalized_score = (weighted_score - 1) / 4 × 100
```

The normalized score maps `1 → 0` and `5 → 100` without changing the underlying human ratings.

### Pairwise A/B

Each criterion preference maps to a direction value:

```text
A = +1
Tie = 0
B = -1

preference_score = Σ(directionᵢ × wᵢ) / Σ(wᵢ) × 100
```

Therefore `+100` means every weighted criterion favors A, `-100` means every weighted criterion favors B, and `0` means the criterion aggregate is balanced. This score does **not** replace `overall_preference` or `preference_strength`; those are retained as separate human judgments because a holistic decision is not necessarily identical to a criterion vote count.

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

Audio evaluation records can point to local assets through source metadata. The workbench stores the reference and transcript/context fields but does not copy the referenced audio file into history. This repository intentionally ships no voice recordings.

Evaluators should only process media and prompts they are authorized to access and should follow the applicable data-retention and privacy rules of the organization running the evaluation.

## Architecture

```text
source / candidates / audio reference
              ↓
       human evaluation
              ↓
 typed scalar or pairwise record
              ↓
 validation + deterministic scoring
              ↓
 immutable evaluation artifact
              │
              └── workflow sidecar
                    draft → submitted → reviewed → adjudicated*

* adjudication exists only after an escalated review
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for design constraints and extension rules.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest --cov=turkishevalkit --cov-report=term-missing
```

CI runs the quality suite on Python 3.11, 3.12, and 3.13, executes all example evaluation files through the installed CLI, exercises the live localhost API including review/adjudication transitions, and runs desktop/mobile Chromium workflows.

## Roadmap

Near-term work remains ordered around evaluator correctness rather than surface area:

1. add timestamped audio issue annotations without embedding private media;
2. add multi-evaluator agreement and calibration tooling;
3. design explicit superseding/revision semantics for request-changes/resubmit workflows;
4. add queue/filtering tools for larger local review sets;
5. publish stable evaluation and workflow schema documentation plus migration rules before a `1.0` interchange format.

## Contributing

Small, test-backed changes are welcome. New evaluation dimensions should include a clear definition, scoring guidance, examples, and tests rather than only adding another label. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security and responsible use

Please do not include confidential evaluation data, customer prompts, private audio, credentials, or proprietary datasets in issues or pull requests. See [`SECURITY.md`](SECURITY.md).

## License

MIT. See [`LICENSE`](LICENSE).
