"""Testes do executor de ação (passo 3) — dry-run, gate, uma-por-mão, travas."""
import unittest

from action_executor import ActionExecutor
from action_coordinator import DryRunInput

WIN = (-1280, 0, 3840, 1440)
FRAME = (5760, 2160)
ORIGIN = (1920, 74)


def _buttons(actions=('FOLD', 'CALL', 'RAISE')):
    return dict(status='EXPERIMENTAL_BUTTON_ROW', hero_turn_confirmed=False,
                actions_allowed=False,
                buttons=[dict(box=[100 + i * 120, 1200, 100, 44], action=a,
                              label=a.title()) for i, a in enumerate(actions)])


def _result(rec):
    return dict(advice=dict(status='ADVICE', recommended=rec))


class _Control:
    def __init__(self, running=True):
        self.running = running

    def execution_allowed(self):
        return self.running


def _ok(intent, now):
    return dict(ok=True)


class PlanGateTest(unittest.TestCase):
    def test_refuses_raise_multistep(self):
        ex = ActionExecutor(window_rect=WIN)
        p = ex.plan(_result('raise'), _buttons(), origin=ORIGIN, frame_size=FRAME)
        self.assertFalse(p['ok'])
        self.assertIn('ACAO_MULTI_ETAPA_NAO_ARMADA:RAISE', p['reason'])

    def test_allows_fold_with_screen_rect(self):
        ex = ActionExecutor(window_rect=WIN)
        p = ex.plan(_result('fold'), _buttons(), origin=ORIGIN, frame_size=FRAME)
        self.assertTrue(p['ok'])
        self.assertEqual(p['plan']['action'], 'FOLD')
        self.assertIn('screen_rect', p['plan'])          # coord de tela pronta


class ExecuteTest(unittest.TestCase):
    def _exec(self, ex, inp, rec='fold', hand='h1'):
        return ex.execute(_result(rec), _buttons(), origin=ORIGIN, frame_size=FRAME,
                          input_adapter=inp, validator=_ok, hand_id=hand)

    def test_dry_run_clicks_and_marks_hand(self):
        ex = ActionExecutor(window_rect=WIN, armed=False)
        inp = DryRunInput()
        out = self._exec(ex, inp)
        self.assertTrue(out['acted'])
        self.assertTrue(out['dry_run'])
        self.assertEqual(len(inp.clicks), 1)             # registrou (dry-run)
        # segunda vez na MESMA mão -> nao reaperta
        out2 = self._exec(ex, DryRunInput())
        self.assertFalse(out2['acted'])
        self.assertIn('JA_AGIU_NESTA_MAO', out2['reason'])

    def test_armed_but_paused_does_not_click(self):
        ex = ActionExecutor(window_rect=WIN, armed=True, bot_control=_Control(False))
        inp = DryRunInput()
        out = self._exec(ex, inp)
        self.assertFalse(out['acted'])
        self.assertEqual(out['reason'], 'BOT_PAUSADO')
        self.assertEqual(len(inp.clicks), 0)             # nada enviado

    def test_armed_running_clicks(self):
        ex = ActionExecutor(window_rect=WIN, armed=True, bot_control=_Control(True))
        inp = DryRunInput()
        out = self._exec(ex, inp)
        self.assertTrue(out['acted'])
        self.assertFalse(out['dry_run'])
        self.assertEqual(len(inp.clicks), 1)

    def test_refuses_raise_no_click(self):
        ex = ActionExecutor(window_rect=WIN, armed=True, bot_control=_Control(True))
        inp = DryRunInput()
        out = self._exec(ex, inp, rec='raise')
        self.assertFalse(out['acted'])
        self.assertIn('ACAO_MULTI_ETAPA', out['reason'])
        self.assertEqual(len(inp.clicks), 0)

    def test_abstains_when_advice_abstain(self):
        ex = ActionExecutor(window_rect=WIN)
        out = ex.execute(dict(advice=dict(status='ABSTAIN', reason='X')), _buttons(),
                         origin=ORIGIN, frame_size=FRAME, input_adapter=DryRunInput(),
                         validator=_ok, hand_id='h')
        self.assertFalse(out['acted'])


if __name__ == '__main__':
    unittest.main()
