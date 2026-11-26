"""H2N do PPPoker (Henrique) — TRACKER de mãos próprio, alimentado pelos SNAPSHOTS do estado
protobuf (o mesmo dict que o emitter grava em logs/estado_mesa.json).

Consome o estado ao longo do tempo (uma leitura por tick), detecta INÍCIO/FIM de cada mão do
herói e grava a mão fechada no NOSSO banco (JSONL em logs/pppoker_hands/). DB INDEPENDENTE do
H2N externo [[nvt-tracker-proprio]] — formato próprio, feito p/ estudar as nossas mãos depois.

PURO/injetável (clock e destino de saída) -> testável 100% offline com estados sintéticos ou a
captura de exemplo. NÃO captura tela, NÃO clica: só observa o estado que o agente já leu.

REUSO (sem duplicar):
  - ppp_cards.decode_cards        : int do protobuf -> 'Qh'
  - protobuf_state                : posição/stack(bb) do herói e rua pelo board (mesmo cérebro)
  - hand_recorder.HandRecorder    : GRAVADOR durável em JSONL (append-only + rotação) e load_hands
  A detecção de borda de mão a partir de snapshots é o que este módulo ACRESCENTA — o
  hand_recorder é um sink passivo (recebe ações já parseadas), não vê snapshots.

Como o herói é identificado: pelo `uid` (APRENDIDO do assento com 2 cartas face-up, estável
entre mãos/mesas) ou, na falta dele, pelo assento único com 2 cartas face-up. A MÃO é a dupla de
cartas do herói (muda a cada mão nova) — mesma âncora que o pppoker_agente usa p/ o anti-thrash.

FORMATO de cada mão gravada (dict por linha no JSONL):
    {source:'pppoker', roomid, room, hand_id, ts_start, ts_end,
     hero:{uid, seat, name, position, stack_bb_start, stack_chips_start,
           stack_bb_end, stack_chips_end, cards:['As','Kd']},
     blinds:{sb_chips, bb_chips}, n_players_start, opponents:[uid,...],
     board:{flop:[...], turn:[...], river:[...]}, board_full:[...],
     pot_chips_final, pot_bb_final, reached_street,
     actions:[{ts, street, seat, uid, is_hero, act, bet_chips}, ...]}
"""
from __future__ import annotations

import os
import time

import protobuf_state as PB
from ppp_cards import decode_cards

try:                                             # reuso do gravador durável
    from hand_recorder import HandRecorder as _DurableRecorder, load_hands as _load_hands
except Exception:                                # pragma: no cover
    _DurableRecorder = None
    _load_hands = None

DEFAULT_DIR = os.path.join("logs", "pppoker_hands")
DEFAULT_FILE = "pppoker_hands.jsonl"
_META_PREFIX = "_"


def _board_decoded(table):
    ints = [x for x in ((table or {}).get("board") or [])
            if isinstance(x, int) and 2 <= (x & 0xFF) <= 14]
    return decode_cards(ints)


def _street_of_board(board_cards):
    n = len(board_cards)
    return ("river" if n >= 5 else "turn" if n == 4 else "flop" if n == 3 else "preflop")


def _hero_pair(entry, hero_uid):
    """Dupla de cartas do herói nesta entry (['As','Kd']) ou [] se não visível/ambíguo.
    Por uid quando conhecido (robusto a showdown); senão pelo assento único com 2 face-up."""
    players = [p for p in ((entry or {}).get("players") or []) if isinstance(p, dict)]
    if hero_uid is not None:
        p = next((q for q in players if q.get("uid") == hero_uid), None)
        return decode_cards(p.get("cards") or []) if p else []
    cand = [p for p in players if len(decode_cards(p.get("cards") or [])) == 2]
    return decode_cards(cand[0].get("cards") or []) if len(cand) == 1 else []


def _learn_hero_uid(entry):
    players = [p for p in ((entry or {}).get("players") or []) if isinstance(p, dict)]
    cand = [p for p in players if len(decode_cards(p.get("cards") or [])) == 2
            and p.get("uid") is not None]
    return cand[0].get("uid") if len(cand) == 1 else None


class HandRecorder:
    """Gravador de mãos do PPPoker alimentado por SNAPSHOTS do estado protobuf.

    Reconstrói a mão a partir das leituras ao longo do tempo: detecta a mão nova pela mudança
    da dupla do herói (ou reset do board), acumula board por rua, pote (máximo visto) e um
    rastro das AÇÕES observáveis (mudanças de aposta/act por assento entre snapshots — a coleta
    é por polling, então é o que dá p/ ver sem perder a mão). Fecha e grava no commit.

    Injetável p/ teste: `clock` (relógio) e `out_dir`/`filename` (destino). Por baixo usa
    hand_recorder.HandRecorder como writer durável (JSONL append-only + rotação); dá p/ passar
    um `writer` próprio com .commit(dict) nos testes."""

    def __init__(self, *, out_dir=DEFAULT_DIR, filename=DEFAULT_FILE, clock=None,
                 writer=None, hero_uid=None):
        self.clock = clock or time.time
        self.path = os.path.join(out_dir, filename)
        self.hero_uid = hero_uid
        if writer is not None:
            self._writer = writer
        elif _DurableRecorder is not None:
            self._writer = _DurableRecorder(path=self.path)
        else:                                    # pragma: no cover
            self._writer = None
        self._open = {}                          # roomid -> mão em andamento (dict)
        self._seq = 0                            # contador p/ hand_id

    # ---------------------------------------------------------------- API pública
    def observe(self, estado):
        """Processa UM snapshot do estado inteiro ({roomid: entry}). Devolve a lista de mãos
        FECHADAS neste tick (0+). Chame a cada leitura do estado_mesa.json."""
        closed = []
        if not isinstance(estado, dict):
            return closed
        if "players" in estado:                  # entry solta sem roomid
            c = self.observe_table("mesa", estado)
            return [c] if c else []
        for roomid, entry in estado.items():
            if str(roomid).startswith(_META_PREFIX):
                continue
            if not (isinstance(entry, dict) and "players" in entry):
                continue
            c = self.observe_table(roomid, entry)
            if c:
                closed.append(c)
        return closed

    def observe_table(self, roomid, entry):
        """Processa o snapshot de UMA mesa. Devolve a mão FECHADA se este snapshot encerrou a
        anterior (e abriu outra), senão None. Fecha a mão quando a dupla do herói MUDA, ou
        quando o board RESETA (tinha cartas e voltou a 0) numa mesa com mão aberta."""
        rid = str(roomid)
        # aprende o uid do herói assim que aparecer (vale p/ todas as mesas)
        if self.hero_uid is None:
            uid = _learn_hero_uid(entry)
            if uid is not None:
                self.hero_uid = uid

        table = (entry or {}).get("table") or {}
        board = _board_decoded(table)
        pair = _hero_pair(entry, self.hero_uid)
        cur = self._open.get(rid)
        closed = None

        if pair:                                 # herói tem cartas visíveis nesta mesa
            if cur is None:
                self._open[rid] = self._begin(rid, entry)
            elif cur["hero"]["cards"] and cur["hero"]["cards"] != pair:
                closed = self._commit(cur)       # mão nova (dupla mudou) -> fecha a anterior
                self._open[rid] = self._begin(rid, entry)
            else:
                if not cur["hero"]["cards"]:
                    cur["hero"]["cards"] = pair
                self._update(cur, entry)
        else:                                    # sem cartas visíveis do herói
            if cur is not None:
                had_board = bool(cur["board_full"])
                if had_board and len(board) == 0:
                    closed = self._commit(cur)   # board resetou -> mão anterior acabou
                    self._open.pop(rid, None)
                else:
                    self._update(cur, entry)     # mantém a mão aberta; atualiza board/pote
        return closed

    def flush(self):
        """Fecha e grava TODAS as mãos ainda abertas (fim de sessão). Devolve a lista gravada."""
        out = []
        for rid in list(self._open):
            out.append(self._commit(self._open.pop(rid)))
        return out

    def load(self):
        """Relê o banco gravado (lista de dicts). Reusa hand_recorder.load_hands."""
        if _load_hands is not None:
            return _load_hands(self.path)
        return []                                # pragma: no cover

    # ---------------------------------------------------------------- internos
    def _begin(self, rid, entry):
        self._seq += 1
        table = (entry or {}).get("table") or {}
        bb = PB.bb_chips(table)
        sb = table.get("sb")
        pair = _hero_pair(entry, self.hero_uid)
        hero_pl = self._hero_player(entry)
        pos, stack_bb = self._hero_pos_stack(entry)
        stack_chips = (hero_pl or {}).get("stack")
        ps = [p for p in (entry.get("players") or []) if isinstance(p, dict)]
        opp = [p.get("uid") for p in ps
               if p.get("uid") is not None and p.get("uid") != (hero_pl or {}).get("uid")]
        ts = self.clock()
        board = _board_decoded(table)
        rec = dict(
            source="pppoker", roomid=rid, room=(entry.get("room") or ""),
            hand_id="%s#%d" % (rid, self._seq), ts_start=ts, ts_end=ts,
            hero=dict(uid=(hero_pl or {}).get("uid"), seat=(hero_pl or {}).get("seat"),
                      name=(hero_pl or {}).get("name"), position=pos,
                      stack_bb_start=stack_bb, stack_chips_start=stack_chips,
                      stack_bb_end=stack_bb, stack_chips_end=stack_chips, cards=pair),
            blinds=dict(sb_chips=sb, bb_chips=bb),
            n_players_start=len(ps), opponents=opp,
            board=dict(flop=[], turn=[], river=[]), board_full=[],
            pot_chips_final=table.get("pot"), pot_bb_final=None,
            reached_street="preflop", actions=[],
        )
        rec["_last_bets"] = {}                    # estado interno p/ diff de ações (removido no commit)
        self._apply_board(rec, board)
        self._update(rec, entry)
        return rec

    def _update(self, rec, entry):
        table = (entry or {}).get("table") or {}
        rec["ts_end"] = self.clock()
        board = _board_decoded(table)
        self._apply_board(rec, board)
        # pote: guarda o MAIOR visto (o pote só cresce dentro da mão)
        pot = table.get("pot")
        if isinstance(pot, (int, float)):
            prev = rec["pot_chips_final"]
            if not isinstance(prev, (int, float)) or pot > prev:
                rec["pot_chips_final"] = pot
        # stack do herói ao fim (último visto)
        hero_pl = self._hero_player(entry)
        if hero_pl is not None:
            if isinstance(hero_pl.get("stack"), (int, float)):
                rec["hero"]["stack_chips_end"] = hero_pl.get("stack")
            _pos, stack_bb = self._hero_pos_stack(entry)
            if stack_bb is not None:
                rec["hero"]["stack_bb_end"] = stack_bb
            if rec["hero"]["position"] is None and _pos is not None:
                rec["hero"]["position"] = _pos
        # ações observáveis: registra quando a aposta de um assento MUDA entre snapshots
        street = _street_of_board(board)
        last = rec["_last_bets"]
        for p in (entry.get("players") or []):
            if not isinstance(p, dict):
                continue
            uid = p.get("uid")
            bet = p.get("bet")
            key = uid if uid is not None else p.get("seat")
            if key is None:
                continue
            if last.get(key) != bet and isinstance(bet, (int, float)):
                rec["actions"].append(dict(
                    ts=rec["ts_end"], street=street, seat=p.get("seat"), uid=uid,
                    is_hero=(uid is not None and uid == rec["hero"]["uid"]),
                    act=p.get("act"), bet_chips=bet))
                last[key] = bet

    def _apply_board(self, rec, board):
        if len(board) >= len(rec["board_full"]):
            rec["board_full"] = list(board)
            rec["board"]["flop"] = board[:3] if len(board) >= 3 else rec["board"]["flop"]
            rec["board"]["turn"] = [board[3]] if len(board) >= 4 else rec["board"]["turn"]
            rec["board"]["river"] = [board[4]] if len(board) >= 5 else rec["board"]["river"]
            rec["reached_street"] = _street_of_board(board)

    def _hero_player(self, entry):
        ps = [p for p in ((entry or {}).get("players") or []) if isinstance(p, dict)]
        if self.hero_uid is not None:
            p = next((q for q in ps if q.get("uid") == self.hero_uid), None)
            if p is not None:
                return p
        cand = [p for p in ps if len(decode_cards(p.get("cards") or [])) == 2]
        return cand[0] if len(cand) == 1 else None

    def _hero_pos_stack(self, entry):
        """(posição, stack_bb) do herói via protobuf_state.build_table_state (mesmo cérebro).
        (None, None) quando o estado não permite derivar (abstém, não chuta)."""
        try:
            state, _hero = PB.build_table_state(entry)
        except Exception:
            return None, None
        if not isinstance(state, dict):
            return None, None
        pos = (state.get("positions") or {}).get("hero")
        stack_bb = ((state.get("seats") or {}).get("hero") or {}).get("stack_bb")
        return pos, (round(stack_bb, 2) if isinstance(stack_bb, (int, float)) else None)

    def _commit(self, rec):
        rec.pop("_last_bets", None)
        bb = (rec.get("blinds") or {}).get("bb_chips")
        pot = rec.get("pot_chips_final")
        if isinstance(bb, (int, float)) and bb and isinstance(pot, (int, float)):
            rec["pot_bb_final"] = round(pot / bb, 2)
        if self._writer is not None:
            try:
                self._writer.commit(dict(rec))
            except Exception:                    # gravação nunca derruba o tracker
                pass
        return rec


def load_hands(path=None):
    """Relê o banco de mãos do PPPoker (lista de dicts). Reusa hand_recorder.load_hands."""
    p = path or os.path.join(DEFAULT_DIR, DEFAULT_FILE)
    if _load_hands is not None:
        return _load_hands(p)
    return []                                    # pragma: no cover
