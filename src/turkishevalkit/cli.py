"""Command-line interface for TurkishEvalKit."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .calibration import (
    build_calibration_report,
    calibration_report_to_dict,
    load_calibration_spec,
    write_calibration_report,
)
from .evaluation import EvaluationResult, evaluate_submission
from .interchange import (
    export_workspace,
    import_workspace_file,
    load_interchange_records,
    write_interchange_records,
)
from .metadata_index import (
    clear_metadata_index,
    metadata_index_status,
    metadata_index_status_to_dict,
    rebuild_metadata_index,
)
from .models import EvaluationType, PairwiseEvaluationRecord, Preference
from .pairwise import PairwiseEvaluationResult, evaluate_pairwise_submission
from .reliability import (
    build_population_reliability_report,
    load_reliability_spec,
    population_reliability_report_to_dict,
    write_population_reliability_report,
)
from .rubrics import BUILTIN_RUBRICS
from .serialization import load_record, result_to_dict, write_result


def _port(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _pairwise_outcome(result: PairwiseEvaluationResult) -> str:
    if result.overall_preference is Preference.TIE:
        return "Tie"
    return f"{result.overall_preference.value.upper()} preferred"


def _add_local_app_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Local directory for append-only evaluation history.",
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=8765,
        help="Local TCP port (default: 8765).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the local browser interface automatically.",
    )


def _add_workspace_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Local TurkishEvalKit workspace. Defaults to the platform data directory.",
    )


def _resolved_workspace(path: Path | None) -> Path:
    if path is not None:
        return path
    from .workbench import default_workspace

    return default_workspace()


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
    evaluate_parser.add_argument(
        "input",
        type=Path,
        help="Path to an evaluation JSON file.",
    )
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

    calibrate_parser = subparsers.add_parser(
        "calibrate",
        help="Compare two or more independent evaluations of the same task.",
    )
    calibrate_parser.add_argument(
        "input",
        type=Path,
        help="Path to a calibration spec containing evaluator ids and evaluations.",
    )
    calibrate_parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the calibration report JSON.",
    )
    calibrate_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete calibration report as JSON.",
    )
    calibrate_parser.add_argument(
        "--annotation-tolerance-ms",
        type=_non_negative_int,
        default=250,
        help="Audio point/range matching tolerance in milliseconds (default: 250).",
    )

    reliability_parser = subparsers.add_parser(
        "reliability",
        help="Calculate population reliability across repeated independently rated tasks.",
    )
    reliability_parser.add_argument(
        "input",
        type=Path,
        help="Path to a repeated-task reliability specification.",
    )
    reliability_parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the population reliability report JSON.",
    )
    reliability_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete population reliability report as JSON.",
    )

    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert evaluator records between JSON bundle, array, and JSONL formats.",
    )
    convert_parser.add_argument("input", type=Path, help="Input evaluation dataset.")
    convert_parser.add_argument("output", type=Path, help="Destination dataset path.")
    convert_parser.add_argument(
        "--input-format",
        choices=("auto", "json", "jsonl"),
        default="auto",
        help="Input format (default: infer JSON/JSONL).",
    )
    convert_parser.add_argument(
        "--output-format",
        choices=("bundle", "array", "jsonl"),
        default="bundle",
        help="Output format (default: bundle).",
    )

    export_parser = subparsers.add_parser(
        "export",
        help="Export evaluator-authored records from a local workspace.",
    )
    _add_workspace_argument(export_parser)
    export_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination dataset path.",
    )
    export_parser.add_argument(
        "--format",
        choices=("bundle", "array", "jsonl"),
        default="bundle",
        help="Export format (default: bundle).",
    )

    import_parser = subparsers.add_parser(
        "import",
        help="Import evaluator records into a workspace without trusting workflow metadata.",
    )
    import_parser.add_argument("input", type=Path, help="Input evaluation dataset.")
    _add_workspace_argument(import_parser)
    import_parser.add_argument(
        "--input-format",
        choices=("auto", "json", "jsonl"),
        default="auto",
        help="Input format (default: infer JSON/JSONL).",
    )
    import_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report import actions without writing artifacts.",
    )

    index_parser = subparsers.add_parser(
        "index",
        help="Manage the optional rebuildable local metadata index.",
    )
    index_subparsers = index_parser.add_subparsers(dest="index_command", required=True)

    index_status_parser = index_subparsers.add_parser(
        "status",
        help="Inspect whether the optional metadata index is absent, fresh, stale, or corrupt.",
    )
    _add_workspace_argument(index_status_parser)
    index_status_parser.add_argument(
        "--json",
        action="store_true",
        help="Print complete index status as JSON.",
    )

    index_rebuild_parser = index_subparsers.add_parser(
        "rebuild",
        help="Rebuild the metadata index from canonical JSON artifacts.",
    )
    _add_workspace_argument(index_rebuild_parser)

    index_clear_parser = index_subparsers.add_parser(
        "clear",
        help="Delete the rebuildable index without touching canonical artifacts.",
    )
    _add_workspace_argument(index_clear_parser)

    workbench_parser = subparsers.add_parser(
        "workbench",
        help="Run the localhost-only browser evaluation workbench.",
    )
    _add_local_app_arguments(workbench_parser)

    queue_parser = subparsers.add_parser(
        "queue",
        help="Run the combined workbench and open the action-oriented review queue.",
    )
    _add_local_app_arguments(queue_parser)
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
            result: EvaluationResult | PairwiseEvaluationResult
            if isinstance(record, PairwiseEvaluationRecord):
                result = evaluate_pairwise_submission(record, rubric)
            else:
                result = evaluate_submission(record, rubric)
        except (OSError, TypeError, ValueError) as exc:
            parser.exit(2, f"error: {exc}\n")

        if args.output is not None:
            write_result(args.output, result)

        if args.json:
            print(json.dumps(result_to_dict(result), ensure_ascii=False, indent=2))
        elif isinstance(result, PairwiseEvaluationResult):
            print(
                f"{result.task_id}: {_pairwise_outcome(result)} · "
                f"criterion preference {result.preference_score:+.2f}/100 · "
                f"strength {result.preference_strength}/3"
            )
        else:
            print(
                f"{result.task_id}: {result.weighted_score:.3f}/5 "
                f"({result.normalized_score:.2f}/100)"
            )
        return 0

    if args.command == "calibrate":
        try:
            submissions = load_calibration_spec(args.input)
            if not submissions:
                raise ValueError("calibration spec must contain evaluator submissions")
            rubric = BUILTIN_RUBRICS.get(submissions[0].record.rubric_id)
            if rubric is None:
                available = ", ".join(sorted(BUILTIN_RUBRICS))
                raise ValueError(
                    f"unknown rubric '{submissions[0].record.rubric_id}'; "
                    f"available rubrics: {available}"
                )
            calibration_report = build_calibration_report(
                submissions,
                rubric,
                annotation_tolerance_ms=args.annotation_tolerance_ms,
            )
        except (OSError, TypeError, ValueError) as exc:
            parser.exit(2, f"error: {exc}\n")

        if args.output is not None:
            write_calibration_report(args.output, calibration_report)

        if args.json:
            print(
                json.dumps(
                    calibration_report_to_dict(calibration_report),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            summary = (
                f"{calibration_report.task_id}: "
                f"{calibration_report.evaluator_count} evaluators · "
                "criterion exact agreement "
                f"{calibration_report.exact_criterion_agreement_rate:.1%} · "
                f"aggregate spread {calibration_report.aggregate_score_spread:.2f}"
            )
            if calibration_report.evaluation_type is EvaluationType.PAIRWISE:
                overall_agreement = calibration_report.overall_preference_agreement_rate
                assert overall_agreement is not None
                summary += f" · overall preference agreement {overall_agreement:.1%}"
            else:
                within_one_agreement = (
                    calibration_report.within_one_criterion_agreement_rate
                )
                assert within_one_agreement is not None
                summary += f" · within-one agreement {within_one_agreement:.1%}"
                if calibration_report.audio_annotation_agreement is not None:
                    summary += (
                        " · annotation F1 "
                        f"{calibration_report.audio_annotation_agreement.mean_pairwise_f1:.3f}"
                    )
            print(summary)
        return 0

    if args.command == "reliability":
        try:
            spec = load_reliability_spec(args.input)
            if not spec.tasks:
                raise ValueError("reliability spec must contain repeated tasks")
            rubric_id = spec.tasks[0].submissions[0].record.rubric_id
            rubric = BUILTIN_RUBRICS.get(rubric_id)
            if rubric is None:
                available = ", ".join(sorted(BUILTIN_RUBRICS))
                raise ValueError(
                    f"unknown rubric '{rubric_id}'; available rubrics: {available}"
                )
            reliability_report = build_population_reliability_report(spec, rubric)
        except (OSError, TypeError, ValueError) as exc:
            parser.exit(2, f"error: {exc}\n")

        if args.output is not None:
            write_population_reliability_report(args.output, reliability_report)

        if args.json:
            print(
                json.dumps(
                    population_reliability_report_to_dict(reliability_report),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(
                f"{reliability_report.task_count} tasks · "
                f"{reliability_report.evaluation_type.value} · "
                f"{reliability_report.rubric_id}@{reliability_report.rubric_version}"
            )
            for criterion_id, criterion in (
                reliability_report.criterion_reliability.items()
            ):
                alpha = criterion.krippendorff_alpha
                alpha_text = (
                    f"{alpha.value:.4f}"
                    if alpha.applicable and alpha.value is not None
                    else "n/a"
                )
                print(f"{criterion_id}: {alpha.metric}={alpha_text}")
            if reliability_report.aggregate_score_icc_a1.applicable:
                icc = reliability_report.aggregate_score_icc_a1.value
                assert icc is not None
                print(f"aggregate ICC(A,1)={icc:.4f}")
        return 0

    if args.command == "convert":
        try:
            records = load_interchange_records(
                args.input,
                input_format=args.input_format,
            )
            write_interchange_records(
                args.output,
                records,
                output_format=args.output_format,
            )
        except (OSError, TypeError, ValueError) as exc:
            parser.exit(2, f"error: {exc}\n")
        print(
            f"converted {len(records)} record(s) to {args.output_format}: {args.output}"
        )
        return 0

    if args.command == "export":
        try:
            count = export_workspace(
                _resolved_workspace(args.workspace),
                args.output,
                output_format=args.format,
            )
        except (OSError, TypeError, ValueError) as exc:
            parser.exit(2, f"error: {exc}\n")
        print(f"exported {count} record(s) as {args.format}: {args.output}")
        return 0

    if args.command == "import":
        try:
            import_summary = import_workspace_file(
                _resolved_workspace(args.workspace),
                args.input,
                input_format=args.input_format,
                dry_run=args.dry_run,
            )
        except (OSError, TypeError, ValueError) as exc:
            parser.exit(2, f"error: {exc}\n")
        prefix = "would import" if import_summary.dry_run else "imported"
        print(
            f"{prefix} {import_summary.imported_count}/{import_summary.total_records} record(s) · "
            f"{import_summary.duplicate_count} duplicate(s)"
        )
        return 0

    if args.command == "index":
        workspace = _resolved_workspace(args.workspace)
        if args.index_command == "status":
            status = metadata_index_status(workspace)
            if args.json:
                print(
                    json.dumps(
                        metadata_index_status_to_dict(status),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(
                    f"{status.state.value}: {status.record_count} indexed record(s) · "
                    f"{status.source_file_count} canonical source file(s)"
                )
                if status.reason:
                    print(status.reason)
            return 0

        if args.index_command == "rebuild":
            try:
                from .workbench import scan_history

                entries = scan_history(workspace)
                status = rebuild_metadata_index(workspace, entries)
            except (OSError, TypeError, ValueError) as exc:
                parser.exit(2, f"error: {exc}\n")
            print(
                f"rebuilt metadata index: {status.record_count} record(s) · "
                f"{status.source_file_count} canonical source file(s)"
            )
            return 0

        if args.index_command == "clear":
            try:
                removed = clear_metadata_index(workspace)
            except OSError as exc:
                parser.exit(2, f"error: {exc}\n")
            print("metadata index cleared" if removed else "metadata index already absent")
            return 0

        parser.error("unsupported index command")

    if args.command == "workbench":
        try:
            from .workbench import run_workbench

            run_workbench(
                workspace=args.workspace,
                port=args.port,
                open_browser=not args.no_browser,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            parser.exit(2, f"error: {exc}\n")
        return 0

    if args.command == "queue":
        try:
            from .review_queue_app import run_review_queue

            run_review_queue(
                workspace=args.workspace,
                port=args.port,
                open_browser=not args.no_browser,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            parser.exit(2, f"error: {exc}\n")
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
