# Multi-evaluator calibration

TurkishEvalKit calibration compares **independent human judgments of the same evaluation stimulus**. It is designed to expose disagreement and help teams inspect rubric interpretation. It does not decide whether an evaluator is qualified, automatically overwrite an evaluation, or turn observed agreement into a pass/fail employment decision.

## Input boundary

A calibration spec contains two or more evaluator submissions:

```json
{
  "submissions": [
    {
      "evaluator_id": "evaluator-a",
      "evaluation": {
        "task_id": "text-calibration-001",
        "evaluation_type": "text",
        "rubric_id": "tr-text-quality",
        "rubric_version": "1.0",
        "source": {},
        "ratings": []
      }
    },
    {
      "evaluator_id": "evaluator-b",
      "evaluation": {
        "task_id": "text-calibration-001",
        "evaluation_type": "text",
        "rubric_id": "tr-text-quality",
        "rubric_version": "1.0",
        "source": {},
        "ratings": []
      }
    }
  ]
}
```

Before any agreement metric is calculated, the core requires:

- at least two submissions;
- unique, non-empty evaluator ids;
- the same `task_id`;
- the same evaluation type;
- the same rubric id and rubric version;
- the same source stimulus;
- individually valid evaluation records under the selected rubric.

Metadata may differ because evaluator-specific metadata is not the stimulus itself.

## CLI

Text calibration:

```bash
turkisheval calibrate examples/calibration-text.json
```

Complete JSON report:

```bash
turkisheval calibrate examples/calibration-text.json --json
```

Write an artifact:

```bash
turkisheval calibrate examples/calibration-audio.json --output calibration.json
```

Change the audio timestamp matching tolerance:

```bash
turkisheval calibrate examples/calibration-audio.json --annotation-tolerance-ms 150
```

The default audio tolerance is `250 ms`.

## Scalar text and audio agreement

For every rubric criterion, TurkishEvalKit compares every unique evaluator pair.

The report includes:

- **exact criterion agreement** — fraction of pairwise criterion comparisons with identical 1–5 ratings;
- **within-one agreement** — fraction with an absolute rating difference of at most one point;
- **mean absolute rating difference** — average absolute difference across evaluator pairs and criteria;
- **maximum rating difference** — largest observed 1–5 disagreement;
- **per-criterion observations** — counts of each rating value;
- **per-criterion exact agreement** and mean absolute difference;
- **aggregate normalized score per evaluator**;
- **aggregate score spread** — highest normalized score minus lowest normalized score.

The normalized score spread is diagnostic. It does not replace the original criterion evidence and it is not a statistical confidence interval.

## Pairwise A/B agreement

For pairwise evaluations, criterion labels are categorical (`A`, `Tie`, `B`), so scalar distance metrics are not applied.

The report includes:

- exact criterion preference agreement;
- per-criterion A/Tie/B observation counts;
- overall preference agreement across evaluator pairs;
- mean and maximum absolute difference in preference strength (`1..3`);
- signed criterion-preference score for each evaluator;
- spread between the highest and lowest signed preference score.

The signed score remains an aggregation aid. Agreement on that score is not a substitute for agreement on the underlying criterion judgments.

## Timestamped audio annotation agreement

Audio calibration also compares localized issue annotations. An annotation can be a point marker or a time range and has a human-selected category, severity, and evidence note.

Annotations are eligible to match only when their issue categories are identical. Temporal matching then uses the configured tolerance:

- **point ↔ point** — timestamps must be within the tolerance;
- **point ↔ range** — the point may fall inside the range or within the tolerance of its nearest boundary;
- **range ↔ range** — overlapping ranges use intersection-over-union as temporal similarity; nearby non-overlapping ranges may still match when their gap is within tolerance.

Eligible candidates are matched one-to-one in descending temporal-similarity order. The report then exposes:

- annotation count for each evaluator in every evaluator pair;
- number of matched annotations;
- pairwise annotation F1: `2 × matches / (count_a + count_b)`;
- exact severity agreement among matched annotations;
- mean temporal similarity among matched annotations;
- mean pairwise annotation F1 across all evaluator pairs.

If both evaluators produced zero annotations, that pair receives annotation F1 `1.0`: both independently reported no localized issue evidence. If only one evaluator produced annotations, the pair receives F1 `0.0`.

## What the report does not claim

The current calibration layer deliberately does **not**:

- declare a universal acceptable agreement threshold;
- automatically pass, fail, rank, or remove evaluators;
- compute Cohen's kappa, Fleiss' kappa, Krippendorff's alpha, ICC, or other population-level reliability statistics;
- infer which evaluator is correct when ratings differ;
- resolve disagreements through an LLM or heuristic;
- merge or mutate the underlying immutable evaluation artifacts;
- infer audio issue categories or severity;
- treat annotation counts as score penalties.

Those boundaries matter because a small calibration batch can produce misleading reliability statistics, and acceptable disagreement depends on rubric semantics, task difficulty, evaluator training, and the operational decision being supported.

## Recommended workflow

A practical calibration loop is:

1. assign the same hidden stimulus to two or more evaluators;
2. collect independent evaluations before discussion;
3. generate the calibration report;
4. inspect the criteria with the lowest agreement or largest rating spread;
5. inspect unmatched or differently severe audio annotations;
6. discuss rubric interpretation and evidence;
7. revise guidance only when the rubric itself is genuinely ambiguous;
8. run a new calibration set rather than rewriting the earlier evidence.

This keeps calibration focused on improving shared judgment standards while preserving the original audit trail.
