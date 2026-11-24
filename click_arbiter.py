"""ÁRBITRO DE CLIQUE cross-process (Eduardo 24/11, multi-plataforma): com Suprema E PPPoker jogando ao
MESMO tempo, os dois clicam por SendInput no MESMO cursor físico. Sem coordenação, clicam juntos e o
cursor é arrancado de uma janela pra outra -> misclick. Este árbitro é um LOCK GLOBAL (named mutex do
Windows, por sessão) que SERIALIZA todo clique físico entre os processos: só UM clica por vez; o outro
espera até `timeout_s` e, se não conseguir, PULA a ação (ClickBusy) em vez de travar ou colidir — poker
dá 10-20s pra agir, então esperar 1-3s por um clique é inofensivo.

Uso (nos dois lados — worker de clique da Suprema e operar_mesa do PPPoker):
    from click_arbiter import click_lock, ClickBusy
    try:
        with click_lock():
            C.execute(...)            # a sequência de clique inteira, exclusiva no cursor
    except ClickBusy:
        ...                           # outra plataforma estava clicando -> pula (não força)

Injeção p/ teste: `click_lock(_impl=...)` aceita um gerenciador de contexto alternativo (sem win32).
"""
from __future__ import annotations

import contextlib

MUTEX_NAME = "NVT_CLICK_ARBITER"      # por SESSÃO (sem 'Global\\'): serve p/ processos do mesmo usuário


class ClickBusy(Exception):
    """O cursor está ocupado por outra plataforma e não liberou dentro do timeout."""


@contextlib.contextmanager
def _win32_lock(timeout_s):
    import win32api
    import win32event
    h = win32event.CreateMutex(None, False, MUTEX_NAME)
    try:
        r = win32event.WaitForSingleObject(h, int(max(0.0, timeout_s) * 1000))
        # WAIT_OBJECT_0 = adquirido; WAIT_ABANDONED = adquirido (dono anterior morreu segurando) -> ok.
        if r not in (win32event.WAIT_OBJECT_0, win32event.WAIT_ABANDONED):
            raise ClickBusy("cursor ocupado por outra plataforma (timeout %.1fs)" % timeout_s)
        try:
            yield
        finally:
            with contextlib.suppress(Exception):
                win32event.ReleaseMutex(h)   # deve ser liberado pela MESMA thread que adquiriu
    finally:
        with contextlib.suppress(Exception):
            win32api.CloseHandle(h)


@contextlib.contextmanager
def click_lock(timeout_s=4.0, _impl=None):
    """Gerenciador de contexto: adquire o lock GLOBAL de clique e libera ao sair. ClickBusy se não
    conseguir em `timeout_s`. `_impl` (teste) substitui o backend win32 por outro context manager
    (recebe timeout_s). Se o win32 não existir (não-Windows/sem pywin32), degrada p/ SEM lock (permite
    clicar) — melhor clicar sozinho do que travar; o árbitro só importa quando as DUAS plataformas rodam."""
    if _impl is not None:
        with _impl(timeout_s):
            yield
        return
    try:
        import win32event  # noqa: F401
    except Exception:
        yield                 # sem win32 -> sem arbitragem (degrada seguro; 1 plataforma não precisa)
        return
    with _win32_lock(timeout_s):
        yield
