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
- a feature that mislabels machine-generated judgment as human-authored evaluation.

## Data handling

The current core is local-first and has no runtime network dependency. JSON records may contain sensitive source material because callers control the `source` and `metadata` fields. Treat exported records according to the sensitivity of the underlying evaluation task.

Audio/media files are ignored by the repository defaults and are not required for scoring. TurkishEvalKit does not grant permission to collect, retain, or redistribute any referenced media.

## Security boundaries

TurkishEvalKit validates record structure and rubric consistency. It does not authenticate evaluators, encrypt local files, provide access control, or guarantee that source content is safe to display. Applications embedding the library are responsible for those controls.
