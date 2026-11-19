"""Emissor de ASSENTOS (READ-ONLY): anexa no PPPoker, le os jogadores sentados
(uid+nick+stack por assento) e grava logs/live_seats.json {table_ref: {seat: uid}}
+ um sidecar logs/live_seats_rich.json (com nick/stack) p/ depuracao/plano vivo."""
import os, sys, json, time, tempfile, signal
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import frida

# --- DESLIGAMENTO LIMPO (Eduardo 19/11: "fechar o bot dá fatal error no PPPoker") -------
# Host Frida morto no OSSO deixa os hooks IL2CPP pendurados no PPPoker -> CRASH. Então:
#  (a) tratamos SIGBREAK/SIGTERM/SIGINT como "pare e desanexe limpo";
#  (b) vigiamos o PAI (launcher): se ele morrer de qualquer jeito (Ctrl+C, fechar janela,
#      kill), nós mesmos fazemos script.unload()+session.detach() antes de sair.
_PARENT = int(os.environ.get("NVT_PARENT_PID", "0") or 0)
_stop = {"flag": False}


def _request_stop(*_a):
    _stop["flag"] = True


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

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))   # portátil: _repo_software
if REPO not in sys.path:
    sys.path.insert(0, REPO)   # p/ importar ppp_cards sob `python -I`
OUT = os.path.join(REPO, "logs", "live_seats.json")
RICH = os.path.join(REPO, "logs", "live_seats_rich.json")
ESTADO = os.path.join(REPO, "logs", "estado_mesa.json")   # estado COMPLETO p/ percepcao protobuf
BOUNTY = os.path.join(REPO, "logs", "mtt_bounty.json")    # bounty PKO (leitura automatica)
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


def _on_bounty(p):
    """Grava logs/mtt_bounty.json. Campo cujo NOME diz 'bounty' (>0) é confiado como
    bounty do hero (auto/calibrated=True); reward/prize/ko ficam como candidatos crus
    (calibrar ao vivo). Sem risco: se nada confiável, calibrated=False e o reader devolve
    None (operador cai no pko_icm sem desconto)."""
    sb = p.get("sb")
    bb_chips = (sb * 2) if isinstance(sb, (int, float)) and sb > 0 else None
    bounty = p.get("bounty") or {}
    other = p.get("other") or {}
    hero_chips = next((v for v in bounty.values() if isinstance(v, (int, float)) and v > 0), None)
    obj = {"ts": time.time(), "cls": p.get("cls"), "bb_chips": bb_chips,
           "candidates": dict(**bounty, **other), "calibrated": hero_chips is not None}
    if hero_chips is not None:
        obj["hero_bounty_chips"] = hero_chips
    _write_atomic(BOUNTY, obj)
    print("[emit] bounty %s: hero=%s bb_chips=%s cand=%s" % (
        p.get("cls"), hero_chips, bb_chips, list(obj["candidates"].keys())), flush=True)


def on_msg(m, data):
    if m.get("type") != "send":
        if m.get("type") == "error":
            print("[emit] JS erro:", m.get("stack") or m.get("description"))
        return
    p = m.get("payload") or {}
    if p.get("t") == "bounty":
        _on_bounty(p)
        return
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
    s.on("detached", lambda *a: _request_stop())   # PPPoker fechou -> para sem tentar detach morto
    sc.load()
    print("[emit] anexado (pid %d). Gravando %s. Ctrl+C p/ sair." % (procs[0].pid, OUT), flush=True)
    t0 = time.time()
    try:
        while not _stop["flag"] and (not SECONDS or (time.time() - t0) < SECONDS):
            if _parent_gone():
                print("[emit] launcher encerrou -> desanexando LIMPO.", flush=True)
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        # unload ANTES do detach: reverte os hooks IL2CPP com a conexão viva -> sem crash.
        try: sc.unload()
        except Exception: pass
        try: s.detach()
        except Exception: pass
    print("[emit] fim (desanexado limpo). Mesas capturadas:", list(_tables.keys()), flush=True)


if __name__ == "__main__":
    main()
