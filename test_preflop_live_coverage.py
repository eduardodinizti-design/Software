"""TRAVA DE COBERTURA PRE-FLOP AO VIVO (regra do Eduardo 15/11: cobertura em TODAS
as situacoes preflop, funcionando p/ sempre). Roda o auditor contra o pack validado
real e EXIGE os pisos de cobertura por categoria. Se alguem quebrar o roteamento
(ex.: squeeze/vs_open curto voltar a abster), este teste FALHA. Pula se o pack real
nao estiver presente (CI sem o arquivo)."""
import os
import unittest

import auditar_cobertura_preflop as aud
from preflop_advisor import PreflopAdvisor

PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'


@unittest.skipUnless(os.path.exists(PACK), 'pack validado real ausente')
class PreflopLiveCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adv = PreflopAdvisor.from_file(PACK)
        cls.by_cat = {}
        cls.by_cat_cov = {}
        for cat, _label, _stk, state in aud.enumerate_situations():
            cls.by_cat[cat] = cls.by_cat.get(cat, 0) + 1
            ok, _ = aud._covered(cls.adv, state)
            if ok:
                cls.by_cat_cov[cat] = cls.by_cat_cov.get(cat, 0) + 1

    def _cov(self, cat):
        return self.by_cat_cov.get(cat, 0), self.by_cat.get(cat, 0)

    def test_first_in_full(self):
        c, t = self._cov('first_in')
        self.assertEqual(c, t)                      # abrir: 100%

    def test_vs_open_full(self):
        c, t = self._cov('vs_open')
        self.assertEqual(c, t)                      # enfrentar open: 100% (jam curto + misto fundo)

    def test_vs_3bet_full(self):
        c, t = self._cov('vs_3bet')
        self.assertEqual(c, t)                      # enfrentar 3bet: 100% (call-off curto + no fundo)

    def test_squeeze_short_and_mid_covered(self):
        c, t = self._cov('squeeze')
        self.assertGreaterEqual(c, 35)              # squeeze <=25bb via 3bet_shove; deep 30-40 e gap de range

    def test_overall_floor(self):
        cov = sum(self.by_cat_cov.values())
        tot = sum(self.by_cat.values())
        self.assertGreaterEqual(cov / tot, 0.96)    # piso global 96% (restante = gaps de range reais)

    def test_squeeze_aqo_jam_is_validated(self):
        # O BUG REAL (15/11): AQo SB squeeze curto DEVE jamar validado, nunca call/abster.
        state = dict(positions={'hero': 'SB', 's_lj': 'LJ', 's_btn': 'BTN'},
                     seats={'hero': dict(stack_bb=12, occupied=True),
                            's_lj': dict(stack_bb=30, occupied=True),
                            's_btn': dict(stack_bb=25, occupied=True)},
                     bets=[dict(seat='s_lj', bet_bb=2.0), dict(seat='s_btn', bet_bb=2.0)])
        r = self.adv.advise_from_reading(state, ['Ad', 'Qh'], mode='chip_ev')
        self.assertEqual(r['recommended'], 'all_in')
        self.assertTrue(r['validated'])


if __name__ == '__main__':
    unittest.main()
