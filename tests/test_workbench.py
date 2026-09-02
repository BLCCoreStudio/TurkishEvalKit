from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import turkishevalkit.workbench as workbench
from turkishevalkit.evaluation import evaluate_submission
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC
from turkishevalkit.serialization import load_record


def _text_payload() -> dict[str, Any]:
    return json.loads(Path("examples/text-evaluation.json").read_text(encoding="utf-8"))


def test_default_workspace_honors_xdg_data_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if workbench.os.name == "nt" or workbench.sys.platform == "darwin":
        pytest.skip("XDG assertion is specific to Unix-like non-macOS runners")

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert workbench.default_workspace() == tmp_path / "turkishevalkit"


def test_rubric_payload_exposes_task_family() -> None:
    payload = workbench.rubric_payload()
    by_id = {item["id"]: item for item in payload}

    assert by_id["tr-text-quality"]["evaluation_type"] == "text"
    assert by_id["tr-audio-quality"]["evaluation_type"] == "audio"
    assert len(by_id["tr-text-quality"]["criteria"]) == 5


def test_history_storage_is_append_only_and_skips_invalid_files(tmp_path: Path) -> None:
    record = load_record(Path("examples/text-evaluation.json"))
    result = evaluate_submission(record, TEXT_QUALITY_RUBRIC)

    first = workbench.save_result(tmp_path, result)
    second = workbench.save_result(tmp_path, result)

    assert first != second
    assert first.exists()
    assert second.exists()

    directory = tmp_path / "evaluations"
    (directory / "broken.json").write_text("{bad-json", encoding="utf-8")
    (directory / "array.json").write_text("[]", encoding="utf-8")

    history = workbench.list_history(tmp_path)
    assert len(history) == 2
    assert history[0]["task_id"] == "text-demo-001"
    assert history[0]["evaluation_type"] == "text"
    assert history[0]["normalized_score"] == 95.0


def test_history_is_empty_before_workspace_is_created(tmp_path: Path) -> None:
    assert workbench.list_history(tmp_path) == []


def test_workbench_routes_validate_save_list_and_export(tmp_path: Path) -> None:
    app = workbench.create_app(tmp_path)
    app.testing = True
    client = app.test_client()

    index = client.get("/")
    assert index.status_code == 200
    assert b"TurkishEvalKit" in index.data

    config = client.get("/api/config")
    assert config.status_code == 200
    config_payload = config.get_json()
    assert config_payload["workspace"] == str(tmp_path.resolve())
    assert len(config_payload["rubrics"]) == 2

    empty_history = client.get("/api/history")
    assert empty_history.get_json() == {"items": []}

    invalid = client.post(
        "/api/evaluations",
        data="not-json",
        content_type="application/json",
    )
    assert invalid.status_code == 400
    assert "JSON object" in invalid.get_json()["error"]

    unknown = _text_payload()
    unknown["rubric_id"] = "does-not-exist"
    response = client.post("/api/evaluations", json=unknown)
    assert response.status_code == 400
    assert "unknown rubric" in response.get_json()["error"]

    wrong_type = _text_payload()
    wrong_type["evaluation_type"] = "audio"
    response = client.post("/api/evaluations", json=wrong_type)
    assert response.status_code == 400
    assert "evaluation_type" in response.get_json()["error"]

    saved = client.post("/api/evaluations", json=_text_payload())
    assert saved.status_code == 201
    body = saved.get_json()
    assert body["result"]["task_id"] == "text-demo-001"
    assert body["result"]["normalized_score"] == 95.0

    history = client.get("/api/history").get_json()["items"]
    assert len(history) == 1
    assert history[0]["filename"] == body["filename"]

    download = client.get(f"/api/history/{body['filename']}")
    assert download.status_code == 200
    exported = json.loads(download.data)
    assert exported["task_id"] == "text-demo-001"

    assert client.get("/api/history/missing.json").status_code == 404
    assert client.get("/api/history/not-json.txt").status_code == 404


def test_run_workbench_binds_loopback_and_controls_browser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: dict[str, Any] = {}

    class FakeApp:
        def run(self, **kwargs: Any) -> None:
            calls["run"] = kwargs

    class FakeTimer:
        daemon = False

        def __init__(
            self,
            interval: float,
            function: Any,
            args: tuple[str, ...],
        ) -> None:
            calls["timer"] = (interval, function, args)

        def start(self) -> None:
            calls["timer_started"] = True

    monkeypatch.setattr(workbench, "create_app", lambda workspace: FakeApp())
    monkeypatch.setattr(workbench.threading, "Timer", FakeTimer)

    workbench.run_workbench(tmp_path, port=9999, open_browser=True)

    assert calls["run"] == {
        "host": "127.0.0.1",
        "port": 9999,
        "debug": False,
        "use_reloader": False,
    }
    assert calls["timer"][2] == ("http://127.0.0.1:9999/",)
    assert calls["timer_started"] is True

    with pytest.raises(ValueError, match="port must be between"):
        workbench.run_workbench(tmp_path, port=0)
