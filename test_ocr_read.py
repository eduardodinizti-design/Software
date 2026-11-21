"""TRAVA do OCR de números (F3): lê os stacks (em BB) das caixas do layout numa CAPTURA REAL.
Gated no binário do Tesseract E na captura (pula se faltar)."""
import os
import unittest

_TESS = any(os.path.exists(p) for p in (
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Users\tacao\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'))
_CAP = r'C:\Meus Projetos\Aplicativos\_repo_software\research\suprema_cocos\raise_c_01.png'


@unittest.skipUnless(_TESS and os.path.exists(_CAP), 'tesseract ou captura ausente')
class OcrReal(unittest.TestCase):

    def test_le_stacks_reais(self):
        from vision_yolo.ocr_read import read_seats
        from vision_yolo.suprema_layout import STACK_REGIONS
        seats = read_seats(_CAP, STACK_REGIONS)
        # valores conhecidos na captura raise_c_01 (tolerancia de leitura)
        esperado = {'hero': 112.6, 'top': 41.7, 'top_right': 125.6,
                    'mid_right': 65.3, 'low_right': 39.2}
        acertos = sum(1 for k, v in esperado.items()
                      if k in seats and abs(seats[k] - v) < 0.5)
        self.assertGreaterEqual(acertos, 4, 'leu só %d/5: %r' % (acertos, seats))

    def test_read_number_bb(self):
        from vision_yolo.ocr_read import read_number
        v = read_number(_CAP, (0.50, 0.864, 0.16, 0.026))     # hero stack
        self.assertIsNotNone(v)
        self.assertAlmostEqual(v, 112.6, delta=0.5)


if __name__ == '__main__':
    unittest.main()
