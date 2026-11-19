"""Trava o executor de APOSTA PÓS-FLOP (Eduardo 19/11): casa o preset por FRAÇÃO de pote
(não ×BB) e só clica se achar a fração — nunca dispara às cegas."""
import unittest

from raise_panel import map_fraction_to_preset
import postflop_bet_executor as pfbe


def _presets(*labels):
    return [{'label': l, 'box': (i * 10, 0, 8, 6), 'mult': None} for i, l in enumerate(labels)]


class MapFraction(unittest.TestCase):
    def test_casa_por_rotulo(self):
        ps = _presets('1/3', '1/2', '2/3', 'Pote', 'All in')
        self.assertEqual(map_fraction_to_preset('t33', ps)['label'], '1/3')
        self.assertEqual(map_fraction_to_preset('t50', ps)['label'], '1/2')
        self.assertEqual(map_fraction_to_preset('t66', ps)['label'], '2/3')
        self.assertEqual(map_fraction_to_preset('allin', ps)['label'], 'All in')

    def test_casa_por_percentual(self):
        ps = _presets('33%', '50%', '75%')
        self.assertEqual(map_fraction_to_preset('t33', ps)['label'], '33%')
        self.assertEqual(map_fraction_to_preset('t50', ps)['label'], '50%')
        self.assertEqual(map_fraction_to_preset('t66', ps)['label'], '75%')   # 75% cola em 2/3

    def test_sem_match_devolve_none(self):
        self.assertIsNone(map_fraction_to_preset('t50', _presets('2x', '3x', 'Pote')))
        self.assertIsNone(map_fraction_to_preset('t50', []))


class PanelBucket(unittest.TestCase):
    def test_traduz_slider_para_painel(self):
        self.assertEqual(pfbe.panel_bucket('1/3'), 't33')
        self.assertEqual(pfbe.panel_bucket('1/2'), 't50')
        self.assertEqual(pfbe.panel_bucket('2/3'), 't66')
        self.assertEqual(pfbe.panel_bucket('geo'), 't66')      # geométrico -> melhor fração
        self.assertEqual(pfbe.panel_bucket('allin'), 'allin')


class _FakeEngine:
    def __init__(self, frame):
        self._f = frame

    def capture_frame(self, hwnd=None):
        return self._f, None


class Executor(unittest.TestCase):
    def test_sem_frame(self):
        r = pfbe.execute_postflop_bet(_FakeEngine(None), 1, '1/2', adapter=None, control=None)
        self.assertEqual(r['state'], 'NO_FRAME')

    def test_sem_painel(self):
        rp = lambda f: {'status': 'NO_RAISE_PANEL', 'presets': [], 'confirm': None}
        r = pfbe.execute_postflop_bet(_FakeEngine(object()), 1, '1/2', adapter=None,
                                      control=None, read_panel=rp)
        self.assertEqual(r['state'], 'NO_PANEL')

    def test_fracao_ausente_nao_clica(self):
        # painel só com presets ×BB (pré-flop) -> não acha a fração -> NÃO clica
        rp = lambda f: {'status': 'EXPERIMENTAL_RAISE_PANEL',
                        'presets': _presets('2x', '3x'), 'confirm': {'box': (9, 9, 5, 5)}}
        r = pfbe.execute_postflop_bet(_FakeEngine(object()), 1, '1/2', adapter=None,
                                      control=None, read_panel=rp)
        self.assertEqual(r['state'], 'NO_FRACTION_PRESET')
        self.assertIn('2x', r['labels'])

    def test_find_fraction_preset(self):
        rp = lambda f: {'presets': _presets('1/3', '1/2', '2/3'), 'confirm': {'box': (0, 0, 1, 1)}}
        preset, panel = pfbe.find_fraction_preset(object(), '2/3', read_panel=rp)
        self.assertEqual(preset['label'], '2/3')


if __name__ == '__main__':
    unittest.main()
