"""Percepção PRÉ-FLOP via PROTOBUF (não OCR).

Converte o estado lido da memória do PPPoker (HoldemManager, emitido por
research/ppp_il2cpp/emitir_seats.* em logs/estado_mesa.json) para o MESMO
`table_state` que `PreflopAdvisor.advise_from_reading` consome — e decide pelo
MESMO cérebro/roteamento. Objetivo: acabar a classe "não leu a ação/carta"
(gaveta errada) — aqui cartas, apostas e posições vêm EXATAS da memória.

Entrada (uma mesa do estado_mesa.json):
  {ts, room, table:{dealer, sbseat, bbseat, sb, minraise, maxraise},
   players:[{seat, uid, name, stack(_handChips), sit(_isSittingOut),
             bet(_betChips), act(_actionType), hascard, cards:[int,...]}]}

Saída: um table_state {positions, seats, bets, phase} + hero_cards decodificadas.
O hero é o assento com 2 cartas FACE-UP (as únicas visíveis). Posições vêm do
dealer/SB/BB que o protobuf JÁ dá; se a derivação não bater com o SB/BB do
protobuf -> ABSTÉM (não chuta posição). READ-ONLY; nenhuma ação aqui.
"""
from __future__ import annotations

from ppp_cards import decode_cards

# Ordem canônica RangeLab (idêntica a table_reading.dealer_button._CORE e
# hrc_ingest.POSITIONS; um teste trava a igualdade p/ não divergirem).
_CORE = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')


def bb_chips(table) -> float | None:
    """Fichas por BIG BLIND = 2 * small blind (_smallBlind). None se desconhecido."""
    sb = (table or {}).get('sb')
    if not isinstance(sb, (int, float)) or sb <= 0:
        return None
    return 2.0 * float(sb)


def _active(players):
    """Jogadores NA MÃO = que RECEBERAM cartas nesta mão (_hasCard). Sentados-fora /
    esperando têm hascard=0 e NÃO entram — senão um assento vazio entre o SB e o BB
    quebraria a ordem das posições (visto ao vivo: s1/s7 com hascard=0 fora da mão)."""
    return [p for p in (players or []) if p.get('uid') and p.get('hascard')]


def assign_positions(occupied_ids, dealer, sbseat, bbseat):
    """Rotula os assentos ATIVOS (ids numéricos do protobuf) com as posições RangeLab,
    ancorando no DEALER (botão), em ordem horária, com os rótulos canônicos (_CORE) —
    igual table_reading.dealer_button.derive_positions (labels=('SB','BB')+_CORE[-n:-2];
    dealer=BTN por último; heads-up: dealer=SB).

    Ancora no DEALER, NÃO no SB: o botão está SEMPRE num jogador ativo (confiável),
    enquanto `_nowSmallBlindSeat`/`_nowBigBlindSeat` do protobuf podem ficar STALE num
    assento que acabou de bustar (visto no HU: sb apontava p/ um assento fora da mão
    -> abstinha). Cross-check LEVE com o bbseat quando ele está ativo. Devolve {} se
    não der (dealer ausente/contagem inválida) — aí abstém, nunca chuta posição."""
    ids = sorted(set(occupied_ids))
    n = len(ids)
    if n < 2 or n > 9 or dealer not in ids:
        return {}
    i = ids.index(dealer)
    if n == 2:
        order, labels = [ids[i], ids[(i + 1) % n]], ('SB', 'BB')   # HU: o dealer é o SB
    else:
        order = ids[i + 1:] + ids[:i + 1]          # dealer por ÚLTIMO (BTN)
        labels = ('SB', 'BB') + _CORE[-n:-2]
    pos = dict(zip(order, labels))
    # cross-check leve: se o BB do protobuf está ATIVO e não bate, descarta (não chuta).
    # (se o bbseat também estiver stale/fora dos ativos, ignora e confia no dealer.)
    if bbseat in ids and pos.get(bbseat) != 'BB':
        return {}
    return pos


def hero_seat(players):
    """O assento do HERO = o único com 2 cartas FACE-UP (decodificáveis). None se
    nenhum/ambíguo (0 ou >1 com 2 cartas -> não dá p/ saber)."""
    cand = [p for p in (players or [])
            if len(decode_cards(p.get('cards') or [])) == 2]
    return cand[0].get('seat') if len(cand) == 1 else None


def build_table_state(entry):
    """(table_state, hero_cards) pronto p/ advise_from_reading, ou (None, motivo).

    table_state = {positions:{seat_key->pos, 'hero'->pos}, seats:{seat_key->
    {stack_bb, occupied}}, bets:[{seat, bet_bb}], phase}. O hero usa a chave
    literal 'hero' (exigida por advise_from_reading/from_table_state)."""
    if not isinstance(entry, dict):
        return None, 'ENTRY_INVALIDO'
    table = entry.get('table') or {}
    bb = bb_chips(table)
    if bb is None:
        return None, 'SB_DESCONHECIDO'
    players = _active(entry.get('players'))
    if len(players) < 2:
        return None, 'POUCOS_JOGADORES'
    hs = hero_seat(players)
    if hs is None:
        return None, 'HERO_CARDS_UNKNOWN'          # mesma semântica do OCR
    pos_by_seat = assign_positions([p['seat'] for p in players],
                                   table.get('dealer'), table.get('sbseat'), table.get('bbseat'))
    if not pos_by_seat or hs not in pos_by_seat:
        return None, 'POSICOES_INCONSISTENTES'     # não chuta -> abstém

    def key(p):
        return 'hero' if p['seat'] == hs else 'seat%s' % p['seat']

    positions, seats, bets = {}, {}, []
    for p in players:
        k = key(p)
        positions[k] = pos_by_seat[p['seat']]
        stack = p.get('stack')
        seats[k] = dict(stack_bb=(float(stack) / bb if isinstance(stack, (int, float)) else None),
                        occupied=True, source='protobuf')
        bet = p.get('bet')
        bets.append(dict(seat=k, bet_bb=(float(bet) / bb if isinstance(bet, (int, float)) else 0.0)))

    hero_cards = decode_cards(next(p['cards'] for p in players if p['seat'] == hs))
    # POS-FLOP por MEMORIA (Eduardo 19/11): board + to_call + pote vindos do protobuf
    # (emitir_seats). to_call é EXATO; pote é derivado (carry+bets); board = RoundStartBRC.
    board_ints = [x for x in (table.get('board') or [])
                  if isinstance(x, int) and 2 <= (x & 0xff) <= 14]
    board_cards = decode_cards(board_ints) if board_ints else []
    n = len(board_cards)
    street = ('RIVER' if n >= 5 else 'TURN' if n == 4 else 'FLOP' if n == 3 else 'PREFLOP')
    tocall, pot = table.get('tocall'), table.get('pot')
    to_call_bb = (round(float(tocall) / bb, 2) if isinstance(tocall, (int, float)) else None)
    pot_bb = (round(float(pot) / bb, 2) if isinstance(pot, (int, float)) and pot else None)
    state = dict(positions=positions, seats=seats, bets=bets, phase='mid',
                 source='protobuf', scope=('POSTFLOP_PROTOBUF' if n >= 3 else 'PREFLOP_PROTOBUF'),
                 board=board_cards, street=street,
                 to_call={'to_call_bb': to_call_bb}, pot={'pot_bb': pot_bb})
    return state, hero_cards


def advise_from_protobuf(entry, advisor, **kwargs):
    """Decide o PRÉ-FLOP a partir do estado protobuf, pelo MESMO roteamento do OCR
    (advise_from_reading). Devolve o dict do advisor, ou uma ABSTENÇÃO explícita
    {status:'ABSTAIN', reason} quando o estado não dá p/ decidir (sem chutar)."""
    state, hero_or_reason = build_table_state(entry)
    if state is None:
        return dict(status='ABSTAIN', reason=hero_or_reason, source='protobuf')
    board = state.get('board') or []
    if len(board) >= 3:
        # POS-FLOP por memória: board/to_call/pote EXATOS -> advise_postflop (não OCR).
        from postflop_advisor import advise_postflop
        import postflop_sizing
        adv = advise_postflop(state, hero_or_reason, board, street=state.get('street'),
                              mode=kwargs.get('mode', 'chip_ev'), stage=kwargs.get('stage', 'mid'))
        if isinstance(adv, dict):
            _hero_stk = (state.get('seats', {}).get('hero') or {}).get('stack_bb')
            postflop_sizing.enforce(adv, pot_bb=(state.get('pot') or {}).get('pot_bb'),
                                    stack_bb=_hero_stk, spr=adv.get('spr'))
    else:
        adv = advisor.advise_from_reading(state, hero_or_reason, **kwargs)
    if isinstance(adv, dict):
        # carrega as cartas EXATAS (protobuf) na decisão -> o executor/contrato usam a
        # leitura da memória, não a do OCR (que pode ter falhado).
        adv.setdefault('hero_cards', hero_or_reason)
        adv['perception'] = 'protobuf'
    return adv
