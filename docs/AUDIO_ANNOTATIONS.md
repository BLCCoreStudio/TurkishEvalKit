# Timestamped Audio Annotations

TurkishEvalKit can attach localized human QA evidence to an audio evaluation without embedding or copying the referenced media.

Annotations are evidence. They do **not** automatically change rubric ratings or the aggregate score.

## Data model

Each annotation contains:

```json
{
  "start_ms": 1850,
  "end_ms": 2550,
  "category": "emphasis",
  "severity": "minor",
  "note": "The emphasis sounds synthetic in this interval."
}
```

Timestamps are stored as integer milliseconds so artifacts are deterministic and do not depend on display formatting.

### Point marker

A point observation uses the same start and end:

```json
{
  "start_ms": 5100,
  "end_ms": 5100,
  "category": "intonation",
  "severity": "minor",
  "note": "Sentence-final intonation becomes flat here."
}
```

### Interval

A ranged observation uses `end_ms > start_ms`.

The core rejects negative timestamps, reversed intervals, empty notes, exact duplicate annotations, unsupported categories/severities, and annotations attached to non-audio evaluation records.

## Categories

Current issue categories are:

- `nativeness`
- `pronunciation`
- `fluency`
- `intonation`
- `unnatural_pause`
- `pace`
- `emphasis`
- `audio_artifact`
- `noise`
- `clipping`
- `other`

Categories identify what is audible. They do not prescribe a particular rubric score.

## Severity

Current human-authored severity levels are:

- `minor`
- `major`
- `critical`

Severity expresses evaluator judgment about the localized issue's impact. It is persisted as evidence but is not converted into an automatic score penalty.

## Workbench input

The browser workbench accepts timestamps in these forms:

```text
12.5
01:12.500
00:01:12.500
```

The UI converts them to integer milliseconds before submission.

Leaving **End** empty creates a point marker at the start timestamp. An explicit end before the start is rejected before submission and would also fail core validation if submitted directly through JSON.

## Privacy boundary

An annotation points to time within the audio reference already supplied by the evaluation record. TurkishEvalKit does not copy the referenced audio file into the evaluation artifact.

The annotation note itself is persisted. Evaluators should avoid unnecessary personal or confidential information in notes.

## Deliberate limitations

The current implementation does not:

- open, decode, upload, or retain the referenced audio asset;
- verify annotation timestamps against the real media duration;
- provide a waveform or built-in audio player;
- prevent overlapping intervals;
- infer issue categories automatically;
- convert severity or annotation counts into score penalties;
- claim annotation agreement across multiple evaluators.

These are intentional boundaries. Duration validation requires trustworthy media metadata, and automatic score effects would change the meaning of human-authored rubric ratings.

## Example

See [`../examples/audio-evaluation.json`](../examples/audio-evaluation.json) for a complete audio evaluation containing both an interval annotation and a point marker.
