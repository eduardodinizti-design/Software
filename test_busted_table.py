import unittest
from table_reading.busted_table import detect_busted, BustedConfirmer


class TestDetectBusted(unittest.TestCase):
    def test_rank_gt_left_is_busted(self):
        # caso ao vivo 18/11: TURBO PKO lia 57/52
        d = detect_busted(57, 52)
        self.assertEqual(d['status'], 'BUSTED')
        self.assertEqual(d['reason'], 'RANK_GT_LEFT')

    def test_rank_le_left_is_alive(self):
        self.assertEqual(detect_busted(30, 36)['status'], 'ALIVE')
        self.assertEqual(detect_busted(52, 52)['status'], 'ALIVE')   # igual = vivo

    def test_live_signal_vetoes_bust(self):
        # mesmo com rank>left, se há vida (cartas/ação) NUNCA busta
        self.assertEqual(detect_busted(57, 52, has_action=True)['status'], 'ALIVE')
        self.assertEqual(detect_busted(57, 52, hero_present=True)['status'], 'ALIVE')
        self.assertEqual(detect_busted(57, 52, has_action=True)['confidence'], 'veto')

    def test_unreadable_is_unknown(self):
        self.assertEqual(detect_busted(None, 52)['status'], 'UNKNOWN')
        self.assertEqual(detect_busted(57, None)['status'], 'UNKNOWN')
        self.assertEqual(detect_busted(0, 0)['status'], 'UNKNOWN')
        self.assertEqual(detect_busted(57, 0)['status'], 'UNKNOWN')


class TestBustedConfirmer(unittest.TestCase):
    def _busted(self):
        return detect_busted(57, 52)

    def _alive(self):
        return detect_busted(30, 36)

    def test_needs_consecutive(self):
        c = BustedConfirmer(need=3)
        self.assertFalse(c.update('t', self._busted()))
        self.assertFalse(c.update('t', self._busted()))
        self.assertTrue(c.update('t', self._busted()))   # 3ª confirma

    def test_alive_resets_streak(self):
        c = BustedConfirmer(need=3)
        c.update('t', self._busted())
        c.update('t', self._busted())
        c.update('t', self._alive())                     # zera
        self.assertFalse(c.update('t', self._busted()))
        self.assertFalse(c.update('t', self._busted()))
        self.assertTrue(c.update('t', self._busted()))

    def test_unknown_holds_progress(self):
        c = BustedConfirmer(need=2)
        self.assertFalse(c.update('t', self._busted()))
        self.assertFalse(c.update('t', detect_busted(None, None)))  # UNKNOWN nao zera
        self.assertTrue(c.update('t', self._busted()))

    def test_per_table_independent(self):
        c = BustedConfirmer(need=2)
        c.update('A', self._busted())
        self.assertFalse(c.update('B', self._busted()))  # B tem streak proprio
        self.assertTrue(c.update('A', self._busted()))

    def test_mark_done_blocks_refire(self):
        c = BustedConfirmer(need=1)
        self.assertTrue(c.update('t', self._busted()))
        c.mark_done('t')
        self.assertFalse(c.update('t', self._busted()))  # nao refecha
        self.assertTrue(c.is_done('t'))


if __name__ == '__main__':
    unittest.main()
