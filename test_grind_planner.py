"""E7/E8: núcleo de decisão do grind (agenda por horário + stop-loss/orçamento). Puro."""
import unittest

from grind_planner import GrindPlanner, hhmm_to_min


def _g(id_, start_min, buyin=10.0, reg_opens_min=None):
    e = dict(id=id_, start_min=start_min, buyin_bb=buyin)
    if reg_opens_min is not None:
        e['reg_opens_min'] = reg_opens_min
    return e


class HHMMTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(hhmm_to_min('20:30'), 1230)
        self.assertEqual(hhmm_to_min('00:00'), 0)
        self.assertIsNone(hhmm_to_min('25:00'))
        self.assertIsNone(hhmm_to_min('abc'))


class DueToRegisterTests(unittest.TestCase):
    def setUp(self):
        self.p = GrindPlanner(max_simultaneous=4, reg_lead_min=60)

    def test_janela_aberta_registra(self):
        # início 20:00 (1200), agora 19:30 (1170) -> dentro de [1140,1200)
        due = self.p.due_to_register(1170, [_g('t1', 1200)])
        self.assertEqual([e['id'] for e in due], ['t1'])

    def test_antes_da_janela_nao_registra(self):
        due = self.p.due_to_register(1100, [_g('t1', 1200)])   # 18:20, janela abre 19:00
        self.assertEqual(due, [])

    def test_late_reg_proibido_no_piloto(self):
        # agora == início: seria late-reg -> NÃO registra
        self.assertEqual(self.p.due_to_register(1200, [_g('t1', 1200)]), [])
        self.assertEqual(self.p.due_to_register(1230, [_g('t1', 1200)]), [])

    def test_nao_reregistra_o_ja_inscrito(self):
        due = self.p.due_to_register(1170, [_g('t1', 1200)], registered_ids={'t1'})
        self.assertEqual(due, [])

    def test_respeita_max_simultaneous(self):
        grade = [_g('t1', 1200), _g('t2', 1205), _g('t3', 1210)]
        due = self.p.due_to_register(1170, grade, active=3)   # só 1 vaga
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]['id'], 't1')                 # o de início mais cedo

    def test_respeita_max_per_day(self):
        p = GrindPlanner(max_simultaneous=4, max_per_day=2)
        grade = [_g('t1', 1200), _g('t2', 1205), _g('t3', 1210)]
        due = p.due_to_register(1170, grade, registered_today=1)  # resta 1 no dia
        self.assertEqual(len(due), 1)

    def test_respeita_orcamento(self):
        p = GrindPlanner(max_simultaneous=4, daily_budget_bb=25.0)
        grade = [_g('t1', 1200, buyin=10), _g('t2', 1205, buyin=10), _g('t3', 1210, buyin=10)]
        due = p.due_to_register(1170, grade, spent_bb=0.0)   # cabe 2 (20<=25), 3o estoura
        self.assertEqual(len(due), 2)


class StopTests(unittest.TestCase):
    def test_orcamento_diario_para(self):
        p = GrindPlanner(daily_budget_bb=100.0)
        self.assertEqual(p.should_stop(spent_bb=100.0)[0], True)
        self.assertEqual(p.should_stop(spent_bb=50.0)[0], False)

    def test_stop_loss_para(self):
        p = GrindPlanner(stop_loss_bb=200.0)
        self.assertEqual(p.should_stop(pnl_bb=-200.0), (True, 'STOP_LOSS_ATINGIDO'))
        self.assertEqual(p.should_stop(pnl_bb=-150.0)[0], False)

    def test_parado_nao_registra_nada(self):
        p = GrindPlanner(max_simultaneous=4, daily_budget_bb=10.0)
        due = p.due_to_register(1170, [_g('t1', 1200, buyin=10)], spent_bb=10.0)
        self.assertEqual(due, [])


if __name__ == '__main__':
    unittest.main()
