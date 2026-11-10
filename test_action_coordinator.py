"""Testes do coordenador de ação em dry-run (passo 1 da execução)."""
import time
import unittest

from action_coordinator import (DryRunInput, describe_plan, map_advice_to_action,
                                plan_from_buttons)
from cursor_controller import CursorController, Intent
from cursor_trajectory import TrajectoryGenerator


def _buttons(status='EXPERIMENTAL_BUTTON_ROW', actions=('FOLD', 'CALL', 'RAISE')):
    return dict(status=status, hero_turn_confirmed=False, actions_allowed=False,
                buttons=[dict(box=[100 + i * 120, 1200, 100, 44], action=a,
                              label=a.title()) for i, a in enumerate(actions)])


class MapTest(unittest.TestCase):
    def test_basic_map(self):
        self.assertEqual(map_advice_to_action('fold'), ('FOLD', []))
        self.assertEqual(map_advice_to_action('call'), ('CALL', []))

    def test_raise_needs_sizing(self):
        a, cav = map_advice_to_action('raise')
        self.assertEqual(a, 'RAISE')
        self.assertIn('REQUIRES_SIZING_MULTISTEP', cav)

    def test_all_in_flagged(self):
        a, cav = map_advice_to_action('all_in')
        self.assertEqual(a, 'RAISE')
        self.assertIn('ALL_IN', cav)
        self.assertIn('REQUIRES_SIZING_MULTISTEP', cav)

    def test_unknown_unmapped(self):
        self.assertEqual(map_advice_to_action('xyz'), (None, []))


class PlanTest(unittest.TestCase):
    def test_plan_raise_screen_coords(self):
        r = plan_from_buttons(_buttons(), dict(status='ADVICE', recommended='raise'),
                              origin=(500, 300))
        self.assertTrue(r['ok'])
        p = r['plan']
        self.assertEqual(p['action'], 'RAISE')
        self.assertEqual(p['rect'], (840, 1500, 100, 44))      # RAISE box + origin
        self.assertEqual(p['center'], (890.0, 1522.0))
        self.assertIn('REQUIRES_SIZING_MULTISTEP', p['caveats'])

    def test_abstains_when_not_hero_turn(self):
        r = plan_from_buttons(_buttons(status='PRESELECTION_ROW'),
                              dict(status='ADVICE', recommended='fold'))
        self.assertFalse(r['ok'])
        self.assertIn('NAO_E_VEZ_DO_HERO', r['reason'])

    def test_abstains_when_advice_not_action(self):
        r = plan_from_buttons(_buttons(), dict(status='ABSTAIN', reason='X'))
        self.assertFalse(r['ok'])
        self.assertIn('SEM_ACAO_RECOMENDADA', r['reason'])

    def test_call_falls_back_to_check(self):
        r = plan_from_buttons(_buttons(actions=('FOLD', 'CHECK', 'RAISE')),
                              dict(status='ADVICE', recommended='call'))
        self.assertTrue(r['ok'])
        self.assertEqual(r['plan']['action'], 'CHECK')

    def test_no_button_for_action(self):
        r = plan_from_buttons(_buttons(actions=('FOLD', 'CALL')),
                              dict(status='ADVICE', recommended='raise'))
        self.assertFalse(r['ok'])
        self.assertIn('SEM_BOTAO_PARA:RAISE', r['reason'])

    def test_describe(self):
        r = plan_from_buttons(_buttons(), dict(status='ADVICE', recommended='fold'))
        s = describe_plan(r)
        self.assertIn('FOLD', s)
        self.assertIn('DRY-RUN', s)
        self.assertIn('NAO enviado', s)


class DryRunExecuteTest(unittest.TestCase):
    def test_dry_run_records_click_sends_nothing(self):
        # O plano passa pelo controlador de cursor REAL com DryRunInput: valida,
        # 'move', 'clica' (REGISTRA). Nenhum SendInput; prova o fluxo sem risco.
        inp = DryRunInput(pos=(0, 0))
        rect = (840, 1500, 100, 44)
        c = CursorController(input_adapter=inp,
                             validator=lambda i, n: dict(ok=True, target_rect=rect),
                             clock=time.monotonic, sleep=lambda s: None, step_s=0.0,
                             trajectory=TrajectoryGenerator(clock=time.monotonic))
        it = Intent(id='dry', action='click', source_key='t', target_rect=rect,
                    deadline=1e12)
        out = c.execute(it)
        self.assertEqual(len(inp.clicks), 1)                 # registrou 1 clique
        self.assertEqual(inp.clicks[0], (890.0, 1522.0))     # no centro do botão
        self.assertTrue(len(inp.moves) > 0)                  # houve trajetória
        # sem verificador de efeito (dry-run) -> desconhecido, mas NADA foi enviado
        self.assertEqual(out['state'], 'UNKNOWN_RESULT')


if __name__ == '__main__':
    unittest.main()
