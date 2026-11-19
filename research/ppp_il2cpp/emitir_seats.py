"""Emissor de ASSENTOS (READ-ONLY): anexa no PPPoker, le os jogadores sentados
(uid+nick+stack por assento) e grava logs/live_seats.json {table_ref: {seat: uid}}
+ um sidecar logs/live_seats_rich.json (com nick/stack) p/ depuracao/plano vivo."""
import os, sys, json, time, tempfile
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import frida

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))   # portátil: _repo_software
if REPO not in sys.path:
    sys.path.insert(0, REPO)   # p/ importar ppp_cards sob `python -I`
OUT = os.path.join(REPO, "logs", "live_seats.json")
RICH = os.path.join(REPO, "logs", "live_seats_rich.json")
ESTADO = os.path.join(REPO, "logs", "estado_mesa.json")   # estado COMPLETO p/ percepcao protobuf
SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0

_tables = {}        # ref -> {seat: uid}
_rich = {}          # ref -> {room, players:[...]}
_estado = {}        # ref -> {ts, room, table:{dealer,sb/bb seats,sb,...}, players:[full]}


def _write_atomic(path, obj):
    d = os.path.dirname(path); os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp"); os.close(fd)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def on_msg(m, data):
    if m.get("type") != "send":
        if m.get("type") == "error":
            print("[emit] JS erro:", m.get("stack") or m.get("description"))
        return
    p = m.get("payload") or {}
    if p.get("t") != "seats":
        return
    ref = p.get("ref") or "?"
    players = p.get("players") or []
    table = p.get("table") or {}
    _tables[ref] = {str(pl["seat"]): str(pl["uid"]) for pl in players if pl.get("uid")}
    _rich[ref] = {"room": p.get("room", ""), "players": players}
    _estado[ref] = {"ts": time.time(), "room": p.get("room", ""), "table": table, "players": players}
    _write_atomic(OUT, _tables)
    _write_atomic(RICH, _rich)
    _write_atomic(ESTADO, _estado)
    # validacao ao vivo: dealer + cartas do heroi (quem tem 2 cartas face-up)
    hero = next((pl for pl in players if pl.get("cards") and len(pl["cards"]) == 2), None)
    from ppp_cards import decode_cards  # decodifica int->'Qh'
    hc = (" | HERO s%s cards=%s" % (hero.get("seat"), " ".join(decode_cards(hero["cards"])))) if hero else ""
    print("[emit] mesa %s: %dj dealer=s%s sb=%s%s" % (
        ref, len(players), table.get("dealer"), table.get("sb"), hc), flush=True)


def main():
    dev = frida.get_local_device()
    procs = [x for x in dev.enumerate_processes() if x.name.lower() == "pppoker.exe"]
    if not procs:
        print("[emit] PPPoker fechado."); return
    s = dev.attach(procs[0].pid)
    with open(os.path.join(HERE, "emitir_seats.js"), encoding="utf-8") as fh:
        sc = s.create_script(fh.read())
    sc.set_log_handler(lambda l, t: print(t, flush=True))
    sc.on("message", on_msg)
    sc.load()
    print("[emit] anexado (pid %d). Gravando %s. Ctrl+C p/ sair." % (procs[0].pid, OUT), flush=True)
    t0 = time.time()
    try:
        while not SECONDS or (time.time() - t0) < SECONDS:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        try: s.detach()
        except Exception: pass
    print("[emit] fim. Mesas capturadas:", list(_tables.keys()), flush=True)


if __name__ == "__main__":
    main()
