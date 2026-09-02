# TurkishEvalKit

[![CI](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml/badge.svg)](https://github.com/BLCCoreStudio/TurkishEvalKit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Human-in-the-loop evaluation workbench for Turkish AI text and audio quality.**

TurkishEvalKit provides a small, auditable core for recording human judgments against versioned Turkish-language evaluation rubrics. It is designed for evaluators, QA workflows, research prototypes, and teams that need structured evidence without pretending that a heuristic or model can replace native-language judgment.

> **Status:** early alpha. The current core supports Turkish text and audio-quality evaluations, deterministic rubric validation/scoring, JSON import/export, and a CLI. A richer local workbench UI and pairwise comparison flow are planned only after the underlying data model is stable.

## Why this exists

AI evaluation often fails in two opposite ways: free-form notes are hard to compare, while over-automated scoring can hide the human judgment the task actually depends on. TurkishEvalKit keeps the human evaluator in control and standardizes the surrounding workflow.

The project deliberately separates:

- **judgment** — authored by a human evaluator;
- **rubric structure** — explicit and versioned;
- **validation** — deterministic checks for missing, duplicate, or unknown ratings;
- **aggregation** — reproducible score calculation;
- **evidence** — notes, English justification, source metadata, and exported results.

## Current capabilities

- Turkish text-quality rubric covering fluency, instruction following, factuality, helpfulness, and locale fit.
- Turkish audio-quality rubric covering nativeness, pronunciation, fluency, intonation, and synthesis/audio artifacts.
- Strict 1–5 criterion ratings with complete-rubric validation.
- Versioned rubric identifiers stored with every evaluation record.
- Deterministic weighted and normalized scoring.
- UTF-8 JSON input/output with Turkish text preserved.
- Human evaluator notes plus optional English justification.
- CLI workflows for listing rubrics and scoring validated records.
- Example text/audio evaluation records.
- Python 3.11–3.13 CI with Ruff, mypy, pytest, coverage, and CLI smoke tests.

## Non-goals

TurkishEvalKit does **not** currently:

- automatically decide whether an answer or voice sample is good;
- send evaluation content to an external AI service;
- claim that aggregate scores are objective ground truth;
- store private audio files in this repository;
- provide pairwise A/B evaluation before that workflow has a complete typed model and tests.

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

List the built-in rubrics:

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

Audio evaluation records can point to local assets through source metadata, but media files are ignored by default. This repository intentionally ships no voice recordings. Evaluators should only process media they are authorized to access and should follow the applicable data-retention and privacy rules of the organization running the evaluation.

## Architecture

The current codebase keeps the core independent from any future UI:

```text
JSON record
    ↓
serialization
    ↓
typed domain model
    ↓
rubric validation ── versioned built-in rubrics
    ↓
deterministic scoring
    ↓
CLI / JSON result
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for design constraints and extension rules.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest --cov=turkishevalkit --cov-report=term-missing
```

CI runs the quality suite on Python 3.11, 3.12, and 3.13 and also executes both example workflows through the installed CLI.

## Roadmap

Near-term work is intentionally ordered around correctness before UI surface area:

1. stabilize the record and rubric schemas;
2. add a typed pairwise A/B decision model with tie/insufficient-evidence handling;
3. add evaluator-session history and append-only local storage;
4. build a local text/audio workbench UI on top of the same core;
5. add timestamped audio issue annotations without embedding private media;
6. add agreement/review tooling for multi-evaluator workflows;
7. publish schema documentation and migration rules before a stable `1.0` format.

## Contributing

Small, test-backed changes are welcome. New evaluation dimensions should include a clear definition, scoring guidance, examples, and tests rather than only adding another label. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security and responsible use

Please do not include confidential evaluation data, customer prompts, private audio, credentials, or proprietary datasets in issues or pull requests. See [`SECURITY.md`](SECURITY.md).

## License

MIT. See [`LICENSE`](LICENSE).
