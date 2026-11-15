"""Small authenticated HTTP API for the standalone JSONL parser."""
from __future__ import annotations

import hmac
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .parser import AdvancedDataParser

MAX_BODY_BYTES = 2 * 1024 * 1024


def parse_jsonl(jsonl: str) -> dict[str, Any]:
    """Parse JSONL in an isolated temporary directory and return verified records."""
    with tempfile.TemporaryDirectory(prefix="algorithmic-parser-") as temp_dir:
        root = Path(temp_dir)
        source = root / "input.jsonl"
        output = root / "output.json"
        source.write_text(jsonl, encoding="utf-8")
        summary = AdvancedDataParser(source, output).process_data_stream()
        result = json.loads(output.read_text(encoding="utf-8"))
        return {
            "summary": {
                "total_lines": summary.total_lines,
                "total_successfully_parsed": summary.total_successfully_parsed,
                "total_corrupted_records": summary.total_corrupted_records,
            },
            "data": result["data"],
        }


class ParserRequestHandler(BaseHTTPRequestHandler):
    server_version = "AlgorithmicDataParser/1.0"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "algorithmic-data-parser"})
            return
        self._send_json(404, {"error": "Not found."})

    def do_POST(self) -> None:
        if self.path != "/v1/parse":
            self._send_json(404, {"error": "Not found."})
            return

        configured_key = os.environ.get("KNIGHT_PARSER_API_KEY", "")
        supplied_key = self.headers.get("X-Knight-API-Key", "")
        if not configured_key:
            self._send_json(503, {"error": "Parser API authentication is not configured."})
            return
        if not supplied_key or not hmac.compare_digest(supplied_key, configured_key):
            self._send_json(401, {"error": "Invalid API credentials."})
            return

        content_length = self.headers.get("Content-Length")
        try:
            body_size = int(content_length or "")
        except ValueError:
            self._send_json(411, {"error": "A valid Content-Length header is required."})
            return
        if body_size < 1:
            self._send_json(400, {"error": "Request body is required."})
            return
        if body_size > MAX_BODY_BYTES:
            self._send_json(413, {"error": "Input exceeds the 2 MiB limit."})
            return

        try:
            raw_body = self.rfile.read(body_size)
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "Request body must be valid UTF-8 JSON."})
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("jsonl"), str):
            self._send_json(400, {"error": "jsonl must be a string."})
            return
        if not payload["jsonl"].strip():
            self._send_json(400, {"error": "jsonl must not be empty."})
            return

        try:
            self._send_json(200, parse_jsonl(payload["jsonl"]))
        except (OSError, ValueError):
            self._send_json(422, {"error": "The JSONL input could not be processed."})

    def log_message(self, format: str, *args: Any) -> None:
        # Never log request bodies, API keys, or potentially sensitive records.
        super().log_message(format, *args)


def main() -> None:
    host = os.environ.get("PARSER_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ParserRequestHandler)
    server.daemon_threads = True
    print(f"Algorithmic Data Parser API listening on {host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
