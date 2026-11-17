"""Executor da troca de clube (lógica de alto nível, dependências fakes). As ações
reais (clique/scroll) são gated; aqui cobrimos idempotência, planejamento dry-run,
e o gate (pausado não envia)."""
import os
import unittest

from bot_control import BotControl
from operar_troca_clube import ensure_club_live


class _Engine:
    """Engine fake: devolve sempre o mesmo frame."""
    def __init__(self, frame):
        self._f = frame

    def capture_frame(self, hwnd=None):
        return self._f, {}


def _discover(_hwnd):
    return (0, 0, 1700, 2100)


class NoOcrTests(unittest.TestCase):
    def test_alvo_invalido(self):
        import numpy as np
        eng = _Engine(np.zeros((10, 10, 3), np.uint8))
        r = ensure_club_live('  ', engine=eng, hwnd=1, adapter=None, control=BotControl(),
                             ocr=lambda g: '', discover_rect=_discover, dry_run=True)
        self.assertEqual(r['action'], 'ALVO_INVALIDO')

    def test_sem_grade_quando_frame_vazio(self):
        import numpy as np
        eng = _Engine(np.zeros((400, 400, 3), np.uint8))
        r = ensure_club_live('AK Amakha Club', engine=eng, hwnd=1, adapter=None,
                             control=BotControl(), ocr=lambda g: '',
                             discover_rect=_discover, dry_run=True)
        self.assertEqual(r['action'], 'SEM_GRADE')      # nem OCR é chamado p/ frame preto


def _ocr_ready():
    try:
        from table_reading.pipeline import configure_ocr
        return configure_ocr().get('status') == 'READY'
    except Exception:
        return False


_GRID = os.path.join('tests', 'fixtures', 'club_grid', 'club-grid-live-1.png')
_INSIDE = os.path.join('tests', 'fixtures', 'lobby_live', 'karekas-lobby-live-1.png')


def _ocr():
    from table_reading.ocr_runtime import image_to_string
    return lambda g: image_to_string(g, config='--psm 7')


def _embed_grid(ox=600, oy=350, cw=1700, ch=2100):
    import cv2
    import numpy as np
    grid = cv2.imread(_GRID)
    h, w = grid.shape[:2]
    canvas = np.zeros((ch, cw, 3), np.uint8)
    canvas[oy:oy + h, ox:ox + w] = grid
    return canvas


@unittest.skipUnless(_ocr_ready() and os.path.exists(_GRID) and os.path.exists(_INSIDE),
                     'Tesseract/gabaritos indisponíveis')
class LiveLogicTests(unittest.TestCase):
    def test_idempotente_quando_ja_no_clube(self):
        import cv2
        eng = _Engine(cv2.imread(_INSIDE))             # dentro do Karekas
        r = ensure_club_live('Karekas Yellow', engine=eng, hwnd=1, adapter=None,
                             control=BotControl(), ocr=_ocr(), discover_rect=_discover,
                             dry_run=True)
        self.assertEqual(r['action'], 'NOOP_JA_NO_CLUBE')
        self.assertTrue(r['ok'])

    def test_dry_run_planeja_clique_no_alvo_visivel(self):
        eng = _Engine(_embed_grid())
        r = ensure_club_live('AK Amakha Club', engine=eng, hwnd=1, adapter=None,
                             control=BotControl(), ocr=_ocr(), discover_rect=_discover,
                             dry_run=True)
        self.assertEqual(r['action'], 'PLANO_CLICAR')
        self.assertIn('target_rect_frame', r)

    def test_dry_run_planeja_rolar_quando_alvo_ausente(self):
        eng = _Engine(_embed_grid())
        r = ensure_club_live('Veneza', engine=eng, hwnd=1, adapter=None,
                             control=BotControl(), ocr=_ocr(), discover_rect=_discover,
                             dry_run=True)
        self.assertEqual(r['action'], 'PLANO_ROLAR')

    def test_armado_mas_pausado_nao_rola(self):
        # dry_run=False mas control PAUSADO: o gate barra o scroll (nada enviado).
        eng = _Engine(_embed_grid())
        r = ensure_club_live('Veneza', engine=eng, hwnd=1, adapter=None,
                             control=BotControl(), ocr=_ocr(), discover_rect=_discover,
                             dry_run=False, max_scrolls=2)
        self.assertEqual(r['action'], 'SCROLL_FALHOU')
        self.assertEqual(r['reason'], 'BOT_NOT_RUNNING')


if __name__ == '__main__':
    unittest.main()
