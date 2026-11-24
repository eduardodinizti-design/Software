"""Raise-sizing for the preflop advice, matched to the solver's betting tree.

Sizes are NOT taken from the button label or the pack's historical bets (the
handoff and the cursor spec forbid that). They mirror the sizes the HRC ranges
were solved against: open 2bb (2.5bb at 100bb), 3bet to 2.5x the open in
position / 2.9x from the SB / 3.4x from the BB, 4bet all-in. Isolating limpers
is not in the solved tree, so that add stays a flagged heuristic. Folds, checks,
calls, limps and all-ins are exact.
"""
# Solver betting-tree sizes, in big blinds.
OPEN_RAISE_BB = 2.0           # first-in open at <=40bb
OPEN_RAISE_DEEP_BB = 2.5      # first-in open at 100bb
OPEN_DEEP_THRESHOLD_BB = 40   # above this, use the deep open size
# OPEN sem limper = 2x SEMPRE (2.5x só deep+reg) — LEI open=2x INTACTA (limpers==0).
# ISO vs LIMPERS (Eduardo 23/11 REVERTEU a regra do 21/11): isolar limper INFLA o size — +1bb por
# limper a partir do open 2x => 1 limper=3X, 2 limpers=4X, CAPADO em 4X (ISO_MAX_BB) p/ não voltar ao
# runaway 5X. Só vale quando há limper; o open puro continua 2x. Ver nvt-padrao-de-jogo-henrique.
ISO_ADD_PER_LIMPER_BB = 1.0
ISO_MAX_BB = 4.0              # teto do iso vs limpers = 4X (Eduardo 23/11)
# 3bet-to como múltiplo do open (REGRA do Eduardo, 19/11): 3x em posição, 4x fora de
# posição. SÓ na RETA FINAL do torneio (stage 'ft') diminui p/ 2.5x IP e 3.5x OOP.
THREEBET_IP_MULT = 3.0        # IP, torneio normal
THREEBET_OOP_MULT = 4.0       # OOP, torneio normal
THREEBET_IP_FT_MULT = 2.5     # IP, reta final (FT)
THREEBET_OOP_FT_MULT = 3.5    # OOP, reta final (FT)


def open_size_bb(hero_stack_bb, registration_open=False):
    """Tamanho do open (regra do Eduardo, 15/11): 2.0bb SEMPRE, exceto 2.5bb só no
    INÍCIO DO TORNEIO — enquanto a INSCRIÇÃO (late reg) ainda está ABERTA E o stack
    é deep (>40bb). Fechada a inscrição, ou stack curto -> 2.0bb. Sem o sinal de
    inscrição (default), assume FECHADA = 2.0bb (default seguro pedido pelo Eduardo)."""
    if (registration_open and isinstance(hero_stack_bb, (int, float))
            and hero_stack_bb > OPEN_DEEP_THRESHOLD_BB):
        return OPEN_RAISE_DEEP_BB
    return OPEN_RAISE_BB


def three_bet_mult(ip, final_table=False):
    """3bet-to ×open (Eduardo 19/11): IP 3x, OOP 4x; na RETA FINAL (FT) IP 2.5x, OOP 3.5x.
    SB/BB vs um abridor mais tarde são OOP (o flag `ip` já resolve isso)."""
    if ip:
        return THREEBET_IP_FT_MULT if final_table else THREEBET_IP_MULT
    return THREEBET_OOP_FT_MULT if final_table else THREEBET_OOP_MULT

# Postflop action order (SB first, BTN last = in position).
_POSTFLOP_ORDER = ('SB', 'BB', 'UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN')


def count_limpers(table_state):
    """Non-hero, non-blind seats that just called the BB (bet ~1bb)."""
    positions = table_state.get('positions') or {}
    n = 0
    for bet in (table_state.get('bets') or []):
        seat, amount = bet.get('seat'), bet.get('bet_bb')
        if seat == 'hero' or not isinstance(amount, (int, float)):
            continue
        if 0.9 <= amount <= 1.1 and positions.get(seat) not in ('BB', 'SB'):
            n += 1
    return n


def opener_raise_bb(table_state):
    """The largest non-hero bet above the BB = the opener's raise-to size, or None."""
    best = None
    for bet in (table_state.get('bets') or []):
        seat, amount = bet.get('seat'), bet.get('bet_bb')
        if seat == 'hero' or not isinstance(amount, (int, float)):
            continue
        if amount > 1.5 and (best is None or amount > best):
            best = amount
    return best


def in_position(hero_position, opener_position):
    """Will the hero act after the opener post-flop? (BTN last, blinds first.)"""
    if hero_position not in _POSTFLOP_ORDER or opener_position not in _POSTFLOP_ORDER:
        return True
    return _POSTFLOP_ORDER.index(hero_position) > _POSTFLOP_ORDER.index(opener_position)


def recommend_size(action, *, hero_stack_bb=None, to_call_bb=None, limpers=0,
                   opener_bb=None, ip=True, hero_position=None, registration_open=False,
                   final_table=False):
    """{action, size_bb, basis, heuristic} for one action, or None for fold.

    Open/3bet/4bet sizes come from the solver betting tree; isolating limpers is a
    flagged heuristic; call/limp/all-in/check are exact amounts."""
    cap = hero_stack_bb if isinstance(hero_stack_bb, (int, float)) else None

    def capped(size):
        return round(min(size, cap), 1) if cap is not None else round(size, 1)

    if action == 'fold':
        return None
    if action == 'check':
        return dict(action='check', size_bb=0.0, basis='check', heuristic=False)
    if action == 'call':
        return dict(action='call', size_bb=to_call_bb, basis='to_call', heuristic=False)
    if action == 'limp':
        return dict(action='limp', size_bb=capped(1.0), basis='bb', heuristic=False)
    if action in ('all_in', 'open_shove', 'vs_open_shove', 'three_bet_shove', 'four_bet_shove'):
        return dict(action=action, size_bb=cap, basis='all-in', heuristic=False)
    if action in ('raise', 'open_raise'):
        open_bb = open_size_bb(hero_stack_bb, registration_open)
        if limpers:
            # ISO vs LIMPERS (Eduardo 23/11): +1bb por limper sobre o open 2x, CAPADO em 4X ->
            # 1 limper=3X, 2 limpers=4X, 3+ = 4X. (Reverteu o "não inflar" do 21/11.)
            size = min(open_bb + ISO_ADD_PER_LIMPER_BB * limpers, ISO_MAX_BB)
            return dict(action='raise', size_bb=capped(size), heuristic=True,
                        basis='iso %.1fbb vs %d limper(s) (3X/4X cap, Eduardo 23/11)' % (size, limpers))
        # OPEN puro (sem limper) = tamanho do open SEMPRE (LEI open=2x).
        return dict(action='raise', size_bb=capped(open_bb), heuristic=False,
                    basis='open %.1fbb (solver)' % open_bb)
    if action == 'three_bet':
        base = opener_bb if isinstance(opener_bb, (int, float)) else open_size_bb(hero_stack_bb)
        mult = three_bet_mult(ip, final_table)
        pos = 'IP' if ip else 'OOP'
        return dict(action='three_bet', size_bb=capped(base * mult), heuristic=False,
                    basis='3bet %.1fx open (%s%s)' % (mult, pos, ' reta-final' if final_table else ''))
    if action == 'four_bet':
        return dict(action='four_bet', size_bb=cap, basis='4bet all-in (solver)', heuristic=False)
    return None


def _sb_completed(table_state):
    """SB completou (~1bb) = o 'limper' da BATALHA DE BLINDS. count_limpers() exclui blinds, então
    o complete do SB não entra lá; aqui ele conta como 1 limper p/ o BB isolar a 3X (regra Eduardo)."""
    positions = table_state.get('positions') or {}
    sb = next((s for s, p in positions.items() if p == 'SB'), None)
    if sb is None:
        return False
    for bet in (table_state.get('bets') or []):
        if bet.get('seat') == sb and isinstance(bet.get('bet_bb'), (int, float)):
            return 0.9 <= bet['bet_bb'] <= 1.1
    return False


def size_from_reading(action, table_state, hero_position, opener_position=None, stage=None):
    """Convenience: build the context from a read_table_state result and size the action.
    `stage=='ft'` (reta final) reduz os 3bets (2.5x IP / 3.5x OOP)."""
    hero = (table_state.get('seats') or {}).get('hero', {})
    limpers = count_limpers(table_state)
    # BLIND WAR: o BB isolando o complete do SB conta como 1 limper (iso 3X) — count_limpers
    # exclui blinds, então sem isto o raise sairia 2x (o "mini raise 2x" que o Eduardo reclamou).
    if (action in ('raise', 'open_raise') and hero_position == 'BB'
            and limpers == 0 and _sb_completed(table_state)):
        limpers = 1
    return recommend_size(action, hero_stack_bb=hero.get('stack_bb'),
                          to_call_bb=(table_state.get('to_call') or {}).get('to_call_bb'),
                          limpers=limpers,
                          opener_bb=opener_raise_bb(table_state), hero_position=hero_position,
                          ip=in_position(hero_position, opener_position) if opener_position else True,
                          # 2.5x só com late reg ABERTA (início). Sem o sinal -> 2x (default).
                          registration_open=bool(table_state.get('registration_open')),
                          final_table=(str(stage).lower() == 'ft'))
