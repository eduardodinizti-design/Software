"""TRAVA do planejador de ação da Suprema (Fase 2, offline): decisão do cérebro + prompt
real -> plano concreto, GATED pelas ações legais, com os fallbacks de segurança do PPPoker."""
import unittest

from suprema_state import SupremaTable
import suprema_act as A


def _table_with_prompt(gamer_prompt, bb_chips=500):
    t = SupremaTable(bb_chips=bb_chips)
    t.feed_json({"event": "prompt", "data": {"gamer_prompt": gamer_prompt}})
    return t


ADV = lambda rec, **kw: dict(status='ADVICE', recommended=rec, **kw)

# prompt tipico facing-bet: pode foldar/pagar(500)/aumentar(range)/all-in
FACING = {"fold": True, "check": None, "call": 500,
          "raise": "range,1000,10000,2X,1000,3X,1500,4X,2000", "all_in": True}
# prompt tipico pote nao-aberto: pode checar/apostar/all-in
OPEN = {"fold": True, "check": True, "call": None,
        "raise": "range,1000,10000,2X,1000,3X,1500", "all_in": True}
IDLE = {"fold": None, "check": None, "call": None, "raise": None, "all_in": None}


class PlanAction(unittest.TestCase):

    def test_nao_e_a_vez(self):
        p = A.plan_action(ADV('raise', sizing={'size_bb': 3}), _table_with_prompt(IDLE))
        self.assertEqual(p['action'], A.WAIT)

    def test_raise_size_bb_vira_chips_e_preset(self):
        p = A.plan_action(ADV('raise', sizing={'size_bb': 3}), _table_with_prompt(FACING))
        self.assertEqual(p['action'], A.RAISE)
        self.assertEqual(p['chips'], 1500.0)          # 3 * 500
        self.assertEqual(p['preset'], '3X')           # preset mais proximo (1500)

    def test_raise_clamp_min(self):
        p = A.plan_action(ADV('raise', sizing={'size_bb': 1}), _table_with_prompt(FACING))
        self.assertEqual(p['action'], A.RAISE)
        self.assertEqual(p['chips'], 1000.0)          # 500 -> clamp p/ min 1000

    def test_raise_no_teto_vira_all_in(self):
        p = A.plan_action(ADV('raise', sizing={'size_bb': 30}), _table_with_prompt(FACING))
        self.assertEqual(p['action'], A.ALL_IN)       # 15000 >= max 10000 + all_in legal

    def test_all_in_direto(self):
        p = A.plan_action(ADV('all_in'), _table_with_prompt(FACING))
        self.assertEqual(p['action'], A.ALL_IN)

    def test_fold_de_graca_vira_check(self):
        p = A.plan_action(ADV('fold'), _table_with_prompt(OPEN))   # check disponivel
        self.assertEqual(p['action'], A.CHECK)
        self.assertIn('GRATIS', p['reason'])

    def test_fold_real_quando_sem_check(self):
        p = A.plan_action(ADV('fold'), _table_with_prompt(FACING))  # sem check
        self.assertEqual(p['action'], A.FOLD)

    def test_call_usa_valor_do_prompt(self):
        p = A.plan_action(ADV('call'), _table_with_prompt(FACING))
        self.assertEqual(p['action'], A.CALL)
        self.assertEqual(p['chips'], 500)

    def test_raise_sem_botao_cai_pra_call(self):
        # prompt sem raise (só fold/call) -> cérebro quer raise -> cai p/ call
        p = A.plan_action(ADV('raise', sizing={'size_bb': 3}),
                          _table_with_prompt({"fold": True, "call": 500, "raise": None,
                                              "check": None, "all_in": None}))
        self.assertEqual(p['action'], A.CALL)
        self.assertIn('CALL', p['reason'])

    def test_check_quando_disponivel(self):
        p = A.plan_action(ADV('check'), _table_with_prompt(OPEN))
        self.assertEqual(p['action'], A.CHECK)

    def test_abstain_sem_advice(self):
        p = A.plan_action(dict(status='ABSTAIN'), _table_with_prompt(FACING))
        self.assertEqual(p['action'], A.ABSTAIN)

    def test_raise_sem_size_usa_min(self):
        p = A.plan_action(ADV('raise'), _table_with_prompt(FACING))   # sem sizing
        self.assertEqual(p['action'], A.RAISE)
        self.assertEqual(p['chips'], 1000.0)          # min-raise


class DecideAndPlanIntegrado(unittest.TestCase):
    """Fim-a-fim offline: SupremaTable vivo -> cérebro -> plano (via assistir_suprema)."""

    def test_aa_btn_prompt_ativo(self):
        import os
        pack = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
        if not os.path.exists(pack):
            self.skipTest('pack ausente')
        import assistir_suprema
        from suprema_state import SupremaTable
        adv = assistir_suprema.load_advisor()
        t = SupremaTable(bb_chips=500)
        t.feed_json({"event": "gameinfo", "data": {"game_info": {
            "dealer_seat": 2, "shared_cards": [], "pot": 750, "state": 3}}})
        t.feed_json({"event": "moveturn", "data": {"game_seat": {
            "1": {"seat": 2, "coins": 10000, "cards": [59, 56], "chips": 0, "sitout": False},
            "2": {"seat": 3, "coins": 9000, "cards": None, "chips": 250, "sitout": False},
            "3": {"seat": 6, "coins": 12000, "cards": [0, 0], "chips": 500, "sitout": False}}}})
        t.feed_json({"event": "prompt", "data": {"gamer_prompt": {
            "fold": True, "check": None, "call": 500,
            "raise": "range,1000,10000,2X,1000,3X,1500", "all_in": True}}})
        state, advice, plan = assistir_suprema.decide_and_plan(t, adv)
        self.assertIsNotNone(state)
        self.assertEqual(advice.get('status'), 'ADVICE')
        self.assertIn(plan['action'], (A.RAISE, A.ALL_IN, A.CALL))   # AA agride, nunca folda


if __name__ == '__main__':
    unittest.main()
