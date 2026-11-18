"""CAPTURADOR DE MÃOS ao vivo (fase 2) — roda AO FUNDO e salva cada mão no formato texto
Hand2Note, padrão <base>\\ANO\\MÊS\\DIA\\<torneio>.txt. So LÊ o jogo (hooks read-only),
NÃO age. Reconecta sozinho se o PPPoker fechar/abrir.

Uso:
    python -I capturar_maos.py                      # roda até Ctrl+C, salva na nossa base
    python -I capturar_maos.py --tournament "PPP_X" # nomeia o arquivo do torneio
    python -I capturar_maos.py --base "C:\\Hand2Note4Hh\\PPPoker"   # salvar p/ o H2N importar
    python -I capturar_maos.py --seconds 120        # roda por tempo fixo (teste)
"""
import argparse
import os
import sys
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
from hand_accumulator import HandAccumulator       # noqa: E402
from hand_text_sink import HandTextSink, DEFAULT_BASE  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))


def _make_accumulator(sink, tournament):
    saved = {"n": 0}

    def on_hand(text, hand):
        saved["n"] += 1
        acts = sum(len(v) for v in hand.get("streets", {}).values())
        print(f"  [{datetime.now():%H:%M:%S}] mão #{saved['n']} salva "
              f"({len(hand.get('seats', []))} assentos, {acts} ações)"
              + (f" cartas {hand['hero_cards']}" if hand.get("hero_cards") else ""))

    acc = HandAccumulator(tournament_id=tournament, table_tag=tournament, max_seats=9,
                          sink=sink, on_hand=on_hand)
    return acc


def _route(acc, e):
    t = e.get("t")
    try:
        if t == "round_start":
            acc.on_round_start(e["stage"], cur_blind=e.get("cur_blind", 0),
                               board=e.get("board") or None, hero_cards=e.get("hero_cards") or None)
        elif t == "hand_card":
            acc.on_hand_card(e.get("cards") or [])
        elif t == "action":
            acc.on_action(e["seat"], e["atype"], e.get("chips", 0), hand_chips=e.get("hand_chips"))
        elif t == "winner":
            acc.on_winner()
        # 'ante'/'round_over' não precisam de ação direta aqui
    except Exception as ex:
        print("[cap] erro evento", t, ex)


def run_once(dev, args, sink):
    """Anexa uma vez e captura até o PPPoker sair ou --seconds expirar. Retorna motivo."""
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == args.process.lower()]
    if not procs:
        return "sem_processo"
    session = dev.attach(procs[0].pid)
    acc = _make_accumulator(sink, args.tournament)
    with open(os.path.join(_HERE, "capturar_maos.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())
    stop = {"flag": False, "reason": "ok"}
    session.on("detached", lambda *a: stop.update(flag=True, reason="detached"))
    script.on("message", lambda m, d: (_route(acc, m["payload"])
              if m.get("type") == "send" and isinstance(m.get("payload"), dict) else None))
    script.set_log_handler(lambda level, text: print(text))
    script.load()
    print(f"[cap] conectado ao PPPoker (pid {procs[0].pid}). Salvando em: {sink.base}")
    t0 = time.time()
    try:
        while not stop["flag"]:
            if args.seconds and (time.time() - t0) >= args.seconds:
                stop["reason"] = "tempo"; break
            time.sleep(0.5)
    finally:
        try:
            acc.on_hand_over()      # fecha a mão em aberto
        except Exception:
            pass
        try:
            session.detach()
        except Exception:
            pass
    return stop["reason"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE, help="pasta base dos .txt (padrão: nossa logs/maos_h2n)")
    ap.add_argument("--tournament", default=None, help="nome do arquivo do torneio (default: sessao_AAAA-MM-DD)")
    ap.add_argument("--seconds", type=float, default=0.0, help="0 = roda até Ctrl+C")
    ap.add_argument("--process", default="pppoker.exe")
    args = ap.parse_args()
    if not args.tournament:
        args.tournament = f"sessao_{datetime.now():%Y-%m-%d}"

    import frida
    dev = frida.get_local_device()
    sink = HandTextSink(base=args.base)
    print(f"[cap] CAPTURADOR DE MÃOS (READ-ONLY). Torneio='{args.tournament}'. Ctrl+C p/ sair.")
    try:
        while True:
            reason = run_once(dev, args, sink)
            if args.seconds and reason == "tempo":
                break
            if reason == "sem_processo":
                print("[cap] PPPoker fechado — aguardando abrir...")
            else:
                print(f"[cap] desconectado ({reason}) — tentando reconectar em 3s...")
            time.sleep(3)
    except KeyboardInterrupt:
        pass
    print(f"\n[cap] fim. Total salvo nesta execução: {sink.count} mão(s) em {len(sink.written)} arquivo(s).")
    for p in sorted(sink.written):
        print("   ", p)


if __name__ == "__main__":
    main()
