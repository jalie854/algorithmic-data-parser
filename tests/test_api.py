"""Tests for the optional authenticated HTTP API layer."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from api import app as parser_api


class ParserApiTests(unittest.TestCase):
    def test_requires_configured_secret(self):
        with patch.object(parser_api, "API_KEY", ""):
            with self.assertRaises(HTTPException) as raised:
                parser_api.parse_jsonl(parser_api.ParseRequest(jsonl='{"device_id":"a"}'), "secret")
        self.assertEqual(raised.exception.status_code, 503)

    def test_rejects_wrong_secret(self):
        with patch.object(parser_api, "API_KEY", "correct-secret"):
            with self.assertRaises(HTTPException) as raised:
                parser_api.parse_jsonl(parser_api.ParseRequest(jsonl='{"device_id":"a"}'), "wrong")
        self.assertEqual(raised.exception.status_code, 401)

    def test_returns_valid_records_and_corruption_summary(self):
        sample = (
            '{"device_id":"sensor-01","metric_reading":12.5}\n'
            '{"device_id":"sensor-02","metric_reading":true}\n'
        )
        with patch.object(parser_api, "API_KEY", "correct-secret"):
            result = parser_api.parse_jsonl(
                parser_api.ParseRequest(jsonl=sample),
                "correct-secret",
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["total_lines"], 2)
        self.assertEqual(result["summary"]["total_successfully_parsed"], 1)
        self.assertEqual(result["summary"]["total_corrupted_records"], 1)
        self.assertEqual(result["data"][0]["validated_device"], "sensor-01")


if __name__ == "__main__":
    unittest.main()
