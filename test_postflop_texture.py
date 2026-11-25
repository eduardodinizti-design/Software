"""Trava a regra de TAMANHO por textura (Pós-flop Avançado / Reg-Life). Casos concretos
do próprio material: board baixo não-pareado polariza GRANDE; board alto/pareado seco =
range-bet PEQUENO; molhado = grande (proteção). Tudo clampado ao slider (1/3,1/2,2/3)."""
import unittest

from postflop_eval import classify_board
import postflop_texture as tx

SLIDER = {tx.SMALL, tx.MEDIUM, tx.BIG}


def plan(board, *, is_strong=True, draw=False, hero_agg=True):
    return tx.bet_plan(classify_board(board), is_strong=is_strong,
                       has_strong_draw=draw, hero_is_aggressor=hero_agg)


class Tamanho(unittest.TestCase):
    def test_board_baixo_seco_polariza_grande(self):
        # todos apostam GRANDE (o que importa p/ o slider); 954/752 são secos (polarized_big),
        # 632 tem 4-5 conectando (protect_big) — mesmo tamanho.
        for b in (['9c', '5d', '4h'], ['7c', '5d', '2h']):
            p = plan(b)
            self.assertEqual(p['fraction'], tx.BIG, b)
            self.assertEqual(p['lean'], 'polarized_big', b)
        self.assertEqual(plan(['6c', '3d', '2h'])['fraction'], tx.BIG)   # grande de qualquer forma

    def test_board_alto_seco_range_bet_pequeno(self):
        for b in (['Qc', '5d', '4h'], ['Ah', '9c', '3d'], ['Kc', '8d', '2h']):
            p = plan(b)
            self.assertEqual(p['fraction'], tx.SMALL, b)
            self.assertEqual(p['lean'], 'range_small', b)

    def test_board_pareado_baixo_range_bet_pequeno(self):
        p = plan(['7c', '7d', '2h'])          # 772: UTG c-beta pequeno (20% no PDF)
        self.assertEqual(p['fraction'], tx.SMALL)
        self.assertEqual(p['lean'], 'range_small')

    def test_board_molhado_grande_protecao(self):
        p = plan(['8h', '7h', '6d'])          # conectado -> grande (nega equidade)
        self.assertEqual(p['fraction'], tx.BIG)
        self.assertEqual(p['lean'], 'protect_big')

    def test_semi_blefe_grande_no_polar_medio_no_range(self):
        baixo = plan(['9c', '5d', '2h'], is_strong=False, draw=True)
        alto = plan(['Ah', 'Kc', '2d'], is_strong=False, draw=True)
        self.assertEqual(baixo['fraction'], tx.BIG)
        self.assertEqual(alto['fraction'], tx.MEDIUM)
        self.assertEqual(baixo['lean'], 'semi_bluff')

    def test_fracoes_sempre_no_slider(self):
        for b in (['9c', '5d', '4h'], ['Qc', '5d', '4h'], ['7c', '7d', '2h'],
                  ['8h', '7h', '6d'], ['Ah', 'Kc', '2d']):
            self.assertIn(plan(b)['fraction'], SLIDER, b)
            self.assertIn(plan(b, is_strong=False, draw=True)['fraction'], SLIDER, b)


class RegimeDeep(unittest.TestCase):
    CONNECT = ['9c', '8d', '5h']   # baixo conectado (straightish 3) = dinâmico
    DRY = ['9c', '5d', '2h']       # baixo desconectado seco (straightish 2)

    def test_deep_mao_feita_board_dinamico_controla(self):
        p = plan(self.CONNECT, is_strong=True, hero_agg=True)  # sem spr -> BIG
        self.assertEqual(p['fraction'], tx.BIG)
        d = tx.bet_plan(classify_board(self.CONNECT), is_strong=True,
                        has_strong_draw=False, hero_is_aggressor=True, spr=10)
        self.assertAlmostEqual(d['fraction'], tx.MEDIUM, places=2)   # deep -> controla
        self.assertEqual(d['lean'], 'deep_control')

    def test_short_mao_feita_board_dinamico_mantem_grande(self):
        d = tx.bet_plan(classify_board(self.CONNECT), is_strong=True,
                        has_strong_draw=False, hero_is_aggressor=True, spr=2)
        self.assertEqual(d['fraction'], tx.BIG)     # short -> aposta a equidade pronta

    def test_deep_draw_robusto_infla(self):
        d = tx.bet_plan(classify_board(self.CONNECT), is_strong=False,
                        has_strong_draw=True, hero_is_aggressor=True, spr=10)
        self.assertEqual(d['fraction'], tx.BIG)
        self.assertEqual(d['lean'], 'deep_robust_draw')

    def test_deep_board_seco_seguro_mantem_grande(self):
        d = tx.bet_plan(classify_board(self.DRY), is_strong=True,
                        has_strong_draw=False, hero_is_aggressor=True, spr=10)
        self.assertEqual(d['fraction'], tx.BIG)     # seco-seguro deep -> mantém grande

    def test_sem_spr_inalterado(self):
        self.assertEqual(plan(self.CONNECT, is_strong=True)['fraction'], tx.BIG)


class NutsHolder(unittest.TestCase):
    def test_hero_pfr_board_alto_tem_nuts(self):
        self.assertEqual(tx.nuts_holder(classify_board(['Ah', '9c', '3d']),
                                        hero_is_aggressor=True), 'hero')

    def test_vilao_tem_nuts_board_baixo_conectado(self):
        self.assertEqual(tx.nuts_holder(classify_board(['9c', '8d', '7h']),
                                        hero_is_aggressor=True), 'villain')

    def test_agressor_desconhecido_neutro(self):
        self.assertEqual(tx.nuts_holder(classify_board(['Ah', '9c', '3d']),
                                        hero_is_aggressor=None), 'neutral')


if __name__ == '__main__':
    unittest.main()
