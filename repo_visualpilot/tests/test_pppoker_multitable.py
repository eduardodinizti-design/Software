import json
import os
import tempfile
import threading
import unittest
from queue import Queue
from unittest.mock import patch

import numpy as np

from visualpilot.pppoker.core import Region
from visualpilot.pppoker.discovery import scan_monitors
from visualpilot.pppoker.history import History
from visualpilot.pppoker.multitable import latest, observe_tables, discover
from visualpilot.pppoker.table_registry import TableRegistry
from visualpilot.pppoker.window_geometry import attach_windows, capture_blocked, own_boxes


def candidates(count=8):
    return [{'monitor': 1 if i < 4 else 2, 'box': [i*100, 0, 80, 100],
             'score': .95, 'window_key': f'50:{i}', 'window_box': [i*100, 0, 80, 100]}
            for i in range(count)]


class TableTrackingTests(unittest.TestCase):
    def test_one_two_four_five_eight_and_reordered(self):
        for count in (1, 2, 4, 5, 8):
            registry = TableRegistry()
            rows, _ = registry.update(candidates(count))
            ids = {row['window_key']: row['table_key'] for row in rows}
            moved = list(reversed(candidates(count)))
            for item in moved:
                item.update(box=[-1900, 250, 90, 130], monitor=3)
            updated, retired = registry.update(moved)
            self.assertFalse(retired)
            self.assertEqual(ids, {r['window_key']: r['table_key'] for r in updated})

    def test_replacement_at_same_position_never_inherits_key(self):
        registry = TableRegistry()
        first, _ = registry.update(candidates(1))
        newer = candidates(1)
        newer[0]['window_key'] = 'new:window'
        rows, _ = registry.update(newer)
        active = [r for r in rows if r['visible']]
        self.assertNotEqual(first[0]['table_key'], active[0]['table_key'])
        registry.update(newer)
        rows, retired = registry.update(newer)
        self.assertEqual(len(rows), 1)
        self.assertEqual(retired[0]['table_key'], first[0]['table_key'])

    def test_no_handle_only_close_geometry_preserved(self):
        registry = TableRegistry()
        first = {'monitor': 1, 'box': [10, 20, 80, 100], 'score': .9}
        rows, _ = registry.update([first])
        key = rows[0]['table_key']
        rows, _ = registry.update([dict(first, box=[12, 21, 80, 100])])
        self.assertEqual(key, rows[0]['table_key'])
        rows, _ = registry.update([dict(first, box=[500, 20, 80, 100])])
        self.assertNotEqual(key, next(r['table_key'] for r in rows if r['visible']))

    def test_duplicate_native_window_is_one_table(self):
        rows, _ = TableRegistry().update(candidates(1)*2)
        self.assertEqual(len(rows), 1)

    def test_distinct_tables_in_shared_window_survive_reorder_and_move(self):
        registry = TableRegistry()
        found = candidates(2)
        for item in found:
            item.update(window_key='shared', window_box=[0, 0, 180, 100])
        first, _ = registry.update(found)
        self.assertEqual(len(first), 2)
        ids = [r['table_key'] for r in first]
        moved = []
        for item in reversed(found):
            x, y, w, h = item['box']
            moved.append(dict(item, box=[x-1000, y+40, w, h], monitor=2,
                              window_box=[-1000, 40, 180, 100]))
        rows, _ = registry.update(moved)
        self.assertEqual([r['table_key'] for r in rows], ids)
        self.assertEqual(len([r for r in rows if r['visible']]), 2)

    def test_one_region_leaves_shared_window_other_keeps_key(self):
        registry = TableRegistry()
        found = candidates(2)
        for item in found:
            item.update(window_key='shared', window_box=[0, 0, 180, 100])
        first, _ = registry.update(found)
        rows, _ = registry.update([found[1]])
        self.assertEqual(next(r['table_key'] for r in rows if r['visible']), first[1]['table_key'])

    def test_missing_binding_falls_back_without_stale_native_geometry(self):
        registry = TableRegistry()
        first, _ = registry.update(candidates(1))
        visual = dict(candidates(1)[0], window_key=None, window_box=None, binding='visual')
        rows, _ = registry.update([visual])
        self.assertEqual(rows[0]['table_key'], first[0]['table_key'])
        self.assertIsNone(rows[0]['window_key'])
        self.assertIsNone(rows[0]['window_box'])
        rows, _ = registry.update(candidates(1))
        self.assertEqual(rows[0]['table_key'], first[0]['table_key'])

    def test_covered_native_table_keeps_identity_until_window_disappears(self):
        registry = TableRegistry()
        first, _ = registry.update(candidates(1))
        for _ in range(5):
            rows, retired = registry.update([], ['50:0'])
            self.assertFalse(retired)
            self.assertFalse(rows[0]['visible'])
        back, _ = registry.update(candidates(1))
        self.assertEqual(back[0]['table_key'], first[0]['table_key'])
        for _ in range(3):
            rows, retired = registry.update([], [])
        self.assertEqual(rows, [])
        self.assertEqual(retired[0]['table_key'], first[0]['table_key'])


class WindowTests(unittest.TestCase):
    def test_own_preview_mask_negative_monitor_origin(self):
        class Capture:
            def monitors(self):
                return [Region(-100, -50, 200, 100)]
            def grab(self, region):
                return np.full((100, 200, 3), 255, dtype=np.uint8)
        def detector(rgb, diagnostics):
            self.assertTrue((rgb[10:30, 20:60] == 0).all())
            self.assertTrue((rgb[:10] == 255).all())
            return []
        scan_monitors(Capture(), threading.Event(), detector, [(-80, -40, 40, 20)])

    def test_windows_attachment_and_cover_or_move(self):
        item = candidates(1)[0]
        item['box'] = [5, 8, 70, 88]
        win = {'pid': 50, 'handle': 0, 'box': [0, 0, 80, 100], 'title': 'PPPoker - v228'}
        attached = attach_windows([item], [win])[0]
        self.assertEqual(attached['window_key'], '50:0')
        self.assertEqual(attached['capture_box'], win['box'])
        item = attached
        self.assertIsNone(capture_blocked(item, [win], []))
        self.assertIn('movida', capture_blocked(item, [dict(win, box=[1, 0, 80, 100])], []))
        overlay = {'pid': 51, 'handle': 1, 'box': [1, 1, 20, 20], 'title': 'Other'}
        self.assertIn('coberta', capture_blocked(item, [overlay, win], []))
        self.assertIn('indisponível', capture_blocked(item, [], []))
        self.assertIn('Visual Pilot', capture_blocked(item, [win], [(1, 1, 20, 20)]))

    def test_self_preview_never_attached_as_poker(self):
        item = {'box': [0, 0, 80, 100]}
        win = {'pid': os.getpid(), 'handle': 1, 'box': item['box'], 'title': 'Visual Pilot'}
        self.assertEqual(own_boxes([win]), [item['box']])
        self.assertIsNone(attach_windows([item], [win])[0]['window_key'])

    def test_missing_or_unrecognized_native_title_keeps_visual_candidate(self):
        item = {'monitor': 2, 'box': [0, 0, 80, 100]}
        for windows in ([], [{'pid': 50, 'handle': 2, 'box': item['box'], 'title': ''}]):
            found = attach_windows([item], windows)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]['binding'], 'visual')
            self.assertTrue(found[0]['binding_reason'])


class MultiTableWorkerTests(unittest.TestCase):
    def test_discovery_preserves_both_candidates_without_native_titles(self):
        stop = threading.Event()
        class StopQueue(Queue):
            def put_nowait(self, value):
                super().put_nowait(value)
                stop.set()
        class Capture:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        output = StopQueue(maxsize=1)
        reports = [{'monitor': 1, 'state': 'captured', 'tables': 2}]
        with patch('visualpilot.pppoker.multitable.scan_monitors', return_value=(reports, candidates(2))):
            discover(stop, output, lambda: (), Capture, lambda: [])
        result = output.get()
        self.assertEqual(len(result['found']), 2)
        self.assertEqual(result['reports'][0]['visual_bindings'], 2)
        self.assertEqual(result['reports'][0]['native_bindings'], 0)

    def test_queue_always_keeps_only_newest_snapshot(self):
        queue = Queue(maxsize=1)
        for i in range(100):
            latest(queue, i)
        self.assertEqual(queue.qsize(), 1)
        self.assertEqual(queue.get(), 99)

    def test_eight_separate_tables_one_capture_error_does_not_stop_others(self):
        stop = threading.Event()
        seen = []
        def discover(cancel, results, *args):
            latest(results, {'found': candidates(), 'reports': []})
        class Capture:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def grab(self, region):
                seen.append(region.left)
                if len(seen) == 8:
                    stop.set()
                if region.left == 200:
                    raise OSError('Mesa indisponível no teste')
                return np.zeros((100, 80, 3), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as root:
            queue = Queue(maxsize=1)
            observe_tables(root, stop, queue, interval=.001, capture_factory=Capture,
                           windows_reader=lambda: None, discovery_fn=discover)
            final = queue.get()
            self.assertTrue(final['finished'])
            self.assertIsNone(final['error'])
            self.assertEqual(seen, list(range(0, 800, 100)))
            db = History(root)
            rows = [json.loads(r[0]) for r in db.db.execute('SELECT payload FROM observations')]
            tables = [row for row in rows if 'table_key' in row]
            self.assertEqual(len({r['table_key'] for r in tables}), 8)
            self.assertEqual(sum(r['state'] == 'capturando' for r in tables), 7)
            self.assertEqual(sum(r['state'] == 'erro de captura' for r in tables), 1)
            self.assertEqual(db.sessions()[0][2], 'stopped')
            db.close()

    def test_discovery_error_closes_session(self):
        def discover(cancel, results, *args):
            latest(results, {'error': 'falha', 'reports': [], 'found': []})
        class Capture:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        with tempfile.TemporaryDirectory() as root:
            queue = Queue(maxsize=1)
            observe_tables(root, threading.Event(), queue, interval=.001,
                           capture_factory=Capture, windows_reader=lambda: None,
                           discovery_fn=discover)
            self.assertEqual(queue.get()['error'], 'falha')
            db = History(root)
            self.assertEqual(db.sessions()[0][2], 'error')
            db.close()
