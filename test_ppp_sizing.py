"""TRAVA do on_sizing (raise/bet multi-etapa): dispatch pré×pós, gate DRY, shim ImageGrab. Offline."""
import unittest

import ppp_sizing as S
from bot_control import BotControl


def _entry(board=None):
    return {'table': {'board': board or [], 'tocall': 100, 'pot': 150}, 'players': []}


class _Adapter:
    def move_to(self, *a, **k): pass
    def click_once(self, *a, **k): pass


def _control(armed):
    c = BotControl()
    if armed:
        c.resume()                 # PAUSED -> RUNNING
    return c


# presets REAIS lidos do painel de raise do Eduardo (frame 25/11, read_raise_panel em BGR):
# 2× · 2.5× · 3× · 4×, esquerda->direita.
_REAL_PRESETS = [{'box': [162, 1318, 122, 70]}, {'box': [296, 1318, 123, 70]},
                 {'box': [431, 1318, 122, 70]}, {'box': [565, 1318, 123, 70]}]


class PickRaisePreset(unittest.TestCase):
    def test_exato_por_slot_sem_ocr(self):
        for tm, i in ((2.0, 0), (2.5, 1), (3.0, 2), (4.0, 3)):
            p, exato = S.pick_raise_preset(_REAL_PRESETS, tm)
            self.assertTrue(exato)
            self.assertEqual(p['box'], _REAL_PRESETS[i]['box'])

    def test_nao_exato_cai_no_menor_ou_igual(self):
        p, exato = S.pick_raise_preset(_REAL_PRESETS, 2.2)   # 2.2 -> 2× (slot 0)
        self.assertFalse(exato)
        self.assertEqual(p['box'], _REAL_PRESETS[0]['box'])

    def test_abaixo_de_tudo_pega_o_menor(self):
        p, exato = S.pick_raise_preset(_REAL_PRESETS, 1.5)
        self.assertEqual(p['box'], _REAL_PRESETS[0]['box'])

    def test_none_ou_vazio(self):
        self.assertEqual(S.pick_raise_preset([], 2.0), (None, False))
        self.assertEqual(S.pick_raise_preset(_REAL_PRESETS, None), (None, False))


class ExecuteRaisePreset(unittest.TestCase):
    """Executor OCR-free do raise: crop->read_raise_panel->pick->clica preset+Raise (coords de tela)."""

    def _view(self, origin=(1850, 0)):
        import numpy as np
        return {'origin': origin, 'box': (origin[0], origin[1], 1000, 1440),
                'window_rect': (0, 0, 3840, 1440), 'full_size': (3840, 1440),
                '_frame': np.zeros((1440, 3840, 3), np.uint8)}

    def test_clica_preset_e_raise_nas_coords_mapeadas(self):
        clicks = []
        ad = _Adapter(); ad.move_to = lambda *a, **k: None
        ad.click_once = lambda x=None, y=None, **k: clicks.append((x, y))
        v = self._view(origin=(1850, 0))
        # read_panel FAKE: presets 2×/2.5× + confirmar, em coords do CROP (como read_raise_panel dá)
        fake_panel = lambda crop, _ocr=None: {'status': 'EXPERIMENTAL_RAISE_PANEL',
            'presets': [{'box': [162, 1318, 122, 70]}, {'box': [296, 1318, 123, 70]}],
            'confirm': {'box': [700, 1318, 180, 70]}}
        to_screen = lambda box, *, window_rect, frame_size: box    # 1:1 (janela==frame, origem 0)
        res = S.execute_raise_preset(v, 2.0, adapter=ad, capture_bgr=lambda rect: v['_frame'],
                                     read_panel=fake_panel, to_screen=to_screen, log=lambda *a, **k: None)
        self.assertEqual(res['state'], 'CLICKED_RAISE')
        self.assertTrue(res['exato'])
        # 2× no crop [162,1318,122,70] + origin(1850,0) -> full (2012,1318,122,70) -> centro (2073,1353)
        # Raise [700,1318,180,70] + origin -> (2550,1318,180,70) -> centro (2640,1353)
        self.assertEqual(clicks, [(2073, 1353), (2640, 1353)])

    def test_abre_painel_antes_clica_aumentar_preset_raise(self):
        clicks = []
        ad = _Adapter(); ad.move_to = lambda *a, **k: None
        ad.click_once = lambda x=None, y=None, **k: clicks.append((x, y))
        v = self._view(origin=(1850, 0))
        fake_panel = lambda crop, _ocr=None: {'status': 'EXPERIMENTAL_RAISE_PANEL',
            'presets': [{'box': [162, 1318, 122, 70]}, {'box': [296, 1318, 123, 70]}],
            'confirm': {'box': [700, 1318, 180, 70]}}
        slept = []
        res = S.execute_raise_preset(v, 2.0, adapter=ad, open_box=[500, 1250, 100, 60],
                                     capture_bgr=lambda rect: v['_frame'], read_panel=fake_panel,
                                     to_screen=lambda box, **k: box, sleep=lambda s: slept.append(s),
                                     log=lambda *a, **k: None)
        self.assertEqual(res['state'], 'CLICKED_RAISE')
        # 1º clique = Aumentar [500,1250,100,60]+origin(1850,0) -> (2350,1250,100,60) -> (2400,1280)
        self.assertEqual(clicks[0], (2400, 1280))
        self.assertEqual(clicks[1:], [(2073, 1353), (2640, 1353)])   # preset 2× + Raise
        self.assertTrue(slept)                                       # esperou o painel renderizar

    def test_shove_arrasta_handle_pra_cima_e_confirma(self):
        clicks, drags = [], []
        class Ad:
            def move_to(self, *a, **k): pass
            def click_once(self, x=None, y=None, **k): clicks.append((x, y))
            def drag(self, x0, y0, x1, y1, **k): drags.append((x0, y0, x1, y1))
        v = self._view(origin=(1850, 0))
        slider = lambda crop: {'status': 'SLIDER_FOUND',
                               'handle': {'box': [640, 750, 40, 40], 'center': [660, 770]},
                               'allin_to': [660, 560]}            # topo do trilho (all-in)
        panel = lambda crop, _ocr=None: {'status': 'EXPERIMENTAL_RAISE_PANEL',
                                         'presets': [{'box': [162, 1318, 122, 70]}],
                                         'confirm': {'box': [700, 1318, 180, 70]}}
        res = S.execute_raise_shove(v, adapter=Ad(), open_box=[500, 1250, 100, 60],
                                    capture_bgr=lambda r: v['_frame'], read_slider=slider,
                                    read_panel=panel, to_screen=lambda box, **k: box,
                                    sleep=lambda s: None, log=lambda *a, **k: None)
        self.assertEqual(res['state'], 'CLICKED_SHOVE')
        self.assertEqual(len(drags), 1)
        x0, y0, x1, y1 = drags[0]
        self.assertEqual(x0, x1)          # arrasto VERTICAL (mesma coluna)
        self.assertLess(y1, y0)           # p/ CIMA = all-in (topo do trilho)
        self.assertTrue(clicks)           # confirmou (Raise)

    def test_shove_confirm_fallback_usa_open_box(self):
        # painel NÃO devolve confirm -> usa o slot do Aumentar (open_box) p/ confirmar (não trava)
        clicks, drags = [], []
        class Ad:
            def move_to(self, *a, **k): pass
            def click_once(self, x=None, y=None, **k): clicks.append((x, y))
            def drag(self, x0, y0, x1, y1, **k): drags.append((x0, y0, x1, y1))
        v = self._view(origin=(1850, 0))
        slider = lambda crop: {'status': 'SLIDER_FOUND',
                               'handle': {'box': [640, 750, 40, 40], 'center': [660, 770]},
                               'allin_to': [660, 560]}
        panel_sem_confirm = lambda crop, _ocr=None: {'status': 'EXPERIMENTAL_RAISE_PANEL',
                                                     'presets': [{'box': [162, 1318, 122, 70]}],
                                                     'confirm': None}
        res = S.execute_raise_shove(v, adapter=Ad(), open_box=[500, 1250, 100, 60],
                                    capture_bgr=lambda r: v['_frame'], read_slider=slider,
                                    read_panel=panel_sem_confirm, to_screen=lambda box, **k: box,
                                    sleep=lambda s: None, log=lambda *a, **k: None)
        self.assertEqual(res['state'], 'CLICKED_SHOVE')
        self.assertEqual(len(drags), 1)
        # confirmou no slot do open_box [500,1250,100,60]+origin(1850,0): centro (550,1280)->(2400,1280)+1
        self.assertEqual(clicks[-1], (2401, 1281))

    def test_shove_sem_confirm_nem_openbox_abstem(self):
        v = self._view()
        class Ad:
            def move_to(self, *a, **k): pass
            def click_once(self, *a, **k): pass
            def drag(self, *a, **k): pass
        res = S.execute_raise_shove(v, adapter=Ad(), open_box=None,
                                    capture_bgr=lambda r: v['_frame'],
                                    read_slider=lambda crop: {'status': 'SLIDER_FOUND',
                                        'handle': {'box': [640, 750, 40, 40], 'center': [660, 770]},
                                        'allin_to': [660, 560]},
                                    read_panel=lambda c, _ocr=None: {'confirm': None},
                                    to_screen=lambda box, **k: box, sleep=lambda s: None,
                                    log=lambda *a, **k: None)
        self.assertEqual(res['state'], 'NO_CONFIRM')

    def test_shove_sem_slider_abstem(self):
        v = self._view()
        res = S.execute_raise_shove(v, adapter=_Adapter(), capture_bgr=lambda r: v['_frame'],
                                    read_slider=lambda crop: {'status': 'NO_SLIDER'},
                                    read_panel=lambda c, _ocr=None: {}, to_screen=lambda box, **k: box,
                                    sleep=lambda s: None, log=lambda *a, **k: None)
        self.assertEqual(res['state'], 'NO_SLIDER')

    def test_painel_nao_reconhecido_abstem(self):
        clicks = []
        ad = _Adapter(); ad.move_to = lambda *a, **k: None
        ad.click_once = lambda x=None, y=None, **k: clicks.append((x, y))
        v = self._view()
        res = S.execute_raise_preset(v, 2.0, adapter=ad, capture_bgr=lambda rect: v['_frame'],
                                     read_panel=lambda crop, _ocr=None: {'status': 'NO_RAISE_PANEL', 'presets': []},
                                     to_screen=lambda box, **k: box, log=lambda *a, **k: None)
        self.assertEqual(res['state'], 'NO_PANEL')
        self.assertEqual(clicks, [])          # painel não reconhecido -> não clica


class Street(unittest.TestCase):
    def test_postflop_por_board(self):
        self.assertFalse(S.street_is_postflop(_entry([])))
        self.assertTrue(S.street_is_postflop(_entry([1, 2, 3])))
        self.assertTrue(S.street_is_postflop(_entry([1, 2, 3, 4, 5])))


class ImageGrabEngine(unittest.TestCase):
    def test_capture_frame_usa_imagegrab_injetado(self):
        eng = S.ImageGrabEngine((0, 0, 100, 100), capture=lambda rect: 'FRAME')
        self.assertEqual(eng.capture_frame(hwnd=1), ('FRAME', {}))

    def test_capture_none_propaga(self):
        eng = S.ImageGrabEngine((0, 0, 1, 1), capture=lambda rect: None)
        self.assertEqual(eng.capture_frame(), (None, {}))


class Dispatch(unittest.TestCase):
    def _mk(self, armed, *, postflop_bet=None, sequencer_factory=None, rect=(0, 0, 100, 100)):
        return S.make_on_sizing(
            hwnd=1, adapter=_Adapter(), control=_control(armed),
            discover_rect=lambda h: rect, capture=lambda r: 'FRAME',
            engine_factory=lambda r: S.ImageGrabEngine(r, capture=lambda rr: 'FRAME'),
            postflop_bet=postflop_bet, sequencer_factory=sequencer_factory,
            log=lambda *a, **k: None)

    def test_dry_nao_executa(self):
        called = []
        on_sizing = self._mk(False, postflop_bet=lambda *a, **k: called.append(1) or {'state': 'DONE'})
        res = on_sizing({'bucket': '1/2'}, 'm', _entry([1, 2, 3]), {})
        self.assertEqual(res['state'], 'DRY')
        self.assertEqual(called, [])          # DRY nunca clica

    def test_postflop_chama_fraction_com_bucket(self):
        got = {}
        def fake_bet(engine, hwnd, bucket, *, adapter, control, discover_rect):
            got.update(bucket=bucket, has_engine=hasattr(engine, 'capture_frame'))
            return {'state': 'DONE', 'bucket': bucket}
        on_sizing = self._mk(True, postflop_bet=fake_bet)
        res = on_sizing({'bucket': '2/3'}, 'm', _entry([1, 2, 3]), {})
        self.assertEqual(res['state'], 'DONE')
        self.assertEqual(got['bucket'], '2/3')
        self.assertTrue(got['has_engine'])    # recebeu o shim ImageGrab

    def test_postflop_sem_bucket_usa_default(self):
        got = {}
        on_sizing = self._mk(True, postflop_bet=lambda e, h, b, **k: got.update(b=b) or {'state': 'DONE'})
        on_sizing({}, 'm', _entry([1, 2, 3]), {})
        self.assertEqual(got['b'], '1/2')     # default seguro

    def test_preflop_chama_sequencer_com_target(self):
        got = {}
        class FakeSeq:
            def __init__(self, rect, tmult): got.update(rect=rect, tmult=tmult)
            def run(self): return {'result_state': 'DONE', 'ok': True}
        on_sizing = self._mk(True, sequencer_factory=lambda rect, tmult: FakeSeq(rect, tmult))
        res = on_sizing({'size': 3.0}, 'm', _entry([]), {})     # pré-flop (board vazio)
        self.assertEqual(res['result_state'], 'DONE')
        self.assertEqual(got['tmult'], 3.0)

    def test_preflop_sem_target_nao_executa(self):
        on_sizing = self._mk(True, sequencer_factory=lambda rect, tmult: None)
        self.assertEqual(on_sizing({}, 'm', _entry([]), {})['state'], 'NO_TARGET')

    def test_sem_rect_nao_executa(self):
        on_sizing = self._mk(True, rect=None, postflop_bet=lambda *a, **k: {'state': 'DONE'})
        self.assertEqual(on_sizing({'bucket': '1/2'}, 'm', _entry([1, 2, 3]), {})['state'], 'NO_RECT')


if __name__ == '__main__':
    unittest.main()
