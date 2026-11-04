import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[2]/'tools/check_control_transition.py'
spec=importlib.util.spec_from_file_location('control_transition',path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ControlTransition(unittest.TestCase):
    def test_replay_records_missing_detection_as_failure(self):
        report=module.run_sequence()
        # Acceptance follows observable continuity, never test-run success alone.
        steps=report['steps']
        expected=all(len(s['tables'])==1 for s in steps)
        if expected:
            expected=len({s['tables'][0]['id'] for s in steps})==1
        self.assertEqual(report['passed'],expected)
        for step in steps:
            self.assertEqual(step['active_count'],len(step['tables']))

    def test_exact_frame_return_recovers_without_duplicate(self):
        report=module.run_sequence()
        first,last=report['steps'][0],report['steps'][-1]
        self.assertEqual(len(first['tables']),1)
        self.assertEqual(len(last['tables']),1)
        self.assertEqual(first['tables'][0]['id'],last['tables'][0]['id'])
