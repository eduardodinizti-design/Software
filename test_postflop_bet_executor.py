"""Trava o executor de APOSTA PÓS-FLOP (Eduardo 19/11, API VALIDADA AO VIVO): lê o painel
de FRAÇÃO de pote (botões verdes 1/3,1/2,2/3,pot,allin + "Bet" amarelo), casa o bucket e
só clica se ACHAR a fração — nunca dispara às cegas."""
import unittest

from raise_panel import map_fraction_to_preset
import postflop_bet_executor as pfbe


def _presets(*labels):
    """Presets no formato do raise pré-flop (×BB), só com rótulo — p/ map_fraction_to_preset."""
    return [{'label': l, 'box': (i * 10, 0, 8, 6), 'mult': None} for i, l in enumerate(labels)]


def _panel(*buckets, confirm=True):
    """Painel pós-flop no formato de read_bet_panel: presets com 'bucket'."""
    ps = [{'bucket': b, 'label': b, 'box': (i * 10, 0, 8, 6), 'center': (i * 10 + 4, 3)}
          for i, b in enumerate(buckets)]
    return {'status': 'POSTFLOP_BET_PANEL', 'presets': ps,
            'confirm': {'box': (99, 9, 5, 5), 'center': (101, 11)} if confirm else None}


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
        self.assertEqual(pfbe.panel_bucket('geo'), 'geo')      # geométrico fica 'geo' (slider)
        self.assertEqual(pfbe.panel_bucket('allin'), 'allin')


class Pick(unittest.TestCase):
    def test_acha_bucket_exato(self):
        preset, approx = pfbe._pick(_panel('t33', 't50', 't66')['presets'], 't50')
        self.assertEqual(preset['bucket'], 't50')
        self.assertFalse(approx)

    def test_geo_cai_no_maior_com_flag(self):
        preset, approx = pfbe._pick(_panel('t33', 't50', 't66')['presets'], 'geo')
        self.assertEqual(preset['bucket'], 't66')   # geo -> maior fração disponível
        self.assertTrue(approx)

    def test_allin_fallback(self):
        preset, approx = pfbe._pick(_panel('t33', 't50', 'pot')['presets'], 'allin')
        self.assertEqual(preset['bucket'], 'pot')
        self.assertTrue(approx)

    def test_sem_bucket_devolve_none(self):
        preset, approx = pfbe._pick(_panel('t33')['presets'], 't66')
        self.assertIsNone(preset)


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
        rp = lambda f: {'status': 'NO_BET_PANEL', 'presets': [], 'confirm': None}
        r = pfbe.execute_postflop_bet(_FakeEngine(object()), 1, '1/2', adapter=None,
                                      control=None, read_panel=rp)
        self.assertEqual(r['state'], 'NO_BET_PANEL')

    def test_fracao_ausente_nao_clica(self):
        # painel só com frações que NÃO cobrem o alvo -> não acha -> NÃO clica
        rp = lambda f: _panel('t33')          # pede t50; só existe t33
        r = pfbe.execute_postflop_bet(_FakeEngine(object()), 1, '1/2', adapter=None,
                                      control=None, read_panel=rp)
        self.assertEqual(r['state'], 'NO_FRACTION_BUTTON')
        self.assertIn('t33', r['labels'])


if __name__ == '__main__':
    unittest.main()
