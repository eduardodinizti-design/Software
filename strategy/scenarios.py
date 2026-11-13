"""B08 — classificador ÚNICO de cenário pré-flop (plano de evolução do cérebro).

Um só lugar decide "que situação o hero enfrenta?", com limpers e callers
EXPLÍCITOS. Corrige o caminho divergente antigo (o `infer_live_spot` ignorava
limps -> dois limps viravam `first_in`/pote não aberto, e o tratamento de iso
era um remendo à parte). Critérios do plano (B08):

  - dois limps NÃO se tornam pote não aberto;
  - callers NÃO desaparecem da consulta;
  - ações legais são consistentes com o estado;
  - sequência ausente/ambígua permanece PENDENTE, sem inventar quem agiu.

PURO: sem captura, sem clique, sem leitura de tela. Recebe uma observação
normalizada (participantes com posição/aposta/stack + blinds + hero) e devolve o
cenário. `from_table_state()` adapta a leitura ao vivo para essa observação.
"""

ORDER = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')
RAISE_FACTOR = 1.5          # aposta > 1.5*BB é um RAISE (acima do limp/BB)
_EPS = 1e-6

# Menu de ações LEGAIS por cenário (legalidade, NÃO política). check só quando grátis.
_MENU = {
    'unopened':          ('fold', 'open_raise', 'open_shove'),
    'limped':            ('fold', 'overlimp', 'iso_raise', 'iso_shove'),
    'open':              ('fold', 'call', 'threebet', 'reshove'),
    'open_with_callers': ('fold', 'overcall', 'squeeze', 'reshove'),
    'limp_then_iso':     ('fold', 'call', 'reraise', 'reshove'),
    'vs_3bet':           ('fold', 'call', 'fourbet', 'shove'),
    'vs_4bet_or_more':   ('fold', 'call', 'shove'),
    'threebet_cold':     ('fold', 'call', 'fourbet', 'shove'),
    'pending':           (),
}


def _levels(amounts):
    """Agrupa valores de RAISE em níveis distintos (callers que igualam um raise
    ficam no mesmo nível). Devolve os representantes, do menor ao maior."""
    out = []
    for a in sorted(amounts):
        if not out or a > out[-1] + max(0.5, 0.15 * out[-1]):
            out.append(a)
        else:
            out[-1] = max(out[-1], a)
    return out


def _is_voluntary_limp(position, bet, sb, bb):
    """Limp = call VOLUNTÁRIO do BB sem raise. SB completando (0,5->1,0) e qualquer
    posição não-blind com aposta ~BB são limps. O post forçado do BB (==BB) NÃO é
    limp; o post do SB (==SB) também não."""
    if bet is None or bet <= _EPS:
        return False
    if abs(bet - bb) > max(0.05, 0.1 * bb):     # só conta como limp quem igualou o BB
        return False
    if position == 'BB':
        return False                             # BB com ==BB é o post forçado
    if position == 'SB' and abs(bet - sb) <= _EPS:
        return False                             # SB só postou
    return True


def classify(observation):
    """Classifica o cenário pré-flop a partir de uma observação normalizada.

    observation = {
      'hero': 'BTN' | None,
      'blinds': {'sb': 0.5, 'bb': 1.0},            # opcional
      'phase': 'mid',                               # opcional
      'players': [{'position','bet_bb','stack_bb','is_hero'(opc)}, ...],
    }
    Devolve dict com: scenario, hero_position, aggressor (opener/3bettor ou None),
    limpers (lista de posições), n_limpers, callers (lista), n_callers,
    raise_levels (sizes), stacks (pos->stack), hero_options (menu legal), phase,
    supported (bool) e reason (quando pendente/limitado)."""
    players = list(observation.get('players') or [])
    blinds = observation.get('blinds') or {}
    sb = blinds.get('sb', 0.5)
    bb = blinds.get('bb', 1.0)
    raise_floor = RAISE_FACTOR * bb
    phase = observation.get('phase', 'mid')
    hero_pos = observation.get('hero')

    stacks, hero_bet, raisers, limpers = {}, 0.0, {}, []
    for p in players:
        pos = p.get('position')
        bet = p.get('bet_bb') or 0.0
        if pos:
            stacks[pos] = p.get('stack_bb')
        if p.get('is_hero') or (hero_pos is not None and pos == hero_pos):
            hero_bet = max(hero_bet, bet)
            continue
        if not pos:
            continue
        if bet > raise_floor + _EPS:
            raisers[pos] = max(raisers.get(pos, 0.0), bet)
        elif _is_voluntary_limp(pos, bet, sb, bb):
            limpers.append(pos)

    def earliest(positions):
        return min(positions, key=lambda p: ORDER.index(p) if p in ORDER else 99)

    def result(scenario, *, aggressor=None, callers=(), levels=(), supported=True, reason=None):
        return dict(scenario=scenario, hero_position=hero_pos, aggressor=aggressor,
                    limpers=sorted(limpers, key=lambda p: ORDER.index(p) if p in ORDER else 99),
                    n_limpers=len(limpers), callers=list(callers), n_callers=len(callers),
                    raise_levels=list(levels), stacks=stacks,
                    hero_options=list(_MENU.get(scenario, ())), phase=phase,
                    supported=supported, reason=reason)

    # ---------- HERO JÁ ABRIU/RAISOU: enfrenta reraise? ----------
    if hero_bet > raise_floor + _EPS:
        above = {p: a for p, a in raisers.items() if a > hero_bet + 0.4}
        if not above:
            return result('pending', supported=False, reason='HERO_RAISED_NO_RERAISE')
        levels = _levels(above.values())
        agg = earliest([p for p, a in above.items()
                        if a > levels[-1] - max(0.5, 0.15 * levels[-1])])
        # 1 nível acima do hero = um 3bet (hero abriu -> vs_3bet). 2+ níveis acima =
        # 4bet+ (ou cenário multi-reraise) -> suporte limitado, não inventa.
        scen = 'vs_3bet' if len(levels) == 1 else 'vs_4bet_or_more'
        return result(scen, aggressor=agg, levels=levels,
                      supported=(scen == 'vs_3bet'),
                      reason=None if scen == 'vs_3bet' else 'FOURBET_OR_MULTIWAY_RERAISE')

    # ---------- HERO AINDA NÃO ABRIU ----------
    if raisers:
        levels = _levels(raisers.values())
        if len(levels) >= 2:
            # Dois ou mais níveis = pote 3bet+ que o hero enfrenta a frio: cenário
            # explícito, suporte limitado (cold 4bet etc. ficam pendentes).
            agg = earliest([p for p, a in raisers.items()
                            if a > levels[-1] - max(0.5, 0.15 * levels[-1])])
            return result('threebet_cold', aggressor=agg, levels=levels,
                          supported=False, reason='COLD_RERAISED_POT')
        top = levels[-1]
        at_top = [p for p, a in raisers.items() if a > top - max(0.5, 0.15 * top)]
        opener = earliest(at_top)
        callers = [p for p in at_top if p != opener]
        if limpers:
            # Limp(s) + um raise de isolamento. Os limpers que ainda podem agir
            # importam (P1 do plano) e NÃO somem.
            return result('limp_then_iso', aggressor=opener, callers=callers, levels=levels)
        scen = 'open_with_callers' if callers else 'open'
        return result(scen, aggressor=opener, callers=callers, levels=levels)

    if limpers:
        # Limps SEM raise: pote LIMPADO. Explicitamente NÃO é pote não aberto.
        return result('limped')

    # Nem raise nem limp: pote realmente NÃO ABERTO (só blinds).
    return result('unopened')


def from_table_state(table_state):
    """Adapta a leitura ao vivo (positions {seat->pos}, bets [{seat,bet_bb}], seats
    {seat->{stack_bb}}, hero em positions['hero']) para a observação normalizada do
    classify(). Mantém UM só caminho de classificação entre laboratório e ao vivo."""
    positions = table_state.get('positions') or {}
    seats = table_state.get('seats') or {}
    bets = {}
    for b in (table_state.get('bets') or []):
        s, a = b.get('seat'), b.get('bet_bb')
        if isinstance(a, (int, float)):
            bets[s] = max(bets.get(s, 0.0), a)
    hero_pos = positions.get('hero')
    players = []
    for seat, pos in positions.items():
        players.append(dict(position=pos, bet_bb=bets.get(seat, 0.0),
                            stack_bb=(seats.get(seat) or {}).get('stack_bb'),
                            is_hero=(seat == 'hero')))
    return dict(hero=hero_pos, players=players, phase=table_state.get('phase', 'mid'))
