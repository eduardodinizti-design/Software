"""Detector da tela de FIM DE TORNEIO (eliminação). Rotina: ao cair -> fechar
a mesa clicando 'Sair'. Gabarito: tests/fixtures/tournament_end/."""
import os
import unittest

import numpy as np

try:
    import cv2
except Exception:                       # pragma: no cover
    cv2 = None

from table_reading.tournament_end import detect_tournament_end

FIX = os.path.join('tests', 'fixtures', 'tournament_end', 'ranking_65_272_popup.png')


@unittest.skipIf(cv2 is None, 'OpenCV ausente')
class TournamentEndTests(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(FIX):
            self.skipTest('fixture ausente: %s' % FIX)
        self.crop = cv2.imread(FIX)

    def test_detects_elimination_screen(self):
        r = detect_tournament_end(self.crop)
        self.assertEqual(r['status'], 'TOURNAMENT_END')

    def test_sair_is_the_right_button_to_close(self):
        r = detect_tournament_end(self.crop)
        self.assertIsNotNone(r['sair_box'])
        self.assertIsNotNone(r['ficar_box'])
        # 'Sair' (fechar) fica à DIREITA do 'Ficar'; é a caixa a clicar na rotina.
        self.assertGreater(r['sair_box'][0], r['ficar_box'][0])

    def test_buttons_are_in_the_bottom_band(self):
        r = detect_tournament_end(self.crop)
        h = self.crop.shape[0]
        for box in (r['ficar_box'], r['sair_box']):
            cy = (box[1] + box[3] / 2) / h
            self.assertGreater(cy, 0.80)

    def test_noise_is_not_tournament_end(self):
        rng = np.random.RandomState(0)
        neg = rng.randint(0, 255, (600, 400, 3), np.uint8)
        self.assertEqual(detect_tournament_end(neg)['status'], 'NO_TOURNAMENT_END')

    def test_black_is_not_tournament_end(self):
        self.assertEqual(detect_tournament_end(np.zeros((600, 400, 3), np.uint8))['status'],
                         'NO_TOURNAMENT_END')

    def test_invalid_crop(self):
        self.assertEqual(detect_tournament_end(None)['status'], 'INVALID_CROP')


if __name__ == '__main__':
    unittest.main()
