"""Emissor de SNAPSHOT AO VIVO da Suprema para o HUD do NvtTracker.

O overlay do tracker (`nvttracker.viz.hud_overlay`) desenha as caixas de HUD lendo
`<base>/_live/<mesa>.json` e puxa os stats do banco POR UID. Este módulo gera esse
snapshot a partir do `SupremaTable` vivo (hook de rede), no schema que o overlay espera:

    {"table_id": "...", "hero_seat": N|null, "max_seats": 9,
     "seats": [{"seat": N, "uid": "...", "nick": "...", "pos": "BTN", "bb": 24.8, "bounty": 7.6}, ...]}

READ-ONLY (só escreve o .json de snapshot; nunca toca no jogo). Liga em
`suprema_net.run_live(..., on_state=SupremaLiveEmitter(live_dir))`.
"""
from __future__ import annotations
import json
import os

# rótulos de posição por nº de jogadores ativos, do BOTÃO (idx 0) em sentido horário.
# BTN, SB, BB, depois as demais aproximando-se do botão (UTG...CO).
_POS_BY_N = {
    2: ["BTN", "BB"],                                             # heads-up: BTN é o SB
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "CO"],
    5: ["BTN", "SB", "BB", "UTG", "CO"],
    6: ["BTN", "SB", "BB", "UTG", "HJ", "CO"],
    7: ["BTN", "SB", "BB", "UTG", "MP", "HJ", "CO"],
    8: ["BTN", "SB", "BB", "UTG", "UTG1", "MP", "HJ", "CO"],
    9: ["BTN", "SB", "BB", "UTG", "UTG1", "MP", "LJ", "HJ", "CO"],
}


def positions(dealer_seat, occupied_seats):
    """{seat: 'BTN'/'SB'/...} p/ os assentos ocupados, a partir do dealer, horário (seat crescente).

    Sem dealer conhecido devolve {} (o overlay mostra sem a posição)."""
    occ = sorted(int(s) for s in occupied_seats)
    if dealer_seat is None or not occ:
        return {}
    n = len(occ)
    labels = _POS_BY_N.get(n)
    if not labels:   # mesas >9 ou 1 jogador: sem rótulo
        return {}
    # ordena os ocupados começando no dealer (ou no 1º ocupado após ele), horário
    d = int(dealer_seat)
    order = sorted(occ, key=lambda s: (s - d) % (max(occ) + 1 if occ else 9))
    # garante que o 1º seja o dealer se ele estiver ocupado; senão o botão "morto" cai no próximo
    return {s: labels[i] for i, s in enumerate(order) if i < len(labels)}


class SupremaLiveEmitter:
    """Chamável p/ usar como `on_state` do run_live: a cada evento de jogo, regrava o snapshot.

    Escreve de forma atômica e só quando o conteúdo muda (evita I/O à toa)."""

    def __init__(self, live_dir, table_id="suprema", max_seats=9):
        self.live_dir = live_dir
        self.table_id = str(table_id)
        self.max_seats = int(max_seats)
        os.makedirs(live_dir, exist_ok=True)
        self.path = os.path.join(live_dir, "%s.json" % self.table_id)
        self._last = None

    def __call__(self, table):
        try:
            self.emit(table)
        except Exception:
            pass   # nunca derruba a captura por causa do HUD

    def snapshot(self, table) -> dict:
        bb = None
        try:
            bb = table.bb()
        except Exception:
            bb = getattr(table, "bb_live", None)
        bb = bb if (isinstance(bb, (int, float)) and bb > 0) else None
        occ = {int(s): p for s, p in getattr(table, "players", {}).items()
               if isinstance(p, dict) and p.get("uid") is not None and not p.get("sitout")}
        # POSIÇÃO e BOUNTY saíram da caixa (decisão do Eduardo: mudavam toda hora e faziam
        # a HUD piscar / sobrecarregar em muitas mesas). A caixa é só ID + 4 stats-chave.
        seats = []
        for s in sorted(occ):
            p = occ[s]
            stack = (p.get("coins") or 0) + (p.get("chips") or 0)   # STACK efetivo (coins atrás + apostado)
            seats.append({
                "seat": s,
                "uid": p.get("uid"),
                "nick": str(p.get("uid")),          # sem nome na rede; uid serve de rótulo e chave de stats
                "pos": "",                           # sem posição na caixa
                "bb": round(stack / bb, 1) if (bb and stack) else None,
                "bounty": None,                      # sem bounty na caixa
            })
        return {"table_id": self.table_id, "hero_seat": getattr(table, "hero_seat", None),
                "max_seats": self.max_seats, "seats": seats}

    def emit(self, table) -> bool:
        snap = self.snapshot(table)
        if not snap["seats"]:
            return False
        blob = json.dumps(snap, ensure_ascii=False, sort_keys=True)
        if blob == self._last:
            return False
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(blob)
        os.replace(tmp, self.path)
        self._last = blob
        return True
