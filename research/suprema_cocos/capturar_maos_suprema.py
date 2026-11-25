"""CAPTURADOR DE MÃOS da SUPREMA (Cocos/V8) — ESQUELETO. Anexa no SupremaPoker.exe,
injeta o emissor JS (inject_emit.js) e roteia os EVENTOS NORMALIZADOS p/ o MESMO
HandAccumulator do PPPoker, salvando .txt (room 'SupremaPoker') que o NvtTracker ingere.

Estado: a INFRA está pronta (injeção + ponte + acumulador agnóstico de sala). Falta
`inject_emit.js` emitir os eventos reais — isso depende do RECON ao vivo (ver
FINDINGS_SUPREMA.md e recon_suprema.py). Enquanto inject_emit.js for no-op, este runner
anexa e não grava nada (seguro). Assim que os hooks forem plugados, começa a capturar.

Uso:
    python -I capturar_maos_suprema.py --base "C:\\Hand2Note4Hh\\SupremaPoker"
    python -I capturar_maos_suprema.py --seconds 120
"""
import argparse
import os
import signal
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_PARENT = int(os.environ.get("NVT_PARENT_PID", "0") or 0)
_STOP = {"flag": False}


def _request_stop(*_a):
    _STOP["flag"] = True


def _parent_gone():
    if not _PARENT:
        return False
    try:
        import psutil
        return not psutil.pid_exists(_PARENT)
    except Exception:
        return False


for _s in ("SIGBREAK", "SIGTERM", "SIGINT"):
    try:
        signal.signal(getattr(signal, _s), _request_stop)
    except Exception:
        pass

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
from hand_accumulator import HandAccumulator          # noqa: E402
from hand_text_sink import HandTextSink, DEFAULT_BASE  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))


def _route(acc, e):
    """MESMO contrato normalizado do PPPoker (ver capturar_maos.py)."""
    t = e.get("t")
    try:
        if t == "round_start":
            acc.on_round_start(e["stage"], cur_blind=e.get("cur_blind", 0),
                               board=e.get("board") or None, hero_cards=e.get("hero_cards") or None,
                               button_seat=e.get("button_seat"), hand_id=e.get("hand_id"),
                               datetime=e.get("datetime"))
        elif t == "hand_card":
            acc.on_hand_card(e.get("cards") or [], seatid=e.get("seat"))
        elif t == "seat":
            acc.set_seat(e["seat"], player=e.get("player"), stack=e.get("stack"))
        elif t == "ante":
            acc.on_ante(e["seat"], e.get("amount", 0))
        elif t == "action":
            acc.on_action(e["seat"], e["atype"], e.get("chips", 0),
                          hand_chips=e.get("hand_chips"), is_all_in=e.get("all_in", False))
        elif t == "winner":
            acc.on_winner(collected=e.get("collected"), total_pot=e.get("total_pot"))
        elif t == "hand_over":
            acc.on_hand_over()
    except Exception as ex:
        print("[cap-sup] erro evento", t, ex, flush=True)


def _make_acc(sink, tournament):
    saved = {"n": 0}

    def on_hand(text, hand):
        saved["n"] += 1
        acts = sum(len(v) for v in hand.get("streets", {}).values())
        print(f"  [{datetime.now():%H:%M:%S}] mão #{saved['n']} salva "
              f"({len(hand.get('seats', []))} assentos, {acts} ações)", flush=True)

    return HandAccumulator(room="SupremaPoker", tournament_id=tournament, table_tag=tournament,
                           max_seats=9, sink=sink, on_hand=on_hand)


def run_once(dev, args, sink):
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == args.process.lower()]
    if not procs:
        return "sem_processo"
    session = dev.attach(procs[0].pid)
    acc = _make_acc(sink, args.tournament)
    session.on("detached", lambda *a: _STOP.update(flag=True))
    with open(os.path.join(_HERE, "suprema_capture_agent.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())

    def on_message(m, _d):
        if m.get("type") == "send":
            p = m.get("payload") or {}
            if isinstance(p, dict) and isinstance(p.get("nvt"), dict):
                _route(acc, p["nvt"])
            elif isinstance(p, dict) and "nvt_raw" in p:
                print("[raw]", p["nvt_raw"], flush=True)
        elif m.get("type") == "error":
            print("[js-erro]", m.get("stack") or m.get("description"), flush=True)

    script.on("message", on_message)
    script.load()
    exp = getattr(script, "exports_sync", None) or script.exports
    exp.ready()
    for js in ("inject_recon.js", "inject_emit.js"):     # recon = helpers __nvt; emit = hooks reais
        path = os.path.join(_HERE, js)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                try:
                    exp.eval_string(fh.read())
                except Exception as e:
                    print(f"[cap-sup] falha ao injetar {js}:", e, flush=True)
    print(f"[cap-sup] conectado à Suprema (pid {procs[0].pid}). Salvando em: {sink.base}", flush=True)
    t0 = time.time()
    try:
        while not _STOP["flag"]:
            if args.seconds and (time.time() - t0) >= args.seconds:
                break
            if _parent_gone():
                _STOP["flag"] = True; break
            time.sleep(0.5)
    finally:
        try:
            acc.on_hand_over()
        except Exception:
            pass
        try:
            script.unload()
        except Exception:
            pass
        try:
            session.detach()
        except Exception:
            pass
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE, help="pasta base dos .txt (aponte p/ C:\\Hand2Note4Hh\\SupremaPoker)")
    ap.add_argument("--tournament", default=None)
    ap.add_argument("--seconds", type=float, default=0.0)
    ap.add_argument("--process", default="SupremaPoker.exe")
    args = ap.parse_args()
    if not args.tournament:
        args.tournament = f"suprema_{datetime.now():%Y-%m-%d}"

    import frida
    dev = frida.get_local_device()
    sink = HandTextSink(base=args.base)
    print(f"[cap-sup] CAPTURADOR SUPREMA (READ-ONLY). Torneio='{args.tournament}'. Ctrl+C p/ sair.", flush=True)
    try:
        while not _STOP["flag"]:
            reason = run_once(dev, args, sink)
            if _STOP["flag"]:
                break
            if reason == "sem_processo":
                print("[cap-sup] Suprema fechada — aguardando abrir...", flush=True)
            for _ in range(6):
                if _STOP["flag"] or _parent_gone():
                    _STOP["flag"] = True; break
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    print(f"\n[cap-sup] fim. Total salvo: {sink.count} mão(s) em {len(sink.written)} arquivo(s).", flush=True)


if __name__ == "__main__":
    main()
