"""Testes do modelo de RP/risk-advantage/bounty (icm_rp), calibrado pela skill ICM."""
import unittest

import icm_rp


class StageRpTests(unittest.TestCase):
    def test_chip_ev_zero(self):
        self.assertEqual(icm_rp.risk_premium('chip_ev', 'bubble', hero_stack=25, villain_stack=25), 0.0)

    def test_gradiente_de_field(self):
        # Referências da skill (stacks iguais): 50%->3,5%, 25%->7,9%, bolha->13,5%.
        self.assertAlmostEqual(icm_rp.stage_base_rp(None, field_fraction=0.5), 0.035, places=3)
        self.assertAlmostEqual(icm_rp.stage_base_rp(None, field_fraction=0.25), 0.079, places=3)
        self.assertAlmostEqual(icm_rp.stage_base_rp(None, field_fraction=0.0), 0.135, places=3)
        # monotônico: mais perto da bolha, maior RP
        self.assertLess(icm_rp.stage_base_rp(None, field_fraction=0.75),
                        icm_rp.stage_base_rp(None, field_fraction=0.25))


class CoverageTests(unittest.TestCase):
    def test_exemplo_skill_btn39_bb16_bolha(self):
        # BTN cobre BB -> RP baixo (~5,2% na skill); BB coberto -> RP cheio (~12,6%).
        rp_btn = icm_rp.risk_premium('icm', 'bubble', hero_stack=39, villain_stack=16)
        rp_bb = icm_rp.risk_premium('icm', 'bubble', hero_stack=16, villain_stack=39)
        self.assertTrue(0.045 <= rp_btn <= 0.065, rp_btn)      # ~5,5%
        self.assertTrue(0.12 <= rp_bb <= 0.135, rp_bb)         # ~13,5% (cheio)
        self.assertGreater(rp_bb, rp_btn)                      # coberto sente mais

    def test_quem_cobre_tem_rp_menor(self):
        ra = icm_rp.risk_advantage('bubble', 40, 15)
        self.assertTrue(ra['hero_covers'])
        self.assertLess(ra['rp_hero_vs_villain'], ra['rp_villain_vs_hero'])
        self.assertGreater(ra['advantage'], 0)                 # hero (cobre) pode pressionar


class BountyTests(unittest.TestCase):
    def test_bounty_so_quando_hero_cobre(self):
        # hero cobre -> realiza bounty
        b = icm_rp.bounty_power(5.0, hero_stack=30, villain_stack=12, pot_bb=3, to_call_bb=12)
        self.assertTrue(b['covers'])
        self.assertGreater(b['pot_fraction'], 0)
        # vilão cobre -> não elimina -> sem poder de bounty
        b2 = icm_rp.bounty_power(5.0, hero_stack=12, villain_stack=30, pot_bb=3, to_call_bb=12)
        self.assertFalse(b2['covers'])
        self.assertEqual(b2['pot_fraction'], 0.0)

    def test_bounty_desconta_equity_exigida(self):
        base = icm_rp.required_equity_icm(0.5, 0.1)                       # 0.6
        comb = icm_rp.required_equity_icm(0.5, 0.1, bounty_pot_fraction=0.3)
        self.assertLess(comb, base)                                      # bounty baixa a exigência

    def test_rp_pode_ser_liquido_negativo_com_bounty_grande(self):
        # RP pequeno + bounty grande -> equity exigida abaixo das pot odds (joga mais largo).
        req = icm_rp.required_equity_icm(0.45, 0.05, bounty_pot_fraction=0.5)
        self.assertLess(req, 0.45)


class PkoTests(unittest.TestCase):
    def test_pko_alivia_rp(self):
        icm = icm_rp.risk_premium('icm', 'bubble', hero_stack=16, villain_stack=39)
        pko = icm_rp.risk_premium('pko_icm', 'bubble', hero_stack=16, villain_stack=39)
        self.assertLess(pko, icm)


if __name__ == '__main__':
    unittest.main()
