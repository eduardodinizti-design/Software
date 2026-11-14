"""Ingestor HRC -> pack de estudo (preflop). Contratos:
- nome de arquivo -> contexto (mode/format/stage/stack/spread) correto, sem adivinhar;
- 169 classes REINDEXADAS por STRING (ordem do HRC é irrelevante): fidelidade exata;
- fold derivado do complemento; frequências somam ~1;
- TODO nó validated=False (estudo/sombra) — nunca executável só por ter sido ingerido;
- o pack resultante CARREGA no PreflopAdvisor.
"""
import json
import tempfile
import unittest
from pathlib import Path

import hrc_ingest as hi
from preflop_advisor import PreflopAdvisor


def _synthetic_hrc(name='hrc_chip_25', hrc_hands=None, unit='bb'):
    """Arquivo HRC mínimo com a ordem de mãos EMBARALHADA (invertida) p/ provar o
    reindex por string. UTG abre AA 100%; BB paga KK 100% vs UTG; resto fold."""
    hands = hrc_hands or list(reversed(hi.HANDS))      # ordem diferente da nossa
    iaa, ikk = hands.index('AA'), hands.index('KK')
    raise_arr = [1.0 if i == iaa else 0.0 for i in range(169)]
    call_arr = [1.0 if i == ikk else 0.0 for i in range(169)]
    zeros = [0.0] * 169
    return {
        'format': 1, 'name': name, 'note': 'synthetic', 'unit': unit,
        'version': 'syn-1', 'source': 'TEST', 'stacks': [25.0] * 9, 'hands': hands,
        'rfi': {'UTG': {'raise': raise_arr, 'shove': zeros,
                        'ev': {'raise': [2.0] * 169, 'shove': zeros, 'fold': zeros}}},
        'resp': {'UTG>BB': {'call': call_arr, 'three': zeros, 'shove': zeros,
                            'ev': {'call': [1.0] * 169, 'three': zeros, 'shove': zeros, 'fold': zeros}}},
        'opv3': {'UTG>BB': {'call': zeros, 'shove': [1.0 if i == iaa else 0.0 for i in range(169)],
                            'ev': {'call': zeros, 'shove': [3.0] * 169, 'fold': zeros}}},
        'limp': {'bbVsLimp': {'check': {'freq': [1.0] * 169, 'ev': zeros},
                              'raise': {'freq': zeros, 'ev': zeros}}},
    }


class ContextTests(unittest.TestCase):
    def test_chip(self):
        c = hi.family_context('hrc_chip_15')
        self.assertEqual((c['mode'], c['format'], c['stage'], c['stack'], c['spread']),
                         ('chip_ev', 'regular', 'early', 15, None))

    def test_ft_icm_bucket(self):
        c = hi.family_context('hrc_ft_iguais_icm_30')
        self.assertEqual((c['mode'], c['format'], c['stage'], c['stack'], c['spread']),
                         ('icm', 'regular', 'ft', 30, 'iguais'))

    def test_curtos_subphase_distinct_spread(self):
        ini = hi.family_context('hrc_ft_curtos_ini_pko', stacks=[25.0] * 9)
        fim = hi.family_context('hrc_ft_curtos_fim_pko', stacks=[25.0] * 9)
        self.assertEqual((ini['mode'], ini['format']), ('pko_icm', 'pko'))
        self.assertNotEqual(ini['spread'], fim['spread'])         # chaves não colidem

    def test_stack_from_stacks_when_no_suffix(self):
        c = hi.family_context('hrc_bubble_iguais_icm', stacks=[20.0] * 9)
        self.assertEqual(c['stack'], 20)

    def test_bad_name_raises(self):
        with self.assertRaises(hi.IngestError):
            hi.family_context('lixo_qualquer')

    def test_pko_shortcuts(self):
        self.assertEqual(hi.family_context('hrc_pkoearly_25')['format'], 'pko')


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.f = self.tmp / 'hrc_chip_25.json'
        self.f.write_text(json.dumps(_synthetic_hrc()), encoding='utf-8')

    def test_reindex_by_string_is_exact(self):
        # AA está na ponta OPOSTA na ordem embaralhada; o valor deve seguir a STRING.
        nodes, _ = hi.nodes_from_file(self.f)
        rfi = [n for n in nodes if n['spot'] == 'open_raise' and n['hero'] == 'UTG'][0]
        iaa = hi.HANDS.index('AA')
        self.assertEqual(rfi['freq']['raise'][iaa], 1.0)
        self.assertEqual(sum(rfi['freq']['raise']), 1.0)          # só AA

    def test_all_nodes_shadow(self):
        nodes, _ = hi.nodes_from_file(self.f)
        self.assertTrue(nodes)
        self.assertTrue(all(n['validated'] is False for n in nodes))
        self.assertTrue(all(n['origin'].startswith('HRC') for n in nodes))

    def test_spots_emitted(self):
        nodes, _ = hi.nodes_from_file(self.f)
        spots = {n['spot'] for n in nodes}
        self.assertEqual(spots, {'open_raise', 'vs_open', 'vs_3bet', 'vs_limp'})

    def test_vs_open_hero_and_opener(self):
        nodes, _ = hi.nodes_from_file(self.f)
        vo = [n for n in nodes if n['spot'] == 'vs_open'][0]
        self.assertEqual((vo['hero'], tuple(vo['vs'])), ('BB', ('UTG',)))
        ikk = hi.HANDS.index('KK')
        self.assertEqual(vo['freq']['call'][ikk], 1.0)

    def test_shove_maps_to_all_in(self):
        nodes, _ = hi.nodes_from_file(self.f)
        v3 = [n for n in nodes if n['spot'] == 'vs_3bet'][0]
        self.assertIn('all_in', v3['actions'])                    # HRC 'shove' -> 'all_in'
        self.assertNotIn('shove', v3['actions'])

    def test_fold_derived_complements(self):
        nodes, _ = hi.nodes_from_file(self.f)
        rfi = [n for n in nodes if n['spot'] == 'open_raise'][0]
        iaa, ikk = hi.HANDS.index('AA'), hi.HANDS.index('KK')
        self.assertAlmostEqual(rfi['freq']['fold'][iaa], 0.0)     # AA abre, não folda
        self.assertAlmostEqual(rfi['freq']['fold'][ikk], 1.0)     # KK folda (nada setado)

    def test_source_provenance(self):
        _, src = hi.nodes_from_file(self.f)
        self.assertEqual(len(src['sha256']), 64)
        self.assertEqual(src['name'], 'hrc_chip_25')


class PackLoadsTests(unittest.TestCase):
    def test_pack_loads_in_advisor_all_shadow(self):
        tmp = Path(tempfile.mkdtemp())
        for nm in ('hrc_chip_25', 'hrc_ft_iguais_icm_30'):
            (tmp / (nm + '.json')).write_text(json.dumps(_synthetic_hrc(name=nm)), encoding='utf-8')
        pack = hi.build_pack(sorted(tmp.glob('*.json')))
        out = tmp / 'pack.json'
        out.write_text(json.dumps(pack, ensure_ascii=False), encoding='utf-8')
        a = PreflopAdvisor.from_file(out, strict=False)
        m = a.manifest()
        self.assertEqual(m['validated_nodes'], 0)                 # sombra: nada executável
        self.assertGreater(m['index_keys'], 0)
        self.assertEqual(len(m['collisions']), 0)


if __name__ == '__main__':
    unittest.main()
