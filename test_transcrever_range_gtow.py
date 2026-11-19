"""Trava o transcritor de charts GTOWizard (Eduardo 19/11, método automático).
- Fixture SINTÉTICA (sempre roda): grid 13×13 pintado com cores conhecidas por célula ->
  valida GEOMETRIA (mapa de mãos) + CLASSIFICAÇÃO de cor + summary combo-ponderado.
- Charts REAIS (roda só se a pasta existir): o % combo-ponderado TEM que bater com a barra
  do cabeçalho do GTOWizard (tolerância 1,5 pts) — o oráculo de verdade."""
import os
import unittest

import numpy as np
import cv2

import transcrever_range_gtow as tg

_RANGES_DIR = os.path.join(os.path.dirname(__file__), '..', 'Ranges E TEORIAS')

# centroides (RGB) p/ pintar a fixture
_C = {'fold': (63, 122, 180), 'call': (91, 181, 103),
      'raise': (247, 124, 124), 'allin': (110, 25, 25)}


def _synthetic(suited='call', offsuit='fold', pair='allin'):
    """Grid 13×13: toda suited=verde, offsuit=azul, par=vinho (padrão) — mãos distinguíveis
    por geometria. Monta header escuro em cima e um painel colorido à direita (p/ a detecção
    ter que ignorá-los)."""
    W, H = 2200, 950
    img = np.full((H, W, 3), 18, np.uint8)             # fundo escuro ~ (18,18,18)
    gx, gy, cw, ch = 10, 150, 100, 60                  # grid 1300×780
    for r in range(13):
        for c in range(13):
            if r == c:
                col = _C[pair]
            elif c > r:
                col = _C[suited]
            else:
                col = _C[offsuit]
            x0, y0 = gx + c * cw, gy + r * ch
            cv2.rectangle(img, (x0 + 1, y0 + 1), (x0 + cw - 2, y0 + ch - 2),
                          col[::-1], -1)               # BGR
    # painel direito colorido (deve ser ignorado pela detecção)
    cv2.rectangle(img, (1700, 400), (2100, 560), _C['raise'][::-1], -1)
    return img


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.join(os.path.dirname(__file__),
                                'logs', '_test_synth_range.png')
        os.makedirs(os.path.dirname(self.tmp), exist_ok=True)
        cv2.imwrite(self.tmp, _synthetic())
        self.res = tg.read_range(self.tmp)

    def tearDown(self):
        try:
            os.remove(self.tmp)
        except OSError:
            pass

    def test_mapa_de_maos_por_geometria(self):
        h = self.res['hands']
        self.assertEqual(max(h['AKs'], key=h['AKs'].get), 'call')     # suited -> verde
        self.assertEqual(max(h['AKo'], key=h['AKo'].get), 'fold')     # offsuit -> azul
        self.assertEqual(max(h['AA'], key=h['AA'].get), 'allin')      # par -> vinho
        self.assertEqual(max(h['72o'], key=h['72o'].get), 'fold')
        self.assertEqual(max(h['22'], key=h['22'].get), 'allin')
        self.assertIn('AKs', h); self.assertIn('2 2'.replace(' ', ''), h)
        self.assertEqual(len(h), 169)

    def test_summary_combo_ponderado(self):
        s = tg.summary(self.res['hands'])
        # suited=312 combos, offsuit=936, pares=78 (total 1326)
        self.assertAlmostEqual(s['call']['pct'], 23.5, delta=1.0)
        self.assertAlmostEqual(s['fold']['pct'], 70.6, delta=1.0)
        self.assertAlmostEqual(s['allin']['pct'], 5.9, delta=1.0)


class HandMapping(unittest.TestCase):
    def test_hand_at_cantos(self):
        self.assertEqual(tg.hand_at(0, 0), 'AA')
        self.assertEqual(tg.hand_at(0, 1), 'AKs')
        self.assertEqual(tg.hand_at(1, 0), 'AKo')
        self.assertEqual(tg.hand_at(12, 12), '22')
        self.assertEqual(tg.hand_at(0, 12), 'A2s')
        self.assertEqual(tg.hand_at(12, 0), 'A2o')


# ground-truth do cabeçalho dos charts reais (ação: (pct, combos))
_REAL = {
    os.path.join('20 BB', 'BB 20 vs SB Shove.jpg'): {'call': 23.5, 'fold': 76.5},
    os.path.join('20 BB', 'BTN 20.jpg'): {'allin': 4.3, 'raise': 37.2, 'fold': 58.5},
}


@unittest.skipUnless(os.path.isdir(_RANGES_DIR), 'pasta de charts reais ausente')
class RealCharts(unittest.TestCase):
    def test_bate_com_cabecalho(self):
        for rel, truth in _REAL.items():
            p = os.path.join(_RANGES_DIR, rel)
            if not os.path.exists(p):
                self.skipTest('chart ausente: %s' % rel)
            s = tg.summary(tg.read_range(p)['hands'])
            for act, pct in truth.items():
                got = s.get(act, {}).get('pct', 0.0)
                self.assertAlmostEqual(got, pct, delta=1.5,
                                       msg='%s %s: %.1f vs %.1f' % (rel, act, got, pct))


if __name__ == '__main__':
    unittest.main()
