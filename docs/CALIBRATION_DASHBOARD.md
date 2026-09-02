# Calibration dashboard and history

The local workbench includes a dedicated `/calibration` workspace for comparing independent human evaluations that already exist in TurkishEvalKit's local history.

The dashboard is an interface over the same calibration engine exposed by the Python API and `turkisheval calibrate`. It does not introduce a second scoring model and it does not alter source evaluations.

## Data flow

```text
saved evaluation A ─┐
saved evaluation B ─┼─ compatibility check ─ calibration engine ─ report artifact
saved evaluation C ─┘                                      │
                                                           └─ dashboard/history
```

A dashboard calibration uses real evaluation artifacts from:

```text
<workspace>/evaluations/
```

Evaluator identity is read from the matching workflow sidecar in:

```text
<workspace>/workflows/
```

The resulting calibration is stored separately in:

```text
<workspace>/calibrations/
```

The original evaluation files and workflow sidecars are not rewritten while a calibration is generated or viewed.

## Compatibility requirements

The dashboard groups saved evaluations by a deterministic compatibility identity. A calibration batch must contain at least two submissions with:

- unique, non-empty evaluator IDs;
- the same task ID;
- the same evaluation type;
- the same rubric ID and rubric version;
- the same source stimulus.

Each source record is validated again by the existing scalar or pairwise evaluation engine before agreement metrics are calculated.

An evaluation without a valid workflow evaluator identity remains visible in the candidate list but is marked as unavailable for calibration. This avoids inventing attribution after the original judgment was recorded.

## Dashboard views

The report view exposes:

- evaluator count;
- exact criterion agreement;
- within-one rating agreement for scalar tasks;
- overall-preference agreement for pairwise tasks;
- aggregate score per evaluator and score spread;
- per-criterion observation counts;
- mean rating differences where applicable;
- audio annotation F1, severity agreement, and temporal similarity when timestamped audio evidence exists;
- pair-level audio agreement details.

The interface deliberately displays the underlying observations instead of collapsing disagreement into an evaluator leaderboard.

## Calibration history artifact

A dashboard-generated report uses this envelope:

```json
{
  "schema_version": "1.0",
  "created_at": "2026-09-02T00:00:00+00:00",
  "source_artifacts": [
    {
      "filename": "task-...json",
      "evaluator_id": "evaluator-a"
    },
    {
      "filename": "task-...json",
      "evaluator_id": "evaluator-b"
    }
  ],
  "report": {
    "task_id": "...",
    "evaluator_count": 2
  }
}
```

The full `report` object is the same JSON-friendly calibration report produced by the core calibration module. `source_artifacts` records which immutable local evaluation files participated in that report.

History is append-only. Reopening a report reads the saved calibration artifact; it does not recompute it against possibly different future records.

## HTTP surface

The localhost workbench exposes:

| Route | Purpose |
| --- | --- |
| `GET /calibration` | Dashboard page |
| `GET /api/calibrations/candidates` | Saved evaluation candidates and compatibility metadata |
| `GET /api/calibrations` | Calibration history summaries |
| `POST /api/calibrations` | Validate selected artifacts, calculate agreement, and save a report |
| `GET /api/calibrations/<file>/details` | Read one saved calibration artifact |
| `GET /api/calibrations/<file>/download` | Export one saved calibration artifact as JSON |

These routes are available only through the same Flask process as the workbench. `turkisheval workbench` continues to bind to `127.0.0.1` by default.

## Audio tolerance

Timestamped audio annotation matching defaults to `250 ms`. The dashboard allows an explicit tolerance from `0` to `5000 ms` when generating a report.

The tolerance affects annotation matching only. It does not alter the evaluator's 1–5 criterion ratings or normalized score.

## Privacy and trust boundary

The dashboard:

- performs no external LLM calls;
- has no telemetry;
- does not upload prompts, responses, evaluator IDs, audio references, or calibration reports;
- does not copy referenced audio media into calibration history;
- treats evaluator IDs as local workflow identifiers rather than verified real-world identities.

Organizations using the tool remain responsible for their own authorization, retention, and access-control requirements around evaluation data.

## Non-goals

The dashboard does not:

- decide which evaluator is correct;
- automatically pass, fail, rank, or remove evaluators;
- define a universal acceptable agreement threshold;
- adjudicate disagreements;
- mutate ratings or workflow outcomes;
- claim that a small calibration batch establishes population reliability;
- calculate Cohen/Fleiss kappa, Krippendorff's alpha, or ICC yet.

Review/adjudication and calibration remain separate concepts: review records a human workflow decision about an evaluation, while calibration exposes agreement patterns across independent evaluations.
