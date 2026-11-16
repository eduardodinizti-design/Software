"""End-to-end: read one PPPoker table crop and produce an exploratory read-out.

Ties together the readers (hero cards, table state, hand id, board) and the
PreflopAdvisor so that, for one frame, the bot prints what it sees and what it
would do. Observation only: no capture, no clicks, execution never allowed.
Preflop advice comes from the PreflopAdvisor (spot inferred from the bets); from
the flop on, the postflop_advisor attaches a founded-heuristic read (phase
'postflop'). Both are exploratory and never executable (the armed operator plays
preflop only and skips anything marked postflop).
"""
import argparse
import json

import cv2

from table_reading.pipeline import configure_ocr
from table_reading.ocr_runtime import ocr_frame
from table_reading.table_state import read_table_state
from table_reading.community_cards import read_board
from table_reading.hand_tracking import read_hand_id
from table_reading.tournament import read_tournament, tournament_context
from preflop_advisor import PreflopAdvisor, infer_spread
from postflop_advisor import advise_postflop
from preflop_context import villain_postflop_range
import solver_cbet_shadow
import solver_pr12_shadow
import solver_sb40_shadow


def read_hero_card_slots(crop):
    """Candidatos por slot do hero: 2 entradas (card_candidate ou None cada). Base
    da leitura por frame E da memória temporal por-slot, que recupera o par quando
    um slot pisca AMBÍGUO num frame mas lê no outro ([[hero_card_memory]])."""
    from table_reading.inspect_cards import inspect
    reading = inspect(crop, (0, 0, crop.shape[1], crop.shape[0]))
    slots = [c.get('card_candidate') for c in reading.get('hero_rank_candidates', [])]
    return slots if len(slots) == 2 else [None, None]


def _pair_from_slots(slots):
    """Par válido (2 cartas distintas e lidas) ou None."""
    if len(slots) != 2 or not all(slots) or slots[0] == slots[1]:
        return None
    return list(slots)


def read_hero_cards(crop):
    """Hero's two face-up cards, or None when not readable/duplicate."""
    return _pair_from_slots(read_hero_card_slots(crop))


def _pot_type_from_context(ctx):
    """Tipo de pote a partir do contexto do rastreador, p/ o gating honesto do
    pós-flop: sem contexto/sem raise -> 'unknown'; não-HU -> 'multiway'; >=2 níveis de
    raise -> 'three_bet'; 1 nível -> 'single_raised' (pote de um raise só)."""
    if ctx is None or ctx.get('pending'):
        return 'unknown'                     # sem contexto ou ID pendente (#A5): não arrisca
    if not ctx['heads_up']:
        return 'multiway'
    if ctx['raises'] >= 2:
        return 'three_bet'
    if ctx['raises'] == 1:
        return 'single_raised'
    return 'unknown'


def _postflop_in_context(advisor, tracker, state, hero, board, *, mode, stage, table_key):
    """Recalcula o conselho pós-flop usando o CONTEXTO rastreado entre frames: deriva
    pot_type (gating), aggressor (iniciativa) e o range do vilão (equity no HU, pote de
    um raise só) e rechama advise_postflop. Espelha o que o operador armado já fazia,
    agora disponível a qualquer observador contínuo que passe um `tracker`."""
    ctx = tracker.context(table_key)
    if ctx and ctx.get('pending'):
        ctx = None                           # ID ilegível: não aplica range/iniciativa antigos (#A5)
    seats = state.get('seats') or {}
    spread = (infer_spread({p: (seats.get(s) or {}).get('stack_bb')
                            for s, p in (state.get('positions') or {}).items()})
              if mode in ('icm', 'pko_icm') else None)
    ptype = _pot_type_from_context(ctx)
    combos, meta = villain_postflop_range(advisor, ctx, mode=mode, stage=stage, spread=spread,
                                          hero_stack_bb=(seats.get('hero') or {}).get('stack_bb'))
    # Exploit do HUD: stats do VILÃO (lidos por advise_table em state['hud']). HU = o
    # agressor rastreado, ou o único vilão com HUD lido.
    vstats = None
    hud = state.get('hud') or {}
    if hud:
        positions = state.get('positions') or {}
        aggr = (ctx or {}).get('aggressor')
        vseat = next((s for s, p in positions.items() if p == aggr), None) if aggr and aggr != 'hero' else None
        if vseat is None and len(hud) == 1:
            vseat = next(iter(hud))
        ventry = hud.get(vseat) if vseat else None
        # Só exploita com leitura CONFIÁVEL (8/8 high) E RECÉM-RECONFIRMADA (_age 0, #A7):
        # 'partial' pode ter campo mal-lido/linha trocada num skin não calibrado, e um
        # refresh que falhou (valor velho mantido p/ continuidade) não deve alimentar o
        # exploit como se fosse fresco.
        vstats = (ventry['stats'] if (ventry and ventry.get('confidence') == 'high'
                                      and not ventry.get('_age')) else None)
    advice = advise_postflop(state, hero, board['cards'], street=board.get('street'),
                             mode=mode, stage=stage, aggressor=(ctx or {}).get('aggressor'),
                             villain_range=(combos or None), pot_type=ptype, narrow_range=True,
                             villain_stats=vstats)
    if isinstance(advice, dict):
        # Observabilidade: qual range foi usado (ou o motivo de ter ficado na Fase 1).
        advice['villain_range_source'] = meta if combos else {'reason': meta}
        _attach_solver_shadow(advice, ctx, seats, state, hero, board, ptype, mode)
    return advice


def _attach_solver_shadow(advice, ctx, seats, state, hero, board, ptype, mode):
    """Anexa a SOMBRA do solver (pacote btn_vs_bb_25) quando o spot ao vivo é o que o
    TexasSolver resolveu: FLOP, pote de um raise só, BTN vs BB ~25bb, chip EV, e o board
    cai num dos 100 flops (por isomorfismo). PURO overlay de estudo/auditoria: não troca
    `recommended` nem libera execução (segue o gate — solver em sombra até homologação).
    Fora da cobertura não faz nada."""
    if advice.get('phase') != 'postflop' or advice.get('street') != 'FLOP':
        return
    if ptype != 'single_raised':
        return                                   # só pote de um raise só (HU)
    positions = state.get('positions') or {}
    hero_pos = positions.get('hero')
    vseat = next((s for s in (seats or {})
                  if s != 'hero' and (seats.get(s) or {}).get('occupied')), None)
    villain_pos = positions.get(vseat) if vseat else None
    try:
        shadow = solver_cbet_shadow.lookup(
            hero, board.get('cards'), hero_pos=hero_pos, villain_pos=villain_pos,
            to_call_bb=advice.get('to_call_bb'), pot_bb=advice.get('pot_bb'),
            hero_stack_bb=(seats.get('hero') or {}).get('stack_bb'),
            villain_stack_bb=(seats.get(vseat) or {}).get('stack_bb') if vseat else None,
            mode=mode, aggressor=(ctx or {}).get('aggressor'))
    except Exception:                            # noqa: BLE001 — sombra nunca quebra o conselho
        shadow = None
    if shadow:
        advice['solver_shadow'] = shadow
        advice.setdefault('caveats', [])
        for cav in shadow.get('caveats', []):
            if cav not in advice['caveats']:
                advice['caveats'].append(cav)
        _prefer_solver_on_covered_spot(advice, shadow)
    # Cross-check PR#12 (2ª referência, mais convergida, árvore bet-1/3): no flop As7d2c
    # da c-bet do BTN, anexa a opinião independente p/ ESTUDO (não vira recomendação —
    # evita duas fontes brigando; o pacote de 100 flops é a fonte preferida sistemática).
    if (advice.get('street') == 'FLOP' and hero_pos == 'BTN'
            and (advice.get('to_call_bb') in (0, None))):
        try:
            pr12 = solver_pr12_shadow.flop_cbet(hero, board.get('cards'))
        except Exception:                        # noqa: BLE001
            pr12 = None
        if pr12:
            advice['solver_shadow_pr12'] = pr12
            advice.setdefault('caveats', [])
            if 'SOLVER_CROSSCHECK_PR12_AS7D2C' not in advice['caveats']:
                advice['caveats'].append('SOLVER_CROSSCHECK_PR12_AS7D2C')
    # Cross-check SB x BB 40bb SRP (estudo do outro agente, AMOSTRAGEM INCREMENTAL):
    # a sombra é PARCIAL (cresce leva a leva), então é ESTUDO/auditoria — anexa a opinião
    # do solver no flop-lead do SB (OOP, 1º a agir), sem trocar `recommended` nem liberar
    # execução. Só engata no contexto exato: SB OOP, BB, ~40bb, pote single-raised, chip-EV.
    if (advice.get('street') == 'FLOP' and hero_pos == 'SB'
            and (advice.get('to_call_bb') in (0, None))
            and solver_sb40_shadow.context_matches(
                (hero_pos, villain_pos), ptype, mode,
                (seats.get('hero') or {}).get('stack_bb'))):
        try:
            sb40 = solver_sb40_shadow.flop_policy(hero, board.get('cards'))
        except Exception:                        # noqa: BLE001 — sombra nunca quebra o conselho
            sb40 = None
        if sb40:
            advice['solver_shadow_sb40'] = sb40
            advice.setdefault('caveats', [])
            if 'SOLVER_CROSSCHECK_SB40_SRP' not in advice['caveats']:
                advice['caveats'].append('SOLVER_CROSSCHECK_SB40_SRP')


# Mapa size do solver -> fração de pote (p/ o sizing quando a sombra manda apostar).
_SOLVER_BET_FRACTION = {'b33': 0.33, 'b50': 0.50, 'b70': 0.70, 'allin': None}


def _prefer_solver_on_covered_spot(advice, shadow):
    """Homologação: onde há VERDADE do solver (nó per-combo DECISIVO), a recomendação
    passa a ser a do SOLVER, não a da heurística — que, medida contra o solver neste
    spot, acerta ~42%% (postflop_homologation). NÃO libera execução (segue gated) e NÃO
    toca nó misto (coinflip não vira regra) nem o lado `def` (agregado de range, não é
    específico da mão). Preserva a leitura da heurística em `heuristic_recommended`."""
    if shadow.get('side') != 'agg' or not shadow.get('combo_in_range') or not shadow.get('decisive'):
        return
    coarse = shadow.get('coarse')             # 'check' ou 'bet'
    if coarse not in ('check', 'bet'):
        return
    prev = (advice.get('recommended') or '').lower()
    advice['heuristic_recommended'] = advice.get('recommended')
    advice['recommended'] = coarse
    advice['recommended_source'] = 'solver_shadow'
    advice['execution_allowed'] = False       # reafirma o gate: sombra homologada NÃO executa
    if coarse == 'bet':
        frac = _SOLVER_BET_FRACTION.get(shadow.get('bet_size'))
        pot = advice.get('pot_bb')
        size_bb = (round(pot * frac, 1) if isinstance(pot, (int, float)) and frac
                   else (advice.get('spr') and None))
        advice['sizing'] = dict(size_bb=size_bb, solver_size=shadow.get('bet_size'),
                                basis='solver c-bet (%s)' % shadow.get('bet_size'),
                                heuristic=False)
    else:
        advice['sizing'] = dict(size_bb=0.0, basis='solver check', heuristic=False)
    tag = 'SOLVER_PREFERRED_ON_COVERED_SPOT'
    if tag not in advice['caveats']:
        advice['caveats'].append(tag)
    if prev and prev != coarse:
        advice['caveats'].append('SOLVER_OVERRODE_HEURISTIC_%s_TO_%s' % (prev.upper(), coarse.upper()))


def advise_table(crop, advisor, *, mode=None, stage=None, stabilizer=None, table_key='default',
                 villain_range=None, hero_override=None, tracker=None, bounty_bb=None,
                 enable_hud=False, read_cache=None):
    """Read the table and attach an exploratory recommendation. The tournament
    phase chooses chip EV vs ICM unless mode/stage are forced. Pure read; the
    caller wraps it in an ocr_frame so one snapshot reuses OCR.

    `stabilizer` (opcional, PositionStabilizer): suaviza as POSIÇÕES ao longo dos
    frames — o leitor é stateless e os rótulos oscilam quando a ocupação/dealer
    pisca; o estabilizador trava o dealer (debounce) e usa ocupação por maioria.
    `table_key` identifica a mesa p/ o estado por-mesa do estabilizador."""
    state = read_table_state(crop)
    hand = read_hand_id(crop)
    if stabilizer is not None:
        occ = [s for s, d in (state.get('seats') or {}).items() if d.get('occupied')]
        hkey = (hand or {}).get('hand_id') or (hand or {}).get('hand_number')
        sdealer, spos = stabilizer.update(table_key=table_key, hand_key=hkey,
                                          dealer_seat=state['dealer'].get('seat'),
                                          occupied_seats=occ)
        # As posições do estabilizador são AUTORITATIVAS: {} (pendente/sem dealer)
        # força abstenção em vez de cair na leitura crua que oscila. Mantém o dealer
        # original quando o estável é None (não enfraquece o is_table).
        new_dealer = dict(state['dealer'], stabilized=True)
        if sdealer is not None:
            new_dealer['seat'] = sdealer
        state = dict(state, positions=spos, dealer=new_dealer)
    hero_slots = read_hero_card_slots(crop)
    hero = _pair_from_slots(hero_slots)
    # As cartas do hero são imutáveis na mão: se este frame não leu mas o chamador
    # tem uma leitura confiável da MESMA mão (hero_override), reusa — evita abster
    # (HERO_CARDS_UNKNOWN) por falha pontual de leitura/animação num frame. O
    # override vem da memória temporal por-slot ([[hero_card_memory]]).
    if hero is None and hero_override and len(hero_override) == 2:
        hero = list(hero_override)
    board = read_board(crop, hero_cards=hero or [None, None])
    tourney = read_tournament(crop)
    auto_mode, auto_stage = tournament_context(tourney)
    use_mode, use_stage = mode or auto_mode, stage or auto_stage
    # Reject a crop that carries no table field at all (a lobby/tournament list the
    # detector picked up as a false-positive blue table).
    is_table = (state['pot'].get('pot_bb') is not None or state['dealer'].get('seat') is not None
                or tourney.get('paid') is not None or hero is not None
                or any(s['stack_bb'] is not None for s in state['seats'].values()))
    if not is_table:
        return dict(hand=hand, hero_cards=hero, hero_slots=hero_slots, board=board, table_state=state, tournament=tourney,
                    context=dict(mode=use_mode, stage=use_stage), is_table=False,
                    advice=dict(status='SKIP', reason='NAO_PARECE_MESA_LOBBY', exploratory=True, execution_allowed=False))
    # PKO: lê o bounty por assento e anexa ao estado (p/ o call-off escalar a caça pelo
    # bounty do vilão). Só com o overlay armado (bounty_bb) e torneio PKO, p/ não pagar o
    # custo de OCR fora disso. Best-effort: assentos ilegíveis simplesmente não entram.
    if bounty_bb and use_mode in ('pko', 'pko_icm'):
        occ = [s for s, d in (state.get('seats') or {}).items() if d.get('occupied')]
        if read_cache is not None:          # cache: relê só a cada N frames (latência)
            state = dict(state, bounties=read_cache.bounties(crop, table_key, occ))
        else:
            from table_reading.bounty import read_seat_bounties
            bread = read_seat_bounties(crop, seats=occ)
            state = dict(state, bounties={s: v['value'] for s, v in bread.items() if v['value'] is not None})
    # HUD VIP (opcional): lê os 8 stats por vilão e anexa a state['hud'] (p/ o exploit
    # no pós-flop). Custo ALTO (~1s/8 assentos) -> com read_cache, relê só a cada N frames.
    if enable_hud:
        occ = [s for s, d in (state.get('seats') or {}).items() if d.get('occupied')]
        if read_cache is not None:
            state = dict(state, hud=read_cache.huds(crop, table_key, occ))
        else:
            from table_reading.hud_reader import read_seat_huds
            state = dict(state, hud=read_seat_huds(crop, occ))
    # Postflop guard. A read board (cards) is clearly postflop. A board that was
    # DETECTED but not fully read (incomplete, duplicate, or obstructed with the
    # anchor found) is also postflop and must abstain, not be treated as preflop.
    # Preflop itself has no board, which reads as 'anchor missing' -> advise.
    board_status, board_reason = board.get('status'), board.get('reason')
    board_present_unread = (board_status in ('BOARD_INCOMPLETE', 'BOARD_DUPLICATE_REJECTED')
                            or (board_status == 'BOARD_PARTIAL_OR_OBSTRUCTED'
                                and board_reason != 'FIRST_CARD_ANCHOR_MISSING'))
    if board.get('cards'):
        if hero is None:
            advice = dict(status='ABSTAIN', reason='HERO_CARDS_UNKNOWN', phase='postflop',
                          exploratory=True, execution_allowed=False)
        else:
            advice = advise_postflop(state, hero, board['cards'], street=board.get('street'),
                                     mode=use_mode, stage=use_stage, villain_range=villain_range)
    elif board_present_unread:
        advice = dict(status='ABSTAIN', reason='BOARD_PRESENT_BUT_UNREADABLE', exploratory=True, execution_allowed=False)
    elif hero is None:
        advice = dict(status='ABSTAIN', reason='HERO_CARDS_UNKNOWN', exploratory=True, execution_allowed=False)
    else:
        # `bounty_bb` (PKO, opcional): só o call-off o usa, e só engata se o torneio
        # ler como PKO (use_mode pko/pko_icm) e o hero cobrir o shove.
        advice = advisor.advise_from_reading(state, hero, mode=use_mode, stage=use_stage,
                                             bounty_bb=bounty_bb)
        if isinstance(advice, dict):
            advice.setdefault('caveats', []).append('SPOT_INFERRED_FROM_BETS')
    # Contexto ENTRE frames (opcional): atualiza o rastreador do agressor pré-flop e,
    # no pós-flop, recalcula o conselho com pot_type/iniciativa/range do vilão. Só é
    # útil a observadores CONTÍNUOS (um frame único não tem histórico pré-flop).
    if tracker is not None:
        hkey = (hand or {}).get('hand_id') or (hand or {}).get('hand_number')
        has_board = bool(board.get('cards'))
        tracker.update(table_key=table_key, hand_key=hkey, table_state=state, has_board=has_board)
        if has_board and hero is not None and isinstance(advice, dict) and advice.get('phase') == 'postflop':
            advice = _postflop_in_context(advisor, tracker, state, hero, board,
                                          mode=use_mode, stage=use_stage, table_key=table_key)
    return dict(hand=hand, hero_cards=hero, hero_slots=hero_slots, board=board, table_state=state, is_table=True,
                tournament=tourney, context=dict(mode=use_mode, stage=use_stage), advice=advice)


def _summary(result):
    st = result['table_state']
    occ = [s for s, d in st['seats'].items() if d['occupied']]
    tour = result['tournament']
    lines = ['=== LEITURA DA MESA (observacao, sem cliques) ===',
             'Mao: %s | Dealer: %s | Pote: %s BB | Pagar: %s BB' % (
                 result['hand'].get('hand_number'), st['dealer'].get('seat'),
                 st['pot'].get('pot_bb'), st['to_call'].get('to_call_bb')),
             'Fase: pagos=%s restantes=%s -> %s/%s' % (
                 tour.get('paid'), tour.get('players_left'),
                 result['context']['mode'], result['context']['stage']),
             'Hero: %s' % (result['hero_cards'] or 'nao identificado'),
             'Assentos ocupados: %d' % len(occ)]
    for seat in occ:
        d = st['seats'][seat]
        lines.append('  %-9s pos=%-5s stack=%s BB%s' % (
            seat, st['positions'].get(seat, '-'), d['stack_bb'],
            ' [DEALER]' if st['dealer'].get('seat') == seat else ''))
    bets = [b for b in (st.get('bets') or []) if isinstance(b.get('bet_bb'), (int, float))]
    if bets:   # per-seat bets drive the spot inference; log them to diagnose it
        lines.append('Bets: ' + ', '.join(
            '%s=%sbb(%s)' % (b['seat'], b['bet_bb'], st['positions'].get(b['seat'], '-')) for b in bets))
    adv = result['advice']
    lines.append('=== RECOMENDACAO (exploratoria, nao-executar) ===')
    if adv.get('phase') == 'postflop' and adv.get('status') == 'ADVICE':
        sz = adv.get('sizing') or {}
        size_txt = ' %.1fbb (%s)' % (sz['size_bb'], sz.get('basis', '')) if sz.get('size_bb') else ''
        extra = []
        if adv.get('pot_odds') is not None:
            extra.append('pot odds %.0f%%' % (adv['pot_odds'] * 100))
        if adv.get('draw_equity') is not None:
            extra.append('eq draw ~%.0f%%' % (adv['draw_equity'] * 100))
        if adv.get('spr') is not None:
            extra.append('SPR %.1f' % adv['spr'])
        lines.append('POSFLOP %s: %s%s | mao: %s (%s) | outs: %s%s' % (
            adv.get('street'), str(adv['recommended']).upper(), size_txt,
            adv.get('made'), adv.get('category'), adv.get('outs'),
            (' | ' + ', '.join(extra)) if extra else ''))
        sh = adv.get('solver_shadow')
        if sh:
            mixtxt = ', '.join('%s %d%%' % (m['action'], round(m['frequency'] * 100))
                               for m in (sh.get('mix') or [])) or '(mao fora do range de open)'
            lines.append('  SOMBRA solver [%s %s%s]: %s -> %s (freq, nao-executar)' % (
                sh.get('spot'), sh.get('node'), ' iso' if sh.get('iso') else '',
                str(sh.get('recommended_shadow')).upper(), mixtxt))
    elif adv.get('status') == 'ADVICE':
        mix = ', '.join('%s %d%%' % (m['action'], round(m['frequency'] * 100)) for m in adv['mix'])
        sz = adv.get('sizing') or {}
        size_txt = ''
        if sz.get('size_bb') is not None:
            size_txt = ' -> %s BB (%s%s)' % (sz['size_bb'], sz.get('basis', ''),
                                             '; heuristica' if sz.get('heuristic') else '')
        caveats = adv.get('caveats') or []
        deep = ''
        if 'STACK_ABOVE_SOLVED_DEPTH_100BB_REFERENCE' in caveats:
            deep = ' [ref 100bb p/ %sbb deep]' % adv.get('stack_bb')
        mw = next((c for c in caveats if c.startswith('MULTIWAY_') and 'CALLERS' in c), None)
        if mw:
            deep += ' [multiway aprox: %s caller(s) via vs_open]' % mw.split('_')[1]
        lines.append('ACAO: %s%s | mix: %s | stack usado: %sbb%s | no: %s' % (
            adv['recommended'].upper(), size_txt, mix, adv['stack_bucket'], deep, adv['node_id']))
    else:
        lines.append('ABSTEM: %s' % adv.get('reason'))
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ranges', required=True, help='nvt-ranges-validados.json')
    p.add_argument('--deep', default=None, help='Pacote deep 40/100bb opcional (reference, nao validado)')
    p.add_argument('--imagem', required=True, help='Recorte de uma mesa (PNG)')
    p.add_argument('--mode', default=None, help='Forca o modo; padrao: detecta da fase do torneio')
    p.add_argument('--stage', default=None, help='Forca o estagio; padrao: detecta da fase')
    p.add_argument('--json', action='store_true')
    args = p.parse_args(argv)
    advisor = PreflopAdvisor.from_files(args.ranges, args.deep) if args.deep else PreflopAdvisor.from_file(args.ranges)
    crop = cv2.imread(args.imagem)
    if crop is None:
        raise SystemExit('Nao consegui ler a imagem: ' + args.imagem)
    configure_ocr()
    with ocr_frame():
        result = advise_table(crop, advisor, mode=args.mode, stage=args.stage)
    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != 'table_state'}, ensure_ascii=False, indent=2, default=str))
    else:
        print(_summary(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
