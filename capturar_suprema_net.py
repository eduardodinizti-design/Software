"""CAPTURADOR DE MÃOS da SUPREMA ao vivo (rota de REDE) — READ-ONLY.

Liga a captura validada da Suprema ao banco NVT:

    suprema_net.run_live (hook SSL_read)  -> on_message(msg crua)
        -> SupremaHandBuilder (reconstrói a mão por delta de chips_round)
            -> HandAccumulator(room='SupremaPoker')  -> HandTextSink (.txt Hand2Note)
                -> (watcher do tracker ingere no banco)

A cada mão fechada, re-parseia o TEXTO com o parser ESTRITO do nvttracker
(`parse_hand(text, check_chips=True)`) e mostra o SALDO (0 = conserva dinheiro =
pronta p/ o banco). NÃO envia nada ao jogo (nenhum clique).

Uso:
    python -I capturar_suprema_net.py                 # roda até Ctrl+C
    python -I capturar_suprema_net.py --seconds 120   # janela fixa (teste)
    python -I capturar_suprema_net.py --base "C:\\Hand2Note4Hh\\SupremaPoker"
"""
import argparse
import os
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
# raiz do pacote do tracker (parser estrito fica em nvttracker\nvttracker\parser)
_TRK = r"C:\Users\tacao\NvtVoz\nvttracker"
if os.path.isdir(_TRK) and _TRK not in sys.path:
    sys.path.insert(0, _TRK)

from hand_accumulator import HandAccumulator       # noqa: E402
from hand_text_sink import HandTextSink, DEFAULT_BASE  # noqa: E402
from suprema_hand_builder import SupremaHandBuilder  # noqa: E402
import suprema_net                                   # noqa: E402

try:
    from nvttracker.parser.nlhe_text import parse_hand, ParseError  # noqa: E402
    _HAS_PARSER = True
except Exception as _e:   # sem o tracker: grava mesmo assim, só não re-valida
    _HAS_PARSER = False
    parse_hand = None

    class ParseError(Exception):
        pass


class LiveStats:
    def __init__(self):
        self.ok = 0
        self.bad = 0
        self.unbalanced = 0

    def on_hand(self, text, hand):
        hid = hand.get("hand_id")
        seats = len(hand.get("seats") or [])
        hero = hand.get("hero_cards") or []
        tail = (" cartas " + " ".join(hero)) if hero else ""
        if not _HAS_PARSER:
            print("  [%s] mão #%s salva (%s assentos)%s" % (
                datetime.now().strftime("%H:%M:%S"), hid, seats, tail), flush=True)
            self.ok += 1
            return
        try:
            h = parse_hand(text, check_chips=True)
            bal = h.chip_balance()
            flag = "OK" if bal == 0 else ("SALDO!=0 (%s)" % bal)
            if bal == 0:
                self.ok += 1
            else:
                self.unbalanced += 1
            print("  [%s] mão #%s | parse %s | %s assentos | pote=%s%s" % (
                datetime.now().strftime("%H:%M:%S"), hid, flag, seats,
                getattr(h, "total_pot", "?"), tail), flush=True)
        except ParseError as e:
            self.bad += 1
            print("  [%s] mão #%s | PARSE FALHOU: %s" % (
                datetime.now().strftime("%H:%M:%S"), hid, e), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE, help="pasta base dos .txt (padrão: logs/maos_h2n)")
    ap.add_argument("--tournament", default=None, help="nome do arquivo (default: suprema_AAAA-MM-DD)")
    ap.add_argument("--seconds", type=float, default=0.0, help="0 = roda até Ctrl+C")
    ap.add_argument("--process", default="SupremaPoker.exe")
    ap.add_argument("--bb-chips", type=float, default=1.0, help="fichas por BB (só p/ leitura; builder não usa)")
    ap.add_argument("--dump-raw", default=None,
                    help="grava TODOS os eventos crus em um .jsonl (p/ validar folds pós-flop e crackear cartas >59 do gameover)")
    ap.add_argument("--hud-dir", default=None,
                    help="pasta _live p/ o HUD overlay: grava snapshot por assento (nick/pos/bb) p/ o nvttracker desenhar a HUD")
    ap.add_argument("--advise", action="store_true",
                    help="além de capturar, MOSTRA o conselho (dry-run) na sua vez — mesmo cérebro do assistir_suprema, num só hook")
    ap.add_argument("--mode", default="chip_ev", help="modo do conselho (chip_ev/icm/pko/pko_icm)")
    ap.add_argument("--stage", default="mid", help="fase do conselho (pre_itm/bubble/ft/mid)")
    args = ap.parse_args()
    if not args.tournament:
        args.tournament = "suprema_%s" % datetime.now().strftime("%Y-%m-%d")

    sink = HandTextSink(base=args.base)
    stats = LiveStats()
    # tournament_id PRECISA ser numérico: o parser só classifica como TORNEIO quando o
    # cabeçalho é "Tournament #<dígitos>,". Com id não-numérico as mãos entravam como 'cash'
    # e a HUD (torneio) não achava as stats. table_tag segue legível (nome do arquivo/Table).
    tour_id = "".join(ch for ch in args.tournament if ch.isdigit()) or \
        datetime.now().strftime("%Y%m%d")
    acc = HandAccumulator(room="SupremaPoker", tournament_id=tour_id,
                          table_tag=args.tournament, max_seats=9,
                          sink=sink, on_hand=stats.on_hand)
    builder = SupremaHandBuilder(acc)

    # feed do builder, opcionalmente espelhando o evento cru p/ um .jsonl (evidência durável)
    feed = builder.feed
    raw_fp = None
    if args.dump_raw:
        import json as _json
        import time as _time
        os.makedirs(os.path.dirname(os.path.abspath(args.dump_raw)) or ".", exist_ok=True)
        raw_fp = open(args.dump_raw, "a", encoding="utf-8")

        def feed(msg, _b=builder.feed, _fp=raw_fp, _json=_json, _time=_time):
            try:
                _fp.write(_json.dumps({"ts": _time.time(), "msg": msg}, ensure_ascii=False) + "\n")
                _fp.flush()
            except Exception:
                pass
            return _b(msg)

    # on_state COMPOSTO (tudo num só hook): HUD snapshot + CONSELHO (dry-run). run_live chama
    # on_state(table) a cada evento; aqui encadeamos os dois (nenhum clica).
    state_cbs = []
    emitter = None
    if args.hud_dir:
        from suprema_live_emit import SupremaLiveEmitter
        emitter = SupremaLiveEmitter(args.hud_dir)
        state_cbs.append(emitter)

    advise_stats = {"decisao": 0}
    if args.advise:
        from assistir_suprema import load_advisor, make_on_state
        advisor = load_advisor()
        state_cbs.append(make_on_state(advisor, mode=args.mode, stage=args.stage, stats=advise_stats))

    def on_state(table, _cbs=state_cbs):
        for cb in _cbs:
            try:
                cb(table)
            except Exception:
                pass
    on_state = on_state if state_cbs else None

    print("[suprema-cap] CAPTURA DE MÃOS (READ-ONLY). Torneio='%s'" % args.tournament, flush=True)
    print("[suprema-cap] gravando .txt em: %s" % sink.base, flush=True)
    if args.dump_raw:
        print("[suprema-cap] eventos crus -> %s" % os.path.abspath(args.dump_raw), flush=True)
    if emitter is not None:
        print("[suprema-cap] HUD snapshot -> %s" % emitter.path, flush=True)
    if args.advise:
        print("[suprema-cap] CONSELHO ligado (dry-run; nenhum clique) — mostro o PLANO na sua vez.", flush=True)
    if not _HAS_PARSER:
        print("[suprema-cap] AVISO: parser do nvttracker indisponível — grava sem re-validar.", flush=True)
    print("[suprema-cap] Ctrl+C p/ sair. Jogue na Suprema; reconstruo cada mão fechada.", flush=True)

    try:
        suprema_net.run_live(bb_chips=args.bb_chips, on_message=feed, on_state=on_state,
                             seconds=args.seconds, process=args.process)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            acc.on_hand_over()   # fecha mão em aberto (se houver)
        except Exception:
            pass
        if raw_fp is not None:
            try:
                raw_fp.close()
            except Exception:
                pass

    print("\n[suprema-cap] fim. mãos: %d parse-OK, %d saldo!=0, %d parse-falhou | arquivos: %d" % (
        stats.ok, stats.unbalanced, stats.bad, len(sink.written)), flush=True)
    for p in sorted(sink.written):
        print("   ", p, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
