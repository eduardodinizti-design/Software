"""Sombra SB x BB 40bb SRP (estudo incremental). Valida o scaffold: contexto casa só
no spot certo, lookup do flop-lead do SB devolve a política amostrada, execution_allowed
False (shadow), fora-da-amostra = None. Pula se o pack ainda não foi ingerido."""
import os
import unittest

import solver_sb40_shadow as s

PACK = s.DATA


@unittest.skipUnless(os.path.exists(PACK), 'pack SB40 ainda não ingerido')
class SB40ShadowScaffold(unittest.TestCase):
    def setUp(self):
        s._PACK = None                      # força recarregar do disco
        self.pack = s.load_pack()

    def test_tem_pontos_e_contexto(self):
        cov = s.coverage()
        self.assertGreater(cov['points'], 0)
        self.assertGreater(cov['flops'], 0)
        self.assertEqual(tuple(self.pack['context']['positions']), ('SB', 'BB'))
        self.assertEqual(self.pack['context']['pot_type'], 'single_raised')

    def test_contexto_casa_so_no_spot_certo(self):
        self.assertTrue(s.context_matches(('SB', 'BB'), 'single_raised', 'chip_ev', 40))
        self.assertFalse(s.context_matches(('BTN', 'BB'), 'single_raised', 'chip_ev', 40))
        self.assertFalse(s.context_matches(('SB', 'BB'), 'single_raised', 'chip_ev', 20))
        self.assertFalse(s.context_matches(('SB', 'BB'), '3bet', 'chip_ev', 40))

    def test_flop_lead_do_sb_devolve_politica_shadow(self):
        # pega QUALQUER ponto de flop (combo@raiz) do pack e confirma o lookup.
        found = None
        for fe in self.pack['flops'].values():
            flop_root = (fe.get('streets', {}).get('flop', {}) or {}).get('')
            if flop_root:
                combo = next(iter(flop_root))
                found = (fe['board'], combo)
                break
        self.assertIsNotNone(found, 'pack sem ponto de flop-raiz')
        board, combo = found
        hero = [combo[:2], combo[2:]]
        r = s.flop_policy(hero, board)
        self.assertIsNotNone(r)
        self.assertFalse(r['execution_allowed'])            # SHADOW, nunca executa
        self.assertTrue(r['candidates'])                    # tem frequências por ação
        self.assertAlmostEqual(sum(c[1] for c in r['candidates']), 1.0, places=2)

    def test_fora_da_amostra_retorna_none(self):
        # combo improvável em qualquer flop amostrado
        self.assertIsNone(s.flop_policy(['Ah', 'Ad'], ['2c', '3d', '4h']))

    def test_board_fora_do_estudo_none(self):
        self.assertIsNone(s.flop_policy(['Kc', 'Qc'], ['2c', '3d', '4h']))


if __name__ == '__main__':
    unittest.main()
