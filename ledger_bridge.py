"""Ponte do Henrique -> ledger de torneios do NVT Tracker.

No FIM do torneio (tela de ranking / herói eliminado), o Henrique já tem o MttRankInfo lido do lobby
(rank, total de entradas, prêmio). Esta ponte envia isso pro tracker, que calcula Lucro/ROI.

Desacoplado: fala com o tracker por HTTP (o nvt-server precisa estar no ar). Nada de DB aqui.

    from ledger_bridge import report_from_rankinfo
    report_from_rankinfo(rank_info, room="PPPoker", tournament_id=tid, player_id=hero_id, name=nome)
"""
from __future__ import annotations

import json
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8750"


def report_tournament_end(room: str, tournament_id, player_id, *, rank=None, field=None,
                          prize=None, name=None, entries: int = 1, rebuys: int = 0,
                          base_url: str = DEFAULT_URL, timeout: float = 4.0) -> dict:
    """Envia o resultado de um torneio ao tracker (idempotente do lado de lá)."""
    body = json.dumps({
        "room": room, "tournament_id": str(tournament_id), "player_id": str(player_id),
        "rank": rank, "field": field, "prize": prize, "name": name,
        "entries": entries, "rebuys": rebuys,
    }).encode("utf-8")
    req = urllib.request.Request(base_url + "/api/tournament_result", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def report_from_rankinfo(info, room: str, tournament_id, player_id, **kw) -> dict:
    """Atalho: extrai rank/field/prêmio de um MttRankInfo (mtt_rank.py) e reporta."""
    return report_tournament_end(
        room, tournament_id, player_id,
        rank=getattr(info, "rank", None) or None,
        field=getattr(info, "total_player_num", None) or None,
        prize=getattr(info, "current_reward_ppcoins", None),
        **kw)
