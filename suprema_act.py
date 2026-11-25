"""Fase 2 (execução) da SUPREMA — PLANEJADOR de ação (lógica pura, testável offline).

Traduz a decisão do cérebro (advise_from_suprema -> {recommended, sizing,...}) + o `prompt`
da Suprema (ações legais + raise_range + call_amount) num PLANO DE AÇÃO concreto, GATED pelas
ações LEGAIS (nunca tenta o que o servidor não ofereceu). NÃO executa — só decide o QUE fazer;
o COMO (clique no botão/overlay da Suprema) é a camada ao vivo (mesma filosofia do PPPoker:
ação externa, nunca injeção de comando de rede em conta real — ver nvt-hotkeys-politica).

Regras herdadas do PPPoker:
  - NUNCA foldar de graça: se o cérebro diz fold e CHECK está disponível -> check.
  - RAISE sem a ação legal -> cai p/ CALL (se legal) ou CHECK; nunca trava.
  - size do raise clampado a [min,max] do prompt; >= max (ou all_in pedido) -> all_in.
"""
from __future__ import annotations

# rótulos de ação do PLANO (o executor ao vivo mapeia p/ o botão da Suprema)
FOLD, CHECK, CALL, RAISE, ALL_IN, WAIT, ABSTAIN = \
    'fold', 'check', 'call', 'raise', 'all_in', 'wait', 'abstain'


# Vocabulário do cérebro -> família de ação (ALINHADO ao action_coordinator._MAP: 3bet/
# 4bet/three_bet/four_bet/squeeze/isolate/iso/open_raise = RAISE; shove/open_shove = ALL_IN;
# limp = CALL). Faltar aqui fazia o `three_bet` cair em ABSTAIN:REC_DESCONHECIDO (bug 21/11).
_FAM_FOLD = frozenset({'fold'})
_FAM_CHECK = frozenset({'check'})
_FAM_CALL = frozenset({'call', 'limp', 'overlimp', 'complete'})
_FAM_ALLIN = frozenset({'all_in', 'allin', 'open_shove', 'shove', 'jam'})
_FAM_RAISE = frozenset({'raise', 'raises', 'bet', 'bets', 'open_raise', 'open', 'min_raise',
                        'reraise', '3bet', '4bet', '5bet', 'three_bet', 'four_bet', 'five_bet',
                        'squeeze', 'isolate', 'iso'})


def _rec_family(rec):
    """Normaliza o `recommended` do cérebro p/ família de ação. Vocabulário alinhado ao
    action_coordinator; com rede de segurança por substring p/ variantes não listadas."""
    r = (rec or '').lower().replace('-', '_')
    if r in _FAM_FOLD:
        return FOLD
    if r in _FAM_CHECK:
        return CHECK
    if r in _FAM_CALL:
        return CALL
    if r in _FAM_ALLIN:
        return ALL_IN
    if r in _FAM_RAISE:
        return RAISE
    # rede de segurança: variante não catalogada mas reconhecível
    if any(k in r for k in ('shove', 'jam', 'allin', 'all_in')):
        return ALL_IN
    if any(k in r for k in ('raise', 'bet', 'squeeze', 'iso')):
        return RAISE
    return None


def _target_chips(advice, table):
    """Fichas-alvo do raise a partir do size do cérebro. Prioriza sizing.size_bb (×bb);
    senão o multiplicador (sizing.multiplier × bb); senão None (usa min-raise)."""
    bb = table.bb()
    sizing = (advice or {}).get('sizing') or {}
    size_bb = sizing.get('size_bb')
    if isinstance(size_bb, (int, float)) and bb:
        return float(size_bb) * bb
    mult = sizing.get('multiplier') or advice.get('target_multiplier')
    if isinstance(mult, (int, float)) and bb:
        return float(mult) * bb
    return None


def _hero_stack_chips(table):
    """Fichas do próprio hero (p/ dimensionar o all-in quando o slider não foi lido). None se não der."""
    try:
        hs = getattr(table, 'hero_seat', None)
        players = getattr(table, 'players', None) or {}
        if hs is not None and hs in players:
            c = players[hs].get('chips')
            if isinstance(c, (int, float)) and c > 0:
                return float(c)
    except Exception:
        pass
    return None


def _clamp_and_preset(chips, rr):
    """Clampa `chips` a [min,max] da raise_range e acha o preset (label) mais próximo."""
    lo, hi = rr.get('min'), rr.get('max')
    if isinstance(lo, (int, float)):
        chips = max(chips, lo)
    if isinstance(hi, (int, float)):
        chips = min(chips, hi)
    preset = None
    presets = rr.get('presets') or {}
    if presets:
        preset = min(presets.items(), key=lambda kv: abs(kv[1] - chips))[0]
    return round(chips, 2), preset


def plan_action(advice, table):
    """Devolve o plano: {action, chips?, preset?, reason}. `advice` = dict do cérebro;
    `table` = SupremaTable (legal_actions/prompt/bb). action=WAIT se não é a vez; ABSTAIN se
    o cérebro não deu conselho executável."""
    legal = set(table.legal_actions())
    if not legal:
        return dict(action=WAIT, reason='NAO_E_A_VEZ')
    if not isinstance(advice, dict) or advice.get('status') != 'ADVICE':
        return dict(action=ABSTAIN, reason='SEM_ADVICE')
    fam = _rec_family(advice.get('recommended'))
    if fam is None:
        return dict(action=ABSTAIN, reason='REC_DESCONHECIDO:%s' % advice.get('recommended'))

    # FOLD: nunca de graça -> se dá p/ checar, checa.
    if fam == FOLD:
        if CHECK in legal:
            return dict(action=CHECK, reason='FOLD->CHECK_GRATIS')
        if FOLD in legal:
            return dict(action=FOLD, reason='fold')
        return dict(action=ABSTAIN, reason='FOLD_SEM_BOTAO')

    if fam == CHECK:
        if CHECK in legal:
            return dict(action=CHECK, reason='check')
        if CALL in legal and (table.prompt.get('call_amount') or 0) <= 0:
            return dict(action=CALL, reason='CHECK->CALL0')
        return dict(action=ABSTAIN, reason='CHECK_INDISPONIVEL')

    if fam == CALL:
        if CALL in legal:
            return dict(action=CALL, chips=table.prompt.get('call_amount'), reason='call')
        if CHECK in legal:
            return dict(action=CHECK, reason='CALL->CHECK')
        return dict(action=ABSTAIN, reason='CALL_INDISPONIVEL')

    want_jam = False
    if fam == ALL_IN:
        if ALL_IN in legal:
            return dict(action=ALL_IN, reason='all_in')
        # sem botão all-in: JAMMA pelo slider no MÁXIMO. JAMAIS rebaixa um shove a um flat/min-raise
        # (bug QQ 25/11: CÉREBRO=all_in caía p/ CALL porque o slider não foi lido -> flatou QQ).
        want_jam = True
        fam = RAISE

    if fam == RAISE:
        rr = table.prompt.get('raise_range')
        # PÓS-FLOP: quando não há aposta anterior, a ação legal é 'bet' (não 'raise'); é o MESMO
        # botão (Apostar/Aumentar) e o mesmo raise_range. Sem isso, bet pós-flop caía p/ check.
        if (RAISE in legal or 'bet' in legal) and rr:
            if want_jam:
                target = rr.get('max')                 # JAM = topo do slider (all-in via Aumentar)
            else:
                target = _target_chips(advice, table)
                if target is None:
                    target = rr.get('min')
            if target is None:
                return dict(action=ABSTAIN, reason='RAISE_SEM_SIZE')
            chips, preset = _clamp_and_preset(float(target), rr)
            # se bateu o teto (all-in efetivo) e o botão all_in existe, prefere all_in
            hi = rr.get('max')
            if ALL_IN in legal and isinstance(hi, (int, float)) and chips >= hi:
                return dict(action=ALL_IN, reason='RAISE_NO_TETO->ALL_IN')
            return dict(action=RAISE, chips=chips, preset=preset,
                        reason=('jam_slider_max' if want_jam else 'raise'))
        # Slider NÃO lido, mas há botão de aumentar e o cérebro quer JAMMAR -> usa o STACK do hero
        # como alvo do all-in (all-in = TODAS as fichas; não inventa size). JAMAIS vira flat silencioso.
        if want_jam and (RAISE in legal or 'bet' in legal):
            hs = _hero_stack_chips(table)
            if isinstance(hs, (int, float)) and hs > 0:
                return dict(action=RAISE, chips=round(float(hs), 2), reason='JAM_SLIDER_NAO_LIDO->STACK')
        # RAISE/jam pedido mas SEM botão de aumentar -> call (põe fichas, JAMAIS folda o premium)
        if CALL in legal:
            return dict(action=CALL, chips=table.prompt.get('call_amount'),
                        reason=('JAM_SEM_AUMENTO->CALL' if want_jam else 'RAISE_SEM_BOTAO->CALL'))
        if CHECK in legal:
            return dict(action=CHECK, reason='RAISE_SEM_BOTAO->CHECK')
        return dict(action=ABSTAIN, reason='RAISE_SEM_BOTAO_NEM_CALL')

    return dict(action=ABSTAIN, reason='SEM_MAPA')
