"""Check-raise por vantagem de NUTS (Pós-flop Avançado / Reg-Life): como DEFENSOR em board
onde o nosso range de defesa tem vantagem de nuts (pareado ou baixo-conectado), o BB
check-raiseia — VALOR e SEMI-BLEFE (~3x). Antes o semi-blefe só aparecia como metadado
(passividade). Só dispara com vilão-agressor conhecido + draw forte + aposta não gigante."""
import unittest

from postflop_advisor import advise_postflop


def tbl(pot, call, stack=200):
    return {'pot': {'pot_bb': pot}, 'to_call': {'to_call_bb': call},
            'seats': {'hero': {'occupied': True, 'in_hand': True, 'stack_bb': stack},
                      'v': {'occupied': True, 'in_hand': True, 'stack_bb': stack}}}


BOARD_NUTS = ['9h', '8h', '5c']   # baixo conectado 2-tone: DEFENSOR tem vantagem de nuts
DRAW = ['Jh', 'Th']               # combo: flush draw + OESD (15 outs)


class SemiBluffCheckRaise(unittest.TestCase):
    def test_defensor_com_draw_forte_check_raiseia(self):
        a = advise_postflop(tbl(20, 6), DRAW, BOARD_NUTS, aggressor='v',
                            pot_type='single_raised', iters=50)
        self.assertEqual(a['recommended'], 'raise')
        self.assertIn('CHECK_RAISE_SEMIBLUFF_VANTAGEM_NUTS', a['caveats'])
        self.assertGreater(a['sizing']['size_bb'], 6)
        self.assertFalse(a.get('execution_allowed'))        # continua sombra

    def test_agressor_desconhecido_nao_promove(self):
        a = advise_postflop(tbl(20, 6), DRAW, BOARD_NUTS, pot_type='single_raised', iters=50)
        self.assertIn(a['recommended'], ('call', 'fold'))
        self.assertNotIn('CHECK_RAISE_SEMIBLUFF_VANTAGEM_NUTS', a.get('caveats', []))

    def test_hero_agressor_nao_check_raiseia(self):
        a = advise_postflop(tbl(20, 6), DRAW, BOARD_NUTS, aggressor='hero', iters=50)
        self.assertNotIn('CHECK_RAISE_SEMIBLUFF_VANTAGEM_NUTS', a.get('caveats', []))

    def test_board_alto_defensor_nao_check_raiseia(self):
        # board A-alto: o PFR tem a vantagem de nuts, o defensor NÃO -> sem x/r semi-blefe
        a = advise_postflop(tbl(20, 6), DRAW, ['Ah', '9h', '5c'], aggressor='v', iters=50)
        self.assertNotIn('CHECK_RAISE_SEMIBLUFF_VANTAGEM_NUTS', a.get('caveats', []))


class ValueCheckRaise(unittest.TestCase):
    def test_defensor_forte_check_raiseia_valor(self):
        a = advise_postflop(tbl(20, 6), ['2c', '2d'], ['7c', '7d', '2h'], aggressor='v', iters=50)
        self.assertEqual(a['recommended'], 'raise')
        self.assertIn('CHECK_RAISE_VALOR_VANTAGEM_NUTS', a['caveats'])


if __name__ == '__main__':
    unittest.main()
