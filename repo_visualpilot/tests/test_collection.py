import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from visualpilot.collector import Collector, field_statuses
from visualpilot.vision import Profile, detect_tables, infer_stage, observe, pending, read_card


def fixture(root):
    rng = np.random.default_rng(31)
    anchor = rng.integers(0, 256, (12, 16), dtype=np.uint8)
    ace = rng.integers(0, 256, (16, 12), dtype=np.uint8)
    king = rng.integers(0, 256, (16, 12), dtype=np.uint8)
    empty = rng.integers(0, 256, (16, 12), dtype=np.uint8)
    for name, image in [('anchor', anchor), ('ace', ace), ('king', king), ('empty', empty)]:
        cv2.imwrite(str(root / f'{name}.png'), image)
    regions = {f'c{i}': [8 + i * 18, 45, 12, 16] for i in range(7)}
    data = {'version': 1, 'table_size': [160, 90], 'anchor_image': 'anchor.png',
            'anchor_offset': [5, 5], 'regions': regions, 'hero_cards': ['c0', 'c1'],
            'board_cards': [f'c{i}' for i in range(2, 7)],
            'card_templates': {'As': 'ace.png', 'Kh': 'king.png'},
            'empty_slot_templates': {f'c{i}': 'empty.png' for i in range(2, 7)}}
    (root / 'profile.json').write_text(json.dumps(data), encoding='utf-8')
    table = np.full((90, 160, 3), 20, dtype=np.uint8)
    table[5:17, 5:21] = cv2.cvtColor(anchor, cv2.COLOR_GRAY2BGR)
    for i in range(7):
        sample = ace if i == 0 else king if i == 1 else empty
        x, y, w, h = regions[f'c{i}']
        table[y:y+h, x:x+w] = cv2.cvtColor(sample, cv2.COLOR_GRAY2BGR)
    return Profile.load(root / 'profile.json'), table


class VisionTests(unittest.TestCase):
    def test_ambiguous_and_missing_models_stay_pending(self):
        image = np.random.default_rng(1).integers(0, 255, (16, 12), dtype=np.uint8)
        self.assertEqual(read_card(image, {})['status'], 'pending')
        self.assertEqual(read_card(image, {'As': image, 'Kh': image})['status'], 'pending')

    def test_stages_require_empty_slot_evidence(self):
        card = lambda value: {'status': 'recognized', 'value': value}
        empty = {'status': 'empty', 'value': None}
        board = [card('As'), card('Kh'), card('2c'), pending(), pending()]
        self.assertEqual(infer_stage(board, pending())['status'], 'pending')
        self.assertEqual(infer_stage(board[:3] + [empty, empty], pending())['value'], 'flop')
        self.assertEqual(infer_stage([empty] * 5, pending())['value'], 'preflop')
        self.assertEqual(infer_stage(board[:3] + [card('3d'), empty], pending())['value'], 'turn')
        self.assertEqual(infer_stage(board[:3] + [card('3d'), card('4s')], pending())['value'], 'river')

    def test_profile_detection_and_duplicate_cards(self):
        with tempfile.TemporaryDirectory() as folder:
            profile, table = fixture(Path(folder))
            screen = np.zeros((210, 400, 3), dtype=np.uint8)
            screen[10:100, 20:180] = table
            screen[110:200, 210:370] = table
            self.assertEqual(detect_tables(screen, profile), [(20, 10, 160, 90), (210, 110, 160, 90)])
            result = observe(table, profile)
            self.assertEqual([v['value'] for v in result['hero_cards']], ['As', 'Kh'])
            self.assertEqual(result['stage']['value'], 'preflop')
            x, y, w, h = profile.data['regions']['c1']
            x0, y0, _, _ = profile.data['regions']['c0']
            table[y:y+h, x:x+w] = table[y0:y0+h, x0:x0+w]
            result = observe(table, profile)
            self.assertTrue(all(v['status'] == 'pending' for v in result['hero_cards']))


class CollectionTests(unittest.TestCase):
    def test_replay_persistence_and_no_stale_carryover(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile, table = fixture(root)
            replay = root / 'replay'
            replay.mkdir()
            for i in range(3):
                image = table.copy()
                if i == 2:
                    x, y, w, h = profile.data['regions']['c0']
                    image[y:y+h, x:x+w] = 0
                cv2.imwrite(str(replay / f'{i}.png'), image)
            collector = Collector(profile, root / 'sessions', replay, interval=.2)
            collector.start()
            collector.join(10)
            self.assertFalse(collector.thread.is_alive())
            state = collector.snapshot()
            self.assertIsNone(state['error'])
            path = Path(state['session'])
            records = [json.loads(line) for line in (path / 'observations.jsonl').read_text().splitlines()]
            self.assertEqual(len(records), 3)
            self.assertEqual(len({r['table_track_id'] for r in records}), 1)
            self.assertIsNone(records[0]['hero_cards'][0]['value'])
            self.assertEqual(records[1]['hero_cards'][0]['value'], 'As')
            self.assertIsNone(records[-1]['hero_cards'][0]['value'])
            self.assertTrue((path / records[0]['evidence']).is_file())
            self.assertEqual(json.loads((path / 'metrics.json').read_text())['cycles'], 3)
            self.assertTrue((path / 'session.json').is_file())

    def test_two_monitors_do_not_share_table_tracks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile, table = fixture(root)

            class Source:
                calls = 0
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def frames(self):
                    self.calls += 1
                    if self.calls > 1: raise StopIteration
                    return [(str(i), {'left': offset, 'top': 0}, table) for i, offset in [(1, -160), (2, 0)]]

            with patch('visualpilot.collector.ScreenSource', Source):
                collector = Collector(profile, root / 'sessions', interval=.2)
                collector.start()
                collector.join(10)
            self.assertIsNone(collector.snapshot()['error'])
            tables = collector.snapshot()['tables']
            self.assertEqual(len(tables), 2)
            self.assertEqual({v['monitor'] for v in tables.values()}, {'1', '2'})
            self.assertEqual({v['bounds']['left'] for v in tables.values()}, {-160, 0})

    def test_capture_failure_is_reported_and_session_is_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile, _ = fixture(root)
            with patch('visualpilot.collector.ScreenSource.__enter__', side_effect=OSError('captura indisponível')):
                collector = Collector(profile, root / 'sessions')
                collector.start()
                collector.join(10)
            state = collector.snapshot()
            self.assertEqual(state['status'], 'error')
            self.assertIn('captura indisponível', state['error'])
            self.assertTrue((Path(state['session']) / 'metrics.json').is_file())


if __name__ == '__main__':
    unittest.main()
