from __future__ import annotations

from copy import deepcopy

import pytest

from turkishevalkit.review_queue import (
    QueueAction,
    QueueQuery,
    QueueSort,
    build_review_queue,
    derive_queue_action,
)


def _item(
    task_id: str,
    *,
    state: str | None,
    saved_at: str,
    review_outcome: str | None = None,
    evaluator_id: str | None = "eval-01",
    evaluation_type: str = "text",
    rubric_id: str = "tr-text-quality",
    superseded_by: str | None = None,
) -> dict[str, object]:
    return {
        "filename": f"{task_id}.json",
        "task_id": task_id,
        "workflow_state": state,
        "review_outcome": review_outcome,
        "evaluator_id": evaluator_id,
        "evaluation_type": evaluation_type,
        "rubric_id": rubric_id,
        "rubric_version": "1.0",
        "saved_at": saved_at,
        "superseded_by": superseded_by,
        "revision_number": 0,
    }


def test_queue_action_derivation_covers_workflow_lifecycle() -> None:
    cases = [
        (_item("draft", state="draft", saved_at="2026-01-01T00:00:00+00:00"), QueueAction.DRAFT),
        (
            _item("submitted", state="submitted", saved_at="2026-01-01T00:00:00+00:00"),
            QueueAction.AWAITING_REVIEW,
        ),
        (
            _item(
                "revision",
                state="revision_requested",
                saved_at="2026-01-01T00:00:00+00:00",
            ),
            QueueAction.AWAITING_REVISION,
        ),
        (
            _item(
                "escalated",
                state="reviewed",
                review_outcome="escalate",
                saved_at="2026-01-01T00:00:00+00:00",
            ),
            QueueAction.AWAITING_ADJUDICATION,
        ),
        (
            _item(
                "accepted",
                state="reviewed",
                review_outcome="accept",
                saved_at="2026-01-01T00:00:00+00:00",
            ),
            QueueAction.COMPLETE,
        ),
        (
            _item("done", state="adjudicated", saved_at="2026-01-01T00:00:00+00:00"),
            QueueAction.COMPLETE,
        ),
        (
            _item(
                "old",
                state="superseded",
                saved_at="2026-01-01T00:00:00+00:00",
                superseded_by="new.json",
            ),
            QueueAction.SUPERSEDED,
        ),
        (
            _item("raw", state=None, saved_at="2026-01-01T00:00:00+00:00"),
            QueueAction.UNTRACKED,
        ),
    ]

    for item, expected in cases:
        assert derive_queue_action(item) is expected


def test_priority_sort_and_facets_are_deterministic() -> None:
    entries = [
        _item("draft", state="draft", saved_at="2026-01-05T00:00:00+00:00"),
        _item("review-old", state="submitted", saved_at="2026-01-02T00:00:00+00:00"),
        _item("review-new", state="submitted", saved_at="2026-01-04T00:00:00+00:00"),
        _item(
            "adjudicate",
            state="reviewed",
            review_outcome="escalate",
            saved_at="2026-01-01T00:00:00+00:00",
            evaluator_id="eval-02",
        ),
        _item(
            "complete",
            state="reviewed",
            review_outcome="accept",
            saved_at="2026-01-06T00:00:00+00:00",
            evaluation_type="audio",
            rubric_id="tr-audio-quality",
        ),
    ]

    payload = build_review_queue(entries, QueueQuery())

    assert [item["task_id"] for item in payload["items"]] == [
        "adjudicate",
        "review-new",
        "review-old",
        "draft",
        "complete",
    ]
    assert payload["summary"]["workspace_total"] == 5
    assert payload["summary"]["actionable_total"] == 4
    assert payload["summary"]["by_action"]["awaiting_review"] == 2
    assert payload["facets"]["evaluation_type"][0] == {"value": "text", "count": 4}
    assert {facet["value"] for facet in payload["facets"]["evaluator_id"]} == {
        "eval-01",
        "eval-02",
    }


def test_filter_search_sort_and_pagination_do_not_mutate_input() -> None:
    entries = [
        _item(
            f"task-{index}",
            state="submitted" if index % 2 else "draft",
            saved_at=f"2026-01-{index + 1:02d}T00:00:00+00:00",
            evaluator_id="alice" if index < 4 else "bob",
        )
        for index in range(8)
    ]
    original = deepcopy(entries)
    query = QueueQuery(
        search="task-",
        actions=(QueueAction.AWAITING_REVIEW,),
        evaluator_ids=("alice",),
        sort=QueueSort.OLDEST,
        page=1,
        per_page=2,
    )

    payload = build_review_queue(entries, query)

    assert payload["total"] == 2
    assert payload["pages"] == 1
    assert [item["task_id"] for item in payload["items"]] == ["task-1", "task-3"]
    assert entries == original
    assert "queue_action" not in entries[0]


def test_second_page_and_task_sort() -> None:
    entries = [
        _item("charlie", state="submitted", saved_at="2026-01-01T00:00:00+00:00"),
        _item("alpha", state="submitted", saved_at="2026-01-03T00:00:00+00:00"),
        _item("bravo", state="submitted", saved_at="2026-01-02T00:00:00+00:00"),
    ]

    payload = build_review_queue(
        entries,
        QueueQuery(sort=QueueSort.TASK, page=2, per_page=2),
    )

    assert payload["pages"] == 2
    assert [item["task_id"] for item in payload["items"]] == ["charlie"]


def test_query_validation_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="page must be at least"):
        QueueQuery(page=0)
    with pytest.raises(ValueError, match="per_page must be between"):
        QueueQuery(per_page=101)
    with pytest.raises(ValueError, match="search query"):
        QueueQuery(search="x" * 201)
    with pytest.raises(ValueError, match="evaluation_types contains"):
        QueueQuery(evaluation_types=("",))
