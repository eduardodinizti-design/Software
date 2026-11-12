"""B05 — provar a LIGAÇÃO da fonte (plano de evolução do cérebro, Lote 1).

Critérios: nó conhecido reproduz a linha da fonte; mudança controlada da política
em fixture aparece na consulta; conflito é explícito; nó inexistente NÃO recebe
validade emprestada. Também cobre o B03 (consulta explicável: fonte, hash, nó)."""
import json
import os
import tempfile
import unittest

from preflop_study import RANKS
from preflop_advisor import PreflopAdvisor

HANDS = [r + r for r in RANKS] + [a + b + s for i, a in enumerate(RANKS)
                                  for b in RANKS[i + 1:] for s in ('s', 'o')]


def open_node(node_id, raise_row, *, hero='BTN', stack=25, validated=True, source='test'):
    """Nó open_raise com a LINHA de freq de 'raise' dada (169 valores); fold = 1-raise."""
    fold_row = [round(1.0 - r, 6) for r in raise_row]
    return dict(id=node_id, context=dict(mode='chip_ev', format='regular', stage='mid',
                players=9, stack=stack), spot='open_raise', hero=hero, vs=[],
                validated=validated, evUnit='bb', legalActions=['fold', 'raise'],
                actions=['raise', 'fold'], freq={'raise': raise_row, 'fold': fold_row},
                ev={'raise': [0.0] * 169, 'fold': [0.0] * 169}, outOfRange=[], source=source)


def pack(nodes):
    return dict(format='nvt-range-export', version=1, engineCommit='test', hands=HANDS, nodes=nodes)


def row_for(freqs):
    """Linha de 169 com freq de raise por mão (dict hand->freq), resto 0."""
    return [float(freqs.get(HANDS[k], 0.0)) for k in range(169)]


class ParityTests(unittest.TestCase):
    def test_query_reproduces_source_row(self):
        # Nó conhecido: AKs = 0.6 raise / 0.4 fold. A consulta reproduz EXATAMENTE a linha.
        a = PreflopAdvisor(pack([open_node('n1', row_for({'AKs': 0.6}))]))
        r = a.advise(hero_cards=['Ah', 'Kh'], hero_position='BTN', stack_bb=25)
        self.assertEqual(r['status'], 'ADVICE')
        mix = {m['action']: m['frequency'] for m in r['mix']}
        self.assertAlmostEqual(mix.get('raise'), 0.6)
        self.assertAlmostEqual(mix.get('fold'), 0.4)


class UpdateTests(unittest.TestCase):
    def test_controlled_policy_change_shows_in_query(self):
        # v1: AA abre 100%. v2: mesma chave, AA folda 100%. A consulta segue a fonte.
        v1 = PreflopAdvisor(pack([open_node('n', row_for({'AA': 1.0}))]))
        v2 = PreflopAdvisor(pack([open_node('n', row_for({'AA': 0.0}))]))
        q1 = v1.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=25)
        q2 = v2.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=25)
        self.assertEqual(q1['recommended'], 'raise')
        self.assertEqual(q2['recommended'], 'fold')


class ConflictTests(unittest.TestCase):
    def test_conflict_is_explicit_not_silent(self):
        # Referência (stale) + validado, MESMA chave: validado vence e a colisão é
        # registrada explicitamente (nunca escolha silenciosa).
        ref = open_node('stale', row_for({'AA': 0.0}), validated=False, source='reference')
        good = open_node('good', row_for({'AA': 1.0}), validated=True)
        a = PreflopAdvisor(pack([ref, good]))
        self.assertEqual(len(a.collisions), 1)
        self.assertEqual(a.collisions[0]['chosen'], 'good')
        self.assertEqual(a.advise(hero_cards=['As', 'Ac'], hero_position='BTN',
                                  stack_bb=25)['node_id'], 'good')


class NoScenarioTests(unittest.TestCase):
    def test_absent_context_abstains_no_borrowed_validity(self):
        # Só há nó de BTN. Consultar CO (sem nó em NENHUM bucket) -> ABSTÉM, sem validade.
        a = PreflopAdvisor(pack([open_node('n', row_for({'AA': 1.0}), hero='BTN')]))
        r = a.advise(hero_cards=['As', 'Ac'], hero_position='CO', stack_bb=25)
        self.assertEqual(r['status'], 'ABSTAIN')
        self.assertNotEqual(r.get('validated'), True)

    def test_borrowed_stack_is_never_validated(self):
        # Nó só em 25bb; consultar 30bb (sem nó) empresta o de 25 -> validated=False.
        a = PreflopAdvisor(pack([open_node('n', row_for({'AA': 1.0}), stack=25)]))
        r = a.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=30)
        self.assertEqual(r['status'], 'ADVICE')
        self.assertFalse(r['validated'])            # validade NÃO é emprestada
        self.assertEqual(r['stack_borrowed_from'], 25)
        self.assertTrue(any(c.startswith('STACK_BORROWED') for c in r['caveats']))


class ExplainLinkageTests(unittest.TestCase):
    """B03: a explicação liga a recomendação à fonte (hash + nó) e mostra o diff."""

    def test_explain_carries_source_hash_and_node(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'pack.json')
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(pack([open_node('n1', row_for({'AKs': 1.0}))]), fh)
        a = PreflopAdvisor.from_file(p)
        ex = a.explain(hero_cards=['Ah', 'Kh'], hero_position='BTN', stack_bb=25)
        self.assertEqual(ex['source']['node_id'], 'n1')
        self.assertEqual(len(ex['source']['pack_sha256'][0]), 64)
        self.assertEqual(ex['source']['node_context']['stack'], 25)
        self.assertEqual(ex['differences'], {})                 # exato, sem aproximação
        self.assertEqual(ex['answer']['recommended'], 'raise')

    def test_explain_shows_bucketing_difference(self):
        a = PreflopAdvisor(pack([open_node('n1', row_for({'AKs': 1.0}), stack=25)]))
        ex = a.explain(hero_cards=['Ah', 'Kh'], hero_position='BTN', stack_bb=27)
        self.assertEqual(ex['differences']['stack_bucketed'], dict(from_bb=27, to_bucket=25))


if __name__ == '__main__':
    unittest.main()
