"""Testes do ingestor de ARVORE HRC (push/fold + resteal). Unit-level: nao depende
dos .zip reais (que sao grandes/externos); valida nome->contexto, snap de bucket e
a classificacao de spot pela sequence, e um smoke sobre um .zip real se existir."""
import glob
import os
import unittest

import hrc_ingest
import hrc_tree_ingest as ti

SH = r'C:\Meus Projetos\Aplicativos\HoldemResources\SavedHands'


class ContextFromName(unittest.TestCase):
    def test_chip_resteal_is_mid_no_spread(self):
        self.assertEqual(ti.context_from_name('nresteal_chip12'), ('chip_ev', 'regular', 'mid', None))

    def test_icm_pushfold_curtos(self):
        self.assertEqual(ti.context_from_name('npf_icm_bubble_curtosfim'),
                         ('icm', 'regular', 'bubble', 'curtos_fim'))
        self.assertEqual(ti.context_from_name('npf_icm_ft_curtosini'),
                         ('icm', 'regular', 'ft', 'curtos_ini'))

    def test_icm_pushfold_iguais_default(self):
        self.assertEqual(ti.context_from_name('npf_icm_bubble10'),
                         ('icm', 'regular', 'bubble', 'iguais'))

    def test_pko_mid_vs_pkoicm_staged(self):
        self.assertEqual(ti.context_from_name('npf_pko_mid10'), ('pko', 'pko', 'mid', None))
        self.assertEqual(ti.context_from_name('npf_pko_bubble10'),
                         ('pko_icm', 'pko', 'bubble', 'iguais'))

    def test_variant_suffix_and_bad_name(self):
        self.assertEqual(ti.context_from_name('nresteal_icm_bubble15c'),
                         ('icm', 'regular', 'bubble', 'iguais'))
        with self.assertRaises(ti.TreeIngestError):
            ti.context_from_name('alguma_coisa_qualquer')


class SnapBucket(unittest.TestCase):
    def test_snaps_to_nearest_tie_lower(self):
        self.assertEqual(ti._snap_bucket(17.5), 15)      # empate 15/20 -> menor (jam mais tight)
        self.assertEqual(ti._snap_bucket(12.4), 12)
        self.assertEqual(ti._snap_bucket(9.0), 8)        # empate 8/10 -> 8


def _hands(jam_frac_by_class):
    """169 classes: played=[fold,jam] onde jam = freq dada (default 0)."""
    h = {}
    for hk in hrc_ingest.HANDS:
        j = jam_frac_by_class.get(hk, 0.0)
        h[hk] = {'weight': 1.0, 'played': [1.0 - j, j], 'evs': [0.0, 1.0]}
    return h


class ClassifySpot(unittest.TestCase):
    STACKS = [10.0] * 9              # bb ja normalizado nao importa aqui (usa stacks/bb externamente)

    def test_open_shove_first_in(self):
        node = dict(player=0, street=0, sequence=[],
                    actions=[{'type': 'F', 'amount': 0}, {'type': 'R', 'amount': 10.0}],
                    hands=_hands({'AA': 1.0}))
        cl = ti._classify(node, self.STACKS, 1.0)
        self.assertEqual(cl[:4], ('open_shove', 'UTG', (), 1))

    def test_vs_open_shove_over_a_jam(self):
        node = dict(player=2, street=0,
                    sequence=[{'player': 0, 'type': 'F'}, {'player': 1, 'type': 'R', 'amount': 10.0}],
                    actions=[{'type': 'F', 'amount': 0}, {'type': 'R', 'amount': 10.0}],
                    hands=_hands({'AA': 1.0}))
        cl = ti._classify(node, self.STACKS, 1.0)
        self.assertEqual(cl[:3], ('vs_open_shove', 'UTG+2', ('UTG+1',)))

    def test_3bet_shove_over_a_min_open(self):
        node = dict(player=1, street=0,
                    sequence=[{'player': 0, 'type': 'R', 'amount': 2.0}],   # open 2bb << stack
                    actions=[{'type': 'F', 'amount': 0}, {'type': 'R', 'amount': 10.0}],
                    hands=_hands({'AA': 1.0}))
        cl = ti._classify(node, self.STACKS, 1.0)
        self.assertEqual(cl[:3], ('3bet_shove', 'UTG+1', ('UTG',)))

    def test_skip_open_raise_not_shove(self):
        # first-in com min-raise disponivel (nao-jam) -> NAO e open_shove
        node = dict(player=0, street=0, sequence=[],
                    actions=[{'type': 'F', 'amount': 0}, {'type': 'R', 'amount': 2.0},
                             {'type': 'R', 'amount': 10.0}],
                    hands=_hands({'AA': 1.0}))
        self.assertIsNone(ti._classify(node, self.STACKS, 1.0))

    def test_skip_4bet_and_limp(self):
        two_raises = dict(player=2, street=0,
                          sequence=[{'player': 0, 'type': 'R', 'amount': 2.0},
                                    {'player': 1, 'type': 'R', 'amount': 6.0}],
                          actions=[{'type': 'F', 'amount': 0}, {'type': 'R', 'amount': 10.0}],
                          hands=_hands({'AA': 1.0}))
        self.assertIsNone(ti._classify(two_raises, self.STACKS, 1.0))
        limp = dict(player=1, street=0, sequence=[{'player': 0, 'type': 'C', 'amount': 1.0}],
                    actions=[{'type': 'F', 'amount': 0}, {'type': 'R', 'amount': 10.0}],
                    hands=_hands({'AA': 1.0}))
        self.assertIsNone(ti._classify(limp, self.STACKS, 1.0))


@unittest.skipUnless(glob.glob(os.path.join(SH, 'Hand Npf_icm_bubble_curtosfim.zip')),
                     'zips reais ausentes')
class SmokeRealZip(unittest.TestCase):
    def test_curtos_pushfold_yields_open_shove_aa_jams(self):
        f = glob.glob(os.path.join(SH, 'Hand Npf_icm_bubble_curtosfim.zip'))[0]
        nodes, src = ti.nodes_from_tree(f)
        self.assertTrue(nodes)
        osh = [n for n in nodes if n['spot'] == 'open_shove']
        self.assertTrue(osh)
        n = osh[0]
        self.assertEqual((n['context']['mode'], n['spread']), ('icm', 'curtos_fim'))
        iAA = hrc_ingest.HANDS.index('AA')
        self.assertGreater(n['freq']['all_in'][iAA], 0.9)      # AA jama
        self.assertFalse(n['validated'])                        # estudo


if __name__ == '__main__':
    unittest.main()
