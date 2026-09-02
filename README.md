# TurkishEvalKit

[![CI](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml/badge.svg)](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Human-in-the-loop evaluation toolkit and local workbench for Turkish AI text and audio quality.**

TurkishEvalKit records native-language human judgments against explicit, versioned rubrics and turns them into auditable evaluation artifacts. The project is designed for evaluator workflows, QA, research prototypes, and teams that need structured evidence without pretending that an automated heuristic can replace human judgment.

> **Status:** alpha. The current release line supports Turkish text and audio-quality evaluations, deterministic rubric validation/scoring, JSON import/export, a CLI, and an optional localhost-only browser workbench with append-only local history.

## Why this exists

AI evaluation often fails in two opposite ways: free-form notes are difficult to compare, while over-automated scoring can hide the human judgment the task actually depends on. TurkishEvalKit keeps the evaluator in control and standardizes the surrounding workflow.

The project deliberately separates:

- **judgment** — authored by a human evaluator;
- **rubric structure** — explicit, typed, and versioned;
- **validation** — deterministic checks for task type, missing, duplicate, or unknown ratings;
- **aggregation** — reproducible score calculation;
- **evidence** — criterion notes, evaluator notes, English justification, source metadata, and exports;
- **interfaces** — CLI and local workbench are adapters over the same core.

## Current capabilities

- Turkish text-quality rubric covering fluency, instruction following, factuality, helpfulness, and locale fit.
- Turkish audio-quality rubric covering nativeness, pronunciation, fluency, intonation, and synthesis/audio artifacts.
- Rubrics explicitly bound to their evaluation type; text/audio mismatches are rejected by the core.
- Strict 1–5 criterion ratings with complete-rubric validation.
- Versioned rubric identifiers stored with every evaluation record.
- Deterministic weighted and normalized scoring.
- UTF-8 JSON input/output with Turkish text preserved.
- Human evaluator notes plus optional English justification.
- CLI workflows for listing rubrics and scoring validated records.
- Optional browser workbench bound to `127.0.0.1` only.
- Append-only local evaluation history with JSON export.
- No CDN or external service requirement for the workbench UI.
- Example text/audio evaluation records.
- Python 3.11–3.13 CI with Ruff, strict mypy, pytest, coverage, and CLI smoke tests.

## Non-goals

TurkishEvalKit does **not** currently:

- automatically decide whether an answer or voice sample is good;
- send evaluation content to an external AI service;
- claim that aggregate scores are objective ground truth;
- copy referenced private audio into evaluation history;
- provide pairwise A/B evaluation before that workflow has a dedicated typed model and tests.

These boundaries are intentional.

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

Emit the complete scored result as JSON:

```bash
turkisheval evaluate examples/text-evaluation.json --json
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

The server binds to `127.0.0.1` and opens the browser automatically. Evaluation content is processed locally. Saved results are written to a platform-appropriate local data directory in an append-only `evaluations/` history.

Use a dedicated workspace when needed:

```bash
turkisheval workbench --workspace ./my-evaluations --port 8765
```

Run without opening a browser:

```bash
turkisheval workbench --no-browser
```

See [`docs/WORKBENCH.md`](docs/WORKBENCH.md) for storage, privacy, and workflow details.

## Evaluation record

A record contains the task identity, evaluation type, exact rubric version, source material/metadata, one rating per rubric criterion, and human-authored notes.

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

A real record must include **every** criterion required by its rubric exactly once. See [`examples/text-evaluation.json`](examples/text-evaluation.json) and [`examples/audio-evaluation.json`](examples/audio-evaluation.json) for complete records.

## Scoring model

Criterion scores are bounded to `1..5`. For a rubric with weights `wᵢ` and human ratings `rᵢ`:

```text
weighted_score = Σ(rᵢ × wᵢ) / Σ(wᵢ)
normalized_score = (weighted_score - 1) / 4 × 100
```

The normalized score therefore maps `1 → 0` and `5 → 100` without changing the underlying human ratings. Aggregation is deterministic; interpretation remains a human responsibility.

## Audio and privacy

Audio evaluation records can point to local assets through source metadata. The workbench stores the reference and transcript/context fields but does not copy the referenced audio file into history. This repository intentionally ships no voice recordings.

Evaluators should only process media they are authorized to access and should follow the applicable data-retention and privacy rules of the organization running the evaluation.

## Architecture

The UI and CLI share the same core:

```text
JSON / workbench form
        ↓
serialization
        ↓
typed domain model
        ↓
type + rubric validation ── versioned built-in rubrics
        ↓
deterministic scoring
        ↓
CLI result / append-only local history / JSON export
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for design constraints and extension rules.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest --cov=turkishevalkit --cov-report=term-missing
```

CI runs the quality suite on Python 3.11, 3.12, and 3.13 and executes the example workflows through the installed CLI.

## Roadmap

Near-term work remains ordered around evaluator correctness rather than surface area:

1. harden the local workbench and history/export schema;
2. add a typed pairwise A/B decision model with tie and insufficient-evidence handling;
3. add timestamped audio issue annotations without embedding private media;
4. add evaluator-session metadata and review states;
5. add agreement/calibration tooling for multi-evaluator workflows;
6. publish stable schema documentation and migration rules before a `1.0` interchange format.

## Contributing

Small, test-backed changes are welcome. New evaluation dimensions should include a clear definition, scoring guidance, examples, and tests rather than only adding another label. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security and responsible use

Please do not include confidential evaluation data, customer prompts, private audio, credentials, or proprietary datasets in issues or pull requests. See [`SECURITY.md`](SECURITY.md).

## License

MIT. See [`LICENSE`](LICENSE).
