"""SmoothCursor: curva (vários passos), termina no ponto exato, clica no lugar. Offline."""
import unittest

from smooth_cursor import SmoothCursor


class FakeBackend:
    """Registra move_to/click_once/drag e devolve posição do cursor = último move."""
    def __init__(self, start=(0, 0)):
        self.moves = []
        self.clicks = []
        self.drags = []
        self._pos = start

    def cursor_pos(self):
        return self._pos

    def virtual_bounds(self):
        return (0, 0, 3840, 1440)

    def normalize_abs(self, x, y, bounds=None):
        return (x, y)

    def move_to(self, x, y, bounds=None):
        self._pos = (x, y)
        self.moves.append((x, y))
        return {'accepted': 1, 'norm': (x, y)}

    def click_once(self, x=None, y=None, *, bounds=None, hold_s=None):
        self.clicks.append((x, y, self._pos))
        return {'released': True}

    def drag(self, x0, y0, x1, y1, *, bounds=None, steps=14, settle_s=0.05):
        self.drags.append((x0, y0, x1, y1))
        self._pos = (x1, y1)
        return {'released': True}


def _clock():
    # relógio determinístico, passo fino -> o laço gera vários pontos ao longo da curva
    _clock.t += 0.004
    return _clock.t
_clock.t = 0.0


class SmoothCursorTest(unittest.TestCase):
    def setUp(self):
        _clock.t = 0.0

    def _cursor(self, start=(10, 10)):
        from cursor_trajectory import TrajectoryGenerator
        b = FakeBackend(start=start)
        tg = TrajectoryGenerator(clock=_clock)          # MESMO relógio do loop (senão progresso=0)
        c = SmoothCursor(backend=b, tg=tg, clock=_clock, sleep=lambda s: None, step_s=0.0)
        return b, c

    def test_move_curva_varios_passos_e_ponto_exato(self):
        b, c = self._cursor(start=(100, 100))
        c.move_to(900, 1315)
        self.assertGreaterEqual(len(b.moves), 3)          # vários passos = curva, não teleporte
        self.assertEqual(b.moves[-1], (900, 1315))        # termina EXATO no destino

    def test_curva_nao_e_reta_pura(self):
        # com bow>0 o caminho sai da reta início->destino em algum ponto intermediário
        b, c = self._cursor(start=(0, 0))
        c.move_to(1000, 0)                                # destino na horizontal
        # algum ponto intermediário sai da reta y=0 -> o caminho CURVOU (Bézier com bow)
        self.assertTrue(any(m[1] != 0 for m in b.moves[:-1]))

    def test_click_once_curva_e_clica_no_lugar(self):
        b, c = self._cursor(start=(50, 50))
        c.click_once(685, 1315)
        self.assertEqual(b.moves[-1], (685, 1315))        # curvou até o alvo
        self.assertEqual(len(b.clicks), 1)
        self.assertEqual(b.clicks[0][:2], (None, None))   # clicou NO LUGAR (sem re-teleportar)
        self.assertEqual(b.clicks[0][2], (685, 1315))     # posição do clique = destino

    def test_drag_aproxima_em_curva_depois_arrasta(self):
        b, c = self._cursor(start=(0, 0))
        c.drag(660, 770, 660, 560)
        self.assertTrue(b.moves)                           # aproximação curva ocorreu
        self.assertEqual(b.moves[-1], (660, 770))          # terminou no handle (x0,y0)
        self.assertEqual(b.drags, [(660, 770, 660, 560)])  # delegou o arrasto ao backend

    def test_leituras_passam_direto(self):
        b, c = self._cursor()
        self.assertEqual(c.virtual_bounds(), (0, 0, 3840, 1440))
        self.assertEqual(c.normalize_abs(5, 6), (5, 6))


if __name__ == '__main__':
    unittest.main()
