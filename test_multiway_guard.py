"""A4/A5: multiway (open_with_callers / limp_then_iso) não auto-executa a range HU.

O pack não tem nó multiway; aplicar a range heads-up de vs_open num pote multiway é
LARGO demais (leak executável). O advise_from_reading marca esses resultados como
validated=False + multiway_approx -> o operador trata como estudo/seguro (premium
segue protegido pela blindagem). Direção multiway = mais apertado."""
import unittest

from preflop_advisor import PreflopAdvisor
from test_preflop_advisor import HANDS


def _vs_open_pack(stack=25, hero='BB', vs=('HJ',)):
    idx = HANDS.index('KQs')
    call = [1.0 if k == idx else 0.0 for k in range(169)]
    fold = [0.0 if k == idx else 1.0 for k in range(169)]
    node = dict(id='vo1', context=dict(mode='chip_ev', format='regular', stage='mid',
                                        players=9, stack=stack),
                spot='vs_open', hero=hero, vs=list(vs), validated=True, evUnit='bb',
                legalActions=['fold', 'call'], actions=['call', 'fold'],
                freq={'call': call, 'fold': fold},
                ev={'call': [0.0] * 169, 'fold': [0.0] * 169}, outOfRange=[], source='test')
    return dict(format='nvt-range-export', version=1, engineCommit='test',
                hands=HANDS, nodes=[node])


def _ts_open_with_caller(stack=25):
    # hero BB; HJ abre 2.5; CO paga 2.5 -> open_with_callers (opener HJ, caller CO)
    return dict(phase='mid',
                positions={'hero': 'BB', 'left_up': 'HJ', 'top_center': 'CO'},
                seats={'hero': {'stack_bb': stack}, 'left_up': {'stack_bb': stack},
                       'top_center': {'stack_bb': stack}},
                bets=[dict(seat='hero', bet_bb=1.0), dict(seat='left_up', bet_bb=2.5),
                      dict(seat='top_center', bet_bb=2.5)],
                to_call=dict(to_call_bb=1.5))


def _ts_heads_up_vs_open(stack=25):
    # hero BB; HJ abre 2.5; ninguém paga -> vs_open HU (sem callers)
    return dict(phase='mid',
                positions={'hero': 'BB', 'left_up': 'HJ'},
                seats={'hero': {'stack_bb': stack}, 'left_up': {'stack_bb': stack}},
                bets=[dict(seat='hero', bet_bb=1.0), dict(seat='left_up', bet_bb=2.5)],
                to_call=dict(to_call_bb=1.5))


class MultiwayGuardTests(unittest.TestCase):
    def setUp(self):
        self.a = PreflopAdvisor(_vs_open_pack())

    def test_multiway_marca_nao_validado(self):
        r = self.a.advise_from_reading(_ts_open_with_caller(), ['Ks', 'Qs'])
        self.assertEqual(r['status'], 'ADVICE')
        self.assertFalse(r['validated'])            # não auto-executa a range HU multiway
        self.assertTrue(r.get('multiway_approx'))
        self.assertTrue(any('MULTIWAY' in c for c in r.get('caveats', [])))

    def test_heads_up_continua_validado(self):
        r = self.a.advise_from_reading(_ts_heads_up_vs_open(), ['Ks', 'Qs'])
        self.assertEqual(r['status'], 'ADVICE')
        self.assertTrue(r['validated'])             # HU real: segue validado/executável
        self.assertFalse(r.get('multiway_approx', False))


if __name__ == '__main__':
    unittest.main()
