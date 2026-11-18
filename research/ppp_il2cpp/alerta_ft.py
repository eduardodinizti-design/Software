"""ALERTA SONORO de MESA FINAL e de DEAL — fica rodando, lê os dados do PPPoker (Frida
read-only) e toca um alarme quando:
  • qualquer torneio entra na MESA FINAL  -> som "arpejo subindo" (A5-D6-G6)
  • chega proposta de DEAL (divisão)       -> som "sirene dois-tons" (grave/agudo)
...pra o Eduardo ASSUMIR O CONTROLE. Repete até você apertar ENTER (silencia tudo).
Nunca aceita/rejeita nada — só avisa (decisão é sua).

Uso:
    python -I alerta_ft.py                 # monitora até Ctrl+C; ENTER silencia
    python -I alerta_ft.py --interval 180  # repetição da FT (default 300s)
    python -I alerta_ft.py --deal-interval 15   # repetição do deal (default 20s)
    python -I alerta_ft.py --ft-size 8     # FT de 8 lugares
    python -I alerta_ft.py --bubble        # também alerta na bolha
    python -I alerta_ft.py --test          # toca os dois sons e sai

Depende de: frida, e mtt_rank.py (em _repo_software — adicionado ao path).
"""
import argparse
import os
import sys
import threading
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_REPO = r"C:\Meus Projetos\Aplicativos\_repo_software"
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
from mtt_rank import MttRankInfo  # noqa: E402

try:
    import winsound
except ImportError:
    winsound = None

_HERE = os.path.dirname(os.path.abspath(__file__))


def _beeps(sequencia, repeticoes, pausa):
    if winsound is None:
        for _ in range(repeticoes):
            sys.stdout.write("\a"); sys.stdout.flush(); time.sleep(0.3)
        return
    for _ in range(repeticoes):
        for freq, dur in sequencia:
            winsound.Beep(freq, dur)
        time.sleep(pausa)


def tocar_alarme_ft(repeticoes=3):
    """FT: arpejo subindo (A5 D6 G6 D6 A5)."""
    _beeps([(880, 140), (1175, 140), (1568, 140), (1175, 140), (880, 140)], repeticoes, 0.15)


def tocar_alarme_deal(repeticoes=4):
    """DEAL: sirene dois-tons (grave/agudo) — bem diferente da FT."""
    _beeps([(1320, 180), (660, 180)], repeticoes, 0.1)


def chave_torneio(info):
    return (info.total_player_num, info.itm_player_num)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ft-size", type=int, default=9)
    ap.add_argument("--interval", type=float, default=300.0, help="repetição da FT (s)")
    ap.add_argument("--deal-interval", type=float, default=20.0, help="repetição do deal (s)")
    ap.add_argument("--bubble", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--process", default="pppoker.exe")
    args = ap.parse_args()

    if args.test:
        print(">>> TESTE: som de MESA FINAL..."); tocar_alarme_ft()
        time.sleep(0.5)
        print(">>> TESTE: som de DEAL..."); tocar_alarme_deal()
        print(">>> Se você ouviu os DOIS (diferentes), está ok. 🔔💰")
        return

    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == args.process.lower()]
    if not procs:
        print(f"[alerta] {args.process} não está aberto."); return
    session = dev.attach(procs[0].pid)
    with open(os.path.join(_HERE, "alerta_ft.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())

    lock = threading.Lock()
    # alarmes ativos: id -> {'next':epoch, 'interval':s, 'sound':callable}
    alarmes = {}
    alertado_bolha = set()
    parar = threading.Event()

    def armar(aid, interval, sound, banner):
        with lock:
            if aid not in alarmes:
                alarmes[aid] = {"next": 0.0, "interval": interval, "sound": sound}
                print("\n" + banner)

    def on_message(msg, data):
        if msg.get("type") != "send":
            return
        p = msg.get("payload")
        if not isinstance(p, dict):
            print("[alerta]", p); return
        kind = p.get("kind")

        # ---------- DEAL ----------
        if kind == "deal":
            cn = str(p.get("msg", ""))
            if any(t in cn.lower() for t in ("refuse", "cancel", "over")):
                with lock:
                    if "deal" in alarmes:
                        del alarmes["deal"]
                        print(f"  ❎ deal encerrado/recusado ({cn}) — alarme de deal silenciado.")
                return
            armar("deal", args.deal_interval, tocar_alarme_deal,
                  "=" * 56 + f"\n  💰 DEAL PROPOSTO!  ({cn})"
                  f"\n  >>> DECIDA aceitar/rejeitar na tela — ENTER p/ silenciar <<<"
                  f"\n  (repete a cada {int(args.deal_interval)}s)\n" + "=" * 56)
            return

        # ---------- RANK / FT ----------
        info = MttRankInfo.from_fields(
            rank=p.get("rank", 0), itm_player_num=p.get("itm", 0),
            total_player_num=p.get("total", 0), alive_player_num=p.get("alive", 0),
            current_reward_ppcoins=p.get("reward", 0), ft_size=args.ft_size)
        if info.alive_player_num < 2 or info.total_player_num <= 0:
            return
        if info.at_final_table:
            armar(("ft", chave_torneio(info)), args.interval, tocar_alarme_ft,
                  "=" * 56 + f"\n  🏆 MESA FINAL!  {info.summary()}"
                  f"\n  >>> ASSUMA O CONTROLE — ENTER p/ silenciar <<<"
                  f"\n  (repete a cada {int(args.interval)}s)\n" + "=" * 56)
        elif args.bubble and info.on_bubble:
            k = chave_torneio(info)
            if k not in alertado_bolha:
                alertado_bolha.add(k)
                print(f"\n  🫧 BOLHA!  {info.summary()}"); tocar_alarme_ft(repeticoes=2)

    def loop_alarme():
        while not parar.is_set():
            agora = time.time(); devidos = []
            with lock:
                for aid, a in alarmes.items():
                    if a["next"] <= agora:
                        a["next"] = agora + a["interval"]; devidos.append(a["sound"])
            for sound in devidos:
                sound()
            parar.wait(1.0)

    threading.Thread(target=loop_alarme, daemon=True).start()
    script.on("message", on_message)
    script.set_log_handler(lambda level, text: print(text))
    script.load()
    print(f"[alerta] monitorando FT (ft_size={args.ft_size}, {int(args.interval)}s) + DEAL "
          f"({int(args.deal_interval)}s){', +bolha' if args.bubble else ''}. ENTER=silenciar | Ctrl+C=sair.")
    try:
        while True:
            line = sys.stdin.readline()
            if line == "":
                break
            with lock:
                n = len(alarmes); alarmes.clear()
            print(f"  ✅ controle assumido — {n} alarme(s) silenciado(s)." if n else "  (nenhum alarme ativo)")
    except KeyboardInterrupt:
        pass
    finally:
        parar.set(); session.detach()


if __name__ == "__main__":
    main()
