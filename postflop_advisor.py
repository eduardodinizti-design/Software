"""Conselho pós-flop EXPLORATÓRIO (observação, nunca executa).

Motor de heurística fundamentada — NÃO é um solver. Decide sobre primitivas
verificáveis: força da mão feita (postflop_eval), outs/draws pela regra do 2 e do
4, pot odds, MDF e SPR (fundamentos da skill poker-fundamentos-posflop). Onde a
decisão depende de ler o vilão (bluffcatch marginal contra aposta grande), ABSTÉM
em vez de inventar um range — o projeto não fabrica números de solver. Toda saída
carrega `execution_allowed=False`; a execução pós-flop é uma etapa futura separada,
validada à parte (igual ao pré-flop, que só clicou depois de aconselhar).

`advise_postflop(table_state, hero, board, ...)` devolve o mesmo formato de
contrato do pré-flop: status ADVICE/ABSTAIN, `recommended`, métricas e `caveats`.
"""
import postflop_texture
import postflop_exploit
import postflop_turn_barrel
import postflop_river
import postflop_cbet_bb
from postflop_eval import classify_board, hand_strength, narrow_to_continuation
from preflop_equity import required_equity, equity_vs_range, hand_to_combos
from hud_exploit import classify_villain, exploit_caveats
from multiway_equity import (apply_multiway_penalty, cbet_bluff_blocked,
                             count_opponents, penalty_pct)
from postflop_adjustments import (geometric_bet_pct, geometric_street_plan, out_manipulation,
                                  pool_adjusted_mdf, remaining_streets, scare_present)

BASE_CAVEATS = ('EXPLORATORY_NOT_FOR_EXECUTION', 'POSTFLOP_HEURISTIC_NO_SOLVER',
                'SINGLE_FRAME_NO_VILLAIN_MODEL')

# Famílias de força da mão feita.
_STRONG = ('set', 'trips', 'two_pair', 'overpair', 'straight', 'flush',
           'full_house', 'quads', 'straight_flush')
_MARGINAL = ('second_pair', 'third_pair', 'low_pair', 'underpair')
# Ordem de ação PÓS-FLOP (quem age por ÚLTIMO = mais em posição): SB<BB<...<CO<BTN.
_POS_RANK = {'SB': 0, 'BB': 1, 'UTG': 2, 'UTG1': 3, 'UTG2': 4, 'UTG+1': 3, 'UTG+2': 4,
             'LJ': 5, 'MP': 5, 'MP1': 5, 'MP2': 6, 'HJ': 6, 'CO': 7, 'BTN': 8, 'BU': 8}


def _hero_in_position(positions):
    """True/False se o hero age por ÚLTIMO (IP) vs os vilões pós-flop; None se indeterminado."""
    if not positions:
        return None
    hp = _POS_RANK.get(positions.get('hero'))
    if hp is None:
        return None
    vr = [_POS_RANK[p] for k, p in positions.items() if k != 'hero' and p in _POS_RANK]
    return (hp > max(vr)) if vr else None

# Deságio aplicado ao decidir um CALL pela equity vs o range PRÉ-FLOP do vilão: o
# range pré-flop é mais largo que o range que realmente aposta/continua pós-flop,
# então a equity crua até o showdown SUPERESTIMA a do hero. Exigir folga extra evita
# pagar demais. Aposta grande/overbet (pot_odds>0.40) tem range polarizado — o
# pré-flop erra demais lá, então continua abstendo mesmo com range.
_CALL_HAIRCUT = 0.05
_BIG_BET_POT_ODDS = 0.40
# OVERBET: aposta > ~1.2x pote (pot_odds > 0.55 = exige >55% equity). O guia (cap.14) defende
# BARRIL NORMAL (≤ pote) com top pair/par médio, mas NÃO paga bluff-catcher vs overbet polarizada.
# Sem leitura, flop/turn DEFENDE o barril normal e FOLDA só a overbet (e o river, que o pool sub-blefa).
_OVERBET_POT_ODDS = 0.55
# TETO do HERO-CALL em runout de blefe (Eduardo 24/11): mesmo no campo mole + draw morto, o herói
# paga só até um overbet MODERADO (~1.7x pote, pot_odds<=0.63). Jam gigante acima disso = mesmo o
# pior jogador tem mais valor que blefe lá -> folda (disciplina anti-callstation, "não é spew").
_HERO_CALL_MAX_POT_ODDS = 0.63
# Equity mínima (vs range) para AUMENTAR por valor com uma mão de categoria forte.
# Abaixo disso (mas acima das pot odds) paga; se nem as pot odds bater, folda — a
# categoria não manda sozinha quando a equity contra o range diz o contrário.
_VALUE_RAISE_MIN_EQUITY = 0.60
# 3bet pot HU: abaixo deste SPR, mãos feitas fortes (até top pair) COMETEM (pote já
# grande, pouco atrás). Acima, top pair enfrenta um range polarizado e vira bluffcatch.
SPR_COMMIT_3BET = 4.0


def _normalize_range(villain_range):
    """Aceita lista de (combo, peso) OU de strings de mão ('AA','AKs','72o'); devolve
    [(frozenset, peso)] p/ o equity_vs_range (peso 1.0 p/ strings). None se vazio."""
    if not villain_range:
        return None
    out = []
    for item in villain_range:
        if isinstance(item, str):
            h = item.strip()
            # 'AK' (2 chars, ranks distintos) = suited + offsuit; 'AKs'/'AKo'/'AA' literais.
            variants = ([h + 's', h + 'o'] if len(h) == 2 and h[0].upper() != h[1].upper()
                        else [h])
            for v in variants:
                out.extend((c, 1.0) for c in hand_to_combos(v))
        else:
            combo, weight = item
            out.append((combo, weight))
    return out or None


def _abstain(reason, **extra):
    return dict(status='ABSTAIN', reason=reason, phase='postflop', exploratory=True,
                execution_allowed=False, caveats=list(BASE_CAVEATS), **extra)


def _uncovered_pot(reason, info, caveats, pot, to_call):
    """ABSTENÇÃO explícita p/ tipo de pote fora da cobertura (3bet/multiway): mantém
    a LEITURA (mão, board, outs, SPR, pote) mas não recomenda — a dinâmica difere do
    pote de um raise só e o pack não resolve esses nós, então não damos heurística."""
    read = {k: info[k] for k in ('street', 'made', 'category', 'board_texture',
                                 'structure', 'outs', 'spr', 'pot_bb', 'to_call_bb')}
    po = required_equity(to_call, pot) if isinstance(to_call, (int, float)) and to_call > 0 else None
    return dict(status='ABSTAIN', phase='postflop', reason=reason, recommended=None,
                pot_odds=round(po, 4) if po is not None else None,
                exploratory=True, execution_allowed=False,
                caveats=caveats + ['POSTFLOP_POT_TYPE_UNCOVERED'], **read)


def _street(board):
    return {3: 'FLOP', 4: 'TURN', 5: 'RIVER'}[len(board)]


def _draw_equity(outs, street):
    """Equity aproximada de um draw até o river pela regra do 2 e do 4 (fração).

    Flop (2 cartas): ~outs×4; turn (1 carta): ~outs×2+2; river: 0. Aproximação de
    estudo, NÃO equity exata vs range — por isso vem sempre com caveat e limitada."""
    if street == 'FLOP':
        pct = outs * 4
    elif street == 'TURN':
        pct = outs * 2 + 2
    else:
        return 0.0
    return min(pct / 100.0, 0.90)


# Implied odds (skill poker-fundamentos-posflop): fichas a ganhar nas PRÓXIMAS ruas
# quando o draw completa. Estimativa conservadora = fração do pote por nº de ruas que
# faltam, LIMITADA pelo que há atrás (não se ganha mais do que o stack efetivo). Draw
# ÓBVIO (flush, 3º naipe visível) realiza menos que escondido (sequência). Reverse
# implied (completar p/ a 2ª melhor mão) NÃO é modelado -> caveat.
IMPLIED_POT_FRACTION = {'FLOP': 0.5, 'TURN': 0.25}   # 2 ruas restantes vs 1
OBVIOUS_DRAW_IMPLIED = 0.5                            # desconto p/ flush draw (óbvio)
REVERSE_IMPLIED_NONNUT = 0.5                          # flush NÃO-nut: às vezes perde ao acertar


def _implied_bb(street, pot, hero_stack, to_call, draws):
    """Ganho futuro estimado (BB) quando o draw completa; 0 no river/sem stack atrás.
    Flush não-nut leva REVERSE IMPLIED (perde pro flush maior às vezes)."""
    if street not in IMPLIED_POT_FRACTION or not isinstance(pot, (int, float)) or pot <= 0:
        return 0.0
    frac = IMPLIED_POT_FRACTION[street]
    if draws.get('flush_draw') and not draws.get('combo'):
        frac *= OBVIOUS_DRAW_IMPLIED                  # flush é óbvio -> implied menor
        if not draws.get('nut_flush_draw'):
            frac *= REVERSE_IMPLIED_NONNUT            # reverse implied do flush não-nut
    raw = frac * pot
    if isinstance(hero_stack, (int, float)) and isinstance(to_call, (int, float)):
        raw = min(raw, max(0.0, hero_stack - to_call))   # teto = stack efetivo atrás
    return round(raw, 2)


def _bet_fraction(bclass, made, draws, hero_is_aggressor=None, spr=None):
    """Fração do pote por TEXTURA do board (Pós-flop Avançado — postflop_texture): board
    alto/pareado seco = range-bet pequeno; board baixo não-pareado = polariza grande;
    molhado = grande (proteção). Devolve (fraction, plan). O plan traz lean/nuts p/ caveat.

    'Vantagem de range -> frequência; vantagem de nuts -> tamanho.' Clampado ao slider.
    """
    plan = postflop_texture.bet_plan(
        bclass, is_strong=(made in _STRONG),
        has_strong_draw=bool(draws.get('combo') or draws.get('flush_draw') or draws.get('oesd')),
        hero_is_aggressor=hero_is_aggressor, spr=spr)
    return plan['fraction'], plan


def _size(pot_bb, fraction, cap_bb, basis):
    size = round(min(pot_bb * fraction, cap_bb), 1) if cap_bb is not None else round(pot_bb * fraction, 1)
    return dict(size_bb=size, fraction=round(fraction, 2), basis=basis, heuristic=True)


def _advise_three_bet_pot(info, strength, bclass, caveats, *, pot, to_call,
                          hero_stack, spr, street, equity=None):
    """Heurística pós-flop para 3bet pot HEADS-UP (antes abstinha). Três ajustes vs o
    pote de um raise só, fundamentados: (1) SPR BAIXO -> mãos fortes (até top pair)
    COMETEM; (2) range do vilão mais FORTE/POLARIZADO -> marginais foldam; (3) implied
    BAIXO -> draws só por odds diretas. Tier + SPR, sem range de 3bet (não temos um;
    usar o range de open seria errado)."""
    made, draws, outs = strength['made'], strength['draws'], strength['outs']
    strong = made in _STRONG
    monster = made in ('set', 'trips', 'two_pair', 'straight', 'flush',
                       'full_house', 'quads', 'straight_flush')
    has_strong_draw = bool(draws['combo'] or draws['flush_draw'] or draws['oesd'])
    caveats = caveats + ['POSTFLOP_THREE_BET_POT_HEURISTIC', 'LOW_SPR_3BET',
                         'VILLAIN_RANGE_STRONGER_POLARIZED']
    cap = hero_stack if isinstance(hero_stack, (int, float)) else None
    board_beats_us = (bclass['straight_on_board']
                      or (bclass['flush_possible'] and made not in
                          ('flush', 'full_house', 'quads', 'straight_flush')))
    low_spr = spr is None or spr <= SPR_COMMIT_3BET
    if to_call > 0:
        pot_odds = required_equity(to_call, pot)
        if pot_odds is None:
            return _abstain('CANNOT_COMPUTE_POT_ODDS', pot_bb=pot, to_call_bb=to_call)
        info.update(pot_odds=round(pot_odds, 4))
        if equity is not None:
            info['equity'] = round(equity, 4)
            # Range FORNECIDO manda: um "monstro" DOMINADO (equity < pot odds, ex.: full
            # vs quadra) NÃO compromete por categoria — folda em vez de pagar/raise.
            if equity < pot_odds:
                info.update(recommended='fold',
                            caveats=caveats + ['THREE_BET_DOMINATED_BY_RANGE'])
                return info
        if strong:
            if monster and not board_beats_us:
                raise_to = round(min(to_call * 3, cap), 1) if cap else round(to_call * 3, 1)
                info.update(recommended='raise',
                            sizing=dict(size_bb=raise_to, basis='3bet pot: comete (SPR baixo)',
                                        heuristic=True), caveats=caveats)
                return info
            if board_beats_us:
                caveats.append('BOARD_MAY_BEAT_ONE_PAIR_CALL_ONLY')
            info.update(recommended='call', caveats=caveats)       # overpair/forte comete
            return info
        if made == 'top_pair':
            if low_spr:
                info.update(recommended='call', caveats=caveats + ['TOP_PAIR_COMMITS_LOW_SPR'])
                return info
            info.update(recommended='fold',
                        caveats=caveats + ['TOP_PAIR_DEEP_3BET_POLARIZED_FOLD'])
            return info
        if made in _MARGINAL:
            info.update(recommended='fold', caveats=caveats + ['MARGINAL_FOLD_VS_3BET_RANGE'])
            return info
        if street != 'RIVER' and has_strong_draw:
            clean = draws.get('clean_outs', outs)
            deq = _draw_equity(clean, street)                      # SEM implied (SPR baixo)
            info.update(draw_equity=round(deq, 4), clean_outs=clean,
                        recommended=('call' if deq >= pot_odds else 'fold'),
                        caveats=caveats + ['DRAW_DIRECT_ODDS_NO_IMPLIED_3BET'])
            return info
        info.update(recommended='fold', caveats=caveats)
        return info
    # Passaram a vez (to_call == 0): comete/semi-blefe no SPR baixo.
    if strong:
        info.update(recommended='bet',
                    sizing=_size(pot, 0.66, cap, '3bet pot: valor/comete (size maior)'),
                    caveats=caveats)
        return info
    if has_strong_draw:
        info.update(recommended='bet',
                    sizing=_size(pot, 0.5, cap, '3bet pot: semi-blefe (SPR baixo)'),
                    caveats=caveats + ['SEMI_BLUFF_LOW_SPR'])
        return info
    if made == 'top_pair':
        info.update(recommended='bet',
                    sizing=_size(pot, 0.5, cap, '3bet pot: valor top pair'), caveats=caveats)
        return info
    info.update(recommended='check', sizing=dict(size_bb=0.0, basis='check', heuristic=False),
                caveats=caveats + ['CHECK_SHOWDOWN_OR_GIVEUP'])
    return info


def _board_is_nuts_chop(board):
    """True se os 5 cards do board formam um NUTS imbatível (royal flush): qualquer um
    joga o board -> chop garantido, independente das cartas do vilão. (Outros boards
    imbatíveis — ex. quadra com kicker máximo — ficam p/ depois; royal cobre o contrato
    e é 100% seguro: nada bate um royal no board.)"""
    if not board or len(board) != 5:
        return False
    suits = {c[1] for c in board if isinstance(c, str) and len(c) >= 2}
    ranks = {c[0] for c in board if isinstance(c, str) and c}
    return len(suits) == 1 and ranks == set('TJQKA')


def advise_postflop(table_state, hero, board, *, street=None, mode='chip_ev',
                    stage='mid', aggressor=None, villain_range=None, pot_type=None,
                    narrow_range=False, villain_stats=None, villains=None,
                    villain_line=None, soft_field=False, iters=4000, seed=0):
    """Conselho pós-flop para uma leitura. `hero`: 2 strings; `board`: 3-5 strings.

    `aggressor` (opcional): quem teve a iniciativa no pré-flop ('hero'/posição), para
    a lógica de c-bet quando passam a vez. Desconhecido -> flag e postura conservadora.

    `villain_range` (opcional): range do vilão — lista de (combo, peso) ou de strings
    de mão. Quando dado, enfrentando aposta, a decisão de CALL passa a ser por EQUITY
    ESTIMADA por Monte Carlo no board (semente fixa -> determinística, mas é
    estimativa, não valor fechado) vs esse range, em vez da regra do 2-e-4
    / tiers. É o range PRÉ-FLOP (não estreitado pós-flop) -> deságio + caveats; aposta
    grande segue abstendo. Sem range, cai no comportamento da Fase 1.
    """
    if not board or len(board) < 3:
        return _abstain('NO_BOARD')
    try:
        strength = hand_strength(hero, board)
        bclass = classify_board(board)
    except (ValueError, KeyError, TypeError):
        return _abstain('UNREADABLE_CARDS')
    if strength is None:
        return _abstain('HERO_BOARD_CARD_CONFLICT')
    street = street or _street(board)

    pot = (table_state.get('pot') or {}).get('pot_bb')
    to_call = (table_state.get('to_call') or {}).get('to_call_bb')
    hero_seat = (table_state.get('seats') or {}).get('hero', {})
    hero_stack = hero_seat.get('stack_bb')
    if not isinstance(pot, (int, float)) or pot <= 0:
        return _abstain('POT_UNKNOWN', pot_bb=pot)
    if to_call is None:
        return _abstain('TO_CALL_UNKNOWN')

    made = strength['made']
    draws = strength['draws']
    outs = strength['outs']
    spr = round(hero_stack / pot, 2) if isinstance(hero_stack, (int, float)) and pot else None
    strong = made in _STRONG
    marginal = made in _MARGINAL
    has_strong_draw = bool(draws['combo'] or draws['flush_draw'] or draws['oesd'])
    has_weak_draw = bool(draws['gutshot'] or draws['backdoor_flush'])

    caveats = list(BASE_CAVEATS)
    if spr is not None:
        caveats.append('SPR_PROXY_HERO_STACK')
    if aggressor == 'hero':
        caveats.append('HERO_HAS_INITIATIVE')
    elif aggressor:
        caveats.append('VILLAIN_HAS_INITIATIVE')
    else:
        caveats.append('AGGRESSOR_UNKNOWN')
    if mode != 'chip_ev':
        caveats.append('ICM_PKO_NOT_APPLIED_POSTFLOP')

    info = dict(status='ADVICE', phase='postflop', street=street, made=made,
                category=strength['category_name'], board_texture=bclass['texture'],
                structure=bclass['structure'], outs=outs, spr=spr, equity=None,
                pot_bb=pot, to_call_bb=to_call, exploratory=True, execution_allowed=False)

    # Barril de TURN (advisory): gaveta polarizada (valor/blefe/meio) + tipo de carta de
    # turn + lean de frequência. Metadado p/ o operador/auditor e p/ alinhar a polarização;
    # NÃO troca a recomendação (made/draws/textura/equity seguem decidindo). Só turn.
    if street == 'TURN' and len(board) >= 4:
        _flop_bclass = classify_board(list(board)[:3])
        _range_bet_flop = postflop_cbet_bb.cbet_check_category(_flop_bclass, stack_bb=hero_stack) is None
        _tb_tier = postflop_turn_barrel.barrel_tier(made, draws)
        _tb_type = postflop_turn_barrel.classify_turn(list(board))
        _tb_lean = postflop_turn_barrel.barrel_lean(_tb_type, range_bet_flop=_range_bet_flop)
        info['turn_barrel'] = dict(tier=_tb_tier, turn_type=_tb_type,
                                   range_bet_flop=_range_bet_flop, **_tb_lean)
        caveats.append('TURN_BARREL_%s' % _tb_tier.upper())
        if _tb_type:
            caveats.append('TURN_CARD_%s' % _tb_type.upper())
        # Give-up turn (pareia carta média/baixa, ex. 3/9 em A93): mão NÃO-valor dá check
        # ~100% (a teoria é enfática). Advisory: sinaliza p/ o auditor/execução futura.
        if _tb_lean.get('give_up') and _tb_tier != postflop_turn_barrel.VALUE:
            caveats.append('TURN_GIVE_UP')

    # River (advisory): polarização máxima — gaveta valor/blefe/check por VALOR RELATIVO +
    # lean de size (nuts -> overbet). Metadado; a disciplina de valor (promoção) age abaixo.
    if street == 'RIVER':
        _rv_tier = postflop_river.river_tier(made, draws, bclass)
        info['river'] = dict(tier=_rv_tier, value_ok=postflop_river.river_value_ok(made, bclass),
                             draw_complete=postflop_river.is_draw_complete(bclass),
                             size_hint=postflop_river.river_size_hint(made, bclass))
        caveats.append('RIVER_%s' % _rv_tier.upper())

    # Scare card (metadado exploratório): carta de perigo no turn/river. Não altera a
    # equity de Monte Carlo (o board já entra lá); serve de sinal p/ mãos de 1 par e p/
    # o auditor de leaks. Só marca; a decisão de valor segue a lógica existente.
    scare = scare_present(bclass, street)
    if scare['present']:
        info['scare_card'] = scare['kinds']
        caveats.append('SCARE_CARD_' + '_'.join(scare['kinds']).upper())

    # Tipos de pote fora da cobertura: ABSTÉM com rótulo ANTES de qualquer Monte
    # Carlo (abstenção conhecida não paga o custo da equity, a cada frame/mesa).
    if pot_type == 'three_bet':      # HU 3bet pot (multiway é pego como 'multiway')
        # Com um range FORNECIDO, computa a equidade vs esse range p/ o ramo 3bet não
        # comprometer por CATEGORIA um "monstro" dominado (ex.: full vs quadra). Sem
        # range, segue a heurística (não temos um range de 3bet).
        _vr3 = _normalize_range(villain_range)
        _eq3 = equity_vs_range(hero, _vr3, board=list(board), iters=iters, seed=seed) if _vr3 else None
        return _advise_three_bet_pot(info, strength, bclass, caveats, pot=pot, to_call=to_call,
                                     hero_stack=hero_stack, spr=spr, street=street, equity=_eq3)
    # Nº de oponentes: explícito, senão lido da mesa, senão >=2 se o pote é multiway.
    n_opp = villains if isinstance(villains, int) and villains > 0 else count_opponents(table_state)
    if not isinstance(n_opp, int) or n_opp < 1:
        n_opp = 2 if pot_type == 'multiway' else 1
    info['opponents'] = n_opp
    if pot_type == 'multiway':
        # Multiway já NÃO abstém às cegas: segue com PENALIDADE de equity por vilão
        # extra e BLOQUEIO de blefe de c-bet (>2 oponentes). Camada exploratória.
        caveats.append('MULTIWAY_%dOPP_EQUITY_PENALTY_%dPCT' % (n_opp, penalty_pct(n_opp)))

    # Equity ESTIMADA do hero vs o range do vilão (se dado), Monte Carlo no board com
    # semente fixa -> determinística (mas estimativa). É a Fase 2: CALL quantitativo.
    vr = _normalize_range(villain_range)
    # Enfrentando aposta, com `narrow_range`, ESTREITA o range pré-flop do vilão para o
    # range de continuação no board (equity robusta vs não-robusta) ANTES do Monte
    # Carlo — mais preciso que o deságio fixo, que vira dispensável quando estreitamos.
    narrowed = False
    if vr and narrow_range and isinstance(to_call, (int, float)) and to_call > 0:
        vr_cont = narrow_to_continuation(vr, list(board), street=street)
        if vr_cont:
            vr, narrowed = vr_cont, True
    equity = equity_vs_range(hero, vr, board=list(board), iters=iters, seed=seed) if vr else None
    # Penalidade MULTIWAY: a equity vs UM range superestima a equity vs VÁRIOS.
    # Reduz -12% (relativo) por vilão extra antes de qualquer decisão de call.
    if equity is not None and n_opp > 1:
        equity = apply_multiway_penalty(equity, n_opp)
        caveats.append('MULTIWAY_EQUITY_PENALTY_%dPCT_%dOPP' % (penalty_pct(n_opp), n_opp))
    haircut = 0.0 if narrowed else _CALL_HAIRCUT
    # Exploit do HUD (opcional): classifica o vilão e nudgeia o limiar de bluffcatch
    # (foldar mais vs passivo/value-heavy; pagar mais largo vs quem blefa). Bounded e
    # sempre flagado (amostra desconhecida). Só mexe nas mãos FEITAS enfrentando aposta.
    profile = classify_villain(villain_stats) if villain_stats else None
    ex_delta = profile['bluffcatch_delta'] if profile else 0.0
    if profile and profile['category'] != 'unknown':
        caveats = caveats + exploit_caveats(profile)
    if equity is not None:
        if narrowed:
            caveats += ['EQUITY_VS_VILLAIN_CONTINUATION_RANGE', 'RANGE_NARROWED_TO_BOARD']
        else:
            caveats += ['EQUITY_VS_VILLAIN_PREFLOP_RANGE', 'RANGE_NOT_NARROWED_POSTFLOP',
                        'CALL_HAIRCUT_%dPCT' % round(_CALL_HAIRCUT * 100)]
        info['equity'] = round(equity, 4)

    # ---- Enfrentando uma aposta -------------------------------------------------
    if to_call > 0:
        pot_odds = required_equity(to_call, pot)
        if pot_odds is None:
            return _abstain('CANNOT_COMPUTE_POT_ODDS', pot_bb=pot, to_call_bb=to_call)
        # MDF (defesa mínima de range) = P0/(P0+B), P0=pote ANTES da aposta, B=aposta a
        # pagar. `pot` aqui já inclui a aposta do vilão (P1=P0+B), logo P0=pot-to_call ->
        # MDF=(pot-to_call)/pot. Ex.: pot=20, call=10 -> 10/20=0,5 (não pot/(pot+call)).
        # Assume SEM contribuição anterior do hero na rua; p/ raises/potes laterais a
        # convenção muda (explicitar o estado antes de reusar). Pot odds é conta à parte.
        mdf = round(max(0.0, min(1.0, (pot - to_call) / pot)), 4) if pot else None
        info.update(pot_odds=round(pot_odds, 4), mdf=mdf)
        # Pool-underbluff: no pool da Evolution, linha passiva->agressiva ou overbet é
        # sub-blefada; desconta o MDF teórico (×0.75). Metadado exploratório.
        pta = villain_line == 'passive_turned_aggressive'
        overbet = pot_odds > _BIG_BET_POT_ODDS
        if mdf is not None and (pta or overbet):
            info['pool_adjusted_mdf'] = pool_adjusted_mdf(mdf, passive_turned_aggressive=pta,
                                                          overbet=overbet)
            caveats.append('POOL_UNDERBLUFF_MDF_DISCOUNTED')
        cap = hero_stack if isinstance(hero_stack, (int, float)) else None
        # CHECK-RAISE por vantagem de NUTS (Pós-flop Avançado): como DEFENSOR (o vilão teve
        # a iniciativa) em board onde o nosso range de defesa tem vantagem de nuts (pareado
        # ou baixo conectado), o BB check-raiseia — valor E semi-blefe (~3x). Antes o
        # semi-blefe só aparecia como metadado; aqui vira AÇÃO (mata a passividade).
        _defender = aggressor is not None and aggressor != 'hero'
        _nuts_hero_def = (_defender and street != 'RIVER'
                          and postflop_texture.nuts_holder(bclass, hero_is_aggressor=False) == 'hero')
        board_beats_us = (bclass['straight_on_board']
                          or (bclass['flush_possible'] and made not in
                              ('flush', 'full_house', 'quads', 'straight_flush')))
        # RUNOUT FAVORÁVEL A BLEFE (river, Eduardo 24/11 — "ser herói em determinados runouts"): os
        # draws ÓBVIOS do board NÃO fecharam, então o range de barril do vilão fica PESADO em draws
        # perdidos = blefes. Sinaliza no river onde não há flush/straight FEITO mas havia draw (2-flush
        # máx. = flush-draw morto, OU 3+ cartas conectadas = straight-draw morto). Alimenta o hero-call.
        # Sinal REAL de FLUSH-DRAW MORTO: todo river de 5 cartas TEM 2-flush (pigeonhole), então "2-flush
        # no river" não diz nada. O que importa é se o draw estava VIVO no TURN (board[:4] two-tone = 2 de
        # um naipe = flush-draw possível) e o river NÃO trouxe o 3º (flush_possible=False). Turn RAINBOW
        # (sem flush-draw) é corretamente EXCLUÍDO -> ali top pair folda overbet (não há blefe de draw).
        # Straight-draw morto fica de fora de propósito (o straightish do board é ruidoso em board
        # desconexo); conservador = não inventa hero-call. Alimenta só o hero-call do campo mole.
        _turn_sc = [sum(1 for c in board[:4] if len(c) > 1 and c[1] == s) for s in 'cdhs'] if len(board) == 5 else []
        _missed_draw_river = (street == 'RIVER' and len(board) == 5
                              and not bclass['flush_possible'] and not bclass['straight_on_board']
                              and bool(_turn_sc) and max(_turn_sc) >= 2)
        # CHECK-RAISE DE BLEFE NO RIVER (Eduardo 24/11, "hero-raise em runout de blefe") — a linha mais
        # arriscada do poker, então CIRÚRGICA. Só dispara com TODAS estas travas: (a) AR PURO — um
        # bluff-catcher (par) deve PAGAR (hero-call acima), nunca virar blefe; (b) NUT-BLOCKER do flush
        # FEITO no board (hero segura o Ás do naipe que fechou, sem ter o flush) -> o vilão raramente
        # tem a nut e o check-raise REPRESENTA a nut de forma crível, foldando o valor marginal dele;
        # (c) CAMPO DURO (FT/ICM: o vilão dobra valor marginal sob pressão) — campo mole/station paga o
        # raise, seria spew; (d) vilão NÃO-passivo; (e) aposta RAISEÁVEL (<= aposta grande), não overbet.
        # Sem blocker = blefe sem representar nada = NUNCA. É o espelho de blefe do check-raise de valor.
        if (street == 'RIVER' and _defender and made == 'air' and not soft_field
                and not (profile and profile.get('passive'))
                and bclass['flush_possible'] and pot_odds <= _BIG_BET_POT_ODDS and cap):
            _xr_fs = next((s for s in 'cdhs'
                           if sum(1 for c in board if len(c) > 1 and c[1] == s) >= 3), None)
            if _xr_fs and any(len(c) > 1 and c[1] == _xr_fs and c[0] == 'A' for c in hero):
                info.update(recommended='raise',
                            sizing=dict(size_bb=round(min(to_call * 3, cap), 1),
                                        basis='check-raise de blefe no river (nut-blocker, campo duro)',
                                        heuristic=True),
                            caveats=caveats + ['CHECK_RAISE_BLUFF_RIVER_NUT_BLOCKER_CAMPO_DURO'])
                return info
        # Mão de categoria forte: a equity (quando há range) manda. Não aumenta —
        # nem paga — contra um range que nos domina, mesmo com categoria boa (#7).
        if strong:
            if equity is not None and equity < pot_odds + haircut + ex_delta:
                info.update(recommended='fold',
                            caveats=caveats + ['STRONG_CATEGORY_BUT_DOMINATED_BY_RANGE'])
                return info
            can_value_raise = (not board_beats_us
                               and (equity is None or equity >= _VALUE_RAISE_MIN_EQUITY))
            if can_value_raise:
                raise_to = round(min(to_call * 3, cap), 1) if cap else round(to_call * 3, 1)
                cr = caveats + (['CHECK_RAISE_VALOR_VANTAGEM_NUTS'] if _nuts_hero_def else [])
                info.update(recommended='raise',
                            sizing=dict(size_bb=raise_to, basis='raise ~3x aposta (heuristica)',
                                        heuristic=True), caveats=cr)
                return info
            if board_beats_us:
                caveats.append('BOARD_MAY_BEAT_ONE_PAIR_CALL_ONLY')
            info.update(recommended='call', caveats=caveats)
            return info
        # Mãos FEITAS fracas/médias decidem como bluffcatcher ANTES de qualquer draw
        # (uma mão feita com draw não deve ser foldada como se fosse só draw) (#6).
        if made == 'top_pair':
            if pot_odds > _BIG_BET_POT_ODDS:
                # Aposta grande = bluffcatch que precisa de LEITURA. Com HUD, DECIDE:
                # vilão que blefa (lag/cbet-heavy/3bet-happy) -> paga; passivo/nit (aposta
                # grande = valor) -> folda. Sem HUD, segue abstendo (honesto).
                if profile and profile['category'] != 'unknown':
                    dec = 'call' if profile['aggressive'] else 'fold'
                    info.update(recommended=dec,
                                caveats=caveats + ['BLUFFCATCH_BIG_BET_EXPLOIT_%s'
                                                   % ('AGGRO' if profile['aggressive'] else 'PASSIVE')])
                    return info
                # Sem HUD, mas com a LINHA do vilão informada: passivo que vira agressão
                # pesada no pool underbluffa -> foldar o bluffcatch (não precisa de range).
                if villain_line == 'passive_turned_aggressive':
                    info.update(recommended='fold',
                                caveats=caveats + ['POOL_UNDERBLUFF_FOLD_BIG_BET'])
                    return info
                # GUIA cap.14 (p.83, SOLVER): top pair PAGA o barril de turn 98-100%; o
                # over-fold do pool é SÓ no RIVER (3º barril grande) e vs RAISE. Sem leitura,
                # o default FLOP/TURN passa a DEFENDER (o passivão vinha de foldar top pair pra
                # qualquer aposta ≥2/3); RIVER segue fold seguro. (Agressão 24/11, guia autoridade.)
                if street == 'RIVER':
                    # RIVER BEM PROTEGIDO vs campo que SOBRE-blefa (Eduardo 24/11): no campo MOLE o
                    # pool blefa DEMAIS o river -> top pair é HERÓI e PAGA (não over-folda e vira
                    # explorável). Paga a aposta grande; e em RUNOUT DE BLEFE (draw morreu) paga até
                    # overbet (o barril é quase todo draw perdido). Campo DURO (FT/ICM, pool
                    # underbluffa o river) -> fold seguro (comportamento anterior, intacto).
                    if soft_field and (pot_odds <= _OVERBET_POT_ODDS
                                       or (_missed_draw_river and pot_odds <= _HERO_CALL_MAX_POT_ODDS)):
                        info.update(recommended='call',
                                    caveats=caveats + ['HERO_CALL_RIVER_CAMPO_MOLE'
                                                       + ('_RUNOUT_BLEFE' if _missed_draw_river else '')])
                        return info
                    info.update(recommended='fold',
                                caveats=caveats + ['BLUFFCATCH_RIVER_BIGBET_FOLD_POOL_UNDERBLUFF'])
                    return info
                if pot_odds > _OVERBET_POT_ODDS:            # overbet polarizada: nem top pair paga
                    info.update(recommended='fold',
                                caveats=caveats + ['BLUFFCATCH_OVERBET_FOLD'])
                    return info
                info.update(recommended='call',
                            caveats=caveats + ['TOP_PAIR_DEFENDE_BARRIL_GUIA_CAP14'])
                return info
            if equity is not None:
                caveats.append('BLUFFCATCH_EQUITY_DRIVEN')
                info.update(recommended=('call' if equity >= pot_odds + haircut + ex_delta else 'fold'),
                            caveats=caveats)
                return info
            # Sem range: default é defender ao MDF (call). Mas com a linha passivo->
            # agressivo informada, o pool underbluffa -> folda o bluffcatcher de 1 par.
            if villain_line == 'passive_turned_aggressive':
                info.update(recommended='fold',
                            caveats=caveats + ['POOL_UNDERBLUFF_FOLD_TOP_PAIR'])
                return info
            caveats += ['BLUFFCATCH_DEFEND_TO_MDF', 'EXPLOIT_DEPENDS_ON_VILLAIN']
            info.update(recommended='call', caveats=caveats)
            return info
        if marginal:
            # UNDERPAIR DEVALUADO (review do leak real, H2N #61: QQ em K-alto 3-way pagou all-in e
            # perdeu ~50k). O underpair tem OVERCARD no board por definição (par abaixo da carta mais
            # alta). Em MULTIWAY (n_opp>1) OU vs APOSTA GRANDE/ALL-IN (pot_odds>_BIG_BET), o range de
            # VALOR domina -> FOLDA (bluffcatcher atrás), NUNCA paga pela equity otimista. HU vs aposta
            # normal segue decidindo pela equity abaixo. Eduardo (review underpair, alvo #1).
            # UNDERPAIR DEVALUADO (leak real H2N #61: QQ em K-alto 3-way pagou all-in, -50k):
            # em MULTIWAY ou vs APOSTA GRANDE -> FOLD SEMPRE, campo mole ou não. É o bluff-catcher
            # mais FRACO e all-in é commitment de stack -> NÃO entra no "defende o barril" (nem no
            # campo mole: pagar all-in com underpair é o spew que o Eduardo alertou). Intacto.
            if made == 'underpair' and (n_opp > 1 or pot_odds > _BIG_BET_POT_ODDS):
                info.update(recommended='fold',
                            caveats=caveats + ['UNDERPAIR_DEVALUED_FOLD_MULTIWAY_OR_BIGBET'])
                return info
            if equity is not None:
                caveats.append('MARGINAL_EQUITY_DRIVEN')
                info.update(recommended=('call' if equity >= pot_odds + haircut + ex_delta else 'fold'),
                            caveats=caveats)
                return info
            # CAMPO MOLE (soft_field, stage inicial): o campo SOBRE-blefa (play money ruim) ->
            # par médio DEFENDE o barril normal ao MDF (paga o lixo deles, guia cap.14); só folda
            # vs overbet ou aposta grande de RIVER. Campo duro (FT/ICM callstation) -> fold default.
            # `made != 'underpair'`: o underpair (bluff-catcher mais fraco, hand do leak de 50k)
            # NUNCA entra no soft-defense — folda sem range mesmo no campo mole (protege o call-off).
            # Só o 2º/3º par de verdade defende o barril normal quando o campo sobre-blefa.
            # HERO em RUNOUT DE BLEFE (Eduardo 24/11): no river onde o draw morreu, o barril do vilão
            # é quase todo blefe -> o 2º/3º par (NÃO underpair) vira herói e PAGA a aposta grande de
            # river também (até overbet; acima disso nem o herói paga). Fora do runout de blefe segue a
            # regra antiga (defende barril normal; folda overbet e aposta grande de river).
            _hero_runout = _missed_draw_river and pot_odds <= _OVERBET_POT_ODDS
            if (soft_field and made != 'underpair'
                    and (_hero_runout
                         or not (pot_odds > _OVERBET_POT_ODDS
                                 or (pot_odds > _BIG_BET_POT_ODDS and street == 'RIVER')))):
                info.update(recommended='call',
                            caveats=caveats + (['HERO_CALL_2O_PAR_RUNOUT_BLEFE'] if _hero_runout
                                               else ['MARGINAL_DEFENDE_CAMPO_MOLE_GUIA_CAP14']))
                return info
            caveats.append('MARGINAL_BLUFFCATCH_FOLD_DEFAULT_EXPLOITABLE')
            info.update(recommended='fold', caveats=caveats)
            return info
        # Mão NÃO-feita com draw: só vale fora do river (no river não vem carta) (#6).
        if street != 'RIVER' and (has_strong_draw or has_weak_draw):
            # B1 (x/r semi-blefe, EXPLORATÓRIO): com draw FORTE (combo ou nut-flush-draw)
            # e aposta NÃO-gigante, a linha balanceada OFERECE um RAISE semi-blefe (fold
            # equity + equity do draw) como ALTERNATIVA. Não troca a decisão call/fold
            # por equity abaixo — só a enriquece como estudo (o operador nunca executa).
            if (has_strong_draw and (draws.get('combo') or draws.get('nut_flush_draw'))
                    and pot_odds <= _BIG_BET_POT_ODDS and cap):
                info['semi_bluff_raise'] = dict(size_bb=round(min(to_call * 3, cap), 1),
                                                exploratory=True, basis='x/r semi-blefe draw forte')
                caveats.append('SEMI_BLUFF_RAISE_AVAILABLE_EXPLORATORY')
            # Promove o semi-blefe a AÇÃO (check-raise) quando somos o DEFENSOR com vantagem
            # de nuts (Pós-flop Avançado) e o draw é FORTE (combo/nut-FD/OESD) vs aposta não
            # gigante. É a metade de blefe do check-raise do BB — antes o Henrique só pagava.
            if (_nuts_hero_def and (draws.get('combo') or draws.get('nut_flush_draw') or draws.get('oesd'))
                    and pot_odds <= _BIG_BET_POT_ODDS and cap):
                info.update(recommended='raise',
                            sizing=dict(size_bb=round(min(to_call * 3, cap), 1),
                                        basis='check-raise semi-blefe (vantagem de nuts ~3x)',
                                        heuristic=True),
                            caveats=caveats + ['CHECK_RAISE_SEMIBLUFF_VANTAGEM_NUTS'])
                return info
            # CHECK-RAISE POR BLEFE (guia cap.5-6 + Eduardo 24/11): a metade de BLEFE do
            # check-raise do defensor com vantagem de nuts. Draw FRACO (gutshot/backdoor) com
            # fold equity vira check-raise semi-blefe — SÓ no CAMPO DURO (guia: "semi-blefe
            # quando há fold equity") e vs vilão NÃO-passivo. Balanceia os check-raises de valor.
            # Campo mole/station -> segue call/fold por equity abaixo (não blefa quem não folda).
            if (_nuts_hero_def and has_weak_draw and not has_strong_draw and not soft_field
                    and not (profile and profile.get('passive'))
                    and pot_odds <= _BIG_BET_POT_ODDS and cap):
                info.update(recommended='raise',
                            sizing=dict(size_bb=round(min(to_call * 3, cap), 1),
                                        basis='check-raise por blefe (campo duro: draw fraco + fold equity)',
                                        heuristic=True),
                            caveats=caveats + ['CHECK_RAISE_BLUFF_CAMPO_DURO'])
                return info
            # Implied odds: o ganho futuro quando o draw completa baixa a equity exigida.
            implied = _implied_bb(street, pot, hero_stack, to_call, draws)
            po_imp = required_equity(to_call, pot + implied) if implied > 0 else pot_odds
            if implied > 0:
                caveats.append('IMPLIED_ODDS_APPROX_%gBB' % implied)
                if draws['flush_draw'] and not draws['combo'] and not draws.get('nut_flush_draw'):
                    caveats.append('REVERSE_IMPLIED_NONNUT_FLUSH')      # modelado (implied menor)
                elif not draws['flush_draw']:
                    caveats.append('REVERSE_IMPLIED_STRAIGHT_NOT_MODELED')
            else:
                caveats.append('IMPLIED_ODDS_NONE_NO_STACK_BEHIND')
            if equity is not None:
                info.update(implied_bb=implied, pot_odds_implied=round(po_imp, 4),
                            recommended=('call' if equity >= po_imp + haircut else 'fold'),
                            caveats=caveats)
                return info
            clean = draws.get('clean_outs', outs)
            deq = _draw_equity(clean, street)
            caveats.append('DRAW_EQUITY_RULE_OF_2_AND_4')
            if clean < outs:
                # Outs sujos descontados (board pareado / flush que pareia / sequência
                # dentro de um flush): a equity de draw usa os outs LIMPOS, não os crus.
                caveats.append('DIRTY_OUTS_DISCOUNTED_%g_OF_%d' % (round(outs - clean, 1), outs))
            info.update(draw_equity=round(deq, 4), clean_outs=clean, implied_bb=implied,
                        pot_odds_implied=round(po_imp, 4),
                        recommended=('call' if deq >= po_imp else 'fold'), caveats=caveats)
            return info
        # EMPATE GARANTIDO / equidade TRAVADA no river com o board JOGADO. Chop quando:
        # (a) há range e a equidade é >= 0.5 (nenhum combo do range bate o board), OU
        # (b) o board é um NUTS imbatível (royal flush) — chop independente das cartas do
        # vilão, logo vale mesmo SEM range (p/ o auditor de leaks que replaya sem cartas).
        # Pagar é +EV sempre que pot>to_call (recupera metade), SEM haircut: é lock, 0
        # runout perdedor. NUNCA foldar um chop garantido.
        if (street == 'RIVER' and made == 'plays_board' and pot > to_call
                and ((equity is not None and equity >= 0.5 - 1e-6) or _board_is_nuts_chop(board))):
            info.update(recommended='call', caveats=caveats + ['GUARANTEED_CHOP_LOCKED_EQUITY'])
            return info
        # Ar / joga o board: folda, salvo equity (vs range) acima das pot odds.
        if equity is not None and equity >= pot_odds + haircut + ex_delta:
            info.update(recommended='call', caveats=caveats + ['WEAK_BUT_EQUITY_OK'])
            return info
        # FLOAT (guia cap.7 + Eduardo 24/11): EM POSIÇÃO, mão fraca COM POTENCIAL (overcards ou
        # backdoor) PAGA o c-bet normal (flutua) em vez de foldar — plano de ROUBAR quando o
        # agressor DESISTE no turn (probe). SÓ no CAMPO DURO (o agressor c-beta e desiste; guia:
        # "float em posição com backdoor e aposta") e vs vilão NÃO-passivo. Campo mole/station ->
        # folda (station não desiste da aposta). Só flop, c-bet não-gigante.
        if (_hero_in_position(table_state.get('positions')) is True and street == 'FLOP'
                and made in ('overcards', 'air')
                and (made == 'overcards' or draws.get('backdoor_flush'))
                and not soft_field and not (profile and profile.get('passive'))
                and pot_odds <= _BIG_BET_POT_ODDS):
            info.update(recommended='call', caveats=caveats + ['FLOAT_IP_CAMPO_DURO'])
            return info
        info.update(recommended='fold', caveats=caveats)
        return info

    # ---- Passaram a vez (to_call == 0): apostar ou dar check ---------------------
    info.update(pot_odds=None, mdf=None)
    cap = hero_stack if isinstance(hero_stack, (int, float)) else None
    # Sizing geométrico (metadado): a fração constante por rua que compromete o stack no
    # river. Informa o plano; NÃO substitui a fração por-rua escolhida por vantagem de
    # range/nuts logo abaixo (poucos sizes/rua é intencional).
    geo_n = remaining_streets(street)
    if geo_n:
        geo_pct = geometric_bet_pct(spr, geo_n)
        if geo_pct is not None:
            info['geometric'] = dict(pct=geo_pct,
                                     street_plan=geometric_street_plan(spr, street, pot, hero_stack))
    _hia = True if aggressor == 'hero' else (None if aggressor is None else False)
    _hero_ip = _hero_in_position(table_state.get('positions'))
    # OOP p/ o GATE ANTI-DONK: hero age PRIMEIRO (fora de posição) = _hero_ip is False.
    # Ao vivo (protobuf_state.build_table_state) o mapa `positions` SEMPRE traz os vilões,
    # então _hero_ip é True/False confiável e o donk OOP é pego. Indeterminado (_hero_ip
    # None: sem vilão no mapa — só stubs de teste, nunca um frame vivo) NÃO dispara, p/ não
    # mexer no tier de lead quando a posição relativa é desconhecida.
    _hero_oop = (_hero_ip is False)
    _vill_pos = None                                  # posição do ÚNICO vilão (HU), p/ regra vs SB
    if n_opp == 1:
        _vps = [p for k, p in (table_state.get('positions') or {}).items() if k != 'hero']
        _vill_pos = _vps[0] if len(_vps) == 1 else None
    # Equity buckets (Pós-flop Avançado): classifica a força do hero por equidade quando há
    # range (90-100 nuts / 80-90 strong / 70-80 value / 60-70 medium / <60 weak). Metadado
    # p/ auditoria E refino: mão de bucket forte NÃO vira check no board polar (abaixo).
    _eq_bucket = postflop_texture.equity_bucket(equity)
    if _eq_bucket:
        caveats = caveats + ['EQUITY_BUCKET_%s' % _eq_bucket.upper()]
    # C-bet vs BB (Teoria para c-bet vs BB): board de PERIGO em que o PFR IP não c-beta
    # range (checa mais) — perigo de FLUSH agora stack-gated (só deep ≥60bb; short/vs-humano
    # aposta 100%). Tag honesta + LEAN de frequência por posição+stack (advisory: a decisão
    # por mão made/draws/equity segue decidindo). Só quando o hero tem a iniciativa.
    _cbet_cat = (postflop_cbet_bb.cbet_check_category(bclass, stack_bb=hero_stack)
                 if _hia is True else None)
    if _hia is True:
        _hero_pos = (table_state.get('positions') or {}).get('hero')
        _cbet_freq = postflop_cbet_bb.cbet_freq_vs_bb(_hero_pos, hero_stack)
        if _cbet_freq or _cbet_cat:
            info['cbet_vs_bb'] = dict(danger=_cbet_cat, freq_lean=_cbet_freq,
                                      position=_hero_pos, stack_bb=hero_stack)
        if _cbet_freq:
            caveats = caveats + ['CBET_VS_BB_FREQ_%d' % round(_cbet_freq['freq'] * 100)]
    if _cbet_cat:
        caveats = caveats + ['CBET_VS_BB_PERIGO_%s' % _cbet_cat.upper()]
    # C-bet FORA DE POSIÇÃO (guia pós-flop: o PFR OOP checa ~71% — NÃO range-beta). Só VALOR
    # forte (_STRONG) e DRAW forte c-betam OOP; ar/marginal/top-pair dão CHECK (controle de pote,
    # realiza equidade). Mata o leak de c-bet OOP (a lógica de range-bet 1/3, pensada p/ IP vs BB,
    # vazava p/ OOP). Só quando o hero TEM a iniciativa e está COMPROVADAMENTE OOP.
    # NÃO preempta o DELAYED c-bet nem o VALOR FINO de bet-check-bet (villain_line delayed/checked_turn):
    # nessas linhas o range do vilão está CAPADO (flop check-check / check no turn) e o hero LIDERA mesmo
    # OOP (Eduardo 24/11) — o check-OOP de c-bet padrão não se aplica.
    if (_hia is True and _hero_ip is False and not strong and not has_strong_draw
            and villain_line not in ('delayed', 'checked_turn')):
        info.update(recommended='check',
                    sizing=dict(size_bb=0.0, heuristic=False,
                                basis='check OOP: PFR fora de posição só c-beta valor/draw forte (guia)'),
                    caveats=caveats + ['CBET_OOP_CHECK_MARGINAL'])
        return info
    # C-bet vs SB (guia pós-flop): o SB que COLD-CALLOU tem range mais forte/capado e NÃO
    # over-folda como o BB -> SEM auto-profit de stab. Só VALOR (top pair+ / _STRONG) e draw
    # forte apostam; ar/overcards/par baixo/2º par dão CHECK (vão a showdown; o SB não folda
    # melhor). HU, hero com iniciativa. (top_pair NÃO entra no check -> segue apostando p/ valor.)
    if (_hia is True and n_opp == 1 and _vill_pos == 'SB' and not has_strong_draw
            and (made in _MARGINAL or made in ('air', 'overcards'))):
        info.update(recommended='check',
                    sizing=dict(size_bb=0.0, heuristic=False,
                                basis='check vs SB: SB nao over-folda; ar/marginal vai a showdown (guia)'),
                    caveats=caveats + ['CBET_VS_SB_CHECK_MARGINAL'])
        return info
    # RIVER da linha BET-CHECK-BET (guia): hero c-betou o flop e CHECOU o turn -> range capado-médio;
    # no RIVER value-beta FINO (qualquer par+ com showdown: 2º par/top pair/overpair/dois pares+/
    # flush/sequência) -> bet pequeno (o check no turn capou o range, valor fino lucra). Par baixo/
    # A-high/ar vão a showdown (caem no check abaixo). Gated no sinal villain_line='checked_turn'
    # (NÃO afeta o triple-barrel, que não seta esse sinal). Preempta o check de river (perdeu valor).
    # VALOR FINO: qualquer par+ com showdown (incl. UNDERPAIR — na linha bet-check-bet o range
    # está capado, então o par médio/baixo bate as mãos piores que pagam -> valor fino, guia cap.11).
    _bcb_value = ('second_pair', 'top_pair', 'overpair', 'underpair', 'two_pair', 'set', 'trips',
                  'straight', 'flush', 'full_house', 'quads', 'straight_flush')
    if (_hia is True and street == 'RIVER' and villain_line == 'checked_turn' and n_opp == 1
            and made in _bcb_value and pot_type in (None, 'single_raised', 'unknown')):
        info.update(recommended='bet',
                    sizing=_size(pot, postflop_texture.SMALL, cap,
                                 'valor fino river (bet-check-bet): check no turn capou o range'),
                    caveats=caveats + ['BET_CHECK_BET_RIVER_THIN_VALUE'])
        return info
    # RESOLUÇÃO da tensão de size (aula prática 'c-bet vs BB'): no spot PFR IP vs BB em pote
    # de raise simples HU, c-beta o range INTEIRO com size 1/3 em QUASE TODOS os flops
    # (aposta 1 no pote de 3 só precisa passar >25% -> auto-profit; o BB over-folda). EXCEÇÃO:
    # board baixo CONECTADO (3-8) -> CHECK-RANGE (checa tudo, p/ ter mão forte no turn).
    # C7 (auditoria): 'unknown' (tracking pré-flop piscou) com hero=agressor é tratado como
    # single_raised — senão TODA a agressão do PFR desliga quando a leitura pré-flop falha.
    _cbet_bb_spot = (_hia is True and n_opp == 1 and pot_type in (None, 'single_raised', 'unknown'))
    if _cbet_bb_spot and _cbet_cat == 'low_connected':
        info.update(recommended='check',
                    sizing=dict(size_bb=0.0, basis='check-range: board baixo conectado (3-8) vs BB',
                                heuristic=False),
                    caveats=caveats + ['CBET_VS_BB_CHECK_RANGE_LOW_CONNECTED'])
        return info
    # EXPLOIT flop vs BB que OVERFOLDA (Teoria c-bet vs BB §exploit): vs BB com folds_to_cbet
    # alto, STAB 100% do range com size pequena — inclusive ar/overcards que normalmente
    # dariam check. EXCETO low_connected (tratado acima: lá o BB conecta forte e não folda o
    # bastante). Valor/semi-blefe seguem abaixo (já apostam). Gated no tag folds_to_cbet.
    if (_cbet_bb_spot and street == 'FLOP' and profile
            and 'folds_to_cbet' in (profile.get('tags') or [])
            and made in ('air', 'overcards') and not has_strong_draw):
        info.update(recommended='bet',
                    sizing=_size(pot, postflop_texture.SMALL, cap,
                                 'c-bet 1/3 stab: BB overfolda ao c-bet (exploit vs BB)'),
                    caveats=caveats + ['CBET_VS_BB_EXPLOIT_OVERFOLD_STAB'])
        return info
    # #5 BLEFE DE RIVER em BOARD PAREADO / joga-o-board (guia cap.11 + Eduardo 24/11): o hero NÃO
    # tem showdown próprio (board tem par/trinca, o hero não pareou) -> a ÚNICA forma de ganhar é
    # APOSTAR (WWSF). O blefe REPRESENTA a trinca/boat. BLEFA no CAMPO DURO vs vilão NÃO-passivo;
    # campo mole/station e board de chop (sequência no board) DESISTEM (check abaixo). Mesmo gate
    # do 3º barril de ar; roda ANTES do check de valor-relativo (que senão daria check nessas).
    if (_cbet_bb_spot and street == 'RIVER' and made in ('board_pair_only', 'board_trips')
            and not soft_field and not (profile and profile.get('passive'))
            and not bclass.get('straight_on_board')):
        info.update(recommended='bet',
                    sizing=_size(pot, postflop_texture.BIG, cap,
                                 'blefe river board pareado (campo duro): sem showdown, representa a trinca/boat'),
                    caveats=caveats + ['RIVER_BLUFF_PLAYS_BOARD_CAMPO_DURO'])
        return info
    # PROMOÇÃO RIVER (polarização máxima — Reg-Life): no river IP, mão FEITA que PERDEU VALOR
    # RELATIVO (o board completou draws e ela está abaixo do piso de valor do river — ex.:
    # two pair/overpair/top pair num board de flush/sequência) NÃO value-beta -> CHECK. Mata
    # o leak de pagar/apostar dentro dos draws completos. Nuts/trinca+ seguem (passam o piso)
    # e air cai no ramo de blefe abaixo. Só no spot de barril HU single-raised, hero agressor.
    if (_cbet_bb_spot and street == 'RIVER' and made not in ('air', 'overcards') and made
            and not postflop_river.river_value_ok(made, bclass)):
        info.update(recommended='check',
                    sizing=dict(size_bb=0.0,
                                basis='check: river completou draws, mão perdeu valor relativo (polariza)',
                                heuristic=False),
                    caveats=caveats + ['RIVER_CHECK_PERDEU_VALOR_RELATIVO'])
        return info
    # 3º BARRIL DE RIVER (guia cap.11 + Eduardo 24/11) — BLEFE com mão SEM showdown, GATED POR
    # CAMPO. Ar/overcards (não ganham no check) como AGRESSOR no river BLEFAM pelo pote agora
    # (WWSF: brigar pelos potes sem showdown). SÓ no CAMPO DURO (FT/ICM, há fold equity) e vs
    # vilão NÃO-passivo — o guia proíbe "terceiro barril contra pagador" e "ar em board ruim":
    # campo mole/station e board de chop (sequência no board) DESISTEM (check abaixo). Size
    # grande (polar). Valor já apostou (ramo strong); mão com showdown checou acima.
    # `not flush_possible`: river de flush vai pro bloco de BLOCKER BLUFF (abaixo), que checa o
    # bloqueador (não blefa mão que bloqueia o fold do vilão) e libera OVERBET com o nut-blocker.
    if (_cbet_bb_spot and street == 'RIVER' and made in ('air', 'overcards')
            and not soft_field and not (profile and profile.get('passive'))
            and not bclass.get('straight_on_board') and not bclass.get('flush_possible')
            and postflop_river.river_bluff_blocker_ok(hero, board)):
        info.update(recommended='bet',
                    sizing=_size(pot, postflop_texture.BIG, cap,
                                 '3o barril de river (campo duro): blefe com mao sem showdown (WWSF)'),
                    caveats=caveats + ['RIVER_THIRD_BARREL_BLUFF_CAMPO_DURO'])
        return info
    # VALOR FINO DE RIVER (guia cap.11 + Eduardo 24/11): no river NÃO há pot-control (não vem
    # carta). Mão FEITA que passou o piso de valor (river_value_ok; as que perderam valor
    # relativo já checaram acima) EXTRAI valor fino -> value-beta, não checa. O guia: "valor fino
    # no river" e "Pagador: aumente o size com valor" -> size MAIOR vs station/passivo, fino vs o
    # resto. Valor forte (dois pares+) já apostou no ramo strong. É VALOR, não blefe (sem spew).
    if (_cbet_bb_spot and street == 'RIVER' and made and made not in ('air', 'overcards')
            and not strong and postflop_river.river_value_ok(made, bclass)):
        _vfrac = (postflop_texture.MEDIUM if (profile and profile.get('passive'))
                  else postflop_texture.SMALL)
        info.update(recommended='bet',
                    sizing=_size(pot, _vfrac, cap, 'valor fino de river (guia cap.11): extrai do pagador'),
                    caveats=caveats + ['RIVER_THIN_VALUE'])
        return info
    # GATE ANTI-DONK (LEI Eduardo — NÃO temos estratégia de DONK BET): o hero que PAGOU o
    # pré-flop (DEFENSOR), FORA DE POSIÇÃO e PRIMEIRO a agir no FLOP, CHECA — jamais lidera
    # apostando (donk). Só lidera no flop com INICIATIVA conhecida (_hia is True = c-bet,
    # tratada nos ramos acima) OU com sinal de probe/delayed (ruas posteriores). Ao vivo na
    # Suprema o agressor chega None (_hia None) -> sem este gate a mão feita (strong/top_pair/
    # draw) apostava assim mesmo = o DONK do Q9. Mata o donk mesmo com agressor desconhecido.
    # Só FLOP, só OOP (_hero_oop), só com a vez passada (to_call==0, esta seção toda é lead);
    # NÃO afeta c-bet (hero=agressor), probe/delayed (villain_line), turn/river nem enfrentar
    # aposta (to_call>0, tratado acima).
    if (street == 'FLOP' and to_call == 0 and _hia is not True and _hero_oop
            and villain_line not in ('delayed', 'checked_back')):
        info.update(recommended='check',
                    sizing=dict(size_bb=0.0, heuristic=False,
                                basis='check: defensor OOP primeiro a agir nao lidera (sem donk bet)'),
                    caveats=caveats + ['NO_DONK_CHECK_AS_DEFENDER'])
        return info
    if strong:
        frac, _plan = _bet_fraction(bclass, made, draws, hero_is_aggressor=_hia, spr=spr)
        lean_cv = ['POSTFLOP_TEXTURA_%s' % _plan['lean'].upper()]
        basis = 'valor: %s' % _plan['rationale']
        if _cbet_bb_spot:                        # vs BB: c-bet 1/3 range (auto-profit), não polariza
            frac = postflop_texture.SMALL
            lean_cv = ['CBET_VS_BB_SIZE_1_3']
            basis = 'valor: c-bet 1/3 range vs BB (auto-profit)'
        caveats = caveats + lean_cv
        sizing = _size(pot, frac, cap, basis)
        # B9 (overbet polarizado, EXPLORATÓRIO): com mão NUTADA em rua polar (turn/river),
        # a linha polar inclui OVERBET (>pote). Oferece como OPÇÃO de size; NÃO troca a
        # recomendação (segue 'bet') nem o size primário. Sombra; nunca executa.
        if made in ('full_house', 'quads', 'straight_flush') and street in ('TURN', 'RIVER'):
            over = round(min(pot * 1.25, cap), 1) if cap else round(pot * 1.25, 1)
            sizing = dict(sizing, overbet_option_bb=over, overbet_pct=125)
            caveats = caveats + ['OVERBET_POLAR_EXPLORATORY']
        # PROMOÇÃO RIVER (overbet por vantagem de nuts — Reg-Life): nuts de verdade (fh/quads/
        # sf) no river com board que completou draws -> ALL-IN (executável = botão all-in;
        # overbet-não-allin exigiria arrastar o slider). Extrai o máximo onde o vilão tem
        # segundo-melhor (flush/sequência) que paga. Só no spot de barril HU single-raised.
        if (_cbet_bb_spot and street == 'RIVER' and cap
                and postflop_river.river_jam(made, bclass)):
            sizing = dict(size_bb=round(cap, 1),
                          fraction=(round(cap / pot, 2) if pot else None),
                          bucket='allin', bucket_enforced=True, heuristic=False,
                          basis='all-in: overbet por vantagem de nuts (river)')
            caveats = caveats + ['RIVER_JAM_NUT_ADVANTAGE']
        info.update(recommended='bet', sizing=sizing, caveats=caveats)
        return postflop_exploit.exploit_postflop(info, villain_stats, pot_bb=pot, cap_bb=cap)
    # C-BET RANGE do PFR no FLOP (LEI Eduardo: PFR continua AGRESSIVO; "qualquer equidade
    # mínima OU vantagem de range em combinação do board = c-bet", INCLUSIVE multiway). Em
    # board de c-bet-range (_cbet_cat is None = não perigo) o PFR aposta 1/3 com o RANGE —
    # ar/overcards/par médio/top pair (resolve a passividade: ar nunca c-betava, top pair fino
    # checava). HU: sempre. MULTIWAY: só onde o board FAVORECE o PFR (nuts_holder=='hero'),
    # anti-spew. As fortes já apostaram (ramo strong acima). Size 1/3 fixo. Executável.
    # (draws fortes seguem para o ramo de semi-blefe abaixo, que os trata/tagueia melhor.)
    if (_hia is True and street == 'FLOP' and _cbet_cat is None and not has_strong_draw
            and pot_type in (None, 'single_raised', 'unknown')):
        _pfr_edge = (n_opp == 1) or (
            postflop_texture.nuts_holder(bclass, hero_is_aggressor=True) == 'hero')
        if _pfr_edge:
            _cv = caveats + ['CBET_PFR_RANGE_1_3' + ('' if n_opp == 1 else '_MULTIWAY')]
            _om = out_manipulation(made, draws)          # preserva a tag de manipulação de outs
            if _om:
                _cv = _cv + ['OUT_MANIP_%s' % _om['intent'].upper()]
            info.update(recommended='bet',
                        sizing=_size(pot, postflop_texture.SMALL, cap,
                                     'c-bet 1/3 RANGE vs defensor (PFR, vantagem de range%s)'
                                     % ('' if n_opp == 1 else ' multiway')),
                        caveats=_cv)
            return info
    # DELAYED C-BET no TURN (guia): hero=PFR deu CHECK no flop e o vilão deu CHECK-CHECK -> range
    # capado/fraco; o check no flop disfarçou a mão. Aposta WIDE (c-bet de range, atrasada): par
    # baixo/2º par/A-high/K-high/ar que o barril checaria agora APOSTAM 1/3 (valor forte e draw forte
    # já apostam nos ramos próprios). Gated no sinal villain_line='delayed'. HU single-raised.
    if (_hia is True and street == 'TURN' and villain_line == 'delayed' and _cbet_cat is None
            and not has_strong_draw and n_opp == 1
            and pot_type in (None, 'single_raised', 'unknown')):
        info.update(recommended='bet',
                    sizing=_size(pot, postflop_texture.SMALL, cap,
                                 'delayed c-bet wide: vilao deu check-check (capado/fraco)'),
                    caveats=caveats + ['DELAYED_CBET_WIDE'])
        return info
    # PROBE no TURN (guia §probe): flop foi CHECK-CHECK; o PFR desistiu da iniciativa (range capado/
    # fraco) e o hero (caller) LIDERA o turn apostando WIDE no range capado — par baixo/2º par/top
    # pair/A-high/K-high apostam 1/3; valor forte e draw forte já apostam nos ramos próprios. SÓ o AR
    # PURO (sem par, sem draw, sem overcards) dá check (o guia quase não blefa ar sem outs). Gated no
    # sinal villain_line='checked_back'. HU single-raised.
    if (street == 'TURN' and villain_line == 'checked_back' and _cbet_cat is None
            and not has_strong_draw and not strong and made != 'air' and n_opp == 1
            and pot_type in (None, 'single_raised', 'unknown')):
        info.update(recommended='bet',
                    sizing=_size(pot, postflop_texture.SMALL, cap,
                                 'probe: PFR deu check back (capado), hero lidera wide'),
                    caveats=caveats + ['PROBE_WIDE'])
        return info
    # PROMOÇÃO do barril de turn (a carta DIRIGE a decisão — barril vs BB, Reg-Life): em
    # TURN que FAVORECE O CALLER (completa flush/sequência), as mãos NÃO-valor (que chegaram
    # até aqui; as fortes já apostaram) perdem valor de barril — o range do BB que pagou o
    # flop melhorou -> CHECK (controle de pote; não barrela blefe/thin numa carta que ajudou
    # o vilão). Só no spot de barril HU single-raised com o hero agressor.
    _tb_meta = info.get('turn_barrel') or {}
    _tb_give_up = bool(_tb_meta.get('give_up'))   # pareia carta média/baixa (3/9 em A93)
    _tb_scare = _tb_meta.get('turn_type') in ('completes_flush', 'completes_straight')
    if _cbet_bb_spot and street == 'TURN' and (_tb_scare or _tb_give_up):
        _why = ('turn pareou carta média/baixa do flop (ex. 3/9 em A93), que o BB tem mais'
                if _tb_give_up else 'turn completou draw do caller (barril perde valor)')
        info.update(recommended='check',
                    sizing=dict(size_bb=0.0, basis='check: ' + _why, heuristic=False),
                    caveats=caveats + (['TURN_BARREL_CHECK_GIVE_UP'] if _tb_give_up
                                       else ['TURN_BARREL_CHECK_CALLER_CARD']))
        return info
    # EXPLOIT barril de turn (vs PASSIVO que não lidera — Reg-Life): em carta onde o BB
    # DEVERIA liderar (donk) mas, sendo PASSIVO, só dá check, o check dele fica DESCAPADO
    # (mantém as fortes que deveria ter liderado). Logo o barril de BLEFE (ar/overcards sem
    # draw forte) é ineficaz -> CHECK BACK e realiza equidade. Gated no perfil passivo + spot
    # de barril. Mão de valor/semi-blefe seguem abaixo (valor paga o passivo; draw tem out).
    if (_cbet_bb_spot and street == 'TURN' and profile and profile.get('passive')
            and postflop_turn_barrel.bb_should_donk(board)
            and made in ('air', 'overcards') and not has_strong_draw):
        info.update(recommended='check',
                    sizing=dict(size_bb=0.0,
                                basis='check back: BB passivo não lidera a carta que deveria (check descapado)',
                                heuristic=False),
                    caveats=caveats + ['TURN_BARREL_CHECK_BB_WONT_DONK'])
        return info
    bluff_blocked = cbet_bluff_blocked(n_opp)
    if bluff_blocked:
        caveats.append('CBET_BLUFF_BLOCKED_MULTIWAY_%dOPP' % n_opp)
    if has_strong_draw and not bluff_blocked:
        frac, _plan = _bet_fraction(bclass, made, draws, hero_is_aggressor=_hia, spr=spr)
        caveats.append('SEMI_BLUFF_NEGA_EQUITY_E_CRESCE_POTE')
        sb_basis = 'semi-blefe: %s' % _plan['rationale']
        if _cbet_bb_spot:                            # vs BB: 1/3 range
            frac = postflop_texture.SMALL
            caveats.append('CBET_VS_BB_SIZE_1_3')
            sb_basis = 'semi-blefe: c-bet 1/3 range vs BB'
        else:
            caveats.append('POSTFLOP_TEXTURA_%s' % _plan['lean'].upper())
        _om = out_manipulation(made, draws)          # draw forte -> LIMPEZA
        if _om:
            caveats.append('OUT_MANIP_%s' % _om['intent'].upper())
        info.update(recommended='bet', sizing=_size(pot, frac, cap, sb_basis), caveats=caveats)
        return info
    if made == 'top_pair' and not (bclass['flush_possible'] or bclass['straightish'] >= 3):
        # FREQUÊNCIA do agressor (Pós-flop Avançado): em board POLAR baixo não-pareado, o
        # agressor NÃO aposta mão média — só valor forte + ar polarizam grande. Top pair
        # fino dá CHECK (controle de pote, realiza equidade, bluff-catch). Só quando o hero
        # É o agressor (iniciativa conhecida); senão mantém a aposta fina.
        # Manipulação de outs: mão feita mediana -> MANUTENÇÃO (mantém dominadas do vilão).
        _om = out_manipulation(made, draws)
        _om_cv = ['OUT_MANIP_%s' % _om['intent'].upper()] if _om else []
        # KICKER do top pair (Eduardo 24/11, VALOR): sem range ao vivo o _eq_bucket é None ->
        # o pot-control checava TODO top pair, inclusive TOP KICKER (AK em A-alto = o melhor par,
        # tem que BARRILAR valor; station paga Ax pior). Distingue pelo kicker: Q+ = top pair BOM
        # -> valor (barrila); kicker fraco em board polar -> controle de pote (check).
        _RK = '23456789TJQKA'
        try:
            _btop = max(_RK.index(c[0]) for c in board)
            _hranks = [_RK.index(c[0]) for c in hero]
            _kick = next((r for r in sorted(_hranks, reverse=True) if r != _btop), min(_hranks))
            _tp_strong_kicker = _kick >= _RK.index('Q')
        except Exception:                                 # noqa: BLE001 — leitura ruim -> conservador
            _tp_strong_kicker = False
        # Frequência do agressor: checa mão média em board POLAR (baixo não-pareado) OU em
        # board de PERIGO vs BB (pareado meio). Top pair BOM (kicker Q+) NÃO entra no check -> valor.
        if (_hia is True and (postflop_texture.polarizes(bclass) or _cbet_cat)
                and _eq_bucket not in ('nuts', 'strong') and not _tp_strong_kicker):
            info.update(recommended='check',
                        sizing=dict(size_bb=0.0, basis='check: mão média em board de perigo vs BB (controle de pote)',
                                    heuristic=False),
                        caveats=caveats + ['CHECK_FREQ_BOARD_POLAR_MAO_MEDIA'] + _om_cv)
            return info
        info.update(recommended='bet', sizing=_size(pot, 0.33, cap, 'valor fino top pair, board seco'),
                    caveats=caveats + _om_cv)
        return postflop_exploit.exploit_postflop(info, villain_stats, pot_bb=pot, cap_bb=cap)
    # PROMOÇÃO barril de turn (LADO AGRESSOR — Reg-Life): em TURN OVERCARD (favorece o range
    # IP, que tem as cartas altas; o BB que pagou o flop whiffa), barrela o polo FRACO que
    # tenha EQUIDADE (overcards, gutshot ou backdoor flush) — a polarização teórica quer
    # negar/cuidar nessas cartas boas. Só no spot de barril HU single-raised, hero agressor,
    # não multiway-bloqueado. Size médio (polarização de turn). Ar seco segue de check abaixo.
    if (_cbet_bb_spot and street == 'TURN' and not bluff_blocked
            and not soft_field                              # CAMPO DURO só (FT/ICM, fold equity)
            and not (profile and profile.get('passive'))   # não blefa-barrila um passivo (sticky)
            and (info.get('turn_barrel') or {}).get('turn_type') == 'overcard'
            and made in ('air', 'overcards')
            and (made == 'overcards' or draws.get('gutshot') or draws.get('backdoor_flush'))):
        info.update(recommended='bet',
                    sizing=_size(pot, postflop_texture.MEDIUM, cap,
                                 'barril: turn overcard favorece o agressor (polo fraco c/ equidade)'),
                    caveats=caveats + ['TURN_BARREL_OVERCARD_AGGRESSOR'])
        return info
    # PROMOÇÃO RIVER (blefe polarizado por BLOQUEADOR — Reg-Life): no river IP, mão do bottom
    # (ar/overcards) blefa em frequência ALTA, mas SÓ se (a) o BLOQUEADOR é bom (não bloqueia
    # o range de fold do vilão) e (b) há sinal de FOLD (vilão não é station/fish e tem
    # leitura: nit/reg/lag foldam o river). Vs station/fish ou sem leitura -> check (não
    # spewa). Size grande (polar). Só no spot de barril HU single-raised.
    if (_cbet_bb_spot and street == 'RIVER' and not bluff_blocked
            and made in ('air', 'overcards')
            and postflop_river.river_bluff_blocker_ok(hero, board)):
        _rvp = classify_villain(villain_stats) if villain_stats else None
        _read_fold = bool(_rvp and _rvp.get('category') not in ('unknown', 'fish')
                          and 'station' not in _rvp.get('tags', []))
        # CAMPO DURO (FT/ICM) assume fold equity mesmo SEM leitura de HUD; vilão passivo/station
        # ou campo mole -> NÃO blefa (cai no check abaixo, sem spew).
        _hard_fold = (not soft_field and not (profile and profile.get('passive')))
        if _read_fold or _hard_fold:
            # OVERBET/JAM (Eduardo 24/11): quando o hero segura o BLOQUEADOR DA NUTS (Á do naipe
            # do flush de 3+ no board), REPRESENTA o nut flush e bloqueia o call top -> overbet
            # polar (jam). Blefe + nuts no MESMO size gigante = range balanceada e máxima fold eq.
            _fs = next((s for s in 'cdhs' if sum(1 for c in board if c[1] == s) >= 3), None)
            _nut_blocker = bool(_fs and any(c[1] == _fs and c[0] == 'A' for c in hero))
            if _nut_blocker and cap:
                info.update(recommended='all_in',
                            sizing=dict(size_bb=round(cap, 1), bucket='allin', bucket_enforced=True,
                                        heuristic=False,
                                        basis='overbet/jam de blefe: bloqueador de nut flush (polar)'),
                            caveats=caveats + ['RIVER_BLUFF_OVERBET_NUT_BLOCKER'])
                return info
            info.update(recommended='bet',
                        sizing=_size(pot, postflop_texture.BIG, cap,
                                     'blefe polar de river (bottom, bloqueador ok, campo duro/folda)'),
                        caveats=caveats + ['RIVER_BLUFF_POLAR'])
            return info
    # EXPLOIT (HUD): passaram a vez com AR (sem showdown value) -> normalmente check;
    # mas vs vilão que FOGE de c-bet (tag folds_to_cbet), blefa com size pequeno (a fold
    # equity é alta). Só o ar — mão média tem showdown value e segue de check.
    if (profile and 'folds_to_cbet' in profile.get('tags', [])
            and made in ('air', 'overcards') and not bluff_blocked and street != 'RIVER'):
        # No RIVER o blefe é governado pela branch polar acima (com seleção por bloqueador);
        # aqui é a c-bet-blefe de flop/turn (size pequeno, fold equity alta).
        info.update(recommended='bet', sizing=_size(pot, 0.4, cap, 'c-bet blefe vs folds_to_cbet'),
                    caveats=caveats + ['EXPLOIT_CBET_BLUFF_VS_FOLDCBET'])
        return info
    # Mãos médias/marginais/ar com valor de showdown ou sem: check.
    caveats.append('CHECK_SHOWDOWN_OR_GIVEUP')
    info.update(recommended='check',
                sizing=dict(size_bb=0.0, basis='check', heuristic=False), caveats=caveats)
    return info
