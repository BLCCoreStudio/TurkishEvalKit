# Contributing

Thank you for improving TurkishEvalKit. The project favors small, reviewable changes with explicit evaluation semantics over rapid feature accumulation.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the full local quality suite before opening a pull request:

```bash
ruff check .
mypy src
pytest --cov=turkishevalkit --cov-report=term-missing
```

## Pull requests

A focused pull request should explain:

- what evaluator problem it solves;
- whether it changes persisted data or rubric semantics;
- how the behavior is tested;
- any privacy, bias, or compatibility implications.

Avoid mixing large refactors with rubric changes.

## Rubric changes

Rubrics are part of the evaluation contract. Do not silently edit a published rubric version in a way that changes its meaning.

For a new criterion or changed interpretation, include:

1. a precise definition;
2. 1–5 scoring guidance;
3. at least one positive and negative example;
4. rationale for why the dimension is distinct from existing criteria;
5. tests and a new rubric version when semantics change.

## Human-in-the-loop boundary

Features that automatically generate evaluator judgments must be clearly separated from human-authored ratings and must never be presented as if a human made the decision. Any future model-assisted feature must be opt-in, provenance-labeled, and reviewable.

## Sensitive data

Do not commit or attach:

- private voice recordings;
- customer prompts or responses without permission;
- API keys or credentials;
- proprietary evaluation datasets;
- personally identifying evaluation material.

Use synthetic or explicitly redistributable examples in tests and documentation.
