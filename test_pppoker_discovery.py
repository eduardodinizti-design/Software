"""PPPoker table discovery: table vs lobby, PPPoker-only scope.

Unit test with injected windows and a mocked green-felt check. This is NOT a
real Windows capture: it validates the classification logic only."""
import unittest
from unittest.mock import patch

from table_discovery.windows import WindowInfo
from table_discovery import pppoker


def win(hwnd, process='PPPoker.exe', title='PPPoker', w=800, h=600, x=0, y=0):
    return WindowInfo(hwnd=hwnd, title=title, class_name='UnityWndClass', pid=1000 + hwnd,
                      process=process, rect=(x, y, x + w, y + h), minimized=False, maximized=False)


class DiscoveryTests(unittest.TestCase):
    def discover(self, windows, greens):
        with patch('table_discovery.detector.looks_like_green_table',
                   side_effect=lambda hwnd, ttl=3.0: hwnd in greens):
            return pppoker.discover_pppoker(windows)

    def test_table_has_felt_lobby_does_not(self):
        windows = [win(1), win(2)]  # both PPPoker.exe
        found = self.discover(windows, greens={1})  # only hwnd 1 shows felt
        self.assertEqual([t['hwnd'] for t in found['tables']], [1])
        self.assertEqual([l['hwnd'] for l in found['lobbies']], [2])
        self.assertEqual(found['tables'][0]['kind'], 'table')

    def test_non_pppoker_windows_are_ignored(self):
        windows = [win(1), win(5, process='chrome.exe'), win(6, process='XPoker.exe')]
        found = self.discover(windows, greens={1, 5, 6})
        self.assertEqual([t['hwnd'] for t in found['tables']], [1])
        self.assertEqual(found['lobbies'], [])

    def test_small_window_is_neither_table_nor_lobby(self):
        windows = [win(9, w=120, h=120)]  # below the 150x150 floor
        found = self.discover(windows, greens={9})
        self.assertEqual(found['tables'], [])
        self.assertEqual(found['lobbies'], [])

    def test_hwnds_helper_caps_and_lists(self):
        windows = [win(h) for h in range(1, 9)]  # 8 tables
        with patch('table_discovery.detector.looks_like_green_table', return_value=True):
            hwnds = pppoker.pppoker_table_hwnds(windows, max_tables=6)
        self.assertEqual(hwnds, [1, 2, 3, 4, 5, 6])

    def test_rect_and_identity_fields_present(self):
        found = self.discover([win(3, w=1024, h=768, x=-1920, y=0)], greens={3})
        t = found['tables'][0]
        self.assertEqual((t['x'], t['y'], t['w'], t['h']), (-1920, 0, 1024, 768))
        self.assertEqual(t['pid'], 1003)  # negative-origin multi-monitor case is legitimate


if __name__ == '__main__':
    unittest.main()
