"""Primitivas de ação da troca de clube: scroll GATED (fake adapter/control) e
localizador do clube no frame (gabarito real, guardado por Tesseract)."""
import os
import unittest

from bot_control import BotControl
from club_actions import locate_club_in_frame, scroll_grid_once


class _FakeAdapter:
    def __init__(self, released=True):
        self.drags = []
        self._released = released

    def drag(self, x0, y0, x1, y1, *, bounds=None, steps=14, settle_s=0.05):
        self.drags.append((x0, y0, x1, y1))
        return dict(released=self._released, down_accepted=1, up_accepted=1)


class ScrollTests(unittest.TestCase):
    def test_nao_rola_sem_arme(self):
        ad = _FakeAdapter()
        ctrl = BotControl()                      # PAUSED
        r = scroll_grid_once(ad, ctrl, panel_rect=(100, 200, 300, 800))
        self.assertFalse(r['sent'])
        self.assertEqual(r['reason'], 'BOT_NOT_RUNNING')
        self.assertEqual(ad.drags, [])           # nada enviado

    def test_rola_quando_armado_direcao_below(self):
        ad = _FakeAdapter()
        ctrl = BotControl(); ctrl.resume()       # RUNNING
        r = scroll_grid_once(ad, ctrl, panel_rect=(100, 200, 300, 800), reveal='below')
        self.assertTrue(r['sent'] and r['ok'])
        (x0, y0, x1, y1), = ad.drags
        self.assertEqual(x0, x1)                 # arrasto vertical, no centro-x do painel
        self.assertEqual(x0, 100 + 150)
        self.assertGreater(y0, y1)               # reveal 'below' arrasta p/ CIMA

    def test_release_nao_confirmado_reporta(self):
        ad = _FakeAdapter(released=False)
        ctrl = BotControl(); ctrl.resume()
        r = scroll_grid_once(ad, ctrl, panel_rect=(0, 0, 100, 100))
        self.assertTrue(r['sent'])
        self.assertFalse(r['ok'])
        self.assertEqual(r['reason'], 'RELEASE_UNCONFIRMED')


class SearchLupaTests(unittest.TestCase):
    def test_none_sem_lupa(self):
        import numpy as np
        from club_actions import find_search_lupa
        self.assertIsNone(find_search_lupa(np.zeros((2160, 2700, 3), np.uint8)))

    def test_pega_a_lupa_mais_a_direita(self):
        import numpy as np
        from club_actions import find_search_lupa
        f = np.zeros((2160, 2700, 3), np.uint8)
        green = (60, 200, 60)                          # BGR verde (H~60, S/V altos)
        y = int(0.13 * 2160)
        f[y:y + 28, 2440:2470] = green                 # 'casa+' (à esquerda)
        f[y:y + 28, 2540:2570] = green                 # lupa (à direita)
        r = find_search_lupa(f)
        self.assertIsNotNone(r)
        self.assertGreater(r[0], 2510)                 # pegou a da DIREITA (lupa)


def _ocr_ready():
    try:
        from table_reading.pipeline import configure_ocr
        return configure_ocr().get('status') == 'READY'
    except Exception:
        return False


_FIX = os.path.join('tests', 'fixtures', 'club_grid', 'club-grid-live-1.png')


def _embed(ox, oy, cw=1700, ch=2100):
    import cv2
    import numpy as np
    grid = cv2.imread(_FIX)
    h, w = grid.shape[:2]
    canvas = np.zeros((ch, cw, 3), np.uint8)
    canvas[oy:oy + h, ox:ox + w] = grid
    return canvas, (ox, oy)


@unittest.skipUnless(_ocr_ready() and os.path.exists(_FIX),
                     'Tesseract/gabarito indisponível')
class LocateTests(unittest.TestCase):
    @staticmethod
    def _ocr():
        from table_reading.ocr_runtime import image_to_string
        return lambda g: image_to_string(g, config='--psm 7')

    def test_localiza_o_clube_alvo_no_frame(self):
        frame, (ox, oy) = _embed(600, 350)
        rect = locate_club_in_frame(frame, 'AK Amakha Club', ocr=self._ocr())
        self.assertIsNotNone(rect)
        x, y, w, h = rect
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)
        # o nome "AK Amakha Club" (col direita, 2a linha) cai à direita e meio-baixo
        cx, cy = x + w / 2, y + h / 2
        self.assertAlmostEqual(cx, ox + 578, delta=30)
        self.assertAlmostEqual(cy, oy + 954, delta=30)

    def test_clube_ausente_devolve_none(self):
        frame, _ = _embed(600, 350)
        self.assertIsNone(locate_club_in_frame(frame, 'Veneza', ocr=self._ocr()))

    def test_frame_sem_grade_devolve_none(self):
        import numpy as np
        self.assertIsNone(locate_club_in_frame(np.zeros((400, 400, 3), np.uint8),
                                               'Karekas Yellow', ocr=self._ocr()))


if __name__ == '__main__':
    unittest.main()
