"""B06 (estado por mão) + B07 (replay da sequência de ações). Invariantes do plano:
fichas conciliadas; foldados não somem; outra mão não contamina; open/3bet/4bet
com histórico; sequência ambígua -> pending."""
import unittest

from preflop_study import Blocked
from strategy.action_sequence import replay
from strategy.hand_state import HandState

STACKS = {'UTG': 40.0, 'CO': 40.0, 'BTN': 40.0, 'SB': 40.0, 'BB': 40.0}
BLINDS = [dict(position='SB', type='post_sb', amount_bb=0.5),
          dict(position='BB', type='post_bb', amount_bb=1.0)]


def ev(position, type, amount_bb=0.0):
    return dict(position=position, type=type, amount_bb=amount_bb)


class ReplayLabelTests(unittest.TestCase):
    def test_unopened(self):
        r = replay(list(BLINDS), STACKS)
        self.assertEqual((r['status'], r['label'], r['n_raises']), ('OK', 'unopened', 0))

    def test_limped(self):
        r = replay(BLINDS + [ev('BTN', 'limp', 1.0)], STACKS)
        self.assertEqual(r['label'], 'limped')
        self.assertEqual(r['limpers'], ['BTN'])

    def test_open(self):
        r = replay(BLINDS + [ev('CO', 'raise', 2.5)], STACKS)
        self.assertEqual((r['label'], r['n_raises'], r['aggressor']), ('open', 1, 'CO'))
        self.assertTrue(r['reopened'])

    def test_3bet(self):
        r = replay(BLINDS + [ev('CO', 'raise', 2.5), ev('BTN', 'raise', 7.5)], STACKS)
        self.assertEqual((r['label'], r['n_raises'], r['aggressor']), ('3bet', 2, 'BTN'))

    def test_4bet(self):
        seq = BLINDS + [ev('CO', 'raise', 2.5), ev('BTN', 'raise', 7.5), ev('CO', 'raise', 15.5)]
        r = replay(seq, STACKS)
        self.assertEqual((r['label'], r['n_raises'], r['aggressor']), ('4bet', 3, 'CO'))

    def test_fold_tracked_active_excludes_folded(self):
        r = replay(BLINDS + [ev('CO', 'raise', 2.5), ev('BB', 'fold')], STACKS)
        self.assertIn('BB', r['folded'])
        self.assertNotIn('BB', r['active'])

    def test_chip_conservation(self):
        r = replay(BLINDS + [ev('CO', 'raise', 2.5), ev('BTN', 'raise', 7.5), ev('BB', 'fold')], STACKS)
        self.assertTrue(r['chip_conservation'])

    def test_empty_is_pending(self):
        self.assertEqual(replay([], STACKS)['status'], 'PENDING')

    def test_blinds_missing_is_pending(self):
        r = replay([ev('CO', 'raise', 2.5)], STACKS)
        self.assertEqual((r['status'], r['reason']), ('PENDING', 'BLINDS_MISSING'))

    def test_limp_after_raise_is_pending(self):
        r = replay(BLINDS + [ev('CO', 'raise', 2.5), ev('BTN', 'limp', 2.5)], STACKS)
        self.assertEqual(r['status'], 'PENDING')


class HandStateTests(unittest.TestCase):
    def _hs(self):
        return HandState(('t1', 'h1'), STACKS, hero='BTN')

    def test_init_rejects_bad_identity(self):
        with self.assertRaises(Blocked):
            HandState(('t1',), STACKS)
        with self.assertRaises(Blocked):
            HandState(('t1', ''), STACKS)

    def test_other_hand_does_not_contaminate(self):
        hs = self._hs().ingest(('t1', 'h1'), BLINDS + [ev('CO', 'raise', 2.5)])
        with self.assertRaises(Blocked):
            hs.ingest(('t1', 'h2'), [ev('BTN', 'raise', 9.0)])      # outra mão -> rejeita
        self.assertEqual(hs.label, 'open')                          # estado intacto

    def test_append_guards_identity(self):
        hs = self._hs()
        with self.assertRaises(Blocked):
            hs.append(ev('CO', 'raise', 2.5), identity=('t1', 'h2'))

    def test_folded_preserved_in_participants_not_active(self):
        hs = self._hs().ingest(('t1', 'h1'), BLINDS + [ev('CO', 'raise', 2.5), ev('BB', 'fold')])
        self.assertIn('BB', hs.participants)       # história preservada
        self.assertIn('BB', hs.folded)
        self.assertNotIn('BB', hs.active)

    def test_remaining_stacks_reconcile(self):
        hs = self._hs().ingest(('t1', 'h1'), BLINDS + [ev('CO', 'raise', 2.5)])
        rem = hs.remaining_stacks()
        self.assertAlmostEqual(rem['CO'], 37.5)    # 40 - 2.5
        self.assertAlmostEqual(rem['BB'], 39.0)    # 40 - 1.0 (post)
        self.assertAlmostEqual(rem['UTG'], 40.0)

    def test_label_and_aggressor_delegate_to_replay(self):
        hs = self._hs().ingest(('t1', 'h1'), BLINDS + [ev('CO', 'raise', 2.5), ev('BTN', 'raise', 7.5)])
        self.assertEqual((hs.label, hs.aggressor), ('3bet', 'BTN'))


if __name__ == '__main__':
    unittest.main()
