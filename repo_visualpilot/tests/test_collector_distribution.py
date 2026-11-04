"""The package entry script must import and perform real v2 transport."""
from pathlib import Path
import runpy
import sys
import tempfile
import unittest

from tools.validate_collector_distribution import validate

ENTRY=Path(__file__).resolve().parents[1]/'visualpilot/pppoker/stream_node.py'


class CollectorEntryTests(unittest.TestCase):
    def test_entry_script_imports_without_package_context(self):
        namespace=runpy.run_path(str(ENTRY),run_name='collector_entry_probe')
        self.assertEqual(namespace['VERSION'],2)
        self.assertTrue(callable(namespace['main']))


class CollectorTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_entry_process_sends_two_verified_frames_from_clean_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            result=await validate([sys.executable,str(ENTRY)],folder,expect_frozen=False)
            self.assertEqual(result['status'],'passed',result)
            self.assertEqual(result['transport_metrics']['accepted_verified'],2)
            self.assertEqual([frame['sequence'] for frame in result['frames']],[1,2])
            self.assertFalse(result['collector']['frozen'])
            self.assertTrue((Path(folder)/'collector-transport-validation.json').is_file())

    async def test_success_report_and_zero_exit_cannot_replace_actual_transport(self):
        code="""import json,sys
from pathlib import Path
nonce=sys.argv[sys.argv.index('--nonce')+1]
report=Path(sys.argv[sys.argv.index('--report')+1])
report.write_text(json.dumps(dict(status='passed',nonce=nonce,protocol=2,
    acknowledged_frames=2,frozen=False,collector_session='fake')),encoding='utf-8')
"""
        with tempfile.TemporaryDirectory() as folder:
            result=await validate([sys.executable,'-c',code],folder,expect_frozen=False)
            self.assertEqual(result['status'],'failed')
            self.assertEqual(result['frames'],[])
            self.assertIn('did not accept',result['error'])


if __name__=='__main__':unittest.main()
