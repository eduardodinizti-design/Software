"""Trava o homologador srp (evidência offline do leak passivo do pós-flop). Documenta o
achado de 19/11: a heurística sozinha concorda pouco com o solver no c-bet (leak PASSIVO
dominante) — por isso o solver DIRIGE os nós decisivos cobertos."""
import os
import unittest

import homologate_srp as h

_PACK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'strategy_data', 'postflop_solver', 'btn_vs_bb_40.json')


@unittest.skipUnless(os.path.exists(_PACK), 'pack btn_vs_bb_40 nao gerado')
class HomologateSrp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = h.run(_PACK)

    def test_estrutura_e_amostra(self):
        self.assertEqual(self.r['spot'], 'btn_vs_bb_40')
        self.assertEqual(self.r['flops'], 100)
        self.assertGreater(self.r['total'], 10000)
        self.assertIsNotNone(self.r['agreement_pct'])

    def test_leak_passivo_domina(self):
        # a confirmação do "morrer no pos-flop": a heurística dá MUITO mais check onde o
        # solver aposta do que o contrário. Isto JUSTIFICA o driving do solver.
        pas = self.r['confusion'].get('solver_bet->heur_check', 0)
        agr = self.r['confusion'].get('solver_check->heur_bet', 0)
        self.assertGreater(pas, agr)
        self.assertGreater(pas, 5000)

    def test_agreement_plausivel(self):
        self.assertTrue(20.0 <= self.r['agreement_pct'] <= 80.0)


if __name__ == '__main__':
    unittest.main()
