# Local Workbench

The TurkishEvalKit workbench is a local browser interface over the same typed models, validation rules, and scoring engines used by the CLI.

## Install

```bash
python -m pip install -e ".[workbench]"
```

The workbench dependency is optional so the core package can remain dependency-free for CLI and library use.

## Start

```bash
turkisheval workbench
```

Default behavior:

- binds to `127.0.0.1`;
- uses port `8765`;
- opens the default browser;
- stores results in the platform-specific TurkishEvalKit data directory.

Useful options:

```bash
turkisheval workbench --workspace ./eval-data
turkisheval workbench --port 9876
turkisheval workbench --no-browser
```

The current CLI deliberately does not expose a network bind-address option.

## Evaluation modes

The workbench exposes three task families.

### Text

Provide a prompt/instruction and one model response, then rate every rubric criterion from `1` through `5`.

### Audio

Provide an authorized audio reference plus optional transcript/context, then rate every audio rubric criterion from `1` through `5`. TurkishEvalKit stores the reference rather than copying the audio asset into history.

### Pairwise

Provide one prompt and two candidate responses, **A** and **B**. For every criterion choose:

- **A** — candidate A is better for this criterion;
- **Tie** — neither candidate is meaningfully preferable for this criterion;
- **B** — candidate B is better for this criterion.

Then record a separate **overall preference** (`A`, `Tie`, or `B`) and **preference strength** (`1` slight, `2` moderate, `3` strong). The overall decision is intentionally stored separately from the criterion aggregate.

## Workflow

1. Choose **Text**, **Audio**, or **Pairwise**.
2. Provide a task id and source/context fields.
3. Complete every required scalar rating or pairwise criterion preference.
4. For pairwise tasks, also choose the overall preference and strength.
5. Add criterion notes and evaluator evidence.
6. Submit the record.
7. The local API reconstructs the appropriate typed record.
8. The core validates task type, rubric id/version, completeness, duplicates, and value bounds.
9. The deterministic scalar or pairwise scorer computes the aggregate.
10. The scored JSON result is written to local history and can be exported directly.

The browser does not calculate the authoritative score.

## Pairwise result semantics

Pairwise criterion preferences are converted to directional values:

```text
A = +1
Tie = 0
B = -1
```

After rubric weights are applied, the aggregate is normalized to `-100..+100`:

- `+100`: all weighted criterion evidence favors A;
- `0`: criterion evidence is balanced;
- `-100`: all weighted criterion evidence favors B.

This is a **criterion preference direction**, not an objective quality score. `overall_preference` and `preference_strength` remain distinct fields in the saved result.

## Storage

Each successful submission becomes a separate JSON file:

```text
<workspace>/
└── evaluations/
    ├── text-demo-001-20260902T021500123456Z.json
    ├── audio-demo-001-20260902T021700654321Z.json
    └── pairwise-demo-001-20260902T021900777777Z.json
```

Files are append-only by naming convention. Re-evaluating the same task produces another timestamped file instead of overwriting an earlier judgment.

Scalar history entries expose their normalized `/100` score. Pairwise history entries expose the overall decision plus the signed A↔B criterion preference score so the two scoring concepts are not visually conflated.

## Privacy

The workbench is designed for local evaluator workflows:

- the server listens on loopback only;
- the UI has no CDN dependency;
- no evaluation is sent to a remote API by TurkishEvalKit;
- referenced audio files are not copied into history;
- only the source/context supplied in the record is persisted.

This does not make arbitrary evaluation data safe to process. Evaluators remain responsible for authorization, retention, and organizational privacy requirements. Pairwise prompts and both candidate responses are stored in the exported evaluation artifact, so confidential candidate content should only be used in an appropriately protected workspace.

## Audio references

The current audio form accepts a local asset path, asset id, or other authorized reference plus optional transcript/context. It does not upload or duplicate the audio file.

Future timestamped annotation support should continue to reference media rather than assume that private media can be retained by the tool.

## Failure behavior

Invalid submissions return an error and are not written to history. Examples include:

- missing scalar criterion scores;
- invalid scalar score bounds;
- missing pairwise criterion preferences;
- missing pairwise overall preference or strength;
- duplicate or unknown criterion ids;
- unknown rubric ids;
- cross-type rubric/task mismatch;
- missing required identifiers.

Validation remains authoritative in the Python core, not in browser JavaScript.
