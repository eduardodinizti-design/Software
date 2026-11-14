"""Ledger de cobertura pré-flop: completude por contexto (84 nós = 100%),
células faltantes explícitas, e surrogate de stack rotulado (nunca buraco mudo)."""
import unittest

import hrc_ingest as hi
import preflop_coverage as pc


def _node(mode, stage, stack, spot, hero, vs=(), spread=None, fmt='regular'):
    return dict(context=dict(mode=mode, format=fmt, stage=stage, players=9, stack=stack),
                spot=spot, hero=hero, vs=list(vs), spread=spread, validated=False)


def _full_context(mode='chip_ev', stage='early', stack=25, spread=None):
    """84 nós = contexto 9-max completo."""
    nodes = [_node(mode, stage, stack, 'open_raise', h, spread=spread) for h in pc.OPENERS]
    for (op, later) in pc.expected_pairs():
        nodes.append(_node(mode, stage, stack, 'vs_open', later, (op,), spread))
        nodes.append(_node(mode, stage, stack, 'vs_3bet', op, (later,), spread))
    for k in ('sb_first_in', 'vs_limp', 'vs_iso', 'vs_limp_jam'):
        hero = 'SB' if k in ('sb_first_in', 'vs_iso') else 'BB'
        vs = () if k == 'sb_first_in' else (('BB',) if k == 'vs_iso' else ('SB',))
        nodes.append(_node(mode, stage, stack, k, hero, vs, spread))
    return nodes


class ExpectedTests(unittest.TestCase):
    def test_pairs_are_36(self):
        self.assertEqual(len(pc.expected_pairs()), 36)

    def test_full_context_is_84(self):
        self.assertEqual(pc.FULL_CONTEXT_NODES, 84)
        self.assertEqual(len(_full_context()), 84)


class CoverageTests(unittest.TestCase):
    def test_full_context_is_100pct(self):
        pack = dict(nodes=_full_context())
        rep = pc.coverage_by_context(pack)
        (ctx, r), = rep.items()
        self.assertEqual(r['completeness'], 1.0)
        self.assertEqual(r['missing'], {})

    def test_partial_lists_missing_cells(self):
        nodes = _full_context()
        # remove o RFI do BTN e um par vs_open -> devem aparecer em 'missing'
        nodes = [n for n in nodes if not (n['spot'] == 'open_raise' and n['hero'] == 'BTN')]
        nodes = [n for n in nodes if not (n['spot'] == 'vs_open' and n['hero'] == 'BB' and n['vs'] == ['BTN'])]
        rep = pc.coverage_by_context(dict(nodes=nodes))
        (ctx, r), = rep.items()
        self.assertLess(r['completeness'], 1.0)
        self.assertIn('BTN', r['missing']['open_raise'])
        self.assertIn(('BTN', 'BB'), r['missing']['vs_open'])

    def test_summarize_counts_full_and_partial(self):
        pack = dict(nodes=_full_context('chip_ev', 'early', 25)
                    + _full_context('icm', 'ft', 30, 'iguais')[:-5])   # 2º incompleto
        s = pc.summarize(pack)
        self.assertEqual(s['contexts'], 2)
        self.assertEqual(s['contexts_full'], 1)
        self.assertEqual(s['contexts_partial'], 1)


class SurrogateTests(unittest.TestCase):
    def test_nearest_stack_exact_is_solved(self):
        self.assertEqual(pc.nearest_stack(25, [15, 25, 40]), (25, 'solved'))

    def test_nearest_stack_approx_is_surrogate(self):
        self.assertEqual(pc.nearest_stack(22, [15, 25, 40]), (25, 'surrogate'))

    def test_no_data_is_null(self):
        self.assertEqual(pc.nearest_stack(22, []), (None, 'null'))

    def test_query_grid_labels_each_cell(self):
        pack = dict(nodes=_full_context('chip_ev', 'early', 25))
        grid = pc.query_grid(pack, stacks=[25, 22, 100],
                             modes_stages=[('chip_ev', 'regular', 'early', None)],
                             spots=('open_raise',))
        kinds = {g['stack']: g['kind'] for g in grid}
        self.assertEqual(kinds[25], 'solved')
        self.assertEqual(kinds[22], 'surrogate')      # 22 -> 25 (mais próximo)
        self.assertEqual(kinds[100], 'surrogate')     # deep -> 25 (único bucket)


class RealPackSmokeTests(unittest.TestCase):
    """Fumaça contra a biblioteca HRC real, se presente (não falha se ausente)."""
    HRC = ('C:/Meus Projetos/Aplicativos/range-coach-pro-'
           '356340d98ec068ef07fd3d6221bdc5c53bf4dff7/public/solver/hrc')

    def test_real_library_contexts_are_full_or_explicit(self):
        from pathlib import Path
        d = Path(self.HRC)
        if not d.exists():
            self.skipTest('biblioteca HRC não presente neste ambiente')
        paths = sorted(p for p in d.glob('*.json') if p.name != 'manifest.json')
        pack = hi.build_pack(paths)
        s = pc.summarize(pack)
        self.assertGreater(s['contexts'], 20)
        self.assertEqual(s['nodes_total'], 2798)


if __name__ == '__main__':
    unittest.main()
