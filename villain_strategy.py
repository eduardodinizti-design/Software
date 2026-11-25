"""Estratégia exploratória POR VILÃO a partir do HUD (os 8 stats) — "como jogar contra
cada um". EXPLORATÓRIO: é plano de estudo/observação, nunca executa (o operador não age
por isto); complementa `hud_exploit` (que já dá category/tags e os deltas de
bluffcatch/call-off) com AJUSTES ACIONÁVEIS por situação.

`plan(stats)` devolve dict com ajustes pré e pós-flop (cada um um rótulo + direção +
intensidade) e `summary` legível. Direção: 'wider'/'tighter'/'more'/'less'/'value_only'.
Tudo fundamentado nos tags do HUD (folds_to_cbet, station, 3bet_happy, steal_wide, ...).
Caps conservadores; sem fabricar ranges de solver.
"""
from hud_exploit import classify_villain

# Intensidades nominais (rótulos; o quanto afrouxar/apertar fica a cargo de quem usa).
STRONG, MODERATE, SLIGHT = 'strong', 'moderate', 'slight'


def _adj(situation, direction, strength, why):
    return dict(situation=situation, direction=direction, strength=strength, why=why)


def plan(stats, *, profile=None):
    """Plano vs UM vilão. `stats`: dict dos 8 stats (vpip,pfr,steal,cr,threebet,
    fold3bet,cbet,foldcbet) ou None. Devolve category/tags + listas `preflop`/`postflop`
    de ajustes + `summary`. Vilão desconhecido -> plano VAZIO (joga GTO base, honesto)."""
    prof = profile or classify_villain(stats)
    cat, tags = prof.get('category', 'unknown'), set(prof.get('tags', []))
    pre, post = [], []
    if cat == 'unknown':
        return dict(category='unknown', tags=[], preflop=[], postflop=[],
                    bluffcatch_delta=0.0,
                    summary='Vilão desconhecido (sem amostra): jogar a base GTO, sem exploração.')

    # ---------------- PRÉ-FLOP ----------------
    if 'steal_wide' in tags:
        pre.append(_adj('vs_steal_dele', 'wider', STRONG,
                        'rouba muito (steal alto) -> defender/3bet-ressteal mais largo'))
    if 'folds_to_3bet' in tags:
        pre.append(_adj('3bet_blefe', 'more', STRONG, 'foge de 3bet -> 3bet blefe mais'))
    if 'defends_3bet' in tags or '3bet_nit' in tags:
        pre.append(_adj('3bet', 'value_only', MODERATE,
                        'defende/raro no 3bet -> 3bet só por valor, cortar blefe'))
    if '3bet_happy' in tags:
        pre.append(_adj('flat_e_4bet', 'tighter', STRONG,
                        '3bet-happy -> abrir mais apertado na posição dele, 4bet por valor mais largo'))
    if cat == 'fish':
        pre.append(_adj('isolar_limp', 'wider', STRONG,
                        'fish passa/limpa mal -> isolar mais largo por valor, pouco blefe'))
        pre.append(_adj('blefe_preflop', 'less', MODERATE, 'fish paga demais -> menos blefe puro'))
    if cat == 'nit':
        pre.append(_adj('roubar_blind', 'wider', MODERATE,
                        'nit (vpip baixo) -> roubar os blinds dele mais largo; respeitar a agressão dele'))
    if cat == 'lag':
        pre.append(_adj('vs_abertura', 'tighter', MODERATE,
                        'lag abre muito e agride -> continuar mais apertado fora de posição'))

    # ---------------- PÓS-FLOP ----------------
    if 'folds_to_cbet' in tags:
        post.append(_adj('c_bet', 'more', STRONG, 'desiste do flop (fold-to-cbet alto) -> c-bet blefe mais, size pequeno'))
        post.append(_adj('barrel', 'more', MODERATE, 'continua desistindo -> seguir barrelando turn'))
    if 'station' in tags:
        post.append(_adj('c_bet_blefe', 'less', STRONG, 'calling station -> cortar c-bet blefe'))
        post.append(_adj('value_bet', 'wider', STRONG, 'paga demais -> value bet mais fino e MAIOR'))
        post.append(_adj('blefe_river', 'less', STRONG, 'não dobra no river contra station'))
    if 'cbet_heavy' in tags:
        post.append(_adj('vs_cbet_dele', 'wider', MODERATE,
                         'ele c-beta demais -> flutuar/check-raise mais largo como blefe'))
    if 'cbet_light' in tags:
        post.append(_adj('vs_check_dele', 'more', SLIGHT,
                         'ele c-beta pouco -> o check dele é fraqueza, apostar quando ele passa'))
    if prof.get('passive'):
        post.append(_adj('agressao_dele', 'respect', STRONG,
                         'passivo: quando ELE aposta/raise é valor -> foldar marginais, não pagar leve'))
    if prof.get('aggressive'):
        post.append(_adj('bluffcatch', 'wider', MODERATE,
                         'agressivo blefa -> pagar bluffcatch mais largo (ver bluffcatch_delta)'))

    lines = ['Vilão: %s %s' % (cat.upper(), ('[' + ','.join(sorted(tags)) + ']') if tags else '')]
    for a in pre:
        lines.append('  PRE  %-16s %-10s (%s) — %s' % (a['situation'], a['direction'], a['strength'], a['why']))
    for a in post:
        lines.append('  POS  %-16s %-10s (%s) — %s' % (a['situation'], a['direction'], a['strength'], a['why']))
    return dict(category=cat, tags=sorted(tags), preflop=pre, postflop=post,
                bluffcatch_delta=prof.get('bluffcatch_delta', 0.0),
                aggressive=prof.get('aggressive', False), passive=prof.get('passive', False),
                summary='\n'.join(lines))


def table_plan(huds):
    """Plano para a mesa inteira: {seat: plan}. `huds`: {seat: stats|None}. Útil p/ o
    overlay mostrar, por assento, como explorar cada vilão."""
    return {seat: plan(stats) for seat, stats in (huds or {}).items()}
