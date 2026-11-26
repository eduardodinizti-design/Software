"""ÁRBITRO DE CURSOR GLOBAL (Eduardo 25/11) — serializa TODO clique físico de TODAS as plataformas.

PROBLEMA: Suprema e PPPoker (e, no futuro, X-Poker) jogam ao MESMO tempo e cada um clica movendo o
CURSOR FÍSICO por SendInput. Dois agentes armados ao mesmo tempo BRIGAM pelo cursor — um move a seta
enquanto o outro está no meio de um clique -> misclick / clique perdido. A LEI é clique SEMPRE no
cursor físico visível (SendInput), nunca background/PostMessage; então a única saída é SERIALIZAR:
só UM clique físico por vez, e o cursor nunca é arrancado no meio de uma ação.

ESTE MÓDULO é o serializador único. Constrói EM CIMA de `click_arbiter.click_lock` (mutex nomeado do
Windows = coordenação CROSS-PROCESS entre os processos dos agentes) e acrescenta o que faltava:

  1) Serialização IN-PROCESS JUSTA (FIFO) que funciona SEM win32 (lab/offline e multi-mesa no mesmo
     processo). `click_lock` sozinho degrada p/ no-op sem win32, então não daria p/ testar nem p/
     coordenar várias mesas dentro de um mesmo agente — o portão FIFO daqui resolve isso.
  2) Uma API de submissão limpa — `arbiter.submit(plataforma, acao_fn)` — que roda `acao_fn` como
     UNIDADE ATÔMICA segurando OS DOIS trincos (o portão in-process + o mutex cross-process). Enquanto
     `acao_fn` roda, nenhuma outra plataforma manda SendInput.
  3) Um ADAPTADOR DE CURSOR ARBITRADO (`make_arbitrated_adapter`) que embrulha um adapter estilo
     `WindowsCursorInput` (move_to/click_once/drag) de modo que CADA chamada passe pelo árbitro — assim
     um agente que clica por adapter (PPPoker, via `build_live_execute(adapter=...)`) fica arbitrado
     SEM NENHUMA edição no agente.

Camadas de serialização e por que DUAS:
  - IN-PROCESS (threading, FIFO): ordena mesas/plataformas que rodam no MESMO processo e garante justiça
    (o mutex do Windows NÃO é FIFO). Funciona em qualquer OS -> é o que os testes offline exercitam.
  - CROSS-PROCESS (click_lock / mutex nomeado): ordena os PROCESSOS dos agentes (Suprema num processo,
    PPPoker noutro). É o trinco que de fato impede dois SendInput simultâneos de processos diferentes.
  Os dois são segurados juntos em `submit`. Em produção o mutex faz o trabalho pesado; no lab o portão
  FIFO faz. Se o cursor estiver ocupado além do timeout, `submit` NÃO força: levanta `CursorBusy`
  (o chamador PULA o clique — poker dá 10-20s p/ agir, pular 1 clique é inofensivo; forçar = misclick).

Nada aqui clica sozinho nem arma nada: é só o trilho por onde os cliques passam, um de cada vez.
"""
from __future__ import annotations

import collections
import contextlib
import threading
import time

from click_arbiter import ClickBusy, click_lock

__all__ = [
    "CursorBusy",
    "CursorArbiter",
    "make_arbitrated_adapter",
    "default_arbiter",
]


class CursorBusy(Exception):
    """O cursor físico está ocupado (por outra mesa/plataforma) e não liberou dentro do timeout.
    O chamador deve PULAR a ação — nunca forçar (forçar = cursor arrancado no meio = misclick)."""


class _Ticket:
    """Senha de fila FIFO. `cancelled` marca uma espera que desistiu (timeout) p/ a fila a descartar."""
    __slots__ = ("cancelled",)

    def __init__(self):
        self.cancelled = False


class CursorArbiter:
    """Serializador único de clique físico. Toda intenção de clique de TODA plataforma passa por
    `submit`, que roda a ação segurando o portão FIFO in-process + o mutex cross-process do cursor.

    Parâmetros:
      lock_timeout_s  — quanto esperar pelo MUTEX cross-process antes de desistir (ClickBusy->CursorBusy).
      submit_timeout_s— teto TOTAL de espera na fila in-process antes de desistir (CursorBusy).
      _click_lock     — injeção p/ teste: um context manager que recebe (timeout_s=). Default = o
                        `click_lock` real (mutex nomeado do Windows). Nos testes offline passamos um
                        passthrough (ou um que levanta ClickBusy) p/ exercitar sem win32.
      clock           — relógio monotônico (injeção p/ teste).
    """

    def __init__(self, *, lock_timeout_s=4.0, submit_timeout_s=8.0, _click_lock=None,
                 clock=time.monotonic):
        self._lock_timeout_s = float(lock_timeout_s)
        self._submit_timeout_s = float(submit_timeout_s)
        self._click_lock = _click_lock if _click_lock is not None else click_lock
        self._clock = clock
        self._cond = threading.Condition()
        self._queue = collections.deque()   # tickets FIFO aguardando o portão
        self._busy = False                   # True enquanto alguém segura o portão (clique em curso)
        # telemetria (apenas leitura; ajuda a diagnosticar briga de cursor ao vivo)
        self.stats = {
            "submitted": 0, "executed": 0, "busy_skips": 0,
            "by_platform": collections.defaultdict(lambda: {"ok": 0, "busy": 0}),
            "max_wait_s": 0.0,
        }

    # ---- fila FIFO (in-process) --------------------------------------------------
    def _head_live(self):
        """Descarta tickets cancelados do início e devolve o 1º ticket vivo (ou None)."""
        while self._queue and self._queue[0].cancelled:
            self._queue.popleft()
        return self._queue[0] if self._queue else None

    def _acquire_gate(self, deadline):
        """Entra na fila e espera a vez (FIFO) com o portão livre. True se adquiriu; False se estourou
        o prazo (o ticket é marcado cancelado p/ a fila o pular). Deve rodar sob self._cond."""
        t = _Ticket()
        self._queue.append(t)
        try:
            while True:
                if not self._busy and self._head_live() is t:
                    self._queue.popleft()      # sou a cabeça viva e o portão está livre -> entro
                    self._busy = True
                    return True
                remaining = deadline - self._clock()
                if remaining <= 0:
                    t.cancelled = True
                    self._cond.notify_all()    # se eu era a cabeça, deixo os outros reavaliarem
                    return False
                self._cond.wait(timeout=remaining)
        except BaseException:
            t.cancelled = True
            self._cond.notify_all()
            raise

    def _release_gate(self):
        with self._cond:
            self._busy = False
            self._cond.notify_all()

    # ---- API pública -------------------------------------------------------------
    def submit(self, plataforma, acao_fn, *, timeout_s=None, lock_timeout_s=None):
        """Roda `acao_fn()` como UNIDADE ATÔMICA de cursor: adquire o portão FIFO in-process, depois o
        mutex cross-process, executa e devolve o retorno de `acao_fn`. Se o cursor não liberar a tempo,
        NÃO força — levanta `CursorBusy` (o chamador deve pular a ação).

        `plataforma` é só um rótulo p/ telemetria/log (ex.: "SUPREMA", "PPPOKER")."""
        submit_to = self._submit_timeout_s if timeout_s is None else float(timeout_s)
        lock_to = self._lock_timeout_s if lock_timeout_s is None else float(lock_timeout_s)
        t0 = self._clock()
        deadline = t0 + submit_to
        with self._cond:
            self.stats["submitted"] += 1
            got = self._acquire_gate(deadline)
        if not got:
            self._note_busy(plataforma)
            raise CursorBusy("cursor ocupado: fila não liberou em %.1fs [%s]" % (submit_to, plataforma))
        waited = self._clock() - t0
        if waited > self.stats["max_wait_s"]:
            self.stats["max_wait_s"] = waited
        try:
            # portão in-process na mão: agora o mutex CROSS-PROCESS, segurando ambos durante a ação.
            try:
                with self._click_lock(timeout_s=lock_to):
                    result = acao_fn()
            except ClickBusy as e:
                self._note_busy(plataforma)
                raise CursorBusy("cursor ocupado por outro PROCESSO [%s]: %s" % (plataforma, e)) from None
            self.stats["executed"] += 1
            self.stats["by_platform"][plataforma]["ok"] += 1
            return result
        finally:
            self._release_gate()

    def _note_busy(self, plataforma):
        self.stats["busy_skips"] += 1
        self.stats["by_platform"][plataforma]["busy"] += 1


# Instância de PROCESSO compartilhada: todas as mesas/plataformas do MESMO processo devem usar ESTA,
# p/ dividir o mesmo portão FIFO. (Entre processos, o compartilhamento é automático via mutex nomeado.)
_DEFAULT = None
_DEFAULT_LOCK = threading.Lock()


def default_arbiter():
    """Devolve (criando na 1ª vez) o árbitro único do processo. Use este em código de produção p/ que
    todas as mesas compartilhem a mesma fila justa."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = CursorArbiter()
        return _DEFAULT


# =============================================================================================
# ADAPTADOR DE CURSOR ARBITRADO — embrulha um adapter move_to/click_once/drag (ex.: WindowsCursorInput)
# p/ que CADA ação física passe pelo árbitro. Permite arbitrar um agente que clica por adapter (PPPoker)
# SEM editar o agente: basta injetar este wrapper onde o adapter é passado.
# =============================================================================================
_SKIP_CLICK = {"skipped": True, "reason": "cursor ocupado (outra plataforma)",
               "moved": None, "down_accepted": 0, "up_accepted": 0, "released": False}
_SKIP_MOVE = {"skipped": True, "reason": "cursor ocupado (outra plataforma)",
              "requested": 1, "accepted": 0, "norm": None}
_SKIP_DRAG = {"skipped": True, "reason": "cursor ocupado (outra plataforma)",
              "down_accepted": 0, "up_accepted": 0, "released": False}


class _ArbitratedAdapter:
    """Delega a um adapter real (move_to/click_once/drag), mas CADA movimento/clique/arrasto roda dentro
    de `arbiter.submit` — ou seja, segurando o trinco GLOBAL do cursor. Leituras (bounds, cursor_pos,
    normalize_abs) passam direto (não mexem no cursor).

    Por que CADA chamada e não só o par "move+click": `click_once(x,y)` e `drag(...)` do adapter já
    RE-MOVEM ao alvo DENTRO da própria chamada; então cada um, sozinho e sob o lock, é uma unidade
    atômica AUTO-CORRIGÍVEL — não importa o que outra plataforma tenha feito com o cursor antes, o
    clique ainda reposiciona e acerta o alvo. `move_to` solto (pré-clique cosmético de alguns clickers)
    também é arbitrado p/ NUNCA existir um SendInput fora do árbitro; no pior caso é um salto a mais de
    cursor, inofensivo. Se o cursor estiver ocupado, devolve um dict de SKIP (não levanta) — o clicker
    simplesmente não clica, o que o poker tolera (a janela de ação é longa)."""

    def __init__(self, inner, arbiter, plataforma, *, timeout_s=None, lock_timeout_s=None):
        self._inner = inner
        self._arb = arbiter
        self._plat = plataforma
        self._to = timeout_s
        self._lto = lock_timeout_s

    # --- leituras (não tocam o cursor) ---
    def virtual_bounds(self, *a, **k):
        return self._inner.virtual_bounds(*a, **k)

    def cursor_pos(self, *a, **k):
        return self._inner.cursor_pos(*a, **k)

    def normalize_abs(self, *a, **k):
        return self._inner.normalize_abs(*a, **k)

    # --- ações físicas (arbitradas) ---
    def _run(self, fn, skip):
        try:
            return self._arb.submit(self._plat, fn, timeout_s=self._to, lock_timeout_s=self._lto)
        except CursorBusy:
            return dict(skip)

    def move_to(self, *a, **k):
        return self._run(lambda: self._inner.move_to(*a, **k), _SKIP_MOVE)

    def click_once(self, *a, **k):
        return self._run(lambda: self._inner.click_once(*a, **k), _SKIP_CLICK)

    def drag(self, *a, **k):
        return self._run(lambda: self._inner.drag(*a, **k), _SKIP_DRAG)

    # qualquer outro atributo (press_s, etc.) cai no adapter real
    def __getattr__(self, name):
        return getattr(self._inner, name)


def make_arbitrated_adapter(real_adapter, arbiter=None, plataforma="?", *,
                            timeout_s=None, lock_timeout_s=None):
    """Embrulha `real_adapter` (estilo WindowsCursorInput) num adaptador cujas ações de cursor passam
    TODAS pelo árbitro. Se `arbiter` for None, usa o árbitro único do processo (`default_arbiter()`).

    Ex. (PPPoker, no ponto onde o adapter é montado):
        from cursor_input_win import WindowsCursorInput
        from cursor_arbiter import make_arbitrated_adapter
        adapter = make_arbitrated_adapter(WindowsCursorInput(), plataforma="PPPOKER")
        execute = build_live_execute(hwnd, control=control, adapter=adapter, ...)
    """
    arb = arbiter if arbiter is not None else default_arbiter()
    return _ArbitratedAdapter(real_adapter, arb, plataforma,
                              timeout_s=timeout_s, lock_timeout_s=lock_timeout_s)


@contextlib.contextmanager
def cursor_turn(plataforma, arbiter=None, *, timeout_s=None, lock_timeout_s=None):
    """Açúcar p/ quem já tem a sequência de clique num bloco (ex.: o worker da Suprema poderia trocar
    `with click_lock(): C.execute(...)` por `with cursor_turn("SUPREMA"): C.execute(...)` e ganhar a
    fila justa in-process além do mutex). Levanta CursorBusy se o cursor não liberar."""
    arb = arbiter if arbiter is not None else default_arbiter()
    # Segura o portão FIFO + o mutex cross-process durante o corpo do `with`; libera ao sair.
    with _TurnGate(arb, plataforma, timeout_s, lock_timeout_s):
        yield


class _TurnGate:
    """Suporte do cursor_turn: segura o portão+mutex durante o corpo do `with`."""

    def __init__(self, arb, plataforma, timeout_s, lock_timeout_s):
        self._arb = arb
        self._plat = plataforma
        self._to = timeout_s
        self._lto = lock_timeout_s
        self._release = None

    def __enter__(self):
        submit_to = self._arb._submit_timeout_s if self._to is None else float(self._to)
        lock_to = self._arb._lock_timeout_s if self._lto is None else float(self._lto)
        deadline = self._arb._clock() + submit_to
        with self._arb._cond:
            self._arb.stats["submitted"] += 1
            got = self._arb._acquire_gate(deadline)
        if not got:
            self._arb._note_busy(self._plat)
            raise CursorBusy("cursor ocupado: fila não liberou [%s]" % self._plat)
        try:
            cm = self._arb._click_lock(timeout_s=lock_to)
            cm.__enter__()
        except ClickBusy as e:
            self._arb._release_gate()
            self._arb._note_busy(self._plat)
            raise CursorBusy("cursor ocupado por outro PROCESSO [%s]: %s" % (self._plat, e)) from None
        self._cm = cm
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._cm.__exit__(exc_type, exc, tb)
        finally:
            self._arb.stats["executed"] += 1
            self._arb.stats["by_platform"][self._plat]["ok"] += 1
            self._arb._release_gate()
        return False
