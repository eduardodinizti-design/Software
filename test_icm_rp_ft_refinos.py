"""Refinos de FT/bolha do RP por composição da mesa (ICM na Prática, Reg-Life):
RANK de stack (CL/short baixo, 2º em fichas = pico) e 'RP na lua' (stack moribundo ->
RP explode). Travado nos NÚMEROS do próprio PDF: BB 10bb 2º lugar na bolha = +16,2%;
Yuri 18,2bb com um stack 0,05bb na mesa = +20,6%."""
import unittest

import icm_rp


class RankFactor(unittest.TestCase):
    def test_chip_leader_e_short_tem_fator_baixo(self):
        self.assertEqual(icm_rp.ft_rank_factor(30, [30, 10, 8]), 0.75)   # chip leader
        self.assertEqual(icm_rp.ft_rank_factor(8, [30, 10, 8]), 0.70)    # short

    def test_segundo_em_fichas_e_o_pico(self):
        self.assertEqual(icm_rp.ft_rank_factor(10, [30, 10, 8]), 1.20)   # 2º lugar = pico

    def test_sem_dados_ou_poucos_stacks_neutro(self):
        self.assertEqual(icm_rp.ft_rank_factor(10, None), 1.0)
        self.assertEqual(icm_rp.ft_rank_factor(10, [30, 10]), 1.0)       # <3 stacks


class RpNaLua(unittest.TestCase):
    def test_stack_moribundo_dispara_fator(self):
        f = icm_rp.table_pressure_factor(18.2, [22.8, 18.2, 5, 0.05])
        self.assertGreaterEqual(f, 1.5)

    def test_sem_moribundo_so_rank(self):
        self.assertEqual(icm_rp.table_pressure_factor(10, [30, 10, 8]), 1.20)

    def test_hero_moribundo_nao_ganha_alivio(self):
        self.assertFalse(icm_rp._has_dying_stack(1.0, [30, 10, 1.0]))


class RiskPremiumRefinado(unittest.TestCase):
    def test_bb_segundo_lugar_bolha_bate_16_2(self):
        rp = icm_rp.risk_premium('icm', 'bubble', hero_stack=10, villain_stack=30,
                                 table_stacks=[30, 10, 8])
        self.assertAlmostEqual(rp, 0.162, places=3)

    def test_rp_na_lua_bate_20_6(self):
        # stack moribundo na mesa = pay-jump iminente (momento de bolha): 13,5% x 1,5 = 20,25%
        rp = icm_rp.risk_premium('icm', 'bubble', hero_stack=18.2, villain_stack=22.8,
                                 table_stacks=[22.8, 18.2, 5, 0.05])
        self.assertAlmostEqual(rp, 0.2025, places=3)

    def test_sem_table_stacks_inalterado(self):
        # compat: sem table_stacks, o valor é o de antes (coverage só)
        self.assertEqual(icm_rp.risk_premium('icm', 'bubble', hero_stack=25, villain_stack=25),
                         icm_rp.risk_premium('icm', 'bubble', hero_stack=25, villain_stack=25,
                                             table_stacks=None))

    def test_baixa_pressao_nao_aplica_rank(self):
        # 75% field (baixa pressão) -> refino de rank NÃO entra
        rp = icm_rp.risk_premium('icm', 'mid', hero_stack=10, villain_stack=30,
                                 field_fraction=0.75, table_stacks=[30, 10, 8])
        semrank = icm_rp.risk_premium('icm', 'mid', hero_stack=10, villain_stack=30,
                                      field_fraction=0.75)
        self.assertEqual(rp, semrank)


if __name__ == '__main__':
    unittest.main()
