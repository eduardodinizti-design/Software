import json
from pathlib import Path
from queue import Queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np

from visualpilot.pppoker.observer.runtime import PerceptionSession


class ErrorJournalTests(unittest.TestCase):
    def test_failed_obsolete_job_keeps_exception_without_publishing_old_reading(self):
        entered, release, stop = threading.Event(), threading.Event(), threading.Event()

        class Service:
            def __init__(self, **kwargs):
                pass

            def call(self, kind, image, stopped):
                entered.set()
                release.wait(3)
                raise RuntimeError('diagnóstico de OCR preservado')

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as root, patch(
                'visualpilot.pppoker.observer.runtime.OCRService', Service):
            session = PerceptionSession(root, stop, Queue(128), workers=1)
            thread = threading.Thread(target=session.run, kwargs={'capture': False})
            thread.start()
            try:
                item = dict(table_key='table', number=1)
                image = np.zeros((100, 50, 3), dtype=np.uint8)
                session.frames.put(item, image)
                self.assertTrue(entered.wait(3))
                changed = image.copy()
                changed[80:90, 20:35] = 255
                session.frames.put(item, changed)
                release.set()
                deadline = time.monotonic() + 3
                while not session.metrics.get('discarded_results') and time.monotonic() < deadline:
                    stop.wait(.02)
                self.assertTrue(session.metrics.get('discarded_results'))
            finally:
                release.set()
                stop.set()
                thread.join(5)
            self.assertFalse(thread.is_alive())
            path = next(Path(root).rglob('erros_ocr.jsonl'))
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(rows[0]['table'], 'table')
            self.assertEqual(rows[0]['error_type'], 'RuntimeError')
            self.assertEqual(rows[0]['error'], 'diagnóstico de OCR preservado')
            self.assertEqual(rows[0]['job_kind'], 'text')
            self.assertEqual(rows[0]['generation'], 1)
            rejections = [json.loads(line) for line in
                          next(Path(root).rglob('rejeicoes.jsonl')).read_text(encoding='utf-8').splitlines()]
            self.assertIn(rejections[0]['reason'], ('newer_frame_pending', 'superseded_generation'))
