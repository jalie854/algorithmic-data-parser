"""Command-line entry point."""
import argparse
import json

from .parser import AdvancedDataParser


def main() -> int:
    cli = argparse.ArgumentParser(description="Validate and sanitize JSONL metric records.")
    cli.add_argument("input", help="Path to newline-delimited JSON input")
    cli.add_argument("output", help="Path for the cleaned JSON output")
    args = cli.parse_args()

    try:
        summary = AdvancedDataParser(args.input, args.output).process_data_stream()
    except (OSError, ValueError) as exc:
        cli.error(str(exc))
    print(json.dumps({
        "total_lines": summary.total_lines,
        "total_successfully_parsed": summary.total_successfully_parsed,
        "total_corrupted_records": summary.total_corrupted_records,
        "output_path": summary.output_path,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
