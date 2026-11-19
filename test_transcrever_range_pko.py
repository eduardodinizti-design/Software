"""Trava o transcritor de ranges BOUNTY/PKO (paleta própria: raise=vermelho, fold=azul).
- Fixture sintética (sempre): grid 13×13 pintado -> valida geometria + classificação.
- PDF real (se pymupdf + arquivo presentes): raise% combo-ponderado ~ o % do PDF (±3)."""
import os
import unittest

import numpy as np
import cv2

import transcrever_range_pko as pk

_PDF = os.path.join(os.path.dirname(__file__), '..', 'Ranges E TEORIAS', 'Teoria',
                    'Reg_Life_-_TORNEIOS_BOUNTY_-_RANGES_PRATICOS (1).pdf')
_RED = (237, 59, 59)       # raise
_BLUE = (60, 123, 182)     # fold


def _synthetic(suited='raise', offsuit='fold', pair='raise'):
    img = np.zeros((650, 715, 3), np.uint8)
    cw, ch = 55, 50
    cor = {'raise': _RED, 'fold': _BLUE}
    for r in range(13):
        for c in range(13):
            k = pair if r == c else (suited if c > r else offsuit)
            # a imagem é RGB (como vem do pymupdf); NÃO inverter p/ BGR aqui
            cv2.rectangle(img, (c * cw + 1, r * ch + 1), ((c + 1) * cw - 2, (r + 1) * ch - 2),
                          cor[k], -1)
    return img


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.h = pk.read_range_image(_synthetic())['hands']

    def test_mapa_de_maos(self):
        self.assertEqual(max(self.h['AKs'], key=self.h['AKs'].get), 'raise')
        self.assertEqual(max(self.h['AKo'], key=self.h['AKo'].get), 'fold')
        self.assertEqual(max(self.h['AA'], key=self.h['AA'].get), 'raise')
        self.assertEqual(max(self.h['72o'], key=self.h['72o'].get), 'fold')
        self.assertEqual(len(self.h), 169)

    def test_summary_combo(self):
        s = pk.summary(self.h)
        # suited 312 + pares 78 = 390 raise / 1326 = 29,4%
        self.assertAlmostEqual(s['raise']['pct'], 29.4, delta=1.5)


@unittest.skipUnless(os.path.exists(_PDF), 'PDF de bounty ausente')
class RealPDF(unittest.TestCase):
    def test_p6_utg_abre_cerca_de_24pct(self):
        try:
            import pymupdf
        except ImportError:
            self.skipTest('pymupdf ausente')
        d = pymupdf.open(_PDF)
        img = pk.grid_image_from_page(d[5], d)       # p6: UTG abre ~24%
        self.assertIsNotNone(img)
        s = pk.summary(pk.read_range_image(img)['hands'])
        self.assertAlmostEqual(s['raise']['pct'], 24.0, delta=3.0)
        self.assertEqual(max(pk.read_range_image(img)['hands']['AA'],
                             key=pk.read_range_image(img)['hands']['AA'].get), 'raise')


if __name__ == '__main__':
    unittest.main()
