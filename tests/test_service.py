import json
import os
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from algorithmic_data_parser.service import ParserRequestHandler, parse_jsonl


class ParserServiceTests(unittest.TestCase):
    def test_parse_jsonl_returns_summary_and_verified_records(self):
        result = parse_jsonl(
            '{"device_id":"sensor-01","metric_reading":12.5}\n'
            '{"device_id":"bad","metric_reading":"NaN"}\n'
        )
        self.assertEqual(result["summary"]["total_lines"], 2)
        self.assertEqual(result["summary"]["total_successfully_parsed"], 1)
        self.assertEqual(result["summary"]["total_corrupted_records"], 1)
        self.assertEqual(result["data"][0]["validated_device"], "sensor-01")

    def request(self, method, path, body=None, headers=None, api_key="test-secret"):
        server = ThreadingHTTPServer(("127.0.0.1", 0), ParserRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            request_headers = dict(headers or {})
            if api_key is not None:
                request_headers["X-Knight-API-Key"] = api_key
            if body is not None:
                request_headers["Content-Type"] = "application/json"
                request_headers["Content-Length"] = str(len(body))
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            connection.close()
            return response.status, payload
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_health_endpoint_is_available(self):
        status, payload = self.request("GET", "/health", api_key=None)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")

    def test_parse_requires_matching_shared_secret(self):
        body = json.dumps({"jsonl": '{"device_id":"sensor","metric_reading":1}'}).encode()
        with patch.dict(os.environ, {"KNIGHT_PARSER_API_KEY": "test-secret"}):
            status, payload = self.request("POST", "/v1/parse", body, api_key="wrong")
        self.assertEqual(status, 401)
        self.assertIn("error", payload)

    def test_parse_endpoint_returns_verified_records(self):
        body = json.dumps({"jsonl": '{"device_id":"sensor","metric_reading":1}'}).encode()
        with patch.dict(os.environ, {"KNIGHT_PARSER_API_KEY": "test-secret"}):
            status, payload = self.request("POST", "/v1/parse", body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["summary"]["total_successfully_parsed"], 1)
        self.assertEqual(payload["data"][0]["status"], "VERIFIED")

    def test_parse_rejects_oversized_body(self):
        with patch.dict(os.environ, {"KNIGHT_PARSER_API_KEY": "test-secret"}):
            status, payload = self.request(
                "POST", "/v1/parse", b"x" * (2 * 1024 * 1024 + 1)
            )
        self.assertEqual(status, 413)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
