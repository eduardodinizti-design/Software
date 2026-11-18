"""locate_word: localiza uma palavra de UI e devolve o ponto de clique. Testado no
gabarito real do menu do seletor (guardado por Tesseract)."""
import os
import unittest

from ocr_locate import locate_word


def _ocr_ready():
    try:
        from table_reading.pipeline import configure_ocr
        return configure_ocr().get('status') == 'READY'
    except Exception:
        return False


_FIX = os.path.join('tests', 'fixtures', 'club_grid', 'selector-menu-live-1.png')


@unittest.skipUnless(_ocr_ready() and os.path.exists(_FIX),
                     'Tesseract/gabarito indisponível')
class LocateWordTests(unittest.TestCase):
    def _img(self):
        import cv2
        return cv2.imread(_FIX)

    def test_acha_pesquisar_e_trocar(self):
        img = self._img()
        p = locate_word(img, ['Pesquisar'])
        t = locate_word(img, ['Trocar', 'Trocar exibição'])
        self.assertIsNotNone(p)
        self.assertIsNotNone(t)
        # "Pesquisar" fica ABAIXO de "Trocar exibição" no menu
        self.assertGreater(p[1], t[1])

    def test_case_insensitive(self):
        self.assertIsNotNone(locate_word(self._img(), ['pesquisar']))

    def test_palavra_ausente_none(self):
        self.assertIsNone(locate_word(self._img(), ['Xyzzy']))

    def test_targets_vazio_none(self):
        self.assertIsNone(locate_word(self._img(), []))


if __name__ == '__main__':
    unittest.main()
