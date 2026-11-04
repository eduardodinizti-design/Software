import unittest
from visualpilot.pppoker.window_geometry import attach_windows, capture_blocked


class HostGeometryTests(unittest.TestCase):
    def test_real_two_monitor_host_does_not_replace_table_crop(self):
        table = dict(box=[497, 113, 893, 1587], monitor=2, score=.9824)
        host = dict(box=[-1920, 0, 5760, 2160], pid=23528,
                    handle=1182180, title='PPPoker')
        result = attach_windows([table], [host])[0]
        self.assertEqual(result['capture_box'], table['box'])
        self.assertEqual(result['binding'], 'visual')
        self.assertIsNone(result['window_key'])
        unrelated = dict(box=[-1900, 10, 500, 500], pid=3,
                         handle=5, title='Other monitor')
        self.assertIsNone(capture_blocked(result, [unrelated, host], []))

    def test_matching_native_window_remains_bound(self):
        table = dict(box=[497, 113, 893, 1587])
        win = dict(box=[490, 100, 910, 1610], pid=23528,
                   handle=1182180, title='PPPoker')
        result = attach_windows([table], [win])[0]
        self.assertEqual(result['capture_box'], win['box'])
        self.assertEqual(result['binding'], 'native')
