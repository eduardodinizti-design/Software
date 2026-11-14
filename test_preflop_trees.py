"""Port do Clone 0.5: árvores de EV pré-flop como fonte de ESTUDO no PreflopAdvisor.

Invariante central: uma resposta de árvore NUNCA é auto-executável (validated=False,
execution_allowed=False, não autorizada pelo decision_contract). E a consulta é
OPT-IN: um advise() sem `scenario` se comporta EXATAMENTE como antes (regressão).

Exercita as 12 árvores REAIS em strategy_data/preflop_trees/ (não fixtures sintéticos)."""
import unittest

import decision_contract
from preflop_advisor import PreflopAdvisor
from preflop_tree_book import TreeBook
from test_preflop_advisor import pack_with_node


class TreePortTests(unittest.TestCase):
    def setUp(self):
        # pack_with_node() = nó validado BTN 25 (o advisor normal). As árvores reais
        # carregam sob demanda (lazy) do diretório padrão no 1º consult opt-in.
        self.a = PreflopAdvisor(pack_with_node())

    # ---- a consulta é OPT-IN: sem scenario, nada muda ---------------------------
    def test_sem_scenario_comportamento_inalterado(self):
        r = self.a.advise(hero_cards=['As', 'Ac'], hero_position='BTN', stack_bb=25)
        self.assertEqual(r['status'], 'ADVICE')
        self.assertNotEqual(r.get('origin'), 'CONTEXTUAL_TREE_REFERENCE')
        # o advisor nem precisou tocar nas árvores
        self.assertIsNone(self.a.tree_book)

    # ---- árvore casa e vem como ESTUDO não-executável ---------------------------
    def test_arvore_vs_3bet_e_conselho_nao_executavel(self):
        r = self.a.advise(hero_cards=['As', 'Ah'], hero_position='CO', stack_bb=50,
                          scenario='vs_3bet', aggressor='SB', effective_stack_bb=50.,
                          to_beat=7.5, to_call=5.)
        self.assertEqual(r['status'], 'ADVICE')
        self.assertEqual(r['origin'], 'CONTEXTUAL_TREE_REFERENCE')
        self.assertTrue(r['node_id'].startswith('CO_vs_SB_3bet'))
        # INVARIANTE: nunca auto-executável
        self.assertFalse(r['validated'])
        self.assertFalse(r['solver_validated'])
        self.assertFalse(r['execution_allowed'])
        self.assertIn('CONTEXTUAL_TREE_REFERENCE', r['caveats'])
        self.assertTrue(r['mix'])  # tem mistura de ações

    def test_contrato_nao_autoriza_commit_de_arvore(self):
        r = self.a.advise(hero_cards=['As', 'Ah'], hero_position='CO', stack_bb=50,
                          scenario='vs_3bet', aggressor='SB', effective_stack_bb=50.,
                          to_beat=7.5, to_call=5.)
        verdict = decision_contract.evaluate(r, action=r['recommended'],
                                             hero_cards=['As', 'Ah'])
        # o decision_contract NUNCA libera ficha num nó não-validado agressivo
        if r['recommended'] not in ('fold', 'check'):
            self.assertFalse(verdict['execution_allowed'])
            self.assertNotEqual(verdict['authority'], 'VALIDATED')

    # ---- tradução do nosso nome de cenário p/ o da árvore -----------------------
    def test_alias_vs_4bet_or_more_casa_arvore_vs_4bet(self):
        r = self.a.advise(hero_cards=['Ks', 'Kh'], hero_position='SB', stack_bb=80,
                          scenario='vs_4bet_or_more', aggressor='CO', effective_stack_bb=80.)
        self.assertEqual(r['origin'], 'CONTEXTUAL_TREE_REFERENCE')
        self.assertTrue(r['node_id'].startswith('SB_vs_CO_4bet'))
        self.assertFalse(r['execution_allowed'])

    # ---- study-only não aparece ao vivo; só em modo estudo ----------------------
    def test_study_only_escondido_ao_vivo_e_visivel_em_estudo(self):
        kw = dict(hero_cards=['As', 'Ah'], hero_position='BB', stack_bb=50,
                  scenario='open_with_callers', aggressor='UTG', callers=['HJ', 'CO'],
                  effective_stack_bb=50.)
        live = self.a.advise(**kw)
        self.assertNotEqual(live.get('origin'), 'CONTEXTUAL_TREE_REFERENCE')  # oculto
        study = self.a.advise(reference_tree_study=True, **kw)
        self.assertEqual(study['origin'], 'CONTEXTUAL_TREE_REFERENCE')
        self.assertTrue(study['research_only'])
        self.assertIn('STUDY_ONLY_TREE_NOT_CONVERGED', study['caveats'])

    # ---- contexto que não casa cai no fluxo normal ------------------------------
    def test_agressor_diferente_nao_reusa_arvore(self):
        r = self.a.advise(hero_cards=['As', 'Ah'], hero_position='CO', stack_bb=50,
                          scenario='vs_3bet', aggressor='BB', effective_stack_bb=50.,
                          to_beat=7.5, to_call=5.)
        self.assertNotEqual(r.get('origin'), 'CONTEXTUAL_TREE_REFERENCE')

    def test_facing_all_in_nao_usa_arvore_nao_terminal(self):
        r = self.a.advise(hero_cards=['As', 'Ah'], hero_position='CO', stack_bb=50,
                          scenario='vs_3bet', aggressor='SB', effective_stack_bb=50.,
                          to_beat=7.5, to_call=5., facing_all_in=True)
        self.assertNotEqual(r.get('origin'), 'CONTEXTUAL_TREE_REFERENCE')

    def test_profundidade_diferente_segue_referencia_sem_travar(self):
        # 500bb: fora das profundidades (50/80/200). Casa a mais próxima (200) e
        # declara a diferença — mas continua não-executável.
        r = self.a.advise(hero_cards=['As', 'Ah'], hero_position='CO', stack_bb=500,
                          scenario='vs_3bet', aggressor='SB', effective_stack_bb=500.,
                          to_beat=7.5, to_call=5., reference_tree_study=True)
        self.assertEqual(r['origin'], 'CONTEXTUAL_TREE_REFERENCE')
        self.assertTrue(r['bucketed'])
        self.assertFalse(r['execution_allowed'])
        self.assertTrue(any(c.startswith('TREE_DEPTH_') for c in r['caveats']))

    # ---- robustez: cartas inválidas não quebram, caem no fluxo normal -----------
    def test_cartas_invalidas_com_scenario_nao_quebra(self):
        r = self.a.advise(hero_cards=['Xx', 'Ah'], hero_position='CO', stack_bb=50,
                          scenario='vs_3bet', aggressor='SB', effective_stack_bb=50.)
        self.assertEqual(r['status'], 'ABSTAIN')  # fluxo normal abstém

    # ---- diretório ausente não quebra (árvore é opcional) -----------------------
    def test_sem_arvores_nao_quebra(self):
        a = PreflopAdvisor(pack_with_node(), tree_book=TreeBook())  # livro vazio
        r = a.advise(hero_cards=['As', 'Ah'], hero_position='CO', stack_bb=50,
                     scenario='vs_3bet', aggressor='SB', effective_stack_bb=50.)
        self.assertNotEqual(r.get('origin'), 'CONTEXTUAL_TREE_REFERENCE')


if __name__ == '__main__':
    unittest.main()
