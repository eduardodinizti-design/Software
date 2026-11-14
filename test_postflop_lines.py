"""Lote 7 (pós-flop SOMBRA, nunca executa): linhas novas de ESTUDO.

B1: x/r semi-blefe com draw FORTE (combo/nut-flush-draw) enfrentando aposta.
B9: overbet polarizado (opção de size) com mão NUTADA em turn/river.
Conselho exploratório; o operador nunca clica pós-flop."""
import unittest

from postflop_advisor import advise_postflop


def _tbl(pot, call, stack=200):
    return {'pot': {'pot_bb': pot}, 'to_call': {'to_call_bb': call},
            'seats': {'hero': {'occupied': True, 'in_hand': True, 'stack_bb': stack},
                      'v': {'occupied': True, 'in_hand': True, 'stack_bb': stack}}}


class SemiBluffRaiseTests(unittest.TestCase):
    def test_combo_draw_oferece_semibluff_sem_trocar_decisao(self):
        # 9h8h em 7h6h2c = flush draw + open-ender (combo); x/r OFERECIDO como opção,
        # SEM trocar a decisão call/fold por equity (sombra/estudo).
        a = advise_postflop(_tbl(20, 6), ['9h', '8h'], ['7h', '6h', '2c'],
                            pot_type='single_raised', iters=50)
        self.assertIn('SEMI_BLUFF_RAISE_AVAILABLE_EXPLORATORY', a['caveats'])
        self.assertTrue(a['semi_bluff_raise']['exploratory'])
        self.assertGreater(a['semi_bluff_raise']['size_bb'], 0)
        self.assertIn(a['recommended'], ('call', 'fold'))   # decisão por equity preservada
        self.assertFalse(a.get('execution_allowed'))        # sombra: nunca executa

    def test_draw_fraco_nao_oferece(self):
        # gutshot fraco (Jh9c em 7h6h2c): não é combo/nut-FD -> sem opção de x/r
        a = advise_postflop(_tbl(20, 6), ['Jh', '9c'], ['7h', '6h', '2c'],
                            pot_type='single_raised', iters=50)
        self.assertNotIn('SEMI_BLUFF_RAISE_AVAILABLE_EXPLORATORY', a.get('caveats', []))
        self.assertNotIn('semi_bluff_raise', a)


class OverbetPolarTests(unittest.TestCase):
    def test_quads_river_oferece_overbet(self):
        a = advise_postflop(_tbl(30, 0), ['Ah', 'As'], ['Ac', 'Ad', 'Kh', 'Ks', '2c'],
                            pot_type='single_raised', iters=50)
        self.assertEqual(a['recommended'], 'bet')
        self.assertIn('OVERBET_POLAR_EXPLORATORY', a['caveats'])
        self.assertGreater(a['sizing']['overbet_option_bb'], a['pot_bb'] if a.get('pot_bb') else 30)
        self.assertFalse(a.get('execution_allowed'))

    def test_valor_nao_nutado_sem_overbet(self):
        # top pair (AhKc em Kd 7s 2c), checado: aposta de valor, mas NÃO overbet polar
        a = advise_postflop(_tbl(10, 0), ['Ah', 'Kc'], ['Kd', '7s', '2c'],
                            pot_type='single_raised', iters=50)
        self.assertNotIn('OVERBET_POLAR_EXPLORATORY', a.get('caveats', []))
        self.assertNotIn('overbet_option_bb', a.get('sizing', {}))


if __name__ == '__main__':
    unittest.main()
