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
    """Jogadores NA MÃO: com uid e não sentados fora (_isSittingOut)."""
    return [p for p in (players or []) if p.get('uid') and not p.get('sit')]


def assign_positions(occupied_ids, dealer, sbseat, bbseat):
    """Rotula os assentos (ids numéricos do protobuf) com as posições RangeLab,
    ancorando no SB e andando no sentido horário (do SB o próximo é o BB). Replica
    EXATAMENTE a regra de table_reading.dealer_button.derive_positions (labels =
    ('SB','BB') + _CORE[-n:-2], dealer = BTN por último; heads-up: dealer = SB).

    AUTO-VALIDA: a derivação tem que recair no SB/BB/BTN que o protobuf informou;
    senão devolve {} (abstém — nunca chuta posição e 'abre gaveta errada')."""
    ids = sorted(set(occupied_ids))
    n = len(ids)
    if n < 2 or n > 9:
        return {}
    if sbseat not in ids or bbseat not in ids or dealer not in ids:
        return {}
    si = ids.index(sbseat)
    # sentido horário: do SB o PRÓXIMO assento ativo é o BB (asc ou desc com wrap)
    if ids[(si + 1) % n] == bbseat:
        step = 1
    elif ids[(si - 1) % n] == bbseat:
        step = -1
    else:
        return {}                      # SB e BB não são adjacentes na ordem de assentos
    seq = [ids[(si + step * k) % n] for k in range(n)]   # seq[0]=SB, seq[1]=BB, ...
    if n == 2:
        labels = ('SB', 'BB')          # heads-up: o dealer é o SB
    else:
        labels = ('SB', 'BB') + _CORE[-n:-2]
        if seq[-1] != dealer:          # o último rótulo é BTN -> tem que ser o dealer
            return {}
    return dict(zip(seq, labels))


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
    state = dict(positions=positions, seats=seats, bets=bets, phase='mid',
                 source='protobuf', scope='PREFLOP_PROTOBUF')
    return state, hero_cards


def advise_from_protobuf(entry, advisor, **kwargs):
    """Decide o PRÉ-FLOP a partir do estado protobuf, pelo MESMO roteamento do OCR
    (advise_from_reading). Devolve o dict do advisor, ou uma ABSTENÇÃO explícita
    {status:'ABSTAIN', reason} quando o estado não dá p/ decidir (sem chutar)."""
    state, hero_or_reason = build_table_state(entry)
    if state is None:
        return dict(status='ABSTAIN', reason=hero_or_reason, source='protobuf')
    adv = advisor.advise_from_reading(state, hero_or_reason, **kwargs)
    if isinstance(adv, dict):
        # carrega as cartas EXATAS (protobuf) na decisão -> o executor/contrato usam a
        # leitura da memória, não a do OCR (que pode ter falhado).
        adv.setdefault('hero_cards', hero_or_reason)
        adv['perception'] = 'protobuf'
    return adv
