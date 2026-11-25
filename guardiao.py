"""GUARDIÃO de clientes de poker — DETECTA queda do PPPoker / Suprema e AVISA.

Pedido do Eduardo (20/11): "os aplicativos estão caindo muito; preciso saber se é
o nosso agente ou o próprio cliente, mitigar ao máximo, e ter uma estrutura pronta
que quando cair já IDENTIFIQUE e reaja na hora."

Decisão do Eduardo: **SÓ DETECTAR + ALARME** (não reabre o cliente sozinho).

O que este guardião faz, a cada ~2s:
  1) VIGIA os processos do cliente (PPPoker.exe, SupremaPoker.exe).
  2) Na transição vivo->sumiu (crash ou fechamento), confirma com debounce
     (N leituras seguidas ausentes) pra não disparar em falso.
  3) REGISTRA a queda com a ASSINATURA WER (módulo/exceção/offset do crash) em
     logs/crashes.jsonl — é a EVIDÊNCIA que, acumulada, prova se a culpa é da
     nossa injeção (módulo `unknown`/`0xc0000409`) ou do próprio cliente.
  4) DESANEXA o nosso stack Frida de forma LIMPA (CTRL_BREAK -> unload+detach),
     pra (a) evitar o fatal-error em cascata e (b) deixar o próximo start limpo.
     Opcional via --no-stand-down.
  5) TOCA ALARME (reusa o som audível do alerta_ft) pra você assumir e reabrir.

NUNCA reabre o cliente, nunca re-registra, nunca clica. Só detecta, registra e avisa.

Uso:
    python -I guardiao.py                 # vigia PPPoker + Suprema até Ctrl+C
    python -I guardiao.py --no-stand-down # não mexe no nosso stack ao detectar queda
    python -I guardiao.py --interval 1.5  # período de verificação (default 2.0s)
    python -I guardiao.py --test          # toca o alarme de crash e sai
    python -I guardiao.py --status        # imprime o que está vivo agora e sai
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOGDIR = os.path.join(_HERE, "logs")
_CRASHLOG = os.path.join(_LOGDIR, "crashes.jsonl")

# Clientes vigiados: rótulo -> nomes de processo (lower). Fácil de estender.
CLIENTS: dict[str, tuple[str, ...]] = {
    "PPPoker": ("pppoker.exe",),
    "Suprema": ("supremapoker.exe",),
}

# Scripts do NOSSO stack a desanexar na queda (hosts Frida primeiro = CTRL_BREAK).
_FRIDA_HOSTS = ("emitir_seats", "capturar_maos")
_OTHER_BOT = ("operar_mesa", "alerta_ft", "painel.py")


# ---------------------------------------------------------------------------
# NÚCLEO PURO (sem I/O) — testável offline
# ---------------------------------------------------------------------------
@dataclass
class CrashEvent:
    client: str
    when: float                      # epoch seconds


@dataclass
class ClientMonitor:
    """Detecta transições vivo->ausente por cliente, com debounce.

    Puro: você injeta o 'present' (mapa rótulo->bool) a cada tick; ele devolve
    os CrashEvent confirmados. Não dispara para cliente que nunca apareceu
    (evita alarme antes de o jogo abrir) nem em ausências momentâneas (debounce).
    """
    confirm_ticks: int = 2           # leituras ausentes seguidas p/ confirmar queda
    _seen: set[str] = field(default_factory=set)      # já esteve vivo alguma vez
    _alive: set[str] = field(default_factory=set)     # vivo no último estado estável
    _absent_streak: dict[str, int] = field(default_factory=dict)

    def update(self, present: dict[str, bool], now: float | None = None) -> list[CrashEvent]:
        now = time.time() if now is None else now
        events: list[CrashEvent] = []
        for client, is_present in present.items():
            if is_present:
                self._seen.add(client)
                self._alive.add(client)
                self._absent_streak[client] = 0
                continue
            # ausente agora
            if client not in self._seen or client not in self._alive:
                # nunca apareceu, ou já tínhamos contabilizado a queda
                self._absent_streak[client] = 0
                continue
            streak = self._absent_streak.get(client, 0) + 1
            self._absent_streak[client] = streak
            if streak >= self.confirm_ticks:
                self._alive.discard(client)          # queda confirmada (uma vez)
                self._absent_streak[client] = 0
                events.append(CrashEvent(client=client, when=now))
        return events


# ---------------------------------------------------------------------------
# Camada Windows (I/O) — tudo guardado p/ não quebrar em teste/Linux
# ---------------------------------------------------------------------------
def list_running() -> set[str]:
    """Nomes de processo vivos (lower). psutil; fallback tasklist."""
    try:
        import psutil
    except Exception:
        psutil = None
    names: set[str] = set()
    if psutil is not None:
        for p in psutil.process_iter(["name"]):
            try:
                n = (p.info.get("name") or "").lower()
                if n:
                    names.add(n)
            except Exception:
                continue
        return names
    # fallback sem psutil
    try:
        import subprocess
        out = subprocess.check_output(["tasklist", "/fo", "csv", "/nh"],
                                      stderr=subprocess.DEVNULL).decode("latin-1", "replace")
        for line in out.splitlines():
            if line.startswith('"'):
                names.add(line.split('","')[0].strip('"').lower())
    except Exception:
        pass
    return names


def present_map() -> dict[str, bool]:
    """Para cada cliente, True se ALGUM dos seus processos está vivo agora."""
    running = list_running()
    return {label: any(proc in running for proc in procs)
            for label, procs in CLIENTS.items()}


def read_last_wer(exe_name: str, within_seconds: int = 120) -> dict | None:
    """Lê do Event Viewer (Application Error) a falha MAIS RECENTE do exe dado e
    devolve a assinatura (módulo/exceção/offset). Só Windows; None se nada."""
    if sys.platform != "win32":
        return None
    import subprocess
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$ev=Get-WinEvent -FilterHashtable @{LogName='Application';"
        "ProviderName='Application Error';StartTime=(Get-Date).AddSeconds(-%d)}|"
        "Where-Object{$_.Message -match '%s'}|Sort-Object TimeCreated -Descending|"
        "Select-Object -First 1;"
        "if($ev){$ev.Message}"
    ) % (int(within_seconds), exe_name.replace(".", "\\."))
    try:
        out = subprocess.check_output(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                                      stderr=subprocess.DEVNULL, timeout=20).decode("latin-1", "replace")
    except Exception:
        return None
    msg = out.strip()
    if not msg:
        return None
    return _parse_wer(msg)


def _parse_wer(msg: str) -> dict:
    import re
    def g(*pats):
        for p in pats:
            m = re.search(p, msg)
            if m:
                return m.group(1).strip()
        return ""
    return {
        "app": g(r"Nome do aplicativo com falha:\s*([^\r\n,]+)", r"Faulting application name:\s*([^\r\n,]+)"),
        "modulo": g(r"Nome do m[oó]dulo com falha:\s*([^\r\n,]+)", r"Faulting module name:\s*([^\r\n,]+)"),
        "excecao": g(r"C[oó]digo de exce[cç][aã]o:\s*([^\r\n]+)", r"Exception code:\s*([^\r\n]+)"),
        "offset": g(r"Deslocamento de falha:\s*([^\r\n]+)", r"Fault offset:\s*([^\r\n]+)"),
    }


def classify(wer: dict | None) -> str:
    """Palpite de culpa a partir da assinatura (heurística — a prova vem do acúmulo)."""
    if not wer:
        return "sem_registro_wer (travou/fechado/encerrado — não gerou falha clássica)"
    mod = (wer.get("modulo") or "").lower()
    exc = (wer.get("excecao") or "").lower()
    if mod in ("unknown", "") or "0xc0000409" in exc:
        return "SUSPEITA_INJECAO_OU_JIT (módulo sem DLL / fail-fast — pode ser nossa injeção OU o JIT do Unity)"
    if "ntdll" in mod:
        return "corrupcao_de_heap (ntdll) — memória corrompida no processo"
    return "falha_no_cliente (módulo próprio: %s)" % mod


def stand_down_bot_stack(log=print) -> list[int]:
    """Desanexa o NOSSO stack de forma limpa (NÃO toca no cliente). Hosts Frida
    recebem CTRL_BREAK -> unload()+detach(); o resto leva terminate. Replica a
    disciplina do iniciar_bot._shutdown pra uso standalone."""
    killed: list[int] = []
    try:
        import psutil
    except Exception:
        log("[guardiao] psutil ausente: não desanexo o stack (só aviso).")
        return killed
    import signal
    brk = getattr(signal, "CTRL_BREAK_EVENT", None)
    me = os.getpid()
    targets = []
    for p in list(psutil.process_iter(["pid", "cmdline"])):
        try:
            if p.info["pid"] == me:
                continue
            cmd = " ".join(p.info.get("cmdline") or [])
            if cmd and any(s in cmd for s in (_FRIDA_HOSTS + _OTHER_BOT)):
                targets.append((p, cmd))
        except Exception:
            continue
    # 1) hosts Frida: CTRL_BREAK (detach limpo)
    for p, cmd in targets:
        is_frida = any(s in cmd for s in _FRIDA_HOSTS)
        try:
            if is_frida and brk is not None:
                os.kill(p.info["pid"], brk)
            else:
                p.terminate()
            killed.append(p.info["pid"])
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass
    if killed:
        time.sleep(2.0)                           # tempo p/ unload()+detach()
        for p, _ in targets:
            try:
                if p.is_running():
                    p.kill()
            except Exception:
                pass
        log("[guardiao] stack desanexado/encerrado LIMPO: %s" % killed)
    return killed


def _alarme():
    """Som de CRASH (grave->agudo rápido, bem distinto do alarme de FT)."""
    try:
        sys.path.insert(0, os.path.join(_HERE, "research", "ppp_il2cpp"))
        from alerta_ft import _beeps  # type: ignore
        _beeps([(300, 120), (300, 120), (300, 220)], repeticoes=3, pausa=0.25)
    except Exception:
        try:
            import winsound
            for _ in range(3):
                winsound.MessageBeep(-1); time.sleep(0.3)
        except Exception:
            for _ in range(3):
                sys.stdout.write("\a"); sys.stdout.flush(); time.sleep(0.3)


def log_crash(ev: CrashEvent, wer: dict | None, verdict: str) -> None:
    rec = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "cliente": ev.client,
        "wer": wer,
        "veredito": verdict,
    }
    try:
        os.makedirs(_LOGDIR, exist_ok=True)
        with open(_CRASHLOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CLI / loop
# ---------------------------------------------------------------------------
def _handle_crash(ev: CrashEvent, stand_down: bool, log=print) -> None:
    exe = CLIENTS[ev.client][0]
    log("\n" + "!" * 62)
    log("[GUARDIÃO] QUEDA detectada: %s  (%s)" % (ev.client, datetime.now().strftime("%H:%M:%S")))
    wer = read_last_wer(exe)
    verdict = classify(wer)
    if wer:
        log("  WER: app=%s modulo=%s excecao=%s offset=%s"
            % (wer.get("app"), wer.get("modulo"), wer.get("excecao"), wer.get("offset")))
    log("  Veredito: %s" % verdict)
    log_crash(ev, wer, verdict)
    log("  registrado em logs/crashes.jsonl")
    if stand_down:
        stand_down_bot_stack(log=log)
    log("  >>> REABRA o %s na mão. (o guardião NÃO reabre sozinho) <<<" % ev.client)
    log("!" * 62 + "\n")
    _alarme()


def run(interval: float = 2.0, stand_down: bool = True, log=print) -> None:
    mon = ClientMonitor(confirm_ticks=2)
    log("[guardiao] vigiando: %s  (intervalo %.1fs, stand-down=%s). Ctrl+C para sair."
        % (", ".join(CLIENTS), interval, stand_down))
    # estado inicial
    pm = present_map()
    mon.update(pm)
    log("[guardiao] agora vivo: %s" % ", ".join(c for c, v in pm.items() if v) or "(nenhum)")
    try:
        while True:
            time.sleep(interval)
            for ev in mon.update(present_map()):
                _handle_crash(ev, stand_down, log=log)
    except KeyboardInterrupt:
        log("\n[guardiao] encerrado.")


def main(argv=None):
    p = argparse.ArgumentParser(description="Guardião de clientes de poker (detecta queda e avisa).")
    p.add_argument("--interval", type=float, default=2.0, help="período de verificação (s)")
    p.add_argument("--no-stand-down", dest="stand_down", action="store_false",
                   help="NÃO desanexa o nosso stack Frida ao detectar a queda")
    p.add_argument("--test", action="store_true", help="toca o alarme de crash e sai")
    p.add_argument("--status", action="store_true", help="imprime o que está vivo agora e sai")
    args = p.parse_args(argv)
    if args.test:
        print("[guardiao] tocando alarme de crash de teste...")
        _alarme()
        return 0
    if args.status:
        pm = present_map()
        for c, v in pm.items():
            print("  %-10s %s" % (c, "VIVO" if v else "ausente"))
        return 0
    run(interval=args.interval, stand_down=args.stand_down)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
