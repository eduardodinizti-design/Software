"""Adaptador de entrada do Windows para o cursor — SendInput (Fase 3B).

Envia movimento/clique ao Windows via SendInput (API documentada; a spec
`ORIENTAÇÃO PARA MOVIMENTO NATURAL` §7 propõe migrar do SetCursorPos+mouse_event
do executor manual para SendInput). Responsabilidade ÚNICA: enviar eventos e
RELATAR quantos o sistema aceitou — isso confirma só aceitação de entrada, não a
execução da ação pela aplicação. O adaptador NÃO planeja trajetória, NÃO decide
alvo e NÃO valida mesa — isso é do coordenador.

- Coordenadas absolutas são normalizadas para o DESKTOP VIRTUAL (0..65535 com
  MOUSEEVENTF_VIRTUALDESK), tratando origem/múltiplos monitores e coords
  negativas. Confira o efeito das configurações do Windows antes de prometer
  correspondência entre coordenada enviada e posição observada.
- Clique ÚNICO: um mouse-down e um mouse-up para a MESMA intenção, com soltura
  GARANTIDA (try/finally) mesmo em erro. O tempo de pressionamento é documentado
  e validável no ambiente de teste — NÃO escolhido para alegar invisibilidade.
- win32 é carregado preguiçosamente (lazy): o módulo importa no lab Linux; o
  backend real só é construído quando usado sem um backend injetado (testes).

Valide primeiro com VERIFICAR_EXECUTOR_HU.bat, na janela propria de teste.
O contrato operacional e as provas do efeito pertencem ao executor chamador.
"""
import time
import re

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

DEFAULT_PRESS_S = 0.06   # documentado; validar no ambiente de teste


class CursorInputError(RuntimeError):
    pass


def _build_real_backend():
    """Backend ctypes real (só no Windows; construído sob demanda)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    ULONG_PTR = ctypes.c_size_t

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                    ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                    ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]

    class _U(ctypes.Union):
        pass

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                    ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]

    _U._fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [('type', wintypes.DWORD), ('u', _U)]

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    user32.SetThreadDpiAwarenessContext.argtypes = (ctypes.c_void_p,)
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetAncestor.restype = wintypes.HWND

    def physical_call(fn):
        previous = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        if not previous:
            raise CursorInputError('INPUT_DPI_CONTEXT_UNAVAILABLE')
        try:
            return fn()
        finally:
            user32.SetThreadDpiAwarenessContext(previous)

    class _Real:
        def virtual_bounds(self):
            # SM_XVIRTUALSCREEN=76,77,78,79 (x,y,cx,cy do desktop virtual)
            return physical_call(lambda: (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
                    user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)))

        def get_cursor_pos(self):
            p = wintypes.POINT()
            if not physical_call(lambda: user32.GetCursorPos(ctypes.byref(p))):
                raise CursorInputError('GetCursorPos falhou')
            return (p.x, p.y)

        def send(self, flags_list, abs_xy=None):
            n = len(flags_list)
            arr = (INPUT * n)()
            for i, flags in enumerate(flags_list):
                mi = MOUSEINPUT(0, 0, 0, flags, 0, 0)
                if abs_xy is not None and (flags & MOUSEEVENTF_MOVE):
                    mi.dx, mi.dy = abs_xy
                arr[i] = INPUT(0, _U(mi))   # type 0 = INPUT_MOUSE
            sent = physical_call(lambda: user32.SendInput(n, arr, ctypes.sizeof(INPUT)))
            return int(sent)

        def is_foreground(self, hwnd):
            root = user32.GetAncestor(hwnd, 2) or hwnd
            return user32.GetForegroundWindow() == root

        def activate(self, hwnd):
            user32.SetForegroundWindow(user32.GetAncestor(hwnd, 2) or hwnd)
            return self.is_foreground(hwnd)

        def keyboard(self, events):
            arr = (INPUT * len(events))()
            for i, (vk, scan, flags) in enumerate(events):
                arr[i] = INPUT(1, _U(ki=KEYBDINPUT(vk, scan, flags, 0, 0)))
            return int(physical_call(lambda: user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))))

    return _Real()


class WindowsCursorInput:
    """Adaptador de entrada. Passe `_backend` nos testes (registra chamadas e
    devolve o nº aceito); em produção Windows o backend real é lazy."""

    def __init__(self, *, press_s=DEFAULT_PRESS_S, clock=time.monotonic,
                 sleep=time.sleep, _backend=None):
        self.press_s = float(press_s)
        self._clock = clock
        self._sleep = sleep
        self._backend = _backend

    @property
    def backend(self):
        if self._backend is None:
            self._backend = _build_real_backend()
        return self._backend

    def virtual_bounds(self):
        return self.backend.virtual_bounds()

    def cursor_pos(self):
        return self.backend.get_cursor_pos()

    def is_foreground(self, hwnd):
        return self.backend.is_foreground(hwnd)

    def activate_window(self, hwnd):
        return self.backend.activate(hwnd)

    def write_amount(self, text, *, cancel_check=None):
        """Numeric BB field only. Ctrl is released even if SelectAll fails."""
        if not re.fullmatch(r'\d+(?:[.,]\d+)?', text or '') or len(text) > 20:
            raise CursorInputError('INVALID_NUMERIC_ENTRY')
        accepted, requested, ctrl_attempted = 0, 0, False
        try:
            if cancel_check and cancel_check():
                return dict(ok=False, reason='CANCELLED_BEFORE_TYPING', accepted=0)
            events = [(0x11, 0, 0), (0x41, 0, 0), (0x41, 0, 2), (0x11, 0, 2)]
            requested += 4
            ctrl_attempted = True
            n = self.backend.keyboard(events)
            accepted += n
            if n != 4:
                return dict(ok=False, reason='SELECT_ALL_NOT_ACCEPTED', accepted=accepted)
            for ch in text:
                if cancel_check and cancel_check():
                    return dict(ok=False, reason='CANCELLED_DURING_TYPING', accepted=accepted)
                requested += 2
                n = self.backend.keyboard([(0, ord(ch), 4), (0, ord(ch), 6)])
                accepted += n
                if n != 2:
                    return dict(ok=False, reason='TEXT_INPUT_NOT_ACCEPTED', accepted=accepted)
            return dict(ok=True, accepted=accepted, requested=requested)
        finally:
            if ctrl_attempted:
                self.backend.keyboard([(0x11, 0, 2)])

    def normalize_abs(self, x, y, bounds=None):
        """(nx, ny) em 0..65535 sobre o desktop virtual. Coords negativas OK."""
        bx, by, bw, bh = bounds or self.virtual_bounds()
        bw = max(bw - 1, 1)
        bh = max(bh - 1, 1)
        nx = int(round((float(x) - bx) * 65535.0 / bw))
        ny = int(round((float(y) - by) * 65535.0 / bh))
        return (max(0, min(65535, nx)), max(0, min(65535, ny)))

    def move_to(self, x, y, bounds=None):
        """Move absoluto para (x,y) físico. Retorna quantos eventos foram aceitos."""
        nx, ny = self.normalize_abs(x, y, bounds)
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        accepted = self.backend.send([flags], abs_xy=(nx, ny))
        return dict(requested=1, accepted=accepted, norm=(nx, ny))

    def drag(self, x0, y0, x1, y1, *, bounds=None, steps=14, settle_s=0.05):
        """Arrasta: move a (x0,y0) → LEFTDOWN → move suave até (x1,y1) → LEFTUP.
        Para operar a BARRA de aposta (slider) do painel de aumento. Soltura
        GARANTIDA (try/finally). Retorna o relato de eventos."""
        report = dict(moved_start=self.move_to(x0, y0, bounds), down_accepted=0,
                      up_accepted=0, released=False, steps=steps)
        down_sent = False
        try:
            if settle_s > 0:
                self._sleep(settle_s)
            report['down_accepted'] = self.backend.send([MOUSEEVENTF_LEFTDOWN])
            down_sent = True
            if settle_s > 0:
                self._sleep(settle_s)
            n = max(1, int(steps))
            for i in range(1, n + 1):
                xi = x0 + (x1 - x0) * i / n
                yi = y0 + (y1 - y0) * i / n
                self.move_to(xi, yi, bounds)
                self._sleep(0.012)
            self.move_to(x1, y1, bounds)        # ponto final exato
            if settle_s > 0:
                self._sleep(settle_s)
        finally:
            if down_sent:
                report['up_accepted'] = self.backend.send([MOUSEEVENTF_LEFTUP])
                report['released'] = report['up_accepted'] >= 1
        return report

    def click_once(self, x=None, y=None, *, bounds=None, hold_s=None):
        """Clique ÚNICO na posição atual ou em (x,y): move (se dado) → down → up,
        com soltura GARANTIDA. Retorna o relato de eventos enviados/aceitos."""
        hold = self.press_s if hold_s is None else float(hold_s)
        report = dict(moved=None, down_accepted=0, up_accepted=0, released=False)
        if x is not None and y is not None:
            report['moved'] = self.move_to(x, y, bounds)
        down_sent = False
        try:
            report['down_accepted'] = self.backend.send([MOUSEEVENTF_LEFTDOWN])
            down_sent = True
            if hold > 0:
                self._sleep(hold)
        finally:
            if down_sent:
                # Soltura só é CONFIRMADA se o sistema aceitou o mouse-up; aceitar
                # ≠ garantir, mas up_accepted=0 significa botão possivelmente preso.
                report['up_accepted'] = self.backend.send([MOUSEEVENTF_LEFTUP])
                report['released'] = report['up_accepted'] >= 1
        return report
