from __future__ import annotations

from pathlib import Path
from typing import Any

import turkishevalkit.cli as cli
import turkishevalkit.review_queue_app as queue_app


def test_main_cli_queue_dispatches_to_local_queue(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    calls: dict[str, Any] = {}

    def fake_run_review_queue(
        workspace: Path | None = None,
        *,
        port: int = 8765,
        open_browser: bool = True,
    ) -> None:
        calls["workspace"] = workspace
        calls["port"] = port
        calls["open_browser"] = open_browser

    monkeypatch.setattr(queue_app, "run_review_queue", fake_run_review_queue)

    result = cli.main(
        [
            "queue",
            "--workspace",
            str(tmp_path),
            "--port",
            "9876",
            "--no-browser",
        ]
    )

    assert result == 0
    assert calls == {
        "workspace": tmp_path,
        "port": 9876,
        "open_browser": False,
    }
