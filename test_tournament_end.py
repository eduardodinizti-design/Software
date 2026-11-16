"""Detector da tela de FIM DE TORNEIO (eliminação). Rotina: ao cair -> fechar
a mesa clicando 'Sair'. Gabarito: tests/fixtures/tournament_end/."""
import os
import unittest

import numpy as np

try:
    import cv2
except Exception:                       # pragma: no cover
    cv2 = None

from table_reading.tournament_end import detect_tournament_end, _ocr
from table_reading.pipeline import configure_ocr

FIX = os.path.join('tests', 'fixtures', 'tournament_end', 'ranking_65_272_popup.png')


@unittest.skipIf(cv2 is None, 'OpenCV ausente')
class TournamentEndTests(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(FIX):
            self.skipTest('fixture ausente: %s' % FIX)
        self.crop = cv2.imread(FIX)
        # O operador ao vivo SEMPRE configura o OCR. A TRAVA anti-Pagar exige LER
        # "Sair"/"Ficar" no botão (senão não é fim de torneio -> não clica). Sem
        # tesseract o detector é conservador (NO_TOURNAMENT_END = idle, seguro),
        # então os testes POSITIVOS só valem com OCR disponível.
        try:
            configure_ocr()
        except Exception:                                # pragma: no cover
            pass
        self._ocr_ok = 'sair' in _ocr(self.crop[1360:1441, 499:815]).casefold()

    def _need_ocr(self):
        if not self._ocr_ok:
            self.skipTest('tesseract indisponível: detector exige ler "Sair" p/ confirmar')

    def test_detects_elimination_screen(self):
        self._need_ocr()
        r = detect_tournament_end(self.crop)
        self.assertEqual(r['status'], 'TOURNAMENT_END')

    def test_sair_is_the_right_button_to_close(self):
        self._need_ocr()
        r = detect_tournament_end(self.crop)
        self.assertIsNotNone(r['sair_box'])
        self.assertIsNotNone(r['ficar_box'])
        # 'Sair' (fechar) fica à DIREITA do 'Ficar'; é a caixa a clicar na rotina.
        self.assertGreater(r['sair_box'][0], r['ficar_box'][0])

    def test_buttons_are_in_the_bottom_band(self):
        self._need_ocr()
        r = detect_tournament_end(self.crop)
        h = self.crop.shape[0]
        for box in (r['ficar_box'], r['sair_box']):
            cy = (box[1] + box[3] / 2) / h
            self.assertGreater(cy, 0.80)

    def test_live_preaction_row_is_not_tournament_end(self):
        # REGRESSÃO (incidente 15/11, pixel REAL): mesa VIVA com a linha de pré-ação
        # verde [F/C | Call X | Pagar] + feltro azul no topo era FALSO POSITIVO ->
        # o detector clicava sair_box = botão da direita = PAGAR (o bot "pagava"
        # sozinho). Agora o detector lê o rótulo: "Pagar" != "Sair" -> NÃO é fim.
        live = os.path.join('tests', 'fixtures', 'tournament_end', 'live_preaction_pagar.png')
        if not os.path.exists(live):
            self.skipTest('fixture ausente: %s' % live)
        r = detect_tournament_end(cv2.imread(live))
        self.assertEqual(r['status'], 'NO_TOURNAMENT_END')
        self.assertIsNone(r['sair_box'])                 # nada a clicar -> Pagar intocável

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
