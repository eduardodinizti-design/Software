"""Testes OFFLINE do árbitro de cursor global + launcher único. Sem win32, sem abrir processo, sem
clicar: tudo em threads no MESMO processo, com backend de cursor e click_lock INJETADOS. O ponto
central: cliques CONCORRENTES de 2 plataformas SERIALIZAM em execuções NÃO-sobrepostas."""
from __future__ import annotations

import contextlib
import threading
import time

import pytest

from cursor_arbiter import (CursorArbiter, CursorBusy, make_arbitrated_adapter, cursor_turn)
from click_arbiter import ClickBusy


# ------------------------------------------------------------------ utilidades de teste
class OverlapRecorder:
    """Registra [entrada, saída] de cada ação e detecta sobreposição (= dois cliques ao mesmo tempo)."""
    def __init__(self):
        self.intervals = []
        self._lock = threading.Lock()
        self.max_concurrent = 0
        self._active = 0

    @contextlib.contextmanager
    def action(self, label):
        with self._lock:
            self._active += 1
            self.max_concurrent = max(self.max_concurrent, self._active)
        t0 = time.monotonic()
        try:
            time.sleep(0.01)                 # janela em que uma sobreposição apareceria
            yield
        finally:
            t1 = time.monotonic()
            with self._lock:
                self._active -= 1
                self.intervals.append((t0, t1, label))

    def has_overlap(self):
        iv = sorted(self.intervals)
        for i in range(1, len(iv)):
            if iv[i][0] < iv[i - 1][1] - 1e-9:   # começou antes do anterior terminar
                return True
        return False


@contextlib.contextmanager
def _passthrough_lock(timeout_s=0.0):
    """click_lock falso: sem win32, não serializa nada sozinho (prova que a serialização vem do árbitro)."""
    yield


# ------------------------------------------------------------------ serialização central
def test_duas_plataformas_serializam_sem_sobreposicao():
    arb = CursorArbiter(_click_lock=_passthrough_lock, submit_timeout_s=30.0)
    rec = OverlapRecorder()

    def faz_cliques(plataforma, n):
        for i in range(n):
            arb.submit(plataforma, lambda: _acao(rec, "%s#%d" % (plataforma, i)))

    def _acao(rec, label):
        with rec.action(label):
            return "ok"

    t1 = threading.Thread(target=faz_cliques, args=("SUPREMA", 20))
    t2 = threading.Thread(target=faz_cliques, args=("PPPOKER", 20))
    t1.start(); t2.start(); t1.join(); t2.join()

    assert len(rec.intervals) == 40
    assert not rec.has_overlap(), "cliques de plataformas diferentes se sobrepuseram!"
    assert rec.max_concurrent == 1, "mais de uma ação de cursor ativa ao mesmo tempo"
    assert arb.stats["executed"] == 40


def test_submit_devolve_resultado_da_acao():
    arb = CursorArbiter(_click_lock=_passthrough_lock)
    assert arb.submit("SUPREMA", lambda: 42) == 42


def test_click_busy_cross_process_vira_cursor_busy():
    @contextlib.contextmanager
    def ocupado(timeout_s=0.0):
        raise ClickBusy("outro processo segura o mutex")
        yield  # pragma: no cover

    arb = CursorArbiter(_click_lock=ocupado)
    with pytest.raises(CursorBusy):
        arb.submit("PPPOKER", lambda: "nao deveria rodar")
    assert arb.stats["busy_skips"] == 1
    assert arb.stats["executed"] == 0


def test_fila_fifo_ordem_justa():
    """Com o portão ocupado, os que chegam depois são servidos na ORDEM de chegada (FIFO)."""
    arb = CursorArbiter(_click_lock=_passthrough_lock, submit_timeout_s=30.0)
    ordem = []
    liberar = threading.Event()
    primeiro_dentro = threading.Event()

    def bloqueador():
        def _hold():
            primeiro_dentro.set()
            liberar.wait(5.0)
            ordem.append("BLOQ")
        arb.submit("BLOQ", _hold)

    tb = threading.Thread(target=bloqueador); tb.start()
    assert primeiro_dentro.wait(2.0)

    threads = []
    for nome in ("A", "B", "C"):
        # entram enquanto o bloqueador segura o portão; FIFO deve preservar A,B,C
        t = threading.Thread(target=lambda n=nome: arb.submit(n, lambda n=n: ordem.append(n)))
        threads.append(t); t.start()
        time.sleep(0.05)              # garante ordem de chegada A->B->C

    time.sleep(0.1)
    liberar.set()
    tb.join(); [t.join() for t in threads]

    assert ordem[0] == "BLOQ"
    assert ordem[1:] == ["A", "B", "C"], "fila não respeitou a ordem de chegada (FIFO): %s" % ordem


def test_timeout_na_fila_levanta_cursor_busy_e_nao_trava_os_outros():
    arb = CursorArbiter(_click_lock=_passthrough_lock)
    dentro = threading.Event()
    solta = threading.Event()

    def segura():
        arb.submit("HOLDER", lambda: (dentro.set(), solta.wait(5.0)))

    th = threading.Thread(target=segura); th.start()
    assert dentro.wait(2.0)

    # tenta com timeout curto enquanto o portão está ocupado -> CursorBusy
    with pytest.raises(CursorBusy):
        arb.submit("TARDE", lambda: "x", timeout_s=0.2)

    solta.set(); th.join()
    # após liberar, uma nova submissão PASSA (o desistente não deixou a fila travada)
    assert arb.submit("DEPOIS", lambda: "ok") == "ok"


# ------------------------------------------------------------------ adapter arbitrado (caminho PPPoker)
class FakeBackend:
    """Backend de cursor estilo WindowsCursorInput._build_real_backend, registrando eventos num recorder."""
    def __init__(self, rec):
        self.rec = rec
        self.pos = (0, 0)

    def virtual_bounds(self):
        return (0, 0, 1920, 1080)

    def get_cursor_pos(self):
        return self.pos

    def send(self, flags_list, abs_xy=None):
        # um "clique" físico ocupa a janela do recorder -> sobreposição apareceria aqui
        with self.rec.action("send"):
            if abs_xy is not None:
                self.pos = abs_xy
        return len(flags_list)


def test_adapter_arbitrado_serializa_cliques_de_duas_plataformas():
    from cursor_input_win import WindowsCursorInput
    rec = OverlapRecorder()
    arb = CursorArbiter(_click_lock=_passthrough_lock, submit_timeout_s=30.0)

    def novo_adapter(plat):
        real = WindowsCursorInput(press_s=0.0, sleep=lambda s: None, _backend=FakeBackend(rec))
        return make_arbitrated_adapter(real, arb, plataforma=plat)

    a_sup = novo_adapter("SUPREMA")
    a_ppp = novo_adapter("PPPOKER")

    def clica(adapter, n):
        for i in range(15):
            adapter.click_once(100 + i, 200 + i)

    t1 = threading.Thread(target=clica, args=(a_sup, 15))
    t2 = threading.Thread(target=clica, args=(a_ppp, 15))
    t1.start(); t2.start(); t1.join(); t2.join()

    assert not rec.has_overlap(), "SendInput de plataformas diferentes se sobrepôs!"
    assert rec.max_concurrent == 1
    assert arb.stats["executed"] >= 30   # cada click_once = ao menos uma submissão executada


def test_adapter_devolve_skip_quando_cursor_ocupado():
    @contextlib.contextmanager
    def ocupado(timeout_s=0.0):
        raise ClickBusy("mutex preso")
        yield  # pragma: no cover

    from cursor_input_win import WindowsCursorInput
    arb = CursorArbiter(_click_lock=ocupado)
    real = WindowsCursorInput(press_s=0.0, sleep=lambda s: None, _backend=FakeBackend(OverlapRecorder()))
    adapter = make_arbitrated_adapter(real, arb, plataforma="PPPOKER")
    res = adapter.click_once(10, 20)
    assert res.get("skipped") is True and res.get("released") is False


def test_leituras_passam_direto_sem_arbitro():
    from cursor_input_win import WindowsCursorInput
    arb = CursorArbiter(_click_lock=_passthrough_lock)
    real = WindowsCursorInput(_backend=FakeBackend(OverlapRecorder()))
    adapter = make_arbitrated_adapter(real, arb, plataforma="X")
    assert adapter.virtual_bounds() == (0, 0, 1920, 1080)
    assert adapter.cursor_pos() == (0, 0)
    assert arb.stats["submitted"] == 0   # leitura não entra na fila


# ------------------------------------------------------------------ cursor_turn (caminho Suprema opcional)
def test_cursor_turn_segura_e_serializa():
    arb = CursorArbiter(_click_lock=_passthrough_lock, submit_timeout_s=30.0)
    rec = OverlapRecorder()

    def trabalha(plat):
        for _ in range(10):
            with cursor_turn(plat, arb):
                with rec.action(plat):
                    pass

    t1 = threading.Thread(target=trabalha, args=("SUPREMA",))
    t2 = threading.Thread(target=trabalha, args=("PPPOKER",))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert not rec.has_overlap()
    assert rec.max_concurrent == 1


# ------------------------------------------------------------------ launcher (sem abrir processo real)
class FakeProc:
    def __init__(self, cmd):
        self.cmd = cmd
        self.pid = 4242
        self._alive = True
        self.signals = []
    def poll(self):
        return None if self._alive else 0
    def wait(self, timeout=None):
        self._alive = False
        return 0
    def send_signal(self, sig):
        self.signals.append(sig)
    def terminate(self):
        self._alive = False


def test_launcher_sobe_so_plataformas_habilitadas_e_arma():
    import iniciar_henrique as L
    criados = []
    core = L.LauncherCore(spawn=lambda cmd: criados.append(cmd) or FakeProc(cmd),
                          python_exe="python", log=lambda *a, **k: None)
    core.start_many(["suprema", "pppoker"], armed=True)
    assert len(criados) == 2
    sup = [c for c in criados if "suprema_agente.py" in " ".join(c)][0]
    ppp = [c for c in criados if "iniciar_pppoker.py" in " ".join(c)][0]   # entrada única (emitter+agente)
    assert "--armed" in sup
    assert "--armar" in ppp
    assert core.is_running("suprema") and core.is_running("pppoker")


def test_launcher_dry_nao_passa_flag_de_arme():
    import iniciar_henrique as L
    criados = []
    core = L.LauncherCore(spawn=lambda cmd: criados.append(cmd) or FakeProc(cmd),
                          python_exe="python", log=lambda *a, **k: None)
    core.start("suprema", armed=False)
    assert "--armed" not in criados[0]


def test_launcher_para_tudo_limpo():
    import iniciar_henrique as L
    procs = {}
    def spawn(cmd):
        p = FakeProc(cmd); procs[" ".join(cmd)] = p; return p
    core = L.LauncherCore(spawn=spawn, python_exe="python", log=lambda *a, **k: None)
    core.start_many(["suprema", "pppoker"], armed=False)
    core.stop_all(grace_s=0.1)
    assert core.status() == {"suprema": "parado", "pppoker": "parado"}


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
