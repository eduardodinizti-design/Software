"""MULTI-MESA da Suprema: roteia os eventos de rede por `roomID` -> um SupremaTable por sala.
Resolve o cruzamento (ler mão de uma mesa e decidir na outra) de forma limpa, porque a Suprema
MARCA todo evento com `data.roomID` (cobertura 100% no dump: gameinfo/gamestart/moveturn/prompt/
updateseat/gameover/KOdata). O `hero_uid` (a conta do Eduardo) é o MESMO em todas as mesas e
ancora o herói no assento certo de CADA sala. READ-ONLY (só mantém estado).

Uso: alimentar `feed_json(msg)` com cada evento cru (como o run_live faz), e decidir por sala
via `table(room).to_table_state()`. A camada de CLIQUE depois mapeia cada sala -> sua janela/região.
"""
from __future__ import annotations

import re
import time

from suprema_state import SupremaTable

_SUFFIX = re.compile(r"#\d+$")        # '..._4#113' -> '..._4' (sub-contexto da mesma sala)


def room_of(msg):
    """roomID normalizado do evento (sem o sufixo #NNN), ou None se não houver."""
    if not isinstance(msg, dict):
        return None
    d = msg.get("data") or {}
    rid = d.get("roomID") or d.get("roomId") or d.get("room")
    if rid is None:
        gi = d.get("game_info") or {}
        rid = gi.get("roomID") or gi.get("room")
    if rid is None:
        return None
    return _SUFFIX.sub("", str(rid))


def event_ts(msg):
    """Timestamp (epoch segundos) do evento, p/ liveness. A Suprema carimba `data.ts` em ms
    (ex.: 1795280170226). Converte p/ segundos; None se ausente (o chamador usa o relógio)."""
    if not isinstance(msg, dict):
        return None
    d = msg.get("data") or {}
    t = d.get("ts")
    if isinstance(t, (int, float)) and t > 0:
        return t / 1000.0 if t > 1e11 else float(t)   # ms -> s (heurística de magnitude)
    return None


class RoomOrder:
    """Mapa roomID -> COLUNA-NA-TELA estável + contagem de mesas VIVAS, para a camada de clique
    (room_index/n_rooms). Projetado a partir do dump 2026-11-21:

      * NÃO existe NENHUM campo de posição-de-tela no protocolo da Suprema (varri recursivamente
        todo o dump: só há `mtttablecount`/`remainTables`, que são metadados do TORNEIO, não o
        índice do tile no cliente). Então a ordem das colunas é por PRIMEIRA APARIÇÃO (append-only):
        uma sala nova entra sempre na ÚLTIMA coluna; o índice de uma sala VIVA NUNCA muda enquanto
        ela viver (ao contrário do `sorted()` antigo, que re-embaralhava as colunas a cada mesa nova).
        -> A ordem L/R REAL (append == esquerda->direita?) precisa de uma validação DRY de 30s ao vivo.

      * Liveness por STALENESS RELATIVA: uma sala é podada quando fica `ttl` segundos atrás da
        sala MAIS RECENTE (não do relógio de parede). Assim um break global (todas as mesas param
        juntas — :55->:00 na Suprema) NÃO poda ninguém (o gap entre elas fica ~0), mas uma mesa que
        BUSTOU/foi quebrada (as outras seguem jogando) atrasa e é removida -> n_rooms reflete só as
        VIVAS. Uma sala podada que reaparecer volta a ficar viva (revive no touch).

      * Índice calculado sobre a lista VIVA COMPACTADA (sem buracos): assume que a Suprema RE-TILA
        fechando o buraco quando uma mesa some (as demais deslizam p/ a esquerda) — comportamento
        padrão de tiling lado-a-lado. Se a validação ao vivo mostrar que o cliente deixa buraco,
        trocar `live_rooms()` por uma versão que preserve a coluna. PRECISA de validação ao vivo.
    """

    def __init__(self, *, ttl=90.0, clock=time.time):
        self._seq = {}          # room -> ordinal de primeira aparição (NUNCA muda; append-only)
        self._last = {}         # room -> ts do último evento (epoch s)
        self._dead = set()      # salas marcadas como bustadas (podadas de n_rooms)
        self._n = 0
        self.ttl = ttl          # segundos de atraso (relativo à + recente) p/ considerar bustada
        self._clock = clock

    def touch(self, room, ts=None):
        """Registra atividade da sala (chamar a cada evento). Mantém a ordem de 1ª aparição,
        atualiza o último ts e REVIVE a sala se ela estava podada."""
        if room is None:
            return
        if room not in self._seq:
            self._seq[room] = self._n
            self._n += 1
        self._last[room] = ts if ts is not None else self._clock()
        self._dead.discard(room)

    def mark_dead(self, room):
        """Poda explícita (p/ quando acharmos um sinal real de 'mesa fechada' ao vivo)."""
        if room is not None:
            self._dead.add(room)

    def _prune(self):
        if self.ttl is None or not self._last:
            return
        newest = max(self._last.values())
        for room, ts in self._last.items():
            if newest - ts > self.ttl:
                self._dead.add(room)

    def live_rooms(self):
        """Salas VIVAS na ordem estável de 1ª aparição (append-only), já podando as bustadas."""
        self._prune()
        return [r for r in sorted(self._seq, key=self._seq.get) if r not in self._dead]

    def all_rooms(self):
        """Todas as salas já vistas, na ordem de 1ª aparição (inclui as bustadas)."""
        return [r for r in sorted(self._seq, key=self._seq.get)]

    def n_rooms(self):
        """Quantidade de mesas VIVAS (mínimo 1 — a camada de clique nunca divide por 0)."""
        return max(1, len(self.live_rooms()))

    def index(self, room):
        """Coluna-na-tela (0-based) da sala na lista viva compactada; 0 se desconhecida/bustada."""
        live = self.live_rooms()
        return live.index(room) if room in live else 0


class SupremaRouter:
    """Mantém um SupremaTable por sala. `feed_json` roteia pelo roomID e devolve a sala afetada
    (ou None se o evento não tem sala). Propaga o hero_uid aprendido p/ TODAS as mesas."""

    def __init__(self, bb_chips=None, hero_uid=None):
        self.bb_chips = bb_chips
        self.hero_uid = hero_uid
        self.tables = {}                  # room -> SupremaTable

    def feed_json(self, msg):
        if not isinstance(msg, dict):
            return None
        # uid na RAIZ = o herói (mesma conta em todas as mesas) -> propaga p/ todas.
        if msg.get("uid") is not None and msg["uid"] != self.hero_uid:
            self.hero_uid = msg["uid"]
            for t in self.tables.values():
                t.hero_uid = self.hero_uid
        room = room_of(msg)
        if room is None:
            return None
        t = self.tables.get(room)
        if t is None:
            t = SupremaTable(bb_chips=self.bb_chips, hero_uid=self.hero_uid)
            self.tables[room] = t
        elif self.hero_uid is not None and t.hero_uid is None:
            t.hero_uid = self.hero_uid
        t.feed_json(msg)
        return room

    def rooms(self):
        return list(self.tables)

    def table(self, room):
        return self.tables.get(room)

    def states(self):
        """{room: (state|None, hero_ou_motivo)} de todas as mesas — p/ observar/decidir por sala."""
        return {room: t.to_table_state() for room, t in self.tables.items()}
