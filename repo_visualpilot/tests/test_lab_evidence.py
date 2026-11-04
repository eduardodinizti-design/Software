from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lab_evidence import session_directory


class LabEvidenceTests(unittest.TestCase):
    def test_failed_session_preserves_diagnostics_and_original_assertion(self):
        with tempfile.TemporaryDirectory() as root, \
                patch('lab_evidence.EVIDENCE_ROOT', Path(root)), \
                redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(AssertionError, 'Nenhuma leitura completa'):
                with session_directory('pipeline') as folder:
                    source = Path(folder)
                    (source/'rejeicoes.jsonl').write_text('{"reason":"expired_source"}\n', encoding='utf-8')
                    (source/'metricas.json').write_text('{"errors":0}', encoding='utf-8')
                    raise AssertionError('Nenhuma leitura completa')
            self.assertFalse(source.exists())
            evidence = next(Path(root).glob('pipeline-*'))
            self.assertEqual((evidence/'rejeicoes.jsonl').read_text(encoding='utf-8'),
                             '{"reason":"expired_source"}\n')
            self.assertEqual((evidence/'metricas.json').read_text(encoding='utf-8'), '{"errors":0}')
            self.assertIn('LAB_REJECTION', output.getvalue())

    def test_copy_failure_does_not_mask_the_pipeline_failure(self):
        with patch('lab_evidence.shutil.copytree', side_effect=OSError('disk full')), \
                redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(AssertionError, 'original failure'):
                with session_directory('pipeline'):
                    raise AssertionError('original failure')
            self.assertIn('LAB_EVIDENCE_ERROR OSError', output.getvalue())
