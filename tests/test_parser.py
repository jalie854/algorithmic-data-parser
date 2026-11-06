import json
import tempfile
import unittest
from pathlib import Path

from algorithmic_data_parser import AdvancedDataParser


class ParserTests(unittest.TestCase):
    def test_valid_and_corrupt_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "raw.jsonl"
            output = Path(tmp) / "clean.json"
            source.write_text(
                '{"device_id":"sensor-01","metric_reading":12.5}\n'
                '{"device_id":"bad","metric_reading":"NaN"}\n'
                'not-json\n'
                '{"device_id":"sensor 02","metric_reading":0}\n',
                encoding="utf-8",
            )
            summary = AdvancedDataParser(source, output).process_data_stream()
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(summary.total_successfully_parsed, 2)
            self.assertEqual(summary.total_corrupted_records, 2)
            self.assertEqual(len(result["data"]), 2)
            self.assertEqual(result["data"][0]["validated_device"], "sensor-01")

    def test_rejects_same_input_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "same.txt"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                AdvancedDataParser(path, path).process_data_stream()

    def test_rejects_non_object_and_boolean_metric(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "raw.jsonl"
            output = Path(tmp) / "clean.json"
            source.write_text('[1,2]\n{"metric_reading":true}\n', encoding="utf-8")
            summary = AdvancedDataParser(source, output).process_data_stream()
            self.assertEqual(summary.total_corrupted_records, 2)


if __name__ == "__main__":
    unittest.main()
