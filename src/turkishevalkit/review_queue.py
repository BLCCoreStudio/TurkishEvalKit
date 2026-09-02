"""Deterministic local review-queue filtering and ordering."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import ceil
from typing import Any, Mapping, Sequence


class QueueAction(StrEnum):
    """Action-oriented state derived from one persisted evaluation workflow."""

    AWAITING_REVIEW = "awaiting_review"
    AWAITING_REVISION = "awaiting_revision"
    AWAITING_ADJUDICATION = "awaiting_adjudication"
    DRAFT = "draft"
    COMPLETE = "complete"
    SUPERSEDED = "superseded"
    UNTRACKED = "untracked"


class QueueSort(StrEnum):
    """Supported deterministic queue orderings."""

    PRIORITY = "priority"
    NEWEST = "newest"
    OLDEST = "oldest"
    TASK = "task"


_ACTION_PRIORITY: dict[QueueAction, int] = {
    QueueAction.AWAITING_ADJUDICATION: 0,
    QueueAction.AWAITING_REVIEW: 1,
    QueueAction.AWAITING_REVISION: 2,
    QueueAction.DRAFT: 3,
    QueueAction.UNTRACKED: 4,
    QueueAction.COMPLETE: 5,
    QueueAction.SUPERSEDED: 6,
}

_ACTIONABLE = {
    QueueAction.AWAITING_ADJUDICATION,
    QueueAction.AWAITING_REVIEW,
    QueueAction.AWAITING_REVISION,
    QueueAction.DRAFT,
}


@dataclass(frozen=True, slots=True)
class QueueQuery:
    """Framework-independent review queue query."""

    search: str = ""
    actions: tuple[QueueAction, ...] = ()
    evaluation_types: tuple[str, ...] = ()
    rubric_ids: tuple[str, ...] = ()
    evaluator_ids: tuple[str, ...] = ()
    sort: QueueSort = QueueSort.PRIORITY
    page: int = 1
    per_page: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= self.per_page <= 100:
            raise ValueError("per_page must be between 1 and 100")
        if len(self.search) > 200:
            raise ValueError("search query must be at most 200 characters")
        for field_name, values in (
            ("evaluation_types", self.evaluation_types),
            ("rubric_ids", self.rubric_ids),
            ("evaluator_ids", self.evaluator_ids),
        ):
            if len(values) > 32:
                raise ValueError(f"{field_name} accepts at most 32 values")
            if any(not value.strip() or len(value) > 160 for value in values):
                raise ValueError(f"{field_name} contains an invalid value")


def derive_queue_action(item: Mapping[str, Any]) -> QueueAction:
    """Map persisted workflow/revision summary fields to one queue action."""

    state = str(item.get("workflow_state") or "")
    review_outcome = str(item.get("review_outcome") or "")
    superseded_by = item.get("superseded_by")

    if state == "superseded" or superseded_by:
        return QueueAction.SUPERSEDED
    if not state:
        return QueueAction.UNTRACKED
    if state == "draft":
        return QueueAction.DRAFT
    if state == "submitted":
        return QueueAction.AWAITING_REVIEW
    if state == "revision_requested":
        return QueueAction.AWAITING_REVISION
    if state == "reviewed" and review_outcome == "escalate":
        return QueueAction.AWAITING_ADJUDICATION
    if state in {"reviewed", "adjudicated"}:
        return QueueAction.COMPLETE
    return QueueAction.UNTRACKED


def _timestamp(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return 0.0


def _search_blob(item: Mapping[str, Any]) -> str:
    return " ".join(
        str(item.get(field) or "")
        for field in (
            "task_id",
            "filename",
            "evaluation_type",
            "rubric_id",
            "evaluator_id",
            "session_id",
        )
    ).casefold()


def _matches(item: Mapping[str, Any], query: QueueQuery) -> bool:
    action = derive_queue_action(item)
    if query.actions and action not in query.actions:
        return False
    if query.evaluation_types and str(item.get("evaluation_type") or "") not in query.evaluation_types:
        return False
    if query.rubric_ids and str(item.get("rubric_id") or "") not in query.rubric_ids:
        return False
    if query.evaluator_ids and str(item.get("evaluator_id") or "") not in query.evaluator_ids:
        return False
    search = query.search.strip().casefold()
    return not search or search in _search_blob(item)


def _decorate(item: Mapping[str, Any]) -> dict[str, Any]:
    action = derive_queue_action(item)
    decorated = dict(item)
    decorated["queue_action"] = action.value
    decorated["queue_priority"] = _ACTION_PRIORITY[action]
    return decorated


def _sort_items(items: list[dict[str, Any]], sort: QueueSort) -> None:
    if sort is QueueSort.NEWEST:
        items.sort(key=lambda item: (_timestamp(item.get("saved_at")), item.get("filename", "")), reverse=True)
        return
    if sort is QueueSort.OLDEST:
        items.sort(key=lambda item: (_timestamp(item.get("saved_at")), item.get("filename", "")))
        return
    if sort is QueueSort.TASK:
        items.sort(
            key=lambda item: (
                str(item.get("task_id") or "").casefold(),
                -_timestamp(item.get("saved_at")),
                str(item.get("filename") or ""),
            )
        )
        return
    items.sort(
        key=lambda item: (
            int(item["queue_priority"]),
            -_timestamp(item.get("saved_at")),
            str(item.get("filename") or ""),
        )
    )


def _facet(values: Sequence[str]) -> list[dict[str, Any]]:
    counts = Counter(value for value in values if value)
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].casefold()))
    ]


def build_review_queue(
    entries: Sequence[Mapping[str, Any]],
    query: QueueQuery,
) -> dict[str, Any]:
    """Filter, order, facet, and paginate local history without mutating it."""

    decorated = [_decorate(item) for item in entries]
    action_counts = Counter(item["queue_action"] for item in decorated)
    actionable_total = sum(
        action_counts.get(action.value, 0)
        for action in _ACTIONABLE
    )

    filtered = [item for item in decorated if _matches(item, query)]
    _sort_items(filtered, query.sort)

    total = len(filtered)
    pages = ceil(total / query.per_page) if total else 0
    offset = (query.page - 1) * query.per_page
    page_items = filtered[offset : offset + query.per_page]

    return {
        "items": page_items,
        "total": total,
        "page": query.page,
        "per_page": query.per_page,
        "pages": pages,
        "summary": {
            "workspace_total": len(decorated),
            "actionable_total": actionable_total,
            "by_action": {
                action.value: action_counts.get(action.value, 0)
                for action in QueueAction
            },
        },
        "facets": {
            "evaluation_type": _facet(
                [str(item.get("evaluation_type") or "") for item in decorated]
            ),
            "rubric_id": _facet([str(item.get("rubric_id") or "") for item in decorated]),
            "evaluator_id": _facet(
                [str(item.get("evaluator_id") or "") for item in decorated]
            ),
        },
    }
