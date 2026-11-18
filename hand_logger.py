"""Agrega os frames do OBSERVADOR em MÃOS (por hand_id) e grava via HandRecorder —
a fundação do tracker/histórico (estudo de linhas + DB de adversários + field).

Snapshot-based: por mão (fronteira = `hand_id` do nameplate do torneio), guarda o
CONTEXTO (torneio, herói+cartas+posição+stack, ADVERSÁRIOS por id/nick, board, pote)
e o RASTRO de recomendação do cérebro (o que o bot decidiu no spot). A sequência
EXATA de ações (quem apostou/subiu quando) é fase 2; o que já temos aqui alimenta o
DB de adversários e o estudo de linhas (spot+decisão) — análise em hand_db.py.

PURO: recebe o result do observador e grava. Não captura tela, não clica.
Uso: logger = LiveHandLogger(HandRecorder()); a cada frame logger.observe(tk, result);
ao encerrar logger.flush().
"""
import re

_STACK_RX = re.compile(r'\d[\d.,]*\s*BB', re.I)
_WORD_RX = re.compile(r'[A-Za-z][A-Za-z0-9_]{2,}')
_NOISE = {'bb', 'just', 'do', 'it', 'ev', 'ns', 'nie', 'xe', 'all', 'in'}


def clean_nameplate(raw):
    """Melhor-esforço: extrai o nick do adversário do `raw` do nameplate (tira o
    stack e ruído de OCR). Devolve o maior token plausível, ou None."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = _STACK_RX.sub(' ', raw)
    toks = [t for t in _WORD_RX.findall(s) if t.lower() not in _NOISE]
    return max(toks, key=len) if toks else None


class LiveHandLogger:
    """Junta frames numa mão por `hand_id` e fecha (commit) quando a mão muda."""

    def __init__(self, recorder):
        self._rec = recorder
        self._open = {}            # table_key -> mão em acumulação

    def observe(self, table_key, result):
        """Processa UM frame de UMA mesa. Sem efeito se não for mesa ou sem hand_id."""
        if not isinstance(result, dict) or not result.get('is_table'):
            return
        hand = result.get('hand') or {}
        hid = hand.get('hand_id')
        if not hid:
            return
        cur = self._open.get(table_key)
        if cur and cur['hand_id'] != hid:          # a mão mudou -> fecha a anterior
            self._commit(table_key)
            cur = None
        if cur is None:
            cur = self._open[table_key] = dict(
                hand_id=hid, table_key=table_key, hand_number=hand.get('hand_number'),
                table_ref=hand.get('table_ref'), tournament={}, hero={},
                opponents={}, board={}, advice=None)
        self._accumulate(cur, result)

    def _accumulate(self, cur, result):
        ts = result.get('table_state') or {}
        positions = ts.get('positions') or {}
        seats = ts.get('seats') or {}
        tour = result.get('tournament') or {}
        if tour.get('name'):
            cur['tournament'] = {k: tour.get(k) for k in
                                 ('name', 'is_pko', 'is_mystery', 'paid', 'players_left', 'hero_rank')}
        cards = result.get('hero_cards')
        hero_seat = seats.get('hero') or {}
        if cards or positions.get('hero'):
            prev = cur.get('hero') or {}
            cur['hero'] = dict(position=positions.get('hero') or prev.get('position'),
                               cards=list(cards) if cards else prev.get('cards'),
                               stack_bb=hero_seat.get('stack_bb') if hero_seat.get('stack_bb') is not None
                               else prev.get('stack_bb'))
        for s, info in seats.items():
            if s == 'hero' or not (isinstance(info, dict) and info.get('occupied')):
                continue
            name = clean_nameplate(info.get('raw'))
            cur['opponents'][s] = dict(id=name, seat=s, position=positions.get(s),
                                       stack_bb=info.get('stack_bb'),
                                       nameplate_raw=info.get('raw'))
        board = result.get('board') or {}
        if board.get('cards') and board.get('street'):
            cur['board'][str(board['street']).lower()] = list(board['cards'])
        adv = result.get('advice') or {}
        if adv.get('recommended'):
            cur['advice'] = {k: adv.get(k) for k in
                             ('recommended', 'sizing', 'spot', 'hero_position',
                              'validated', 'ev', 'ev_unit', 'source', 'status', 'node_id')}

    def _commit(self, table_key):
        cur = self._open.pop(table_key, None)
        if not cur:
            return None
        h = self._rec.begin(hand_id=cur['hand_id'], table_key=cur['table_key'],
                            tournament=cur.get('tournament') or {},
                            hero=cur.get('hero') or {},
                            opponents=list(cur['opponents'].values()))
        for street, cards in (cur.get('board') or {}).items():
            h.board(street, cards)
        a = cur.get('advice')
        if a:
            street = 'preflop'
            for s in ('river', 'turn', 'flop'):
                if s in (cur.get('board') or {}):
                    street = s
                    break
            h.advice(street=street, recommended=a.get('recommended'), source=a.get('source'),
                     ev_bb=a.get('ev'), validated=a.get('validated'), spot=a.get('spot'),
                     sizing=a.get('sizing'), node_id=a.get('node_id'))
        self._rec.commit(h)
        return cur['hand_id']

    def flush(self):
        """Fecha todas as mãos abertas (ex.: ao encerrar o observador)."""
        for tk in list(self._open):
            self._commit(tk)
