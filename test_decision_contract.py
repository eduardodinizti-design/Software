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

    # ---- sizing: raise/all-in não é caminho single-click ----
    def test_raise_not_supported_in_single_click_contract(self):
        c = evaluate(adv('raise', validated=True), action='RAISE', hero_cards=CARDS)
        self.assertFalse(c['sizing_supported'])
        self.assertFalse(c['execution_allowed'])
        self.assertIn('SIZING_NAO_SUPORTADO', c['blockers'])


if __name__ == '__main__':
    unittest.main()
