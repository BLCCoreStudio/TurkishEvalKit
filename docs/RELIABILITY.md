# Population reliability

TurkishEvalKit population reliability is a repeated-task analysis layer. It answers a different question from single-task calibration:

- **calibration** asks how evaluators agreed or disagreed on one shared stimulus;
- **population reliability** asks how consistently a rating process behaves across multiple independently rated task units.

The feature is intentionally conservative. A coefficient is calculated only when its design assumptions are satisfied. Otherwise the report returns an explicit `applicable: false` estimate with a reason.

## Input model

A reliability specification contains:

```json
{
  "minimum_task_count": 3,
  "tasks": [
    {"submissions": ["two or more evaluator submissions for task A"]},
    {"submissions": ["two or more evaluator submissions for task B"]},
    {"submissions": ["two or more evaluator submissions for task C"]}
  ]
}
```

Each task uses the same submission shape as calibration. Within one task, TurkishEvalKit requires:

- at least two evaluator submissions;
- unique evaluator IDs;
- the same `task_id`;
- the same evaluation type;
- the same rubric ID/version;
- the same source stimulus;
- individually valid evaluation records.

Across the population dataset, task IDs must be unique and every task must use the same evaluation type and rubric ID/version. Different tasks are expected to have different source stimuli.

`minimum_task_count` is mandatory and must be at least `3`. The dataset must contain at least that many tasks.

This declared minimum is an **inclusion guardrail**, not a universal statistical sample-size claim. A team that needs a stronger minimum should declare a stronger value in the input specification.

## Metrics

### Krippendorff's alpha

TurkishEvalKit uses the general disagreement form:

```text
alpha = 1 - observed_disagreement / expected_disagreement
```

The observed disagreement is computed within each task and weighted by the number of pairable ratings in that task. Expected disagreement is derived from the pooled observed category marginals.

This allows alpha to remain applicable when evaluator counts or evaluator identities vary by task, provided each included task still has at least two ratings.

#### Scalar 1–5 ratings

Scalar criteria use **ordinal** alpha. TurkishEvalKit does not silently treat the 1–5 scale as equally spaced interval data for alpha. Ordinal distance is derived from pooled category frequencies and category order.

#### Pairwise A / Tie / B

Pairwise criterion preferences and the holistic overall preference use **nominal** alpha. `A`, `Tie`, and `B` are categories, not numeric distances.

Pairwise preference strength (`1..3`) uses ordinal alpha.

If the pooled data contain only one observed category, expected disagreement is zero. TurkishEvalKit reports alpha as not applicable instead of manufacturing `1.0` or another value.

## Fleiss' kappa

Fleiss' kappa is reported for pairwise nominal judgments only when every task has the same number of ratings.

Assumptions recorded in every estimate:

- categories are nominal;
- every task has the same number of ratings;
- evaluator identities may vary by task;
- chance agreement is estimated from pooled category marginals.

For scalar 1–5 criteria, TurkishEvalKit does **not** calculate Fleiss' kappa by default because doing so would silently discard the scale's ordinal structure.

If the rater count varies by task, the Fleiss estimate is returned as not applicable. Krippendorff alpha may still be applicable for the same dataset.

## ICC(A,1)

For scalar evaluations, TurkishEvalKit reports the two-way random-effects, absolute-agreement, single-measure intraclass correlation coefficient commonly denoted **ICC(A,1)**.

It is calculated for:

- every scalar rubric criterion;
- the normalized aggregate scalar score.

ICC(A,1) is only applicable when the **same evaluator identities** rate every included task. Equal rater counts alone are not enough.

The implementation uses the two-way ANOVA decomposition:

```text
ICC(A,1) = (MS_task - MS_error)
           / (MS_task
              + (k - 1) * MS_error
              + k * (MS_evaluator - MS_error) / n)
```

where:

- `n` is the number of tasks;
- `k` is the number of evaluators;
- `MS_task` is the between-task mean square;
- `MS_evaluator` is the between-evaluator mean square;
- `MS_error` is the residual mean square.

Negative ICC values are preserved. They are not clipped to zero because doing so would hide disagreement or model mismatch.

Pairwise signed preference scores do not receive ICC(A,1). They are derived from categorical A/Tie/B judgments and are not silently promoted to an interval measurement scale.

## Applicability is part of the result

Every coefficient is represented as a `ReliabilityEstimate`:

```json
{
  "metric": "icc_a1_absolute_agreement",
  "value": null,
  "applicable": false,
  "reason": "ICC(A,1) requires the same evaluator identities on every task",
  "assumptions": ["..."]
}
```

Consumers should check `applicable` before using `value`.

A not-applicable metric is not a failed evaluation. It means the dataset design does not support that coefficient under TurkishEvalKit's documented assumptions.

## CLI

Run the self-authored example:

```bash
turkisheval reliability examples/reliability-text.json
```

Print the complete report:

```bash
turkisheval reliability examples/reliability-text.json --json
```

Write an auditable JSON report:

```bash
turkisheval reliability examples/reliability-text.json --output reliability-report.json
```

## Reliability workspace

`0.13.x` adds a localhost browser workspace at:

```text
/reliability
```

It is an adapter over the same `reliability.py` core used by the CLI. There is no second browser statistics implementation.

The workspace derives candidate task units from canonical local artifacts:

1. saved evaluation JSON is parsed back into the normal typed record model;
2. evaluator identity is accepted only from a valid matching workflow sidecar;
3. records are grouped by task ID, evaluation type, rubric ID/version, and exact source stimulus;
4. groups with missing attribution, duplicate evaluator IDs, or fewer than two usable evaluations are marked unavailable;
5. selecting the first task group locks the browser selection to the same evaluation type and rubric version;
6. the server reloads every submitted filename from canonical storage before analysis rather than trusting browser-provided grouping metadata;
7. the resulting `PopulationReliabilitySpec` is passed directly to `build_population_reliability_report()`.

The analysis endpoint is:

```text
POST /api/reliability/analyze
```

and candidate discovery is:

```text
GET /api/reliability/candidates
```

The browser shows dataset-design properties, criterion-level estimates, population-level estimates, explicit not-applicable reasons, and each metric's recorded assumptions.

### Workspace trust boundary

The browser never establishes evaluator identity on its own. A filename without a valid local workflow attribution cannot become a trusted evaluator submission merely because the client labels it that way.

The server also rejects:

- duplicate filenames within one task group;
- the same evaluation artifact reused across multiple task units;
- duplicate evaluator IDs inside one task unit;
- missing or path-traversal artifact references;
- task selections below the declared `minimum_task_count`;
- datasets rejected by the normal reliability core.

Candidate compatibility keys and dataset keys are UI grouping aids only. They are not accepted as proof of compatibility by the analysis endpoint.

### Persistence behavior

Reliability Workspace reports are **ephemeral by default**. Running an analysis does not create a `reliability/` directory, workflow sidecar, revision record, queue state, evaluator leaderboard, or hidden database.

The browser can export the returned report as an explicit JSON file. That export is equivalent in semantics to the library/CLI report and remains outside authoritative workspace state unless the user chooses to store it elsewhere.

## Interpretation boundary

TurkishEvalKit deliberately does not:

- declare a universal "good" alpha, kappa, or ICC threshold;
- convert reliability coefficients into evaluator pass/fail decisions;
- rank evaluators from population reliability;
- infer which evaluator is correct;
- claim population validity from the declared minimum task count alone;
- hide negative coefficients;
- impute missing evaluator identities to make ICC applicable;
- treat scalar ordinal ratings as nominal just to obtain Fleiss' kappa;
- treat pairwise categorical preference scores as interval measurements for ICC.

Reliability measures agreement/consistency properties of a rating process. It is not ground truth and it is not an evaluator leaderboard.

## Relationship to other artifacts

The core reliability API consumes evaluation submissions directly. It does not mutate evaluation, workflow, revision, calibration, queue, disagreement, interchange, or metadata-index artifacts.

The `0.13.x` browser workspace preserves the same boundary. It reads canonical evaluation/workflow artifacts, builds an in-memory reliability specification, invokes the existing core, and returns the report without persisting a new authoritative artifact class.

## Method references

The implemented method names follow the established formulations associated with:

- Klaus Krippendorff — alpha reliability based on observed versus expected disagreement;
- Joseph L. Fleiss — fixed-marginal multi-rater kappa for nominal categories;
- McGraw & Wong — intraclass correlation forms including two-way absolute-agreement single-measure ICC.

TurkishEvalKit documents its exact applicability rules and formulas above so users do not need to infer which variant was selected.
