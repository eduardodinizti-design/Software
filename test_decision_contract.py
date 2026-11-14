"""Contrato de validade B04 (decision_contract): requisitos separados + autoridade.

Invariantes do plano viram testes: abstenção/fallback nunca viram 'validated';
margem de call-off e rótulo premium NÃO substituem os demais requisitos."""
import unittest

from decision_contract import evaluate

CARDS = ['As', 'Ac']


def adv(rec, **kw):
    return dict(dict(status='ADVICE', recommended=rec), **kw)


class ContractTests(unittest.TestCase):
    # ---- piso de segurança (não-commit) ----
    def test_fold_is_safety_noncommit_never_validated(self):
        c = evaluate(adv('fold'), action='FOLD', hero_cards=CARDS)
        self.assertEqual(c['authority'], 'SAFETY_NONCOMMIT')
        self.assertTrue(c['execution_allowed'])
        self.assertFalse(c['source_validated'])

    def test_check_allowed_without_cards_noncommit(self):
        c = evaluate(adv('check'), action='CHECK', hero_cards=None)
        self.assertEqual(c['authority'], 'SAFETY_NONCOMMIT')
        self.assertTrue(c['execution_allowed'])      # não arrisca ficha

    def test_noncommit_blocked_when_illegal(self):
        c = evaluate(adv('fold'), action='FOLD', hero_cards=CARDS, action_available=False)
        self.assertFalse(c['execution_allowed'])
        self.assertIn('ACAO_ILEGAL', c['blockers'])

    # ---- commit validado ----
    def test_validated_call_all_requirements_met(self):
        c = evaluate(adv('call', validated=True), action='CALL', hero_cards=CARDS)
        self.assertEqual(c['authority'], 'VALIDATED')
        self.assertTrue(c['execution_allowed'])
        self.assertTrue(all(c[k] for k in ('source_validated', 'context_match',
                                           'observation_confirmed', 'action_legal',
                                           'sizing_supported')))

    def test_validated_call_without_cards_is_blocked(self):
        # Observação NÃO é dispensável mesmo com nó validado (R2: os demais requisitos valem).
        c = evaluate(adv('call', validated=True), action='CALL', hero_cards=None)
        self.assertFalse(c['execution_allowed'])
        self.assertIn('SEM_LEITURA', c['blockers'])

    def test_unvalidated_call_has_no_authority(self):
        c = evaluate(adv('call', validated=False), action='CALL', hero_cards=CARDS)
        self.assertEqual(c['authority'], 'NONE')
        self.assertFalse(c['execution_allowed'])
        self.assertIn('SEM_AUTORIDADE_VALIDADA', c['blockers'])

    # ---- R1: fallback/abstain nunca vira validado ----
    def test_fallback_flag_is_not_source_validated(self):
        c = evaluate(adv('call', validated=True, fallback=True), action='CALL', hero_cards=CARDS)
        self.assertFalse(c['source_validated'])      # band-aid não fabrica validade
        self.assertNotEqual(c['authority'], 'VALIDATED')

    def test_deep_guard_flag_is_not_source_validated(self):
        c = evaluate(adv('check', validated=True, deep_guard=True), action='CHECK', hero_cards=CARDS)
        self.assertFalse(c['source_validated'])

    def test_borrowed_stack_is_not_source_validated(self):
        c = evaluate(adv('call', validated=True, stack_borrowed_from=25), action='CALL', hero_cards=CARDS)
        self.assertFalse(c['source_validated'])
        self.assertFalse(c['context_match'])
        self.assertNotEqual(c['authority'], 'VALIDATED')

    # ---- R2: rótulo premium não substitui os demais requisitos ----
    def test_premium_authorizes_commit_but_never_validated(self):
        c = evaluate(adv('call', safety_premium=True), action='CALL', hero_cards=CARDS)
        self.assertEqual(c['authority'], 'SAFETY_PREMIUM')
        self.assertTrue(c['execution_allowed'])      # Opção A: paga o monstro
        self.assertFalse(c['source_validated'])      # ...mas NÃO é 'validated'

    def test_premium_still_needs_observation(self):
        c = evaluate(adv('call', safety_premium=True), action='CALL', hero_cards=None)
        self.assertFalse(c['execution_allowed'])     # rótulo não dispensa leitura
        self.assertIn('SEM_LEITURA', c['blockers'])

    # ---- A13: SAFETY_PREMIUM restrito (só CALL + mão premium real) ----
    def test_premium_paga_AQ_offsuit(self):
        c = evaluate(adv('call', safety_premium=True), action='CALL', hero_cards=['Ah', 'Qs'])
        self.assertEqual(c['authority'], 'SAFETY_PREMIUM')   # AQ é premium (I1)
        self.assertTrue(c['execution_allowed'])

    def test_premium_paga_par_TT(self):
        c = evaluate(adv('call', safety_premium=True), action='CALL', hero_cards=['Tc', 'Td'])
        self.assertEqual(c['authority'], 'SAFETY_PREMIUM')

    def test_premium_flag_em_mao_fraca_nao_comita(self):
        # defesa em profundidade: flag setado por engano em mão não-premium NÃO paga
        c = evaluate(adv('call', safety_premium=True), action='CALL', hero_cards=['7c', '2d'])
        self.assertEqual(c['authority'], 'NONE')
        self.assertFalse(c['execution_allowed'])
        self.assertIn('PREMIUM_FLAG_SEM_MAO_PREMIUM', c['blockers'])

    def test_premium_nunca_agride_sem_no(self):
        # premium sem nó validado nunca INICIA agressão (raise/bet/all-in)
        c = evaluate(adv('raise', safety_premium=True), action='RAISE', hero_cards=['As', 'Ac'])
        self.assertNotEqual(c['authority'], 'SAFETY_PREMIUM')
        self.assertFalse(c['execution_allowed'])
        self.assertIn('PREMIUM_SO_PAGA_NAO_AGRIDE', c['blockers'])

    def test_premium_allin_sem_no_nao_comita(self):
        c = evaluate(adv('all_in', safety_premium=True), action='ALL_IN', hero_cards=['As', 'Ac'])
        self.assertNotEqual(c['authority'], 'SAFETY_PREMIUM')
        self.assertFalse(c['execution_allowed'])

    # ---- R2: margem de call-off não substitui os demais requisitos ----
    def test_calloff_with_margin_authorized(self):
        c = evaluate(adv('call', spot='call_off_vs_3bet_shove', equity=0.52,
                         required_equity_icm=0.40), action='CALL', hero_cards=CARDS)
        self.assertEqual(c['authority'], 'CALL_OFF')
        self.assertTrue(c['execution_allowed'])

    def test_calloff_boundary_not_authorized(self):
        c = evaluate(adv('call', spot='call_off_vs_3bet_shove', equity=0.42,
                         required_equity_icm=0.40), action='CALL', hero_cards=CARDS)
        self.assertFalse(c['execution_allowed'])
        self.assertIn('CALLOFF_NA_FRONTEIRA', c['blockers'])

    def test_calloff_margin_does_not_skip_observation(self):
        c = evaluate(adv('call', spot='call_off_vs_3bet_shove', equity=0.52,
                         required_equity_icm=0.40), action='CALL', hero_cards=None)
        self.assertFalse(c['execution_allowed'])
        self.assertIn('SEM_LEITURA', c['blockers'])

    # ---- D6: anti-freeze pós-flop só CHECK (não-commit); nunca comita pós-flop ----
    def test_postflop_check_anti_freeze_e_noncommit_autorizado(self):
        c = evaluate(dict(status='ADVICE', phase='postflop', recommended='check', anti_freeze=True),
                     action='CHECK', hero_cards=CARDS)
        self.assertEqual(c['authority'], 'SAFETY_NONCOMMIT')
        self.assertTrue(c['execution_allowed'])      # CHECK é grátis

    def test_postflop_commit_sem_no_bloqueado(self):
        c = evaluate(dict(status='ADVICE', phase='postflop', recommended='call'),
                     action='CALL', hero_cards=CARDS)
        self.assertFalse(c['execution_allowed'])      # pós-flop não comita sem autoridade
        self.assertEqual(c['authority'], 'NONE')

    # ---- sizing: raise/all-in não é caminho single-click ----
    def test_raise_not_supported_in_single_click_contract(self):
        c = evaluate(adv('raise', validated=True), action='RAISE', hero_cards=CARDS)
        self.assertFalse(c['sizing_supported'])
        self.assertFalse(c['execution_allowed'])
        self.assertIn('SIZING_NAO_SUPORTADO', c['blockers'])


if __name__ == '__main__':
    unittest.main()
