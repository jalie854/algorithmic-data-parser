# HTTP API

The parser remains a separate Python package and deployable service. Knight calls it over HTTPS; no parser implementation is copied into the Knight repository.

## Endpoints

- `GET /health` — unauthenticated service health check.
- `POST /v1/parse` — authenticated JSONL parsing endpoint.

The parse endpoint requires the `X-Knight-API-Key` header. Configure a high-entropy secret as `KNIGHT_PARSER_API_KEY` on the parser service and as `PARSER_SERVICE_API_KEY` in Knight. The values must match. The API returns HTTP 401 for an invalid key and HTTP 503 when the server-side key is not configured.

## Request

```http
POST /v1/parse
Content-Type: application/json
X-Knight-API-Key: <shared-secret>

{
  "jsonl": "{\"device_id\":\"sensor-01\",\"metric_reading\":12.5}\n{\"device_id\":\"sensor-02\",\"metric_reading\":\"7.2\"}"
}
```

The request body is limited to 2 MiB. The parser validates records using the same `AdvancedDataParser` implementation used by the command-line interface.

## Response

```json
{
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

Invalid individual records are counted and skipped, matching the CLI parser's behavior. Invalid HTTP/JSON requests return a 4xx response; upstream processing failures return 422.

## Run locally

```bash
python -m pip install -e .
KNIGHT_PARSER_API_KEY="replace-with-a-long-random-secret" python -m algorithmic_data_parser.service
```

The service listens on `0.0.0.0:$PORT` (default 8000). Run the existing package tests and HTTP service tests with:

```bash
python -m unittest discover -s tests -v
```

## Deploy separately

Build the repository's Dockerfile as its own web service. Configure `KNIGHT_PARSER_API_KEY`, expose the service over HTTPS, and set Knight's `PARSER_SERVICE_URL` and `PARSER_SERVICE_API_KEY`. Set the platform health-check path to `/health`. Do not commit either secret.
