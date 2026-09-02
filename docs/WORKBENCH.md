# Local Workbench

The TurkishEvalKit workbench is a local browser interface over the same typed models, validation rules, and scoring engine used by the CLI.

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

## Workflow

1. Choose **Text** or **Audio**.
2. Provide a task id and source/context fields.
3. Rate every criterion from 1 through 5.
4. Add criterion notes and evaluator evidence.
5. Submit the record.
6. The local API reconstructs the typed `EvaluationRecord`.
7. The core validates task type, rubric id/version, completeness, and rating bounds.
8. The deterministic scorer computes the aggregate.
9. The scored JSON result is written to local history.
10. The result can be exported directly from the history list.

The browser does not calculate the authoritative score.

## Storage

Each successful submission becomes a separate JSON file:

```text
<workspace>/
└── evaluations/
    ├── text-demo-001-20260902T021500123456Z.json
    └── audio-demo-001-20260902T021700654321Z.json
```

Files are append-only by naming convention. Re-evaluating the same task produces another timestamped file instead of overwriting an earlier judgment.

## Privacy

The workbench is designed for local evaluator workflows:

- the server listens on loopback only;
- the UI has no CDN dependency;
- no evaluation is sent to a remote API by TurkishEvalKit;
- referenced audio files are not copied into history;
- only the reference/context supplied in the record is persisted.

This does not make arbitrary evaluation data safe to process. Evaluators remain responsible for authorization, retention, and organizational privacy requirements.

## Audio references

The current audio form accepts a local asset path, asset id, or other authorized reference plus optional transcript/context. It does not upload or duplicate the audio file.

Future timestamped annotation support should continue to reference media rather than assume that private media can be retained by the tool.

## Failure behavior

Invalid submissions return an error and are not written to history. Examples include:

- missing criterion scores;
- invalid score bounds;
- unknown rubric ids;
- text/audio type mismatch;
- missing required identifiers.

Validation remains authoritative in the Python core, not in browser JavaScript.
