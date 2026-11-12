"""Testes do fluxo multi-etapa do aumento, agora via CursorController.

Mundo com ESTADO (fases BUTTONS -> PANEL -> DONE), compatível com a dupla
revalidação do controlador (inicial + na chegada leem a mesma fase). O adaptador
de input avança a fase a cada clique: 1 abre o painel; 3 fecha (aposta entrou)."""
import unittest

import numpy as np

from raise_sequencer import RaiseSequencer
from action_coordinator import DryRunInput

WIN = (-1280, 0, 3840, 1440)
_PRESETS = [dict(box=[18, 1240, 122, 70], label='2x', mult=2.0),
            dict(box=[152, 1240, 122, 70], label='2.5x', mult=2.5),
            dict(box=[286, 1240, 123, 70], label='3x', mult=3.0),
            dict(box=[421, 1240, 122, 70], label='4x', mult=4.0)]


class World:
    """clicks: 0 BUTTONS; 1-2 PANEL; >=3 DONE. `panel_opens`/`hero_turn` p/ cenários."""
    def __init__(self, panel_opens=True, hero_turn=True):
        self.clicks = 0
        self.panel_opens = panel_opens
        self.hero_turn = hero_turn

    def phase(self):
        if self.clicks == 0:
            return 'BUTTONS'
        if not self.panel_opens:
            return 'NEITHER'
        return 'DONE' if self.clicks >= 3 else 'PANEL'


class WInput(DryRunInput):
    def __init__(self, world):
        super().__init__()
        self.world = world

    def click_once(self, x=None, y=None, bounds=None, hold_s=None):
        r = super().click_once(x, y, bounds=bounds, hold_s=hold_s)
        self.world.clicks += 1
        return r

    def drag(self, x0, y0, x1, y1, **kw):
        self.world.clicks += 1          # arrasto da barra conta como ação (avança o mundo)
        return dict(released=True, down_accepted=1, up_accepted=1)


def _capture_of(world):
    def cap():
        return np.zeros((1334, 753, 3), np.uint8), {}
    return cap


def _detect(rgb, max_tables=6):
    from types import SimpleNamespace
    return [SimpleNamespace(box=(0, 0, 753, 1334), status='COMPLETE_CANDIDATE')]


def _ra_of(world):
    def ra(crop):
        if world.phase() == 'BUTTONS' and world.hero_turn:
            return dict(status='EXPERIMENTAL_BUTTON_ROW',
                        buttons=[dict(box=[500, 1240, 100, 44], action='RAISE', label='Raise')])
        return dict(status='NO_BUTTON_ROW', buttons=[])
    return ra


def _rp_of(world):
    def rp(crop):
        if world.phase() == 'PANEL':
            return dict(status='EXPERIMENTAL_RAISE_PANEL',
                        confirm=dict(box=[555, 1240, 180, 70]), presets=_PRESETS)
        return dict(status='NO_RAISE_PANEL', presets=[], confirm=None)
    return rp


class _Control:
    def __init__(self, running=True):
        self.running = running

    def execution_allowed(self):
        return self.running


def _slider_of(found=True):
    def rs(crop):
        if found:
            return dict(status='SLIDER_FOUND',
                        handle=dict(box=[598, 1139, 94, 52], center=[645, 1165]),
                        allin_to=[645, 600])
        return dict(status='NO_SLIDER', handle=None, allin_to=None)
    return rs


def _seq(world, inp, target=2.5, bot_control=None, hand='H1', read_hand=None,
         read_slider=None):
    return RaiseSequencer(capture=_capture_of(world), window_rect=WIN, input_adapter=inp,
                          target_mult=target, bot_control=bot_control, max_tables=6,
                          sleep=lambda s: None, read_actions=_ra_of(world),
                          read_panel=_rp_of(world), detect=_detect, hand=hand,
                          read_hand=read_hand or (lambda crop: {'hand_id': 'H1'}),
                          read_slider=read_slider or _slider_of(found=False))


class RaiseSequencerTest(unittest.TestCase):
    def test_happy_path_three_clicks(self):
        world = World()
        inp = WInput(world)
        out = _seq(world, inp, target=2.5).run()
        self.assertTrue(out['ok'])
        self.assertEqual(out['preset'], 2.5)
        self.assertTrue(out['confirmed'])                  # botões sumiram
        self.assertEqual(len(inp.clicks), 3)               # abrir, preset, confirmar
        whats = [e[0] for e in out['log'] if isinstance(e[0], str)]
        self.assertIn('ABRIR', whats)
        self.assertIn('PRESET_2.5x', whats)
        self.assertIn('CONFIRMAR', whats)

    def test_maps_3bet_multiplier_to_nearest_preset(self):
        world = World()
        out = _seq(world, WInput(world), target=3.4).run()  # 3bet ~3.4x -> 3x
        self.assertEqual(out['preset'], 3.0)

    def test_large_target_allin_via_slider(self):
        # alvo 25x (shove): NÃO vira 4x; abre o painel e ALL-IN pela BARRA -> confirma.
        # Cliques: ABRIR + (drag da barra) + CONFIRMAR = 3 ações.
        world = World()
        inp = WInput(world)
        out = _seq(world, inp, target=25.0, read_slider=_slider_of(found=True)).run()
        self.assertTrue(out['ok'])
        self.assertEqual(out['preset'], 'ALL_IN')
        self.assertTrue(out['confirmed'])
        whats = [e[0] for e in out['log'] if isinstance(e[0], str)]
        self.assertIn('ABRIR', whats)
        self.assertIn('ALLIN_SLIDER', whats)
        self.assertIn('CONFIRMAR', whats)

    def test_large_target_shove_without_slider_is_unknown(self):
        # shove mas a BARRA não foi localizada -> resultado DESCONHECIDO (não some em
        # silêncio deixando o painel aberto); 1 clique (só o abrir), sem drag.
        world = World()
        inp = WInput(world)
        out = _seq(world, inp, target=25.0, read_slider=_slider_of(found=False)).run()
        self.assertFalse(out['ok'])
        self.assertTrue(out['unknown'])
        self.assertEqual(out['reason'], 'ALLIN_SLIDER_CANCELADO')
        self.assertEqual(len(inp.clicks), 1)

    def test_paused_does_not_click(self):
        world = World()
        inp = WInput(world)
        out = _seq(world, inp, bot_control=_Control(False)).run()
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'BOT_PAUSADO')
        self.assertEqual(len(inp.clicks), 0)

    def test_panel_not_open_is_unknown_after_one_click(self):
        world = World(panel_opens=False)
        inp = WInput(world)
        out = _seq(world, inp).run()
        self.assertFalse(out['ok'])
        self.assertTrue(out['unknown'])                    # clique pode ter saído
        self.assertEqual(out['reason'], 'PAINEL_NAO_ABRIU')
        self.assertEqual(len(inp.clicks), 1)               # só o abrir

    def test_not_hero_turn_aborts_no_click(self):
        world = World(hero_turn=False)
        inp = WInput(world)
        out = _seq(world, inp).run()
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'NAO_E_VEZ_DO_HERO')
        self.assertEqual(len(inp.clicks), 0)

    def test_geometry_change_between_steps_aborts(self):
        world = World()
        inp = WInput(world)
        rects = [WIN, WIN, (0, 0, 100, 100)]               # janela "se move" após o começo

        def geom():
            return rects.pop(0) if len(rects) > 1 else rects[0]
        seq = RaiseSequencer(capture=_capture_of(world), window_rect=geom, input_adapter=inp,
                             target_mult=2.5, max_tables=6, sleep=lambda s: None,
                             read_actions=_ra_of(world), read_panel=_rp_of(world), detect=_detect,
                             hand='H1', read_hand=lambda c: {'hand_id': 'H1'})
        out = seq.run()
        self.assertFalse(out['ok'])                        # não conclui com geometria instável

    def test_unknown_hand_aborts_no_click(self):
        # A2: identidade da mão desconhecida (hand=None) -> não age, zero cliques.
        world = World()
        inp = WInput(world)
        out = _seq(world, inp, hand=None).run()
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'MAO_DESCONHECIDA')
        self.assertEqual(len(inp.clicks), 0)

    def test_hand_mismatch_aborts_no_click(self):
        # A2: a mão relida na mesa diverge da mão da decisão -> cancela antes de clicar.
        world = World()
        inp = WInput(world)
        out = _seq(world, inp, hand='H1', read_hand=lambda c: {'hand_id': 'H2'}).run()
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'ABRIR_CANCELADO')
        self.assertEqual(len(inp.clicks), 0)

    def test_read_failure_in_verify_is_not_confirmed(self):
        # A2: INVALID_CROP na verificação final NÃO é "aposta entrou" (antes confirmava).
        world = World()
        inp = WInput(world)

        def ra(crop):
            ph = world.phase()
            if ph == 'BUTTONS' and world.hero_turn:
                return dict(status='EXPERIMENTAL_BUTTON_ROW',
                            buttons=[dict(box=[500, 1240, 100, 44], action='RAISE', label='Raise')])
            if ph == 'DONE':
                return dict(status='INVALID_CROP', buttons=[])   # falha de leitura, não "sumiu"
            return dict(status='NO_BUTTON_ROW', buttons=[])
        seq = RaiseSequencer(capture=_capture_of(world), window_rect=WIN, input_adapter=inp,
                             target_mult=2.5, max_tables=6, sleep=lambda s: None,
                             read_actions=ra, read_panel=_rp_of(world), detect=_detect,
                             hand='H1', read_hand=lambda c: {'hand_id': 'H1'})
        out = seq.run()
        self.assertFalse(out.get('confirmed'))              # leitura falha != aposta confirmada


if __name__ == '__main__':
    unittest.main()
