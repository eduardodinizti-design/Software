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
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- DESLIGAMENTO LIMPO (Eduardo 19/11): host Frida morto no osso -> PPPoker fatal error.
# SIGBREAK/SIGTERM/SIGINT => parar e desanexar; e se o PAI (launcher) morrer, desanexa só.
_PARENT = int(os.environ.get("NVT_PARENT_PID", "0") or 0)
_GSTOP = {"flag": False}


def _request_stop(*_a):
    _GSTOP["flag"] = True


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
from hand_accumulator import HandAccumulator       # noqa: E402
from hand_text_sink import HandTextSink, DEFAULT_BASE  # noqa: E402
from protobuf_state import assign_positions         # noqa: E402  (posições pela geometria do botão)

_HERE = os.path.dirname(os.path.abspath(__file__))


class RoomRouter:
    """UM HandAccumulator por MESA (roomid = args[2], provado ao vivo 20/11). Cada evento
    traz `room`; mesas diferentes nunca se misturam (antes caíam num acumulador só)."""

    def __init__(self, sink, tournament):
        self.sink = sink
        self.tournament = tournament
        self.accs = {}
        self.saved = 0
        # estado AO VIVO por mesa (p/ o snapshot do HUD: nick/pos/bb/bounty no instante da mão)
        self.live = {}        # room -> {seat: {uid, nick, bounty, stack}}
        self.btn = {}         # room -> {button, sb, bb}
        self.ingame = {}      # room -> [seatid] em jogo (DealerInfoRSP)
        self.hero = {}        # room -> seatid do herói (SeatStatus.card1!=0)
        self._live_dir = os.path.join(getattr(sink, "base", "."), "_live")

    def _on_hand(self, text, hand):
        self.saved += 1
        acts = sum(len(v) for v in hand.get("streets", {}).values())
        print(f"  [{datetime.now():%H:%M:%S}] [mesa {hand.get('table_tag')}] mão #{self.saved} salva "
              f"({len(hand.get('seats', []))} assentos, {acts} ações)"
              + (f" cartas {hand['hero_cards']}" if hand.get("hero_cards") else ""), flush=True)

    def _acc(self, room):
        room = int(room or 0)
        acc = self.accs.get(room)
        if acc is None:
            tag = f"{self.tournament}_r{room}" if room else self.tournament
            acc = HandAccumulator(room="PPPoker", tournament_id=str(room or self.tournament),
                                  table_tag=tag, max_seats=9, sink=self.sink, on_hand=self._on_hand)
            self.accs[room] = acc
        return acc

    def _live_seat(self, room, seat):
        return self.live.setdefault(int(room or 0), {}).setdefault(int(seat), {})

    def _snapshot(self, room, cur_blind):
        """Escreve <base>\\_live\\<table_tag>.json com o estado da mesa AGORA (início da mão):
        nick/posição/stack em BB/bounty por assento. O HUD lê p/ o cabeçalho das caixas."""
        room = int(room or 0)
        bb = 2 * int(cur_blind or 0)
        ingame = self.ingame.get(room) or list(self.live.get(room, {}).keys())
        info = self.btn.get(room, {})
        pos = assign_positions(ingame, info.get("button"), info.get("sb"), info.get("bb")) if ingame else {}
        seats = []
        for s in ingame:
            d = self.live.get(room, {}).get(s, {})
            stack = d.get("stack")
            seats.append({"seat": s, "uid": d.get("uid"), "nick": d.get("nick") or "",
                          "pos": pos.get(s, ""), "bounty": d.get("bounty") or 0,
                          "stack": stack, "bb": (round(stack / bb, 1) if stack and bb else None)})
        tag = f"{self.tournament}_r{room}" if room else self.tournament
        snap = {"room": room, "table_id": tag, "bb": bb, "ts": datetime.now(timezone.utc).isoformat(),
                "hero_seat": self.hero.get(room), "max_seats": 9,
                "seats": seats}
        try:
            os.makedirs(self._live_dir, exist_ok=True)
            with open(os.path.join(self._live_dir, tag + ".json"), "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False)
        except Exception:
            pass

    def _write_tiles(self, order):
        """Ordem de roomids das páginas (tiles) lida da UI -> _live\\_tiles.json p/ o HUD
        pôr cada mesa no tile certo (grade determinística da janela)."""
        try:
            os.makedirs(self._live_dir, exist_ok=True)
            with open(os.path.join(self._live_dir, "_tiles.json"), "w", encoding="utf-8") as f:
                json.dump({"order": [int(r) for r in order], "total": len(order),
                           "ts": datetime.now(timezone.utc).isoformat()}, f)
        except Exception:
            pass

    def route(self, e):
        t = e.get("t")
        if t == "tiles":
            self._write_tiles(e.get("order") or [])
            return
        room = e.get("room")
        acc = self._acc(room)
        try:
            if t == "round_start":
                acc.on_round_start(e["stage"], cur_blind=e.get("cur_blind", 0),
                                   board=e.get("board") or None, hero_cards=e.get("hero_cards") or None)
                if int(e.get("stage", 0)) == 1:
                    self._snapshot(room, e.get("cur_blind", 0))   # estado da mesa no início da mão
            elif t == "hand_card":
                acc.on_hand_card(e.get("cards") or [])
            elif t == "action":
                acc.on_action(e["seat"], e["atype"], e.get("chips", 0), hand_chips=e.get("hand_chips"))
            elif t == "dealer":
                acc.on_dealer(button_seat=e.get("button"), seats=e.get("seats"))
                self.btn[int(room or 0)] = {"button": e.get("button"), "sb": e.get("sb_seat"), "bb": e.get("bb_seat")}
                self.ingame[int(room or 0)] = [s["seat"] for s in (e.get("seats") or [])]
                for s in (e.get("seats") or []):      # stack/bounty iniciais do DealerInfo
                    ls = self._live_seat(room, s["seat"])
                    if s.get("stack") is not None:
                        ls["stack"] = s["stack"]
                    if s.get("bounty"):
                        ls["bounty"] = s["bounty"]
            elif t == "seat":
                acc.set_seat(e["seat"], player=(str(e["uid"]) if e.get("uid") else None),
                             stack=(e["stack"] if e.get("stack") else None))
                ls = self._live_seat(room, e["seat"])    # nick/uid/bounty/stack ao vivo
                if e.get("uid"):
                    ls["uid"] = str(e["uid"])
                if e.get("nick"):
                    ls["nick"] = e["nick"]
                if e.get("bounty"):
                    ls["bounty"] = e["bounty"]
                if e.get("stack"):
                    ls["stack"] = e["stack"]
                if e.get("hero"):
                    acc.mark_hero(e["seat"])
                    self.hero[int(room or 0)] = int(e["seat"])     # p/ a rotação do HUD
            elif t == "winner":
                winners = e.get("winners") or []
                collected = [(w["seat"], w["chips"]) for w in winners if w.get("chips")]
                pot = sum(w["chips"] for w in winners if w.get("chips")) or None
                acc.on_winner(collected=collected or None, total_pot=pot, seat_uids=e.get("seat_uids"))
                for su in (e.get("seat_uids") or []):   # uid de TODOS os assentos (p/ o snapshot/HUD)
                    if su.get("uid"):
                        self._live_seat(room, su["seat"])["uid"] = str(su["uid"])
            # 'ante'/'round_over'/'show' não precisam de ação direta (show = cartas de vilão, futuro)
        except Exception as ex:
            print("[cap] erro evento", t, ex, flush=True)

    def close_all(self):
        for acc in self.accs.values():
            try:
                acc.on_hand_over()
            except Exception:
                pass


def run_once(dev, args, sink):
    """Anexa uma vez e captura até o PPPoker sair ou --seconds expirar. Retorna motivo."""
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == args.process.lower()]
    if not procs:
        return "sem_processo"
    session = dev.attach(procs[0].pid)
    router = RoomRouter(sink, args.tournament)
    with open(os.path.join(_HERE, "capturar_maos.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())
    stop = {"flag": False, "reason": "ok"}
    session.on("detached", lambda *a: stop.update(flag=True, reason="detached"))
    script.on("message", lambda m, d: (router.route(m["payload"])
              if m.get("type") == "send" and isinstance(m.get("payload"), dict) else None))
    script.set_log_handler(lambda level, text: print(text))
    script.load()
    print(f"[cap] conectado ao PPPoker (pid {procs[0].pid}). Salvando em: {sink.base}")
    t0 = time.time()
    try:
        while not stop["flag"] and not _GSTOP["flag"]:
            if args.seconds and (time.time() - t0) >= args.seconds:
                stop["reason"] = "tempo"; break
            if _parent_gone():
                _GSTOP["flag"] = True
                stop["reason"] = "launcher_encerrou"; break
            time.sleep(0.5)
    finally:
        try:
            router.close_all()      # fecha a mão em aberto de CADA mesa
        except Exception:
            pass
        # unload ANTES do detach: reverte os hooks IL2CPP com a conexão viva -> sem crash.
        try:
            script.unload()
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
        while not _GSTOP["flag"]:
            try:
                reason = run_once(dev, args, sink)
            except Exception as ex:   # erro de anexação do Frida (ex.: processo fechando) -> espera e reconecta
                print(f"[cap] falha ao anexar ({type(ex).__name__}) — aguardando PPPoker...")
                reason = "sem_processo"
            if _GSTOP["flag"] or reason == "launcher_encerrou":
                print("[cap] encerrando LIMPO (launcher/sinal).")
                break
            if args.seconds and reason == "tempo":
                break
            if reason == "sem_processo":
                print("[cap] PPPoker fechado — aguardando abrir...")
            else:
                print(f"[cap] desconectado ({reason}) — tentando reconectar em 3s...")
            for _ in range(6):               # ~3s, mas acordando p/ sinal/pai
                if _GSTOP["flag"] or _parent_gone():
                    _GSTOP["flag"] = True; break
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    print(f"\n[cap] fim. Total salvo nesta execução: {sink.count} mão(s) em {len(sink.written)} arquivo(s).")
    for p in sorted(sink.written):
        print("   ", p)


if __name__ == "__main__":
    main()
