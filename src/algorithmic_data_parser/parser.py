"""Robust, memory-efficient parser for newline-delimited JSON metrics."""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class ParseSummary:
    total_lines: int
    total_successfully_parsed: int
    total_corrupted_records: int
    output_path: str


class AdvancedDataParser:
    """Stream, sanitize, validate and export JSONL computational metrics."""

    _SAFE_DEVICE_CHARS = re.compile(r"[^a-zA-Z0-9 _.-]+")

    def __init__(self, input_filepath: str | os.PathLike[str],
                 output_filepath: str | os.PathLike[str]) -> None:
        self.input_path = Path(input_filepath)
        self.output_path = Path(output_filepath)
        # Kept for compatibility; records are deliberately not accumulated here.
        self.processed_records: list[dict[str, Any]] = []
        self.corruption_count = 0
        self.total_lines = 0
        self.success_count = 0

    @classmethod
    def sanitize_string(cls, raw_string: str) -> str:
        """Keep a conservative set of printable identifier characters."""
        return cls._SAFE_DEVICE_CHARS.sub("", raw_string).strip() or "UNKNOWN"

    @staticmethod
    def _validated_record(payload: Any, line_number: int) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("each JSONL record must be an object")
        raw_device = payload.get("device_id", "UNKNOWN")
        if not isinstance(raw_device, str):
            raise ValueError("device_id must be a string")
        raw_metric = payload.get("metric_reading", 0.0)
        if isinstance(raw_metric, bool) or not isinstance(raw_metric, (int, float, str)):
            raise ValueError("metric_reading must be numeric")
        try:
            metric = float(raw_metric)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("metric_reading must be numeric") from exc
        if not math.isfinite(metric):
            raise ValueError("metric_reading must be finite")
        return {
            "record_id": line_number,
            "validated_device": AdvancedDataParser.sanitize_string(raw_device),
            "metric": metric,
            "status": "VERIFIED",
        }

    def _iter_valid_records(self, source) -> Iterator[dict[str, Any]]:
        for line_number, raw_line in enumerate(source, 1):
            self.total_lines = line_number
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
                record = self._validated_record(payload, line_number)
            except (json.JSONDecodeError, ValueError, TypeError, OverflowError):
                self.corruption_count += 1
                continue
            self.success_count += 1
            yield record

    def process_data_stream(self) -> ParseSummary:
        """Parse incrementally and atomically replace the destination on success."""
        if not self.input_path.is_file():
            raise FileNotFoundError(f"Input file does not exist or is not a file: {self.input_path}")
        if self.input_path.resolve() == self.output_path.resolve():
            raise ValueError("Input and output paths must be different")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.processed_records = []
        self.corruption_count = self.total_lines = self.success_count = 0
        records_name: str | None = None
        final_name: str | None = None
        try:
            with self.input_path.open("r", encoding="utf-8") as source:
                with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=self.output_path.parent,
                    prefix=f".{self.output_path.name}.records.", suffix=".tmp", delete=False
                ) as records_file:
                    records_name = records_file.name
                    first = True
                    for record in self._iter_valid_records(source):
                        if not first:
                            records_file.write(",\n")
                        records_file.write("    " + json.dumps(record, ensure_ascii=False, allow_nan=False))
                        first = False

            summary = {
                "total_lines": self.total_lines,
                "total_successfully_parsed": self.success_count,
                "total_corrupted_records": self.corruption_count,
            }
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.output_path.parent,
                prefix=f".{self.output_path.name}.", suffix=".tmp", delete=False
            ) as final_file:
                final_name = final_file.name
                final_file.write("{\n  \"summary\": ")
                json.dump(summary, final_file, ensure_ascii=False, indent=4)
                final_file.write(',\n  "data": [\n')
                with open(records_name, "r", encoding="utf-8") as records_file:
                    while chunk := records_file.read(1024 * 1024):
                        final_file.write(chunk)
                final_file.write("\n  ]\n}\n")
                final_file.flush()
                os.fsync(final_file.fileno())

            os.replace(final_name, self.output_path)
            final_name = None
            return ParseSummary(self.total_lines, self.success_count,
                                self.corruption_count, str(self.output_path))
        finally:
            for temporary_path in (records_name, final_name):
                if temporary_path and os.path.exists(temporary_path):
                    os.unlink(temporary_path)

    def export_clean_metrics(self) -> ParseSummary:
        """Compatibility alias for the streaming export method."""
        return self.process_data_stream()
