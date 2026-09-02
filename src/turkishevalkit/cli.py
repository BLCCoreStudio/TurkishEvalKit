"""Command-line interface for validating and scoring evaluation records."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .evaluation import evaluate_submission
from .rubrics import BUILTIN_RUBRICS
from .serialization import load_record, result_to_dict, write_result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="turkisheval",
        description="Human-in-the-loop evaluation utilities for Turkish AI quality.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("rubrics", help="List built-in rubric ids and versions.")

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="Validate and score one human-authored evaluation JSON file.",
    )
    evaluate_parser.add_argument("input", type=Path, help="Path to an evaluation JSON file.")
    evaluate_parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the scored JSON result.",
    )
    evaluate_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete scored result as JSON.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a conventional process exit code."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "rubrics":
        for builtin_rubric in BUILTIN_RUBRICS.values():
            print(f"{builtin_rubric.id}@{builtin_rubric.version}\t{builtin_rubric.title}")
        return 0

    if args.command == "evaluate":
        try:
            record = load_record(args.input)
            rubric = BUILTIN_RUBRICS.get(record.rubric_id)
            if rubric is None:
                available = ", ".join(sorted(BUILTIN_RUBRICS))
                raise ValueError(
                    f"unknown rubric '{record.rubric_id}'; available rubrics: {available}"
                )
            result = evaluate_submission(record, rubric)
        except (OSError, ValueError) as exc:
            parser.exit(2, f"error: {exc}\n")

        if args.output is not None:
            write_result(args.output, result)

        if args.json:
            print(json.dumps(result_to_dict(result), ensure_ascii=False, indent=2))
        else:
            print(
                f"{result.task_id}: {result.weighted_score:.3f}/5 "
                f"({result.normalized_score:.2f}/100)"
            )
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
