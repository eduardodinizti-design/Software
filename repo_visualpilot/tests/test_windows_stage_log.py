"""Build evidence must survive a failed child, including non-ASCII diagnostics."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER=Path(__file__).resolve().parents[1]/'tools'/'run_windows_stage.py'


class WindowsStageLogTests(unittest.TestCase):
    def run_stage(self,code):
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'evidence with spaces'
            result=subprocess.run([sys.executable,str(RUNNER),'--name','tests','--output',str(output),
                                   '--','-c',code],capture_output=True,text=True,encoding='utf-8',timeout=10)
            report=json.loads((output/'tests.json').read_text(encoding='utf-8'))
            log=(output/'tests.log').read_text(encoding='utf-8')
            return result,report,log

    def test_failed_child_preserves_exit_code_and_both_streams(self):
        result,report,log=self.run_stage("import sys; print('saída'); print('erro de leitura: ação',file=sys.stderr); sys.exit(7)")
        self.assertEqual(result.returncode,7)
        self.assertEqual(report['state'],'failed')
        self.assertEqual(report['exit_code'],7)
        self.assertIn('saída',log)
        self.assertIn('erro de leitura: ação',log)
        self.assertIn('erro de leitura: ação',result.stdout)
        self.assertEqual(result.stderr,'')

    def test_success_and_exception_are_distinct_and_recorded(self):
        for code,expected in [("print('ok')",'passed'),("raise RuntimeError('simulated failure')",'failed')]:
            with self.subTest(expected=expected):
                result,report,log=self.run_stage(code)
                self.assertEqual(report['state'],expected)
                self.assertEqual(report['exit_code'],result.returncode)
                self.assertIn('finished_at',report)
                if expected=='failed':self.assertIn('Traceback',log)


if __name__=='__main__':unittest.main()
