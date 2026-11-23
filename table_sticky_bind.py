"""Binding GRUDENTO posição-do-painel -> roomid, p/ o multi-mesa TILADO do PPPoker.

O crossing (ver [[nvt-multitable-tiled-bug]]) vem de amarrar cada painel da tela ao roomid do
protobuf por OCR (nameplate/sala) A CADA FRAME — frágil: ou abstém à toa (nome ilegível) ou erra
o bind (nome parecido). Como o PPPoker tila em COLUNAS de posição ESTÁVEL entre frames, a posição
(0..N-1, esquerda→direita) é uma CHAVE confiável ENQUANTO a grade não muda.

Este módulo aprende `posição -> roomid` dos binds CONFIANTES (nameplate com score alto e ÚNICO) e
REUSA por posição quando o OCR do frame falha — sem re-OCR. Garantias (anti-crossing):
  - 1 roomid por posição e 1 posição por roomid (nunca dois painéis no mesmo roomid);
  - frame AMBÍGUO (o mesmo roomid casando em >1 posição) NÃO ensina nada;
  - RE-TILE (muda o nº de painéis OU o conjunto de roomids frescos) ZERA o mapa -> re-aprende;
  - roomid que saiu dos frescos, ou cache velho (TTL), devolve None -> o chamador ABSTÉM (não cruza).

PURO: só lógica (sem cv2/OCR/clique). O chamador calcula os binds confiantes (ex. via
table_binding.bind_crop_to_ref por painel) e passa aqui.
"""
from __future__ import annotations

import time as _time

__all__ = ["StickyBinder"]


class StickyBinder:
    def __init__(self, *, confirm_ttl=20.0, min_score=2):
        self.confirm_ttl = float(confirm_ttl)   # seg. que um bind aprendido vale sem reconfirmar
        self.min_score = int(min_score)         # score mínimo do nameplate p/ APRENDER
        self._map = {}                          # pos -> {"roomid", "ts", "score"}
        self._sig = None                        # (n_panels, frozenset(roomids frescos))

    # ---- interno ----
    def _retile_if_needed(self, n_panels, fresh):
        sig = (int(n_panels), frozenset(fresh))
        if sig != self._sig:
            self._map = {}
            self._sig = sig
            return True
        return False

    @staticmethod
    def _unique_frame_binds(frame_binds, min_score, fresh):
        """Filtra os binds confiantes do frame: score>=min, roomid fresco, e descarta QUALQUER
        roomid que apareça em >1 posição no mesmo frame (ambíguo -> não ensina)."""
        cand = {}
        seen = {}
        for pos, rs in (frame_binds or {}).items():
            if not rs:
                continue
            roomid, score = rs
            if roomid is None or roomid not in fresh or score is None or score < min_score:
                continue
            cand[pos] = (roomid, score)
            seen[roomid] = seen.get(roomid, 0) + 1
        return {pos: (r, s) for pos, (r, s) in cand.items() if seen.get(r) == 1}

    # ---- API ----
    def observe(self, *, n_panels, fresh_roomids, frame_binds=None, now=None):
        """Atualiza o mapa com os binds confiantes deste frame. Devolve o binding vivo {pos: roomid}
        (só posições com roomid fresco e dentro do TTL)."""
        now = _time.time() if now is None else now
        fresh = set(fresh_roomids or [])
        self._retile_if_needed(n_panels, fresh)
        good = self._unique_frame_binds(frame_binds, self.min_score, fresh)
        for pos, (roomid, score) in good.items():
            # unicidade: tira esse roomid de qualquer OUTRA posição antes de fixá-lo aqui
            for p in [p for p, e in self._map.items() if e["roomid"] == roomid and p != pos]:
                del self._map[p]
            self._map[pos] = {"roomid": roomid, "ts": now, "score": score}
        # poda: roomid que saiu dos frescos não serve mais
        for p in [p for p, e in self._map.items() if e["roomid"] not in fresh]:
            del self._map[p]
        return self.binding(fresh_roomids=fresh, now=now)

    def roomid_for(self, pos, *, fresh_roomids, now=None):
        """roomid GRUDADO nessa posição se ainda fresco e recente (<=TTL); senão None (abstém)."""
        now = _time.time() if now is None else now
        e = self._map.get(pos)
        if not e:
            return None
        if e["roomid"] not in set(fresh_roomids or []):
            return None
        if (now - e["ts"]) > self.confirm_ttl:
            return None
        return e["roomid"]

    def binding(self, *, fresh_roomids, now=None):
        """Mapa vivo {pos: roomid} das posições com bind válido (fresco + dentro do TTL)."""
        now = _time.time() if now is None else now
        out = {}
        for pos in list(self._map):
            r = self.roomid_for(pos, fresh_roomids=fresh_roomids, now=now)
            if r is not None:
                out[pos] = r
        return out
