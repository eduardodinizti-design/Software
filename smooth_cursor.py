"""Adaptador de cursor SUAVE (Eduardo 25/11) — move em CURVA (min-jerk + Bézier), nunca teleporta.

LEI do Eduardo: ele gosta de VER o cursor se movendo em curva. O `WindowsCursorInput` cru faz um
`move_to` absoluto único (teleporte seco). Este wrapper reusa o MESMO padrão já validado na Suprema
(`suprema_click._click_sendinput`): `TrajectoryGenerator` (cursor_trajectory) planeja o caminho curvo
e amostra por tempo REAL, enviando vários `move_to` intermediários pelo backend físico. O hover real
no destino também ajuda o botão/preset do PPPoker a REGISTRAR (o teleporte às vezes não ativava).

Interface compatível com WindowsCursorInput (move_to/click_once/drag + cursor_pos/virtual_bounds/
normalize_abs), então entra direto no lugar dele em pppoker_agente/ppp_execute/ppp_sizing. Puro e
injetável: backend/tg/clock/sleep dão pra testar offline sem Windows.
"""
from __future__ import annotations

import time


class SmoothCursor:
    """Envolve um backend estilo WindowsCursorInput e faz move_to/click_once/drag seguirem uma
    trajetória CURVA (min-jerk + Bézier). Leituras (cursor_pos/virtual_bounds/normalize_abs) passam
    direto pro backend."""

    def __init__(self, backend=None, tg=None, *, clock=time.monotonic, sleep=time.sleep,
                 step_s=0.008, settle_s=0.04):
        if backend is None:
            from cursor_input_win import WindowsCursorInput
            backend = WindowsCursorInput()
        if tg is None:
            from cursor_trajectory import TrajectoryGenerator
            tg = TrajectoryGenerator()
        self._b = backend
        self._tg = tg
        self._clock = clock
        self._sleep = sleep
        self._step_s = float(step_s)
        self._settle_s = float(settle_s)

    # ---- leituras: passam direto ----
    def cursor_pos(self):
        return self._b.cursor_pos()

    def virtual_bounds(self):
        return self._b.virtual_bounds()

    def normalize_abs(self, x, y, bounds=None):
        return self._b.normalize_abs(x, y, bounds)

    # ---- o movimento curvo ----
    def _start_xy(self, fallback):
        try:
            cur = self._b.cursor_pos()
            if isinstance(cur, dict):
                return float(cur.get('x')), float(cur.get('y'))
            if isinstance(cur, (tuple, list)) and len(cur) >= 2:
                return float(cur[0]), float(cur[1])
        except Exception:
            pass
        return float(fallback[0]), float(fallback[1])

    def move_to(self, x, y, bounds=None):
        """Move em CURVA de (posição atual) até (x,y). Envia vários move_to pelo caminho; termina
        no ponto EXATO. Retorna o relato do move_to final (compat com WindowsCursorInput)."""
        sx, sy = self._start_xy((x, y))
        plan = self._tg.plan((sx, sy), (float(x), float(y)))
        dur = float(getattr(plan, 'duration_s', 0.2))
        t_end = self._clock() + max(0.12, dur + 0.03)
        # amostra por tempo REAL (não pressupõe que cada sleep foi atendido)
        while self._clock() < t_end and not plan.done(self._clock()):
            px, py = plan.point_at(plan.progress(self._clock()))
            self._b.move_to(int(round(px)), int(round(py)), bounds)
            self._sleep(self._step_s)
        return self._b.move_to(int(x), int(y), bounds)        # ponto final EXATO

    def click_once(self, x=None, y=None, *, bounds=None, hold_s=None):
        """Curva até (x,y), assenta (hover) e clica NO LUGAR — sem re-teleportar. Se x/y None, clica
        na posição atual."""
        if x is not None and y is not None:
            self.move_to(x, y, bounds)
            if self._settle_s > 0:
                self._sleep(self._settle_s)                   # hover -> botão/preset ativa
        return self._b.click_once(bounds=bounds, hold_s=hold_s)   # clica onde o cursor está

    def drag(self, x0, y0, x1, y1, *, bounds=None, steps=14, settle_s=0.05):
        """Aproxima de (x0,y0) em CURVA e então arrasta (down -> passos -> up) com o backend. A
        aproximação curva evita o pulo até o handle do slider; o arrasto em si segue o backend."""
        self.move_to(x0, y0, bounds)                          # aproximação CURVA
        return self._b.drag(x0, y0, x1, y1, bounds=bounds, steps=steps, settle_s=settle_s)
