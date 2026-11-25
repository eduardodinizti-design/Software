"""LOCK de INSTÂNCIA ÚNICA por cliente de poker — impede DOIS hooks Frida no MESMO
processo ao mesmo tempo.

Motivo (Eduardo 21/11): injeção dupla (dois SSL_read/Frida no mesmo cliente) é o
suspeito nº1 dos crashes em clientes 32-bit V8/Cocos frágeis como a Suprema
(ver memória guardião de crashes). Hoje vários scripts anexam na Suprema
(capturar_suprema_net, validar_suprema_live, assistir_suprema, diags); se dois
rodarem juntos, injetam por cima um do outro. Este lock RECUSA o 2º na hora.

Mecanismo:
- PRIMÁRIO (Windows): named mutex `Global\\nvt_client_<key>`. O SO libera o mutex
  automaticamente quando o processo dono morre, então NUNCA fica preso/stale — mesmo
  se o dono crashar. É a verdade do lock.
- ESPELHO: lockfile `logs/locks/<key>.lock` com pid/dono/hora, só p/ VISIBILIDADE
  (dizer QUEM está segurando) e diagnóstico. Tolerante a stale (checa se o pid vive).

Uso:
    from client_lock import ClientLock, ClientBusy
    lock = ClientLock("SupremaPoker.exe")
    lock.acquire()          # levanta ClientBusy se já houver dono
    try:
        ... anexa Frida ...
    finally:
        lock.release()
    # ou: with ClientLock("SupremaPoker.exe"): ...
"""
from __future__ import annotations

import os
import sys
import time

_LOCKDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "locks")
_ERROR_ALREADY_EXISTS = 183


class ClientBusy(RuntimeError):
    """Levantado quando o cliente já tem um dono (outro hook Frida ativo)."""


def _safe(s):
    out = "".join(c if c.isalnum() else "_" for c in str(s)).strip("_").lower()
    return out or "client"


def _pid_alive(pid):
    try:
        import psutil
        return psutil.pid_exists(int(pid))
    except Exception:
        return True   # na dúvida, trata como vivo (lockfile é só informativo)


class ClientLock:
    def __init__(self, client_key, owner=None):
        self.key = _safe(client_key)
        self.owner = owner or os.path.basename(sys.argv[0] or "python")
        self.path = os.path.join(_LOCKDIR, self.key + ".lock")
        self._mutex = None
        self.held = False

    # ------------------------------------------------------------------
    def _acquire_mutex(self):
        """True = conseguimos o mutex (ou não é Windows). False = já existe dono."""
        if os.name != "nt":
            return True
        try:
            import ctypes
            from ctypes import wintypes
            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.CreateMutexW.restype = wintypes.HANDLE
            k.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            name = "Global\\nvt_client_" + self.key
            h = k.CreateMutexW(None, False, name)
            err = ctypes.get_last_error()
            if not h:
                return True   # não deu p/ criar mutex -> não bloqueia (cai no lockfile)
            if err == _ERROR_ALREADY_EXISTS:
                k.CloseHandle(h)   # somos o perdedor: não seguramos handle
                return False
            self._mutex = h       # somos o dono: mantém o handle vivo até release()
            return True
        except Exception:
            return True           # qualquer falha no mutex -> não bloqueia

    def _release_mutex(self):
        if self._mutex and os.name == "nt":
            try:
                import ctypes
                ctypes.WinDLL("kernel32").CloseHandle(self._mutex)
            except Exception:
                pass
        self._mutex = None

    def _read_holder(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return "desconhecido"

    def _write_lockfile(self):
        try:
            os.makedirs(_LOCKDIR, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("pid=%d owner=%s ts=%s" % (
                    os.getpid(), self.owner, time.strftime("%Y-%m-%d %H:%M:%S")))
        except Exception:
            pass

    # ------------------------------------------------------------------
    def acquire(self):
        """Toma o lock. Levanta ClientBusy se o cliente já tem dono vivo."""
        if not self._acquire_mutex():
            raise ClientBusy("cliente '%s' já tem um hook ativo (dono: %s)" % (
                self.key, self._read_holder()))
        self._write_lockfile()
        self.held = True
        return self

    def release(self):
        if not self.held:
            return
        self.held = False
        self._release_mutex()
        # só remove o lockfile se for NOSSO (não apaga o de outro dono)
        try:
            holder = self._read_holder()
            if ("pid=%d" % os.getpid()) in holder:
                os.remove(self.path)
        except Exception:
            pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False
