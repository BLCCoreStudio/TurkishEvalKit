# Changelog

All notable TurkishEvalKit changes are documented here. The project follows semantic versioning from the v1.0 release onward.

## 1.0.0 — 2026-09-16

### Evaluation and evidence
- Versioned Turkish text and audio rubrics with strict completeness validation and deterministic aggregate scores.
- Pairwise A/Tie/B evaluation with explicit overall preference and strength.
- Timestamped audio evidence with category, severity and human-authored notes.
- JSON, JSONL and CLI interfaces over the same typed domain model.

### Review and revision workflows
- Local evaluator sessions and independent review, request-changes, escalation and adjudication flows.
- Immutable evaluation artifacts, append-only workflow events and explicit revision lineage.
- Action-oriented review queues derived from trusted history instead of a second mutable state store.

### Calibration and reliability
- Multi-evaluator calibration for scalar, pairwise and timestamped-audio evaluations.
- Evidence-level disagreement exploration without turning agreement metrics into evaluator rankings.
- Repeated-task reliability analysis with applicability-aware Krippendorff alpha, Fleiss kappa and ICC(A,1).
- Local reliability workspace backed by the same core calculations used by the CLI.

### Data portability and local operation
- Versioned evaluation-dataset interchange with JSON/JSONL conversion, dry-run import and exact-content deduplication.
- Optional rebuildable SQLite metadata index; canonical JSON artifacts remain the source of truth.
- Localhost workbench, review queue, calibration dashboard and reliability workspace.
- No required external AI service, telemetry, account or paid backend.

### Quality and governance
- Python 3.11, 3.12 and 3.13 CI coverage.
- Ruff, strict mypy and pytest coverage gate of at least 90%.
- Wheel package-data smoke tests, CLI smoke tests, real localhost HTTP flows and Chromium browser E2E coverage.
- CodeQL, maintainer ownership, security/support policies and structured contribution templates.

### v1 trust boundary
TurkishEvalKit standardizes human evaluation evidence and workflow mechanics. It does not claim that an evaluator is automatically correct, does not infer correctness from agreement alone, and does not silently import external workflow state as trusted local history.

## 0.13.0 — 2026-09-03
- Added the localhost Reliability Workspace and shared reliability navigation.

## 0.12.0 — 2026-09-03
- Added the optional rebuildable SQLite metadata index with canonical fallback.

## 0.11.0 — 2026-09-03
- Added versioned evaluation-dataset interchange and workspace import/export.

## 0.10.0 and earlier
- Established repeated-task reliability, disagreement exploration, review queues, revision lineage, calibration, timestamped audio QA, pairwise evaluation and the localhost workbench.
