"""Trava a ingestão dos ranges TRANSCRITOS como sombra (validated=False) no roteamento:
nós no formato nvt-range-export, ordem row-major das 169 mãos, e — no merge — o sombra
PREENCHE gaps de bucket mas NUNCA sobrepõe um nó validado."""
import os
import unittest

import ingerir_ranges_transcritos as ing


class BuildNodes(unittest.TestCase):
    def setUp(self):
        self.nodes, self.defer = ing.build_nodes()

    def test_gera_nos_todos_sombra(self):
        self.assertTrue(self.nodes)
        self.assertTrue(all(n.get('validated') is False for n in self.nodes))
        spots = {n['spot'] for n in self.nodes}
        self.assertEqual(spots, {'open_raise', 'vs_open', 'vs_limp', 'vs_open_shove'})

    def test_freq_array_169_e_ordem_rowmajor(self):
        self.assertEqual(ing.HANDS[:3], ['AA', 'AKs', 'AQs'])   # = ordem do bundle validado
        n = next(x for x in self.nodes if x['spot'] == 'open_raise')
        for arr in n['freq'].values():
            self.assertEqual(len(arr), 169)

    def test_rfi_soma_1_por_mao(self):
        n = next(x for x in self.nodes if x['spot'] == 'open_raise')
        for i in range(169):
            self.assertAlmostEqual(sum(a[i] for a in n['freq'].values()), 1.0, places=2)

    def test_shove_ingerido_call_off(self):
        sh = [n for n in self.nodes if n['spot'] == 'vs_open_shove']
        self.assertTrue(sh)
        for n in sh:
            self.assertEqual(n['hero'], 'BB')
            self.assertEqual(tuple(n['vs']), ('SB',))
            self.assertIn('call', n['freq'])

    def test_pko_rfi_ingerido_e_snap_bucket(self):
        pko = ing.build_pko_nodes()
        self.assertTrue(pko)
        for n in pko:
            self.assertEqual(n['context']['mode'], 'pko')
            self.assertEqual(n['spot'], 'open_raise')
            self.assertIn(n['context']['stack'], ing._BUCKETS)   # snapado ao bucket nativo

    def test_snap_ao_bucket_nativo(self):
        self.assertEqual(ing._snap(70), 60)
        self.assertEqual(ing._snap(21), 20)
        self.assertEqual(ing._snap(50), 50)


_V = 'dist_bot/NVTBot/_internal/nvt-ranges-validados.json'
_D = 'dist_bot/NVTBot/_internal/nvt-ranges-deep.json'
_S = os.path.join('strategy_data', 'ranges_reg_life_shadow.json')


@unittest.skipUnless(os.path.exists(_V) and os.path.exists(_S), 'bundles ausentes')
class MergeNoRoteamento(unittest.TestCase):
    def _adv(self):
        from preflop_advisor import PreflopAdvisor
        packs = [p for p in (_V, _D, _S) if os.path.exists(p)]
        return PreflopAdvisor.from_files(*packs, strict=False)

    def test_sombra_preenche_gap_50bb(self):
        adv = self._adv()
        n = adv._index.get(('chip_ev', 'regular', 'mid', 9, 50, 'open_raise', 'BTN', (), None))
        self.assertIsNotNone(n)
        self.assertEqual(n.get('source'), 'reg_life_transcrito')
        self.assertIs(n.get('validated'), False)

    def test_validado_vence_no_15bb(self):
        adv = self._adv()
        n = adv._index.get(('chip_ev', 'regular', 'mid', 9, 15, 'open_raise', 'BTN', (), None))
        self.assertIsNotNone(n)
        self.assertIs(n.get('validated'), True)
        self.assertNotEqual(n.get('source'), 'reg_life_transcrito')


if __name__ == '__main__':
    unittest.main()
