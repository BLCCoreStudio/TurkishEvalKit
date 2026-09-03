from __future__ import annotations

import json
from pathlib import Path

import pytest

from turkishevalkit.evaluation import evaluate_submission
from turkishevalkit.reliability import (
    build_population_reliability_report,
    load_reliability_spec,
    population_reliability_report_to_dict,
)
from turkishevalkit.reliability_workspace import (
    build_workspace_reliability_report,
    list_reliability_candidate_groups,
    reliability_candidate_group_to_dict,
)
from turkishevalkit.rubrics import TEXT_QUALITY_RUBRIC
from turkishevalkit.workbench import create_app, create_workflow, save_result, save_workflow


def _populate_text_reliability_workspace(workspace: Path) -> None:
    spec = load_reliability_spec(Path("examples/reliability-text.json"))
    for task_index, task in enumerate(spec.tasks, start=1):
        for submission_index, submission in enumerate(task.submissions, start=1):
            result = evaluate_submission(submission.record, TEXT_QUALITY_RUBRIC)
            destination = save_result(workspace, result)
            workflow = create_workflow(
                artifact_id=destination.name,
                task_id=submission.record.task_id,
                session_id=f"reliability-{task_index}-{submission_index}",
                evaluator_id=submission.evaluator_id,
            )
            save_workflow(workspace, workflow)


def _selected_groups(workspace: Path) -> list[dict[str, list[str]]]:
    groups = list_reliability_candidate_groups(workspace)
    ready = [group for group in groups if group.ready]
    return [
        {"filenames": [artifact.filename for artifact in group.artifacts]}
        for group in ready
    ]


def _corrupt_workflow_task_id(workspace: Path, evaluation_filename: str) -> None:
    workflow_path = workspace / "workflows" / f"{evaluation_filename[:-5]}.workflow.json"
    payload = json.loads(workflow_path.read_text(encoding="utf-8"))
    payload["task_id"] = "wrong-task-id"
    workflow_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_workspace_candidates_group_same_stimulus_submissions(tmp_path: Path) -> None:
    _populate_text_reliability_workspace(tmp_path)

    groups = list_reliability_candidate_groups(tmp_path)

    assert len(groups) == 3
    assert all(group.ready for group in groups)
    assert {group.task_id for group in groups} == {
        "reliability-text-01",
        "reliability-text-02",
        "reliability-text-03",
    }
    assert {group.evaluation_type for group in groups} == {"text"}
    assert {group.rubric_id for group in groups} == {"tr-text-quality"}
    assert len({group.dataset_key for group in groups}) == 1
    assert all(len(group.artifacts) == 3 for group in groups)
    assert all(len({item.evaluator_id for item in group.artifacts}) == 3 for group in groups)


def test_workspace_report_matches_existing_reliability_core(tmp_path: Path) -> None:
    _populate_text_reliability_workspace(tmp_path)
    spec = load_reliability_spec(Path("examples/reliability-text.json"))
    expected = population_reliability_report_to_dict(
        build_population_reliability_report(spec, TEXT_QUALITY_RUBRIC)
    )

    actual = build_workspace_reliability_report(
        tmp_path,
        minimum_task_count=3,
        groups=_selected_groups(tmp_path),
    )

    assert actual == expected


def test_candidate_group_without_attribution_is_not_ready(tmp_path: Path) -> None:
    spec = load_reliability_spec(Path("examples/reliability-text.json"))
    task = spec.tasks[0]
    for index, submission in enumerate(task.submissions):
        result = evaluate_submission(submission.record, TEXT_QUALITY_RUBRIC)
        destination = save_result(tmp_path, result)
        if index == 0:
            continue
        workflow = create_workflow(
            artifact_id=destination.name,
            task_id=submission.record.task_id,
            session_id=f"attributed-{index}",
            evaluator_id=submission.evaluator_id,
        )
        save_workflow(tmp_path, workflow)

    group = list_reliability_candidate_groups(tmp_path)[0]

    assert group.ready is False
    assert any("no trusted evaluator attribution" in reason for reason in group.reasons)
    payload = reliability_candidate_group_to_dict(group)
    assert payload["ready"] is False
    assert payload["artifact_count"] == 3


def test_invalid_workflow_task_attribution_remains_visible_but_untrusted(tmp_path: Path) -> None:
    spec = load_reliability_spec(Path("examples/reliability-text.json"))
    task = spec.tasks[0]
    filenames: list[str] = []
    for index, submission in enumerate(task.submissions[:2]):
        result = evaluate_submission(submission.record, TEXT_QUALITY_RUBRIC)
        destination = save_result(tmp_path, result)
        filenames.append(destination.name)
        save_workflow(
            tmp_path,
            create_workflow(
                artifact_id=destination.name,
                task_id=submission.record.task_id,
                session_id=f"mismatch-{index}",
                evaluator_id=submission.evaluator_id,
            ),
        )

    _corrupt_workflow_task_id(tmp_path, filenames[0])

    group = list_reliability_candidate_groups(tmp_path)[0]
    payload = reliability_candidate_group_to_dict(group)

    assert group.ready is False
    assert len(group.artifacts) == 2
    assert any("invalid workflow attribution" in reason for reason in group.reasons)
    mismatched = next(item for item in payload["artifacts"] if item["filename"] == filenames[0])
    assert mismatched["evaluator_id"] is None
    assert "workflow task_id does not match" in mismatched["attribution_error"]


def test_duplicate_evaluator_attribution_blocks_candidate_group(tmp_path: Path) -> None:
    spec = load_reliability_spec(Path("examples/reliability-text.json"))
    task = spec.tasks[0]
    duplicate_evaluator = task.submissions[0].evaluator_id
    for index, submission in enumerate(task.submissions[:2]):
        result = evaluate_submission(submission.record, TEXT_QUALITY_RUBRIC)
        destination = save_result(tmp_path, result)
        workflow = create_workflow(
            artifact_id=destination.name,
            task_id=submission.record.task_id,
            session_id=f"duplicate-{index}",
            evaluator_id=duplicate_evaluator,
        )
        save_workflow(tmp_path, workflow)

    group = list_reliability_candidate_groups(tmp_path)[0]

    assert group.ready is False
    assert any("duplicate evaluator attribution" in reason for reason in group.reasons)


def test_workspace_report_rejects_fewer_than_declared_task_groups(tmp_path: Path) -> None:
    _populate_text_reliability_workspace(tmp_path)

    with pytest.raises(ValueError, match="selected groups must satisfy minimum_task_count"):
        build_workspace_reliability_report(
            tmp_path,
            minimum_task_count=3,
            groups=_selected_groups(tmp_path)[:2],
        )


def test_workspace_report_rejects_artifact_reuse_across_task_groups(tmp_path: Path) -> None:
    _populate_text_reliability_workspace(tmp_path)
    groups = _selected_groups(tmp_path)
    groups[1]["filenames"][0] = groups[0]["filenames"][0]

    with pytest.raises(ValueError, match="cannot be reused"):
        build_workspace_reliability_report(
            tmp_path,
            minimum_task_count=3,
            groups=groups,
        )


def test_workspace_report_rechecks_workflow_task_attribution(tmp_path: Path) -> None:
    _populate_text_reliability_workspace(tmp_path)
    groups = _selected_groups(tmp_path)
    filename = groups[0]["filenames"][0]
    _corrupt_workflow_task_id(tmp_path, filename)

    with pytest.raises(ValueError, match="workflow task_id does not match evaluation task_id"):
        build_workspace_reliability_report(
            tmp_path,
            minimum_task_count=3,
            groups=groups,
        )


def test_reliability_routes_use_workspace_core_and_do_not_persist_report(tmp_path: Path) -> None:
    _populate_text_reliability_workspace(tmp_path)
    app = create_app(tmp_path)
    client = app.test_client()

    page = client.get("/reliability")
    candidates = client.get("/api/reliability/candidates")
    response = client.post(
        "/api/reliability/analyze",
        json={"minimum_task_count": 3, "groups": _selected_groups(tmp_path)},
    )

    assert page.status_code == 200
    assert candidates.status_code == 200
    candidate_payload = candidates.get_json()
    assert len(candidate_payload["groups"]) == 3
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["report"]["task_count"] == 3
    assert payload["report"]["rubric_id"] == "tr-text-quality"
    assert not (tmp_path / "reliability").exists()
    assert not (tmp_path / "reliabilities").exists()


def test_reliability_api_rejects_invalid_minimum_and_missing_artifact(tmp_path: Path) -> None:
    _populate_text_reliability_workspace(tmp_path)
    app = create_app(tmp_path)
    client = app.test_client()
    groups = _selected_groups(tmp_path)

    bad_minimum = client.post(
        "/api/reliability/analyze",
        json={"minimum_task_count": 2, "groups": groups},
    )
    groups[0]["filenames"][0] = "../outside.json"
    missing = client.post(
        "/api/reliability/analyze",
        json={"minimum_task_count": 3, "groups": groups},
    )

    assert bad_minimum.status_code == 400
    assert "at least 3" in bad_minimum.get_json()["error"]
    assert missing.status_code == 404
