import json
from pathlib import Path
from queue import Queue, Empty
import tempfile
import threading
from time import monotonic
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from visualpilot.pppoker.multitable import observe_tables, latest
from visualpilot.pppoker.observer.runtime import PerceptionSession


class IntegrationTests(unittest.TestCase):
    def test_actual_ocr_process_confirms_same_hand_and_saves_session(self):
        image = np.array(Image.open(Path(__file__).parent/'fixtures/actions/right_99.png').convert('RGB'))
        stop = threading.Event()
        events = Queue(128)
        with tempfile.TemporaryDirectory() as folder:
            session = PerceptionSession(folder, stop, events, workers=1)
            worker = threading.Thread(target=session.run, kwargs={'capture': False})
            worker.start()
            key = {'table_key': 'recorded-table', 'number': 1}
            # Reprodução contínua: uma captura única pode expirar durante o
            # carregamento do OCR, corretamente, e não representa uma mesa ao vivo.
            def feed():
                while not stop.is_set():
                    session.frames.put(key, image)
                    stop.wait(.2)
            feeder = threading.Thread(target=feed)
            feeder.start()
            found = None
            event_kinds = []
            deadline = monotonic() + 25
            try:
                while monotonic() < deadline:
                    try:
                        event = events.get(timeout=.5)
                    except Empty:
                        continue
                    if event['kind'] != 'reading':
                        if event['kind'] == 'partial_cards':
                            event_kinds.append('partial_cards')
                        continue
                    event_kinds.append('reading')
                    self.assertEqual(event['reading']['hero'], ['5c', '2s'])
                    if event['field_confirmation']['hero']['confirmed']:
                        found = event
                        break
                    session.frames.put(key, image)
                self.assertIsNotNone(found, 'Não houve confirmação de duas leituras da mesma mão')
            finally:
                stop.set()
                feeder.join(2)
                worker.join(20)
            self.assertFalse(worker.is_alive())
            journal = next(Path(folder).rglob('percepcao.jsonl'))
            records = [json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()]
            self.assertTrue(any(r['field_confirmation']['hero']['confirmed'] for r in records))
            self.assertIn('partial_cards', event_kinds)
            self.assertLess(event_kinds.index('partial_cards'), event_kinds.index('reading'))
            self.assertTrue(any(r.get('event') == 'PARTIAL_CARDS_READY' for r in records))
            self.assertEqual(records[-1]['study_context']['hero_cards'], ['5c', '2s'])
            self.assertFalse(records[-1]['study_context']['action_event_verified'])
            self.assertTrue(any(r['visual_evidence']['status'] == 'saved' for r in records))
            self.assertTrue((journal.parent / 'session.json').is_file())
            self.assertEqual(json.loads((journal.parent / 'metricas.json').read_text())['errors'], 0)

    def test_seventh_table_produces_explicit_error(self):
        stop = threading.Event()
        output = Queue(128)
        class Capture:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        def finder(stop, results, *args):
            latest(results, {'found': [{'monitor': 1, 'box': [i*100, 0, 80, 100], 'score': .99} for i in range(7)], 'reports': []})
        with tempfile.TemporaryDirectory() as folder:
            observe_tables(folder, stop, output, capture_factory=Capture, windows_reader=lambda: [],
                           discovery_fn=finder, max_tables=6)
        last = None
        while not output.empty(): last = output.get_nowait()
        self.assertTrue(last['finished'])
        self.assertIn('Mais de seis mesas', last['error'])
