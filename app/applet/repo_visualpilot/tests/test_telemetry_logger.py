import json
import os
import unittest
from pathlib import Path

from visualpilot.pppoker.telemetry_logger import TelemetryLogger

class TestTelemetryLogger(unittest.TestCase):
    def setUp(self):
        self.test_log_dir = "logs/test_sessions"
        self.logger = TelemetryLogger(log_dir=self.test_log_dir)

    def tearDown(self):
        try:
            for p in Path(self.test_log_dir).glob("*.jsonl"):
                p.unlink()
            Path(self.test_log_dir).rmdir()
        except Exception:
            pass

    def test_log_event_and_export_summary(self):
        self.logger.log_event("TABLE_SCAN", "tbl-1", {"tables_count": 2, "blinds": "1/2"})
        self.logger.log_event("ACTION_DETECTED", "tbl-1", {"action": "YOUR_TURN", "pot": 45.0})

        summary = self.logger.export_summary()
        self.assertEqual(summary["total_events"], 2)
        self.assertIn("tbl-1", summary["unique_tables"])
        self.assertEqual(summary["event_breakdown"]["TABLE_SCAN"], 1)
        self.assertEqual(summary["event_breakdown"]["ACTION_DETECTED"], 1)

        # Verify file output
        self.assertTrue(Path(self.logger.session_file).exists())
        with open(self.logger.session_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed["event_type"], "TABLE_SCAN")
        self.assertEqual(parsed["table_id"], "tbl-1")

if __name__ == '__main__':
    unittest.main()
