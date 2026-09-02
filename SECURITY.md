# Security Policy

## Reporting a vulnerability

Please report security-sensitive issues privately through GitHub's security reporting features when available rather than opening a public issue with exploit details or sensitive data.

A useful report includes the affected version or commit, reproduction steps, expected impact, and any relevant environment details. Do not include real customer prompts, private audio, credentials, or unrelated personal data.

## Scope

Security concerns may include:

- unsafe file handling;
- path traversal or unintended overwrite behavior;
- parsing behavior that can corrupt or misrepresent evaluation records;
- dependency or CI supply-chain issues;
- accidental leakage of evaluation source data;
- unintended network exposure of the local workbench;
- a feature that mislabels machine-generated judgment as human-authored evaluation.

## Data handling

The core is local-first and has no runtime network dependency. JSON records may contain sensitive source material because callers control the `source` and `metadata` fields. Treat exported records according to the sensitivity of the underlying evaluation task.

Audio/media files are ignored by repository defaults and are not required for scoring. The workbench stores audio references/context but does not copy referenced media into evaluation history. TurkishEvalKit does not grant permission to collect, retain, or redistribute any referenced media.

## Local workbench

The optional browser workbench is intentionally bound to `127.0.0.1`. The CLI does not expose a bind-address option.

Do not treat the built-in server as a production or multi-user service. Do not expose it through port forwarding, a reverse proxy, a tunnel, or a shared host without adding appropriate authentication, authorization, transport security, request limits, and a separate security review.

Saved evaluation files are ordinary local JSON files. TurkishEvalKit does not encrypt them or manage operating-system permissions beyond normal file creation behavior.

## Security boundaries

TurkishEvalKit validates record structure, rubric identity, evaluation type, and scoring consistency. It does not authenticate evaluators, encrypt local files, provide access control, sanitize arbitrary source content for use by other applications, or guarantee that source content is safe to display.

Applications embedding the library are responsible for those controls.
