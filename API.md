# Algorithmic Data Parser HTTP API

This repository remains independently usable as a Python package and CLI. The HTTP service is an optional integration layer for Knight and other trusted backend clients.

## Run locally

Python 3.10+ is required.

```bash
python -m pip install -e .
python -m pip install -r requirements-api.txt
```

Set a long random API key in the service environment:

```bash
# Linux/macOS example
export KNIGHT_PARSER_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn api.app:app --host 127.0.0.1 --port 8000
```

The service exposes an unauthenticated liveness endpoint at `GET /health`. Parsing requires the API key and is available at `POST /v1/parse`.

## Endpoint

### `POST /v1/parse`

Headers:

- `Content-Type: application/json`
- `X-Knight-API-Key: <shared-secret>`

Request:

```json
{
  "jsonl": "{\"device_id\":\"sensor-01\",\"metric_reading\":12.5}\n{\"device_id\":\"sensor-02\",\"metric_reading\":\"7.2\"}"
}
```

Successful response:

```json
{
  "success": true,
  "summary": {
    "total_lines": 2,
    "total_successfully_parsed": 2,
    "total_corrupted_records": 0
  },
  "data": [
    {
      "record_id": 1,
      "validated_device": "sensor-01",
      "metric": 12.5,
      "status": "VERIFIED"
    }
  ]
}
```

The example response's `data` array contains one object per valid non-empty line. Invalid records are skipped and counted in `total_corrupted_records`. Blank lines count toward `total_lines` but are not treated as corrupt records.

## Limits and errors

- Maximum request body defaults to 2 MiB; override with `PARSER_MAX_INPUT_BYTES`.
- `401`: missing or invalid shared secret.
- `413`: request exceeds the configured byte limit.
- `422`: request body or parsing operation is invalid.
- `503`: the service has no `KNIGHT_PARSER_API_KEY` configured.
- Temporary input/output files are created in an isolated temporary directory and removed after the request.
- The service never accepts client-supplied filesystem paths.
- Deploy behind HTTPS. Store the shared key only in the service's and Knight's server-side environment variables. Never put it in frontend code, source control, or logs.

## Deploy as a separate Render web service

Create a new Web Service from this repository, leaving the Knight service unchanged:

- Runtime: Docker
- Dockerfile: `Dockerfile`
- Health check path: `/health`
- Environment variable: `KNIGHT_PARSER_API_KEY` (generate a unique high-entropy secret)
- Optional: `PARSER_MAX_INPUT_BYTES` (default 2097152)

Copy the deployed service's HTTPS base URL into Knight's `PARSER_SERVICE_URL` and set the exact same secret as `PARSER_SERVICE_API_KEY` in Knight's environment. Do not include a trailing slash in the URL.

## Existing CLI remains available

```bash
PYTHONPATH=src python -m algorithmic_data_parser.cli examples/raw_logs.jsonl sanitized_output.json
```
