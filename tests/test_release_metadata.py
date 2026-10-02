from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_version_has_matching_changelog_release_heading() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    release_heading = re.compile(rf"^##\s+{re.escape(version)}(?:\s+—\s+\d{{4}}-\d{{2}}-\d{{2}})?\s*$", re.MULTILINE)
    assert release_heading.search(changelog), (
        f"pyproject.toml declares {version}, but CHANGELOG.md has no matching release heading"
    )
