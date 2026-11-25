"""Leak REAL (H2N #61, review do Eduardo): QQ = UNDERPAIR em board K-alto 3-way pagou all-in e
perdeu ~50k. Alvo #1: desvalorizar underpair vs overcard(sempre há)/MULTIWAY/AGRESSÃO -> FOLD,
em vez de pagar pela equity otimista (o range de valor domina). HU vs aposta pequena segue por equity.
"""
import unittest

from postflop_advisor import advise_postflop


def state(pot, to_call, stack=40.0):
    return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=to_call),
                seats=dict(hero=dict(stack_bb=stack, occupied=True)),
                positions=dict(hero='BTN'))


class UnderpairDevalued(unittest.TestCase):
    BOARD = ['Ks', '8h', '3d']   # K-alto: QQ é UNDERPAIR (par abaixo da carta mais alta)
    QQ = ['Qs', 'Qd']

    def test_qq_multiway_all_in_folds(self):
        # O cenário do leak: 3-way (villains=2), all-in -> FOLD (não paga pela equity otimista).
        r = advise_postflop(state(30, 30, 30), self.QQ, self.BOARD, villains=2)
        self.assertEqual(r['recommended'], 'fold')
        self.assertIn('UNDERPAIR_DEVALUED_FOLD_MULTIWAY_OR_BIGBET', r['caveats'])

    def test_qq_hu_big_bet_folds(self):
        # Mesmo HU, vs APOSTA GRANDE (pot_odds > 0.40) -> fold (range de valor domina).
        r = advise_postflop(state(10, 10), self.QQ, self.BOARD)   # pote grande = aposta grande
        self.assertEqual(r['recommended'], 'fold')
        self.assertIn('UNDERPAIR_DEVALUED_FOLD_MULTIWAY_OR_BIGBET', r['caveats'])

    def test_qq_hu_small_bet_nao_forca_fold(self):
        # HU vs aposta PEQUENA (pot_odds baixo), sem multiway -> NÃO dispara o guard
        # (segue a decisão normal de bluffcatcher por equity/MDF). Guard não over-aperta HU barato.
        r = advise_postflop(state(40, 2), self.QQ, self.BOARD)
        self.assertNotIn('UNDERPAIR_DEVALUED_FOLD_MULTIWAY_OR_BIGBET', r.get('caveats', []))


if __name__ == '__main__':
    unittest.main()
