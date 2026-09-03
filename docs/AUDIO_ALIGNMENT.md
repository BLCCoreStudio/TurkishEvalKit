# Audio alignment primitives

TurkishEvalKit `0.14.x` exposes one shared timestamp-alignment contract for localized audio evidence.

The primitives live in `turkishevalkit.audio_alignment` and are used by both calibration and disagreement exploration. This removes two previously duplicated implementations whose behavior could otherwise drift independently.

## Public API

```python
from turkishevalkit import (
    AudioAnnotationMatch,
    annotation_temporal_similarity,
    match_audio_annotations,
)
```

### `annotation_temporal_similarity(left, right, tolerance_ms)`

Returns a similarity in `0..1` when two annotations are eligible to match, otherwise `None`.

Eligibility is category-aware: annotations with different `AudioIssueCategory` values never match.

### `match_audio_annotations(left, right, tolerance_ms)`

Returns a tuple of `AudioAnnotationMatch` values:

```text
left_index
right_index
temporal_similarity
```

Every annotation participates in at most one returned match.

## Established temporal semantics

The extraction in `0.14.x` intentionally preserves the behavior already used by calibration and the disagreement explorer. It does not introduce a new matching algorithm.

### Point ↔ point

For two point annotations:

```text
distance = abs(left.start_ms - right.start_ms)
```

The pair is ineligible when `distance > tolerance_ms`.

Otherwise:

```text
similarity = 1 - distance / (tolerance_ms + 1)
```

Exact points therefore score `1.0`.

### Point ↔ interval

If one annotation is a point and the other is an interval, distance is zero when the point lies inside the interval. Otherwise distance is measured to the nearest interval boundary.

The same tolerance and proximity formula as point ↔ point is then applied.

### Interval ↔ interval with overlap

Overlapping intervals use overlap over union:

```text
similarity = overlap_duration / union_duration
```

### Interval ↔ interval without overlap

Separated intervals are eligible only when their gap is at most `tolerance_ms`.

The existing conservative proximity score is preserved:

```text
similarity = 0.25 * (1 - gap / (tolerance_ms + 1))
```

Touching intervals therefore receive `0.25`.

## Deterministic one-to-one matching

`match_audio_annotations()` performs the established greedy correspondence procedure:

1. enumerate all category-compatible candidate pairs whose temporal similarity is not `None`;
2. order candidates by descending similarity;
3. break equal-similarity ties by original left index, then right index;
4. accept a candidate only if neither annotation has already been matched.

The result is deterministic for identical inputs.

This is intentionally **not** described as a global assignment optimizer. The `0.14.x` extraction centralizes existing semantics; changing the optimization strategy would be a separate semantic change requiring its own evaluation, tests, and documentation.

## Validation

`tolerance_ms` must be a non-negative integer. Boolean values are rejected even though Python's `bool` is an `int` subclass.

`AudioAnnotationMatch` also validates:

- non-negative left/right indexes;
- `temporal_similarity` inside `0..1`.

The `AudioAnnotation` model continues to validate timestamp ordering, category/severity types, and non-empty human evidence notes.

## Consumers

### Calibration

`calibration.py` uses the shared matches to derive:

- matched annotation count;
- pairwise annotation F1;
- matched severity agreement;
- mean temporal similarity.

### Disagreement explorer

`disagreement.py` uses the exact same correspondence to derive:

- unmatched evidence on each evaluator side;
- matched evidence with timing variance;
- matched evidence with severity variance.

Because both consumers now receive the same `AudioAnnotationMatch` sequence, an annotation cannot be considered matched by calibration and unmatched by the disagreement explorer merely because the two modules implemented correspondence differently.

## Interpretation boundary

Audio alignment establishes correspondence between human-authored localized evidence. It does not:

- decide whether either annotation is correct;
- alter a criterion rating automatically;
- infer an issue from audio media;
- validate timestamps against decoded media duration;
- rank evaluators;
- define a universal agreement threshold.

## Compatibility

The `0.14.x` refactor is expected to be output-preserving for existing non-negative-tolerance calibration/disagreement inputs. Existing calibration and disagreement regression tests remain in place, while `tests/test_audio_alignment.py` locks the primitive-level edge cases directly.

Future changes to category eligibility, temporal formulas, tie-breaking, or assignment strategy are semantic changes and must not be shipped as an undocumented refactor.
