"""Adaptador de TECLADO do Windows via SendInput (KEYBDINPUT), espelhando a
filosofia do cursor_input_win: SÓ envia eventos e RELATA quantos o sistema aceitou
(aceitação ≠ efeito na app). NÃO decide o que digitar e NÃO gateia — isso é do
chamador, atrás do BotControl. Usa KEYEVENTF_UNICODE: digita o caractere direto,
independente do layout do teclado. win32 é lazy (importa no lab Linux; o backend
real só é construído no uso, ou injetado nos testes).

AÇÃO EM CONTA REAL: use somente atrás do gate (execution_allowed). Serve a rota de
BUSCA de clube (clica a lupa -> digita o nome -> seleciona), ver [[nvt-club-switcher]].
"""
import time

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1

# virtual-key codes de teclas especiais (não-Unicode) para press_key
VK = {'ENTER': 0x0D, 'BACKSPACE': 0x08, 'ESC': 0x1B, 'TAB': 0x09, 'DELETE': 0x2E}


class KeyboardInputError(RuntimeError):
    pass


def _build_real_backend():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                    ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                    ('dwExtraInfo', ULONG_PTR)]

    class _U(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [('type', wintypes.DWORD), ('u', _U)]

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT

    class _Real:
        def send(self, events):
            """events: lista de (wVk, wScan, dwFlags). Retorna nº aceito."""
            n = len(events)
            arr = (INPUT * n)()
            for i, (wVk, wScan, flags) in enumerate(events):
                arr[i] = INPUT(INPUT_KEYBOARD, _U(KEYBDINPUT(wVk, wScan, flags, 0, 0)))
            return int(user32.SendInput(n, arr, ctypes.sizeof(INPUT)))

    return _Real()


class WindowsKeyboardInput:
    """Adaptador de teclado. Passe `_backend` nos testes (registra e devolve o nº
    aceito); em produção Windows o backend real é lazy."""

    def __init__(self, *, sleep=time.sleep, key_s=0.012, _backend=None):
        self._sleep = sleep
        self._key_s = float(key_s)
        self._backend = _backend

    @property
    def backend(self):
        if self._backend is None:
            self._backend = _build_real_backend()
        return self._backend

    def type_text(self, text):
        """Digita `text` caractere a caractere (Unicode: down+up por char). Devolve
        dict(requested, accepted). Soltura de cada tecla sempre enviada."""
        req, acc = 0, 0
        for ch in str(text):
            code = ord(ch)
            acc += self.backend.send([(0, code, KEYEVENTF_UNICODE),
                                      (0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)])
            req += 2
            if self._key_s > 0:
                self._sleep(self._key_s)
        return dict(requested=req, accepted=acc)

    def press_key(self, name):
        """Pressiona uma tecla especial (ENTER/BACKSPACE/ESC/TAB/DELETE)."""
        vk = VK.get(str(name).upper())
        if vk is None:
            raise ValueError('tecla desconhecida: %r' % name)
        acc = self.backend.send([(vk, 0, 0), (vk, 0, KEYEVENTF_KEYUP)])
        return dict(requested=2, accepted=acc)

    def clear_field(self, n=40):
        """Limpa um campo com N backspaces (não assume Ctrl+A). Devolve accepted."""
        acc = 0
        for _ in range(max(0, int(n))):
            acc += self.backend.send([(VK['BACKSPACE'], 0, 0),
                                      (VK['BACKSPACE'], 0, KEYEVENTF_KEYUP)])
            if self._key_s > 0:
                self._sleep(self._key_s)
        return dict(accepted=acc)
