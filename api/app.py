"""Private HTTP API for the Algorithmic Data Parser."""
from __future__ import annotations

import hmac
import json
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from algorithmic_data_parser.parser import AdvancedDataParser

MAX_INPUT_BYTES = int(os.getenv("PARSER_MAX_INPUT_BYTES", str(2 * 1024 * 1024)))
API_KEY = os.getenv("KNIGHT_PARSER_API_KEY", "")

app = FastAPI(
    title="Algorithmic Data Parser API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jsonl: str = Field(min_length=1, description="Newline-delimited JSON text")


def authorize(provided_key: str | None) -> None:
    if not API_KEY:
        raise HTTPException(status_code=503, detail="Parser API is not configured")
    if not provided_key or not hmac.compare_digest(provided_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API credentials")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "algorithmic-data-parser"}


@app.post("/v1/parse")
def parse_jsonl(
    request: ParseRequest,
    x_knight_api_key: str | None = Header(default=None),
) -> dict:
    authorize(x_knight_api_key)
    payload = request.jsonl.encode("utf-8")
    if len(payload) > MAX_INPUT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Input exceeds the {MAX_INPUT_BYTES}-byte limit",
        )

    try:
        with tempfile.TemporaryDirectory(prefix="knight-parser-") as temp_dir:
            root = Path(temp_dir)
            source = root / "input.jsonl"
            destination = root / "validated.json"
            source.write_bytes(payload)
            summary = AdvancedDataParser(source, destination).process_data_stream()
            result = json.loads(destination.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Input could not be processed") from exc

    return {
        "success": True,
        "summary": {
            "total_lines": summary.total_lines,
            "total_successfully_parsed": summary.total_successfully_parsed,
            "total_corrupted_records": summary.total_corrupted_records,
        },
        "data": result["data"],
    }
