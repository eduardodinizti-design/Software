"""Regressão 20/11: RoomRouter (capturar_maos) — UMA mesa por roomid (args[2]), snapshot
ao vivo por mesa e _tiles.json. Sem Frida (só a lógica de roteamento). Rodar do repo:
    python -I -m pytest research/ppp_il2cpp/test_room_router.py -q
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from capturar_maos import RoomRouter          # noqa: E402
from hand_text_sink import HandTextSink        # noqa: E402


def _hand_events(room, uid_base):
    """Mão fold-out mínima e LIMPA (round_start stage1) numa mesa."""
    return [
        dict(t="dealer", room=room, button=2, sb_seat=3, bb_seat=5,
             seats=[{"seat": 2, "stack": 100000}, {"seat": 3, "stack": 100000}, {"seat": 5, "stack": 100000}]),
        dict(t="round_start", room=room, stage=1, cur_blind=50),
        dict(t="action", room=room, seat=3, atype=8, chips=50),
        dict(t="action", room=room, seat=5, atype=9, chips=100),
        dict(t="action", room=room, seat=2, atype=7, chips=300),
        dict(t="action", room=room, seat=3, atype=1, chips=0),
        dict(t="action", room=room, seat=5, atype=1, chips=0),
        dict(t="winner", room=room, winners=[{"seat": 2, "chips": 250}],
             seat_uids=[{"seat": 2, "uid": uid_base + 2}, {"seat": 3, "uid": uid_base + 3},
                        {"seat": 5, "uid": uid_base + 5}]),
    ]


def test_duas_mesas_nao_misturam(tmp_path):
    sink = HandTextSink(base=str(tmp_path))
    r = RoomRouter(sink, "live")
    evs_a = _hand_events(100, 1000)
    evs_b = _hand_events(200, 2000)
    for ea, eb in zip(evs_a, evs_b):      # INTERCALADO (as duas mesas ao mesmo tempo)
        r.route(ea)
        r.route(eb)
    r.close_all()
    assert set(r.accs.keys()) == {100, 200}        # 1 acumulador por mesa
    files = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.txt")}
    assert any("live_r100" in n for n in files)
    assert any("live_r200" in n for n in files)
    a_txt = next(t for n, t in files.items() if "live_r100" in n)
    b_txt = next(t for n, t in files.items() if "live_r200" in n)
    assert "1002 collected" in a_txt and not any(u in a_txt for u in ("2002", "2003", "2005"))
    assert "2002 collected" in b_txt and not any(u in b_txt for u in ("1002", "1003", "1005"))


def test_snapshot_por_mesa(tmp_path):
    sink = HandTextSink(base=str(tmp_path))
    r = RoomRouter(sink, "live")
    for e in _hand_events(100, 1000):
        r.route(e)
    snap = tmp_path / "_live" / "live_r100.json"
    assert snap.exists()
    d = json.loads(snap.read_text(encoding="utf-8"))
    assert d["room"] == 100 and d["bb"] == 100            # bb = 2*cur_blind
    seats = {s["seat"]: s for s in d["seats"]}
    assert seats[3]["pos"] and seats[2]["bb"] == 1000.0    # posição atribuída + stack em BB


def test_tiles_json(tmp_path):
    sink = HandTextSink(base=str(tmp_path))
    r = RoomRouter(sink, "live")
    r.route(dict(t="tiles", order=[14603946, 14604231]))
    tiles = tmp_path / "_live" / "_tiles.json"
    assert tiles.exists()
    d = json.loads(tiles.read_text(encoding="utf-8"))
    assert d["order"] == [14603946, 14604231] and d["total"] == 2
