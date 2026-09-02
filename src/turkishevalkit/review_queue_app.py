"""Local review-queue dashboard layered over the existing workbench application."""

from __future__ import annotations

import argparse
import threading
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .review_queue import QueueAction, QueueQuery, QueueSort, build_review_queue
from .workbench import create_app as create_workbench_app
from .workbench import default_workspace, list_history


def _positive_int(raw: str | None, *, default: int, name: str) -> int:
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    return value


def create_review_queue_app(workspace: Path | None = None) -> Any:
    """Create the normal workbench plus review-queue routes."""

    try:
        from flask import jsonify, render_template, request
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            'The review queue requires the workbench dependency. '
            'Install with: python -m pip install "turkishevalkit[workbench]"'
        ) from exc

    resolved_workspace = (workspace or default_workspace()).expanduser().resolve()
    app = create_workbench_app(resolved_workspace)

    @app.get("/queue")
    def review_queue_page() -> str:
        return render_template("review_queue.html")

    @app.get("/api/review-queue")
    def review_queue_api() -> Any:
        try:
            actions = tuple(
                QueueAction(value)
                for value in request.args.getlist("action")
                if value
            )
            sort = QueueSort(request.args.get("sort", QueueSort.PRIORITY.value))
            query = QueueQuery(
                search=request.args.get("q", ""),
                actions=actions,
                evaluation_types=tuple(
                    value for value in request.args.getlist("evaluation_type") if value
                ),
                rubric_ids=tuple(value for value in request.args.getlist("rubric_id") if value),
                evaluator_ids=tuple(
                    value for value in request.args.getlist("evaluator_id") if value
                ),
                sort=sort,
                page=_positive_int(request.args.get("page"), default=1, name="page"),
                per_page=_positive_int(
                    request.args.get("per_page"), default=50, name="per_page"
                ),
            )
            payload = build_review_queue(list_history(resolved_workspace), query)
        except (OSError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(payload)

    return app


def run_review_queue(
    workspace: Path | None = None,
    *,
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Run the combined workbench and queue server on loopback only."""

    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    app = create_review_queue_app(workspace)
    url = f"http://127.0.0.1:{port}/queue"
    if open_browser:
        timer = threading.Timer(0.7, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point for the queue-first combined workbench."""

    parser = argparse.ArgumentParser(
        prog="turkisheval-queue",
        description="Open the local TurkishEvalKit review queue.",
    )
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    run_review_queue(
        args.workspace,
        port=args.port,
        open_browser=not args.no_browser,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
