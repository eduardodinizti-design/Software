"""Testes do fluxo multi-etapa do aumento (dry-run, leitores injetados)."""
import unittest
from types import SimpleNamespace

import numpy as np

from raise_sequencer import RaiseSequencer
from action_coordinator import DryRunInput

WIN = (-1280, 0, 3840, 1440)


def _capture():
    return np.zeros((1334, 753, 3), np.uint8), {}


def _detect(rgb, max_tables=6):
    return [SimpleNamespace(box=(0, 0, 753, 1334), status='COMPLETE_CANDIDATE')]


def _panel(crop):
    return dict(status='EXPERIMENTAL_RAISE_PANEL', confirm=dict(box=[555, 1240, 180, 70]),
                presets=[dict(box=[18, 1240, 122, 70], label='2x', mult=2.0),
                         dict(box=[152, 1240, 122, 70], label='2.5x', mult=2.5),
                         dict(box=[286, 1240, 123, 70], label='3x', mult=3.0),
                         dict(box=[421, 1240, 122, 70], label='4x', mult=4.0)])


class _Actions:
    """1ª chamada: vez do hero com RAISE; demais: botões sumiram (verify)."""
    def __init__(self, turn=True):
        self.calls = 0
        self.turn = turn

    def __call__(self, crop):
        self.calls += 1
        if self.calls == 1 and self.turn:
            return dict(status='EXPERIMENTAL_BUTTON_ROW',
                        buttons=[dict(box=[500, 1240, 100, 44], action='RAISE', label='Raise')])
        return dict(status='NO_BUTTON_ROW', buttons=[])


class _Control:
    def __init__(self, running=True):
        self.running = running

    def execution_allowed(self):
        return self.running


def _seq(inp, target=2.5, read_actions=None, read_panel=_panel, bot_control=None):
    return RaiseSequencer(capture=_capture, window_rect=WIN, input_adapter=inp,
                          target_mult=target, read_actions=read_actions or _Actions(),
                          read_panel=read_panel, detect=_detect, sleep=lambda s: None,
                          bot_control=bot_control)


class RaiseSequencerTest(unittest.TestCase):
    def test_happy_path_three_clicks(self):
        inp = DryRunInput()
        out = _seq(inp, target=2.5).run()
        self.assertTrue(out['ok'])
        self.assertEqual(out['preset'], 2.5)
        self.assertTrue(out['confirmed'])                  # botões sumiram
        self.assertEqual(len(inp.clicks), 3)               # abrir, preset, confirmar
        whats = [e[0] for e in out['log'] if isinstance(e[0], str)]
        self.assertIn('ABRIR', whats)
        self.assertIn('PRESET_2.5x', whats)
        self.assertIn('CONFIRMAR', whats)

    def test_maps_3bet_multiplier_to_nearest_preset(self):
        inp = DryRunInput()
        out = _seq(inp, target=3.4).run()                  # 3bet BB ~3.4x
        self.assertEqual(out['preset'], 3.0)               # preset mais próximo

    def test_paused_does_not_click(self):
        inp = DryRunInput()
        out = _seq(inp, bot_control=_Control(False)).run()
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'BOT_PAUSADO')
        self.assertEqual(len(inp.clicks), 0)

    def test_panel_not_open_aborts_after_one_click(self):
        inp = DryRunInput()
        out = _seq(inp, read_panel=lambda c: dict(status='NO_RAISE_PANEL',
                                                  presets=[], confirm=None)).run()
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'PAINEL_NAO_ABRIU')
        self.assertEqual(len(inp.clicks), 1)               # só o 'abrir'

    def test_not_hero_turn_aborts_no_click(self):
        inp = DryRunInput()
        out = _seq(inp, read_actions=_Actions(turn=False)).run()
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'NAO_E_VEZ_DO_HERO')
        self.assertEqual(len(inp.clicks), 0)


if __name__ == '__main__':
    unittest.main()
