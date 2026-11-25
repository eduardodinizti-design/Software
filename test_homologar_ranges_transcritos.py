"""Trava o gate de homologação/promoção dos ranges transcritos: só promove GTOWizard
(reg_life_transcrito) que passa a SANIDADE e é GAP; PKO fica em sombra; degenerado reprova."""
import os
import unittest

import homologar_ranges_transcritos as hm


def _node(spot='open_raise', raise_f=0.5, fold_f=0.5, src='reg_life_transcrito'):
    return {'id': 'x', 'spot': spot, 'hero': 'BTN', 'vs': [], 'source': src,
            'legalActions': ['raise', 'fold'], 'context': {'mode': 'chip_ev', 'stack': 55},
            'freq': {'raise': [raise_f] * 169, 'fold': [fold_f] * 169}}


class Sanidade(unittest.TestCase):
    def test_aceita_range_valido(self):
        ok, _ = hm._sane(_node(raise_f=0.3, fold_f=0.7))
        self.assertTrue(ok)

    def test_rejeita_soma_errada(self):
        ok, why = hm._sane(_node(raise_f=0.5, fold_f=0.8))     # soma 1.3
        self.assertFalse(ok)
        self.assertIn('SOMA', why)

    def test_rejeita_degenerado_tudo_fold(self):
        ok, why = hm._sane(_node(raise_f=0.0, fold_f=1.0))
        self.assertFalse(ok)
        self.assertIn('DEGENERADO', why)


_SHADOW = os.path.join('strategy_data', 'ranges_reg_life_shadow.json')


@unittest.skipUnless(os.path.exists(_SHADOW) and os.path.exists(hm._VAL), 'packs ausentes')
class Promocao(unittest.TestCase):
    def test_promove_so_gtowizard_gaps(self):
        promoted, held, failed = hm.homologate()
        self.assertTrue(promoted)
        self.assertTrue(all(n.get('validated') is True for n in promoted))
        self.assertTrue(all(n.get('source') == 'reg_life_transcrito' for n in promoted))

    def test_pko_fica_em_sombra(self):
        promoted, held, failed = hm.homologate()
        pko = [n for n in held if n.get('source') == 'reg_life_bounty']
        self.assertTrue(pko)
        self.assertTrue(all(n.get('validated') is False for n in pko))

    def test_promovidos_nunca_sobrepoem_o_VALIDADO(self):
        # promovidos podem UPGRADAR o deep (não-validado), mas NUNCA tocar o já-validado
        import json
        promoted, _, _ = hm.homologate()
        valk = set()
        for n in json.load(open(hm._VAL, encoding='utf-8')).get('nodes', []):
            valk.add(hm._key(n))
        for n in promoted:
            self.assertNotIn(hm._key(n), valk)


if __name__ == '__main__':
    unittest.main()
