# Algorithmic Data Parser

A small Python package for validating, sanitizing and exporting newline-delimited JSON (JSONL) metric records.

## Requirements

- Python 3.10+
- No third-party runtime dependencies

## Run from the repository root

```bash
PYTHONPATH=src python -m algorithmic_data_parser.cli examples/raw_logs.jsonl sanitized_output.json
```

Or install the package in editable mode:

```bash
python -m pip install -e .
algorithmic-data-parser examples/raw_logs.jsonl sanitized_output.json
```

Each non-empty input line must contain a JSON object. `device_id` must be a string.
`metric_reading` must be a finite number or a numeric string. Invalid records are
counted and skipped. The output is JSON with a summary and verified data array.

## Tests

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Design notes

- Processes records one line at a time; record accumulation is not required.
- Rejects NaN, Infinity, booleans as metrics, non-object JSON, and non-string IDs.
- Creates the output in the destination directory and replaces the destination
  atomically after successful parsing.
- Creates missing output directories automatically.
- Sanitizes identifiers conservatively while preserving letters, digits, spaces,
  underscores, periods and hyphens.

The output document itself necessarily grows with the number of valid records;
the parser's working memory is bounded by the largest input line plus I/O buffers.


## HTTP service

The package also exposes an optional authenticated HTTP API for Knight. See [HTTP API documentation](docs/HTTP_API.md) and run it with `python -m algorithmic_data_parser.service`. The service uses the same `AdvancedDataParser` implementation as the CLI and requires `KNIGHT_PARSER_API_KEY`.
