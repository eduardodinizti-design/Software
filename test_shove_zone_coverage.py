"""COBERTURA DA ZONA DE SHOVE (Eduardo 19/11: atacar o CONTEXTO do range, não a mão).
Na zona de shove (<20bb) o bot NUNCA pode abster por falta de range: regime push/fold
tem sempre decisão (shove ou fold) pela Nash (empresta bucket vizinho). Trava o
CONTEXTO inteiro — vários spots e mãos diferentes, não o 88 específico."""
import os
import unittest

from preflop_advisor import PreflopAdvisor

_VAL = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


def _ts(positions, stacks_bb, bets):
    return dict(positions=positions,
                seats={s: dict(stack_bb=stacks_bb.get(s), occupied=True) for s in positions},
                bets=[dict(seat=s, bet_bb=b) for s, b in bets.items()],
                phase='mid')


class ShoveZoneCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(_VAL) and os.path.exists(_DEEP)):
            raise unittest.SkipTest('pacotes de range nao encontrados')
        cls.adv = PreflopAdvisor.from_files(_VAL, _DEEP)

    def _decide(self, cards, state, **kw):
        r = self.adv.advise_from_reading(state, cards, **kw)
        self.assertIsInstance(r, dict)
        self.assertIn(r.get('status'), ('ADVICE', 'OUT_OF_RANGE'),
                      'ABSTEVE na zona de shove (%s %s): %s'
                      % (cards, kw, r.get('reason')))
        return r

    # ---- BB vs LIMP curto (o caso do 88 que abstinha) — e com OUTRAS maos ----
    def test_bb_vs_limp_short_decide_varias_maos(self):
        st = _ts({'hero': 'BB', 'vlj': 'LJ', 'vsb': 'SB'},
                 {'hero': 10, 'vlj': 10, 'vsb': 10},
                 {'vlj': 1.0, 'vsb': 0.5, 'hero': 1.0})
        for hand in (['8d', '8s'], ['7c', '5d'], ['7h', '2d'], ['Ad', 'Qs']):
            for stage in ('ft', 'bubble'):
                self._decide(hand, st, mode='icm', stage=stage, players=9)

    # ---- first-in curto (UTG/HJ/CO) ----
    def test_first_in_short_decide(self):
        st = _ts({'hero': 'UTG', 'vsb': 'SB', 'vbb': 'BB'},
                 {'hero': 12, 'vsb': 12, 'vbb': 12},
                 {'vsb': 0.5, 'vbb': 1.0})
        for hand in (['Kd', '3c'], ['Ah', 'Jd'], ['2c', '7d']):
            self._decide(hand, st, mode='icm', stage='ft', players=9)

    # ---- vs OPEN curto (3bet-shove/resteal) ----
    def test_vs_open_short_decide(self):
        st = _ts({'hero': 'BB', 'vco': 'CO', 'vsb': 'SB'},
                 {'hero': 11, 'vco': 11, 'vsb': 11},
                 {'vco': 2.0, 'vsb': 0.5, 'hero': 1.0})
        for hand in (['Ac', 'Jd'], ['5c', '5d'], ['9h', '7s'], ['Jd', '4c']):
            self._decide(hand, st, mode='icm', stage='bubble', players=9)

    # ---- sub-12bb tambem decide (range 12bb tighter-safe) ----
    def test_sub12bb_decide(self):
        st = _ts({'hero': 'CO', 'vsb': 'SB', 'vbb': 'BB'},
                 {'hero': 7, 'vsb': 7, 'vbb': 7},
                 {'vsb': 0.5, 'vbb': 1.0})
        for hand in (['Kc', '6c'], ['Qd', 'Js'], ['3h', '2d']):
            self._decide(hand, st, mode='icm', stage='ft', players=9)


    # ---- cold 3bet (open + 3bet) curto: jam premium / fold resto / call-off se all-in ----
    def test_cold_3bet_short_jam_premium_fold_resto(self):
        # hero BB enfrenta HJ open 2.0 + CO 3bet 6.0 (cold), 10bb (3bet NAO all-in)
        st = _ts({'hero': 'BB', 'vhj': 'HJ', 'vco': 'CO'},
                 {'hero': 10, 'vhj': 10, 'vco': 10},
                 {'vhj': 2.0, 'vco': 6.0, 'hero': 1.0})
        self.assertEqual(self._decide(['Qd', 'Qh'], st, mode='icm', stage='ft', players=9)
                         .get('recommended'), 'all_in')          # QQ 4bet-jam
        self.assertEqual(self._decide(['Ad', 'Kc'], st, mode='icm', stage='ft', players=9)
                         .get('recommended'), 'all_in')          # AKo 4bet-jam
        for h in (['8d', '6d'], ['9h', '8c'], ['Qd', 'Td']):     # resto fold (nao abstem!)
            self.assertEqual(self._decide(h, st, mode='icm', stage='ft', players=9)
                             .get('recommended'), 'fold')

    def test_cold_3bet_allin_calloff_premium(self):
        # CO 3bet ALL-IN (0 fichas ATRAS = stack_bb 0, ja com 6 no pote): premium
        # CALL-off; resto fold.
        st = _ts({'hero': 'BB', 'vhj': 'HJ', 'vco': 'CO'},
                 {'hero': 10, 'vhj': 10, 'vco': 0},
                 {'vhj': 2.0, 'vco': 6.0, 'hero': 1.0})
        self.assertEqual(self._decide(['Kd', 'Kc'], st, mode='icm', stage='ft', players=9)
                         .get('recommended'), 'call')            # KK call-off
        self.assertEqual(self._decide(['7h', '2d'], st, mode='icm', stage='ft', players=9)
                         .get('recommended'), 'fold')


    # ---- vs_3bet na ZONA DE COMMIT (<=25bb) NUNCA abstem (fresta 20bb/pko fechada) ----
    def test_vs_3bet_zona_commit_decide_todos_os_modos(self):
        # hero BTN abre 2.0, SB 3beta 6.0 (nao all-in); o bot tem de DECIDIR (4bet-jam/
        # call-off/fold), nunca ABSTER — inclusive 20bb EXATO e 20-25 em pko/icm.
        for stk in (18, 20, 22, 25):
            for mode, stage in (('pko', 'mid'), ('icm', 'bubble'), ('chip_ev', 'mid')):
                st = _ts({'hero': 'BTN', 'v': 'SB', 'vbb': 'BB'},
                         {'hero': stk, 'v': stk, 'vbb': stk},
                         {'hero': 2.0, 'v': 6.0, 'vbb': 1.0})
                st['pot'] = {'pot_bb': 9.5}
                st['to_call'] = {'to_call_bb': 4.0}
                for hand in (['Ad', 'Kc'], ['Qd', 'Qh'], ['7h', '2d']):
                    self._decide(hand, st, mode=mode, stage=stage, players=9)


if __name__ == '__main__':
    unittest.main()
