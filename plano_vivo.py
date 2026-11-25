"""PLANO VIVO: lê logs/live_seats_rich.json (escrito pelo emissor Frida, assento->
uid+nick ao vivo) + logs/exploit_db.json (nossa DB de 389k mãos) e imprime, por
mesa, o plano de exploit de cada vilão sentado. Fecha o ciclo RE -> uid -> DB ->
exploit AO VIVO (o que o `plano_mesa.py` fazia manual, agora automatico do feed).

Uso:
    python plano_vivo.py            # imprime 1x o que está no feed agora
    python plano_vivo.py --watch    # atualiza a cada 3s
"""
import argparse
import json
import os
import time

_REPO = os.path.dirname(os.path.abspath(__file__))
_RICH = os.path.join(_REPO, "logs", "live_seats_rich.json")
_DB = os.path.join(_REPO, "logs", "exploit_db.json")

try:
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def render(rich, db):
    from plano_mesa import format_villain, table_summary
    if not rich:
        print("(feed vazio: rode o emissor `research/ppp_il2cpp/emitir_seats.py` e "
              "ENTRE/troque de mesa p/ semear o HoldemManager)")
        return
    for ref, info in rich.items():
        players = info.get("players", [])
        ids = [str(p["uid"]) for p in players if p.get("uid")]
        print("\n" + "=" * 72)
        print("MESA %s  %s   (%d sentados)" % (ref, info.get("room", ""), len(players)))
        print(table_summary(ids, db))
        print("-" * 72)
        for p in players:
            uid = str(p.get("uid"))
            nick = (p.get("name") or "").strip()
            sit = " [SIT OUT]" if p.get("sit") else ""
            print("assento %s · %s · uid %s%s" % (p.get("seat"), nick, uid, sit))
            print("   " + format_villain(uid, db.get(uid)).split("\n", 1)[-1]
                  if db.get(uid) else "   SEM LEITURA na DB → base GTO")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    args = ap.parse_args()
    db = _load(_DB)
    if not db:
        print("[plano_vivo] exploit_db.json não encontrado:", _DB)
        return
    if not args.watch:
        render(_load(_RICH), db)
        return
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print("PLANO VIVO (DB: %d vilões) — Ctrl+C p/ sair" % len(db))
            render(_load(_RICH), db)
            time.sleep(3)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
