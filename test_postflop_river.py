"""Trava o capítulo de RIVER IP (polarização + valor relativo): piso de valor sobe quando o
river completa draws; disciplina de valor (promoção) faz a mão que perdeu valor dar check."""
import unittest

from postflop_eval import classify_board
from postflop_advisor import advise_postflop
import postflop_river as rv


def _st(pot, tocall, stack=40):
    return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=tocall),
                seats={'hero': {'stack_bb': stack, 'occupied': True}}, n_opponents=1)


class ValorRelativo(unittest.TestCase):
    def test_board_blank_top_pair_e_valor(self):
        bc = classify_board(['Ah', '7d', '2c', 'Ks', '3h'])   # seco, sem flush/seq
        self.assertFalse(rv.is_draw_complete(bc))
        self.assertTrue(rv.river_value_ok('top_pair', bc))
        self.assertTrue(rv.river_value_ok('two_pair', bc))

    def test_board_flush_derruba_two_pair(self):
        bc = classify_board(['Ah', '7h', '2c', 'Kh', '3h'])   # 4 copas -> flush possível
        self.assertTrue(rv.is_draw_complete(bc))
        self.assertFalse(rv.river_value_ok('two_pair', bc))
        self.assertFalse(rv.river_value_ok('top_pair', bc))
        self.assertTrue(rv.river_value_ok('flush', bc))
        self.assertTrue(rv.river_value_ok('set', bc))

    def test_board_sequencia_derruba_overpair(self):
        bc = classify_board(['9h', '8d', '7c', '6s', '2h'])   # sequência no board
        self.assertTrue(rv.is_draw_complete(bc))
        self.assertFalse(rv.river_value_ok('overpair', bc))
        self.assertTrue(rv.river_value_ok('straight', bc))

    def test_tier_e_size_hint(self):
        bc_dry = classify_board(['Ah', '7d', '2c', 'Ks', '3h'])
        self.assertEqual(rv.river_tier('top_pair', {}, bc_dry), 'value')
        self.assertEqual(rv.river_tier('air', {}, bc_dry), 'bluff')
        self.assertEqual(rv.river_tier('second_pair', {}, bc_dry), 'check')
        self.assertEqual(rv.river_size_hint('full_house', bc_dry), 'overbet')
        self.assertEqual(rv.river_size_hint('top_pair', bc_dry), 'big')
        self.assertEqual(rv.river_size_hint('second_pair', bc_dry), 'none')

    def test_river_jam_so_nuts_em_board_que_completou(self):
        bc_flush = classify_board(['9h', '9d', '2h', 'Kh', '7h'])    # pareado + flush
        bc_dry = classify_board(['9h', '9d', '2c', 'Ks', '7d'])      # pareado seco
        self.assertTrue(rv.river_jam('full_house', bc_flush))
        self.assertTrue(rv.river_jam('straight_flush', bc_flush))
        self.assertFalse(rv.river_jam('full_house', bc_dry))         # seco -> não jam
        self.assertFalse(rv.river_jam('flush', bc_flush))            # flush não é nuts (dominável)


_NIT = {'vpip': 9, 'pfr': 7, 'threebet': 3, 'fold3bet': 55, 'cbet': 40, 'foldcbet': 65}
_STATION = {'vpip': 46, 'pfr': 8, 'threebet': 2, 'fold3bet': 20, 'cbet': 28, 'foldcbet': 25}


class BluffBlocker(unittest.TestCase):
    def test_bloqueia_flush_draw_perdido_eh_blefe_ruim(self):
        # board com 2 copas (flush draw que faltou); hero segura copas -> bloqueia fold -> False
        self.assertFalse(rv.river_bluff_blocker_ok(['Qh', 'Jd'], ['Ah', '7h', '2c', 'Ks', '3d']))

    def test_sem_bloquear_eh_blefe_ok(self):
        self.assertTrue(rv.river_bluff_blocker_ok(['Qc', 'Jd'], ['Ah', '7h', '2c', 'Ks', '3d']))

    def test_board_de_4_eh_ok(self):
        self.assertTrue(rv.river_bluff_blocker_ok(['Qh', 'Jd'], ['Ah', '7h', '2c', 'Ks']))


class BluffRiver(unittest.TestCase):
    def test_blefa_bottom_vs_fold_prone_com_bloqueador_ok(self):
        # ar (QJ off, sem copas) em river, vilão nit (folda) -> blefa polar
        a = advise_postflop(_st(10, 0), ['Qc', 'Jd'], ['Ah', '7h', '2c', 'Ks', '3d'],
                            street='RIVER', aggressor='hero', villain_stats=_NIT)
        self.assertEqual(a['recommended'], 'bet')
        self.assertIn('RIVER_BLUFF_POLAR', a['caveats'])

    def test_nao_blefa_vs_station(self):
        a = advise_postflop(_st(10, 0), ['Qc', 'Jd'], ['Ah', '7h', '2c', 'Ks', '3d'],
                            street='RIVER', aggressor='hero', villain_stats=_STATION)
        self.assertEqual(a['recommended'], 'check')
        self.assertNotIn('RIVER_BLUFF_POLAR', a.get('caveats', []))

    def test_nao_blefa_sem_leitura(self):
        # CAMPO MOLE (início/station) sem leitura: NÃO blefa (conservador). No campo duro (FT/ICM,
        # soft_field=False) o blefe polar dispara pela fold equity — field-gating (Eduardo 24/11).
        a = advise_postflop(_st(10, 0), ['Qc', 'Jd'], ['Ah', '7h', '2c', 'Ks', '3d'],
                            street='RIVER', aggressor='hero', soft_field=True)
        self.assertEqual(a['recommended'], 'check')
        self.assertNotIn('RIVER_BLUFF_POLAR', a.get('caveats', []))

    def test_nao_blefa_mao_que_bloqueia_fold(self):
        # hero QJ com copas (bloqueia flush draw perdido) -> check mesmo vs nit
        a = advise_postflop(_st(10, 0), ['Qh', 'Jd'], ['Ah', '7h', '2c', 'Ks', '3d'],
                            street='RIVER', aggressor='hero', villain_stats=_NIT)
        self.assertEqual(a['recommended'], 'check')
        self.assertNotIn('RIVER_BLUFF_POLAR', a.get('caveats', []))


class PromocaoRiver(unittest.TestCase):
    def test_two_pair_checa_em_river_de_flush(self):
        # board 4 copas no river; hero A7 (two pair A+7, sem copas) perdeu valor -> check
        a = advise_postflop(_st(10, 0), ['Ad', '7s'], ['Ah', '7h', '2c', 'Kh', '3h'],
                            street='RIVER', aggressor='hero')
        self.assertEqual(a['recommended'], 'check')
        self.assertIn('RIVER_CHECK_PERDEU_VALOR_RELATIVO', a['caveats'])

    def test_flush_segue_apostando_em_river_de_flush(self):
        # hero com flush (A+K de copas? usa 2 copas) -> valor, não é dampeado
        a = advise_postflop(_st(10, 0), ['Qh', 'Jh'], ['Ah', '7h', '2c', 'Kh', '3h'],
                            street='RIVER', aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertNotIn('RIVER_CHECK_PERDEU_VALOR_RELATIVO', a.get('caveats', []))

    def test_top_pair_value_beta_em_river_blank(self):
        # river blank seco (A-K-9-8-4, sem flush/sequência): top pair segue sendo valor (aposta)
        a = advise_postflop(_st(10, 0), ['Ad', 'Qs'], ['Ah', '9d', '8c', 'Ks', '4h'],
                            street='RIVER', aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertNotIn('RIVER_CHECK_PERDEU_VALOR_RELATIVO', a.get('caveats', []))


class JamPorNuts(unittest.TestCase):
    def test_full_house_jama_em_river_de_flush(self):
        # board 9-9-2-K-7 com 4 copas; hero 9-7 = full house -> all-in (overbet por nuts)
        a = advise_postflop(_st(20, 0), ['9s', '7c'], ['9h', '9d', '2h', 'Kh', '7h'],
                            street='RIVER', aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertEqual(a['sizing']['bucket'], 'allin')
        self.assertIn('RIVER_JAM_NUT_ADVANTAGE', a['caveats'])

    def test_full_house_nao_jama_em_board_seco(self):
        # board 9-9-2-K-7 rainbow (sem flush/seq); full house -> aposta grande, NÃO all-in
        a = advise_postflop(_st(20, 0), ['9s', '7h'], ['9h', '9d', '2c', 'Ks', '7d'],
                            street='RIVER', aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertNotIn('RIVER_JAM_NUT_ADVANTAGE', a.get('caveats', []))
        self.assertNotEqual(a['sizing'].get('bucket'), 'allin')


if __name__ == '__main__':
    unittest.main()
